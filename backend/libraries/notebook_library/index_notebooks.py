"""notebook_library.index_notebooks

CLI / importable function to scan Jupyter notebooks, extract code (and nearby
markdown) snippets, embed them, and persist a FAISS index + metadata file.
"""
from __future__ import annotations

import json
import os
import pathlib
import uuid
import ast
from typing import List, Dict, Any, Tuple, Set
import re
import builtins

import nbformat
from tqdm import tqdm

try:
    import faiss  # type: ignore
except ImportError as e:
    raise ImportError("faiss-cpu is required: pip install faiss-cpu") from e

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except ImportError as e:
    raise ImportError("sentence-transformers is required: pip install sentence-transformers") from e

EMBED_MODEL_NAME = os.getenv("SNIPPET_EMBED_MODEL", "all-MiniLM-L6-v2")


def _load_model() -> SentenceTransformer:  # type: ignore
    """Load (or cache) the sentence-transformer model used for embeddings."""
    if not hasattr(_load_model, "_model"):
        _load_model._model = SentenceTransformer(EMBED_MODEL_NAME)  # type: ignore
    return _load_model._model  # type: ignore


############################
# Dependency helpers
############################


def _names_defined_used(code: str) -> Tuple[Set[str], Set[str], Set[str]]:
    """Return sets (defined, used, imports) for a code cell."""
    defined: Set[str] = set()
    used: Set[str] = set()
    imports: Set[str] = set()

    # Strip Jupyter magics and shell escapes so AST can parse
    cleaned_lines = [
        l for l in code.splitlines()
        if not l.lstrip().startswith("%") and not l.lstrip().startswith("!")
    ]

    try:
        tree = ast.parse("\n".join(cleaned_lines))
    except SyntaxError:
        return defined, used, imports  # skip broken cell

    class NameCollector(ast.NodeVisitor):
        def visit_Name(self, node):  # type: ignore
            if isinstance(node.ctx, ast.Store):
                defined.add(node.id)
            elif isinstance(node.ctx, ast.Load):
                used.add(node.id)

        def visit_FunctionDef(self, node):  # type: ignore
            defined.add(node.name)
            self.generic_visit(node)

        def visit_Import(self, node):  # type: ignore
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                defined.add(name)
                imports.add(name)

        def visit_ImportFrom(self, node):  # type: ignore
            for alias in node.names:
                name = alias.asname or alias.name
                defined.add(name)
                imports.add(name)

    NameCollector().visit(tree)
    return defined, used, imports


IMPORT_RE = re.compile(r"^\s*(?:import\s+\w|from\s+\S+\s+import)" )


def extract_snippets(nb_path: pathlib.Path, *, hoist_imports: bool = True, synth_imports: bool = True) -> List[Dict[str, Any]]:
    """Return list of multi-cell recipe snippets from a notebook.

    Heuristic:
    * A markdown cell starting with `#` denotes the beginning of a new recipe.
    * All following code cells until the next heading (or EOF) belong to it.
    * Before finalising, we prepend earlier dependency cells so that all
      variables used in the block are defined.
    """
    nb = nbformat.read(nb_path, as_version=4)
    cells = nb.cells

    # Precompute defined names per code cell
    code_cells_info: List[Tuple[int, str, Set[str], Set[str], Set[str]]] = []  # (idx, code, defined, used, imports)
    for idx, cell in enumerate(cells):
        if cell.cell_type == "code":
            d, u, imps = _names_defined_used(cell.source)
            code_cells_info.append((idx, cell.source, d, u, imps))

    idx_to_info = {idx: (code, defined, used, imports) for idx, code, defined, used, imports in code_cells_info}

    snippets: List[Dict[str, Any]] = []

    current_block_code_idxs: List[int] = []
    current_heading = "Notebook start"

    def flush_block():
        if not current_block_code_idxs:
            return

        # Determine dependencies
        block_defined: Set[str] = set()
        block_used: Set[str] = set()
        block_imports: Set[str] = set()

        # consider current block cells first
        for idx in current_block_code_idxs:
            code, defined, used, imports = idx_to_info[idx]
            block_defined.update(defined)
            block_used.update(used)
            block_imports.update(imports)

        unresolved = block_used - block_defined

        # remove Python builtins (initial pass)
        builtin_names = set(dir(builtins))
        unresolved -= builtin_names

        dependency_code_idxs: List[int] = []
        if unresolved:
            # First pass: look backwards only within current heading (already done by current_block_code_idxs)
            first_idx = current_block_code_idxs[0]
            for prev_idx in reversed(range(0, first_idx)):
                if prev_idx not in idx_to_info:
                    continue
                code, defined, _, imports_prev = idx_to_info[prev_idx]
                if unresolved & defined:
                    dependency_code_idxs.insert(0, prev_idx)
                    unresolved -= defined
                    block_imports.update(imports_prev)
                if not unresolved:
                    break

        # Second pass: widen search to any earlier cell that defines unresolved symbols
        if unresolved:
            first_idx = current_block_code_idxs[0]
            for prev_idx in reversed(range(0, first_idx)):
                if prev_idx in dependency_code_idxs or prev_idx not in idx_to_info:
                    continue
                code_prev, defined_prev, _, imports_prev = idx_to_info[prev_idx]
                if unresolved & defined_prev or unresolved & imports_prev:
                    dependency_code_idxs.insert(0, prev_idx)
                    unresolved -= defined_prev
                    block_imports.update(imports_prev)
                if not unresolved:
                    break

        all_code_idxs = dependency_code_idxs + current_block_code_idxs

        # recompute metadata across ALL cells (dependencies included)
        block_defined.clear()
        block_used.clear()
        block_imports.clear()
        for idx in all_code_idxs:
            code, defined, used, imports = idx_to_info[idx]
            block_defined.update(defined)
            block_used.update(used)
            block_imports.update(imports)

        unresolved = block_used - block_defined
        
        builtin_names = set(dir(builtins))
        unresolved -= builtin_names

        # Concatenate code with separators
        code_sections = [idx_to_info[i][0] for i in all_code_idxs]

        # Synthesise missing imports if requested
        synthetic_import_lines: List[str] = []
        if synth_imports and unresolved:
            for name in sorted(unresolved):
                synthetic_import_lines.append(f"import {name}")
            if synthetic_import_lines:
                block_imports.update(unresolved)
                block_defined.update(unresolved)
                unresolved.clear()

        if synthetic_import_lines:
            code_sections.insert(0, "\n".join(synthetic_import_lines))

        if hoist_imports:
            import_lines: List[str] = []
            other_lines: List[str] = []
            seen_imports = set()
            for section in code_sections:
                for line in section.splitlines():
                    if IMPORT_RE.match(line):
                        stripped = line.strip()
                        if stripped not in seen_imports:
                            seen_imports.add(stripped)
                            import_lines.append(line)
                    else:
                        other_lines.append(line)

            full_code = "\n".join(import_lines) + "\n\n" + "\n".join(other_lines)
        else:
            full_code = "\n\n# ----\n".join(code_sections)

        snippet_id = str(uuid.uuid4())
        snippets.append({
            "id": snippet_id,
            "notebook": str(nb_path),
            "cell_indices": all_code_idxs,
            "code": full_code,
            "markdown_context": current_heading.strip(),
            "defined": sorted(block_defined),
            "used": sorted(block_used),
            "imports": sorted(block_imports),
            "unresolved": sorted(unresolved),
        })

    # iterate over cells
    for idx, cell in enumerate(cells):
        if cell.cell_type == "markdown" and cell.source.lstrip().startswith("#"):
            # heading boundary
            flush_block()
            current_block_code_idxs = []
            current_heading = cell.source
            continue

        if cell.cell_type == "code":
            current_block_code_idxs.append(idx)

    # flush last block
    flush_block()

    return snippets


def build_index(
    notebook_paths: List[pathlib.Path],
    out_dir: pathlib.Path,
    *,
    hoist_imports: bool = True,
    keep_invalid: bool = False,
    synth_imports: bool = True,
) -> pathlib.Path:
    """Index notebooks and write FAISS + metadata.

    Returns the path to the created index directory.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "snippets_meta.jsonl"
    index_path = out_dir / "snippets.faiss"

    all_snippets: List[Dict[str, Any]] = []
    workflows_by_notebook: Dict[str, List[Dict[str, Any]]] = {}
    for nb_path in tqdm(notebook_paths, desc="Scanning notebooks"):
        snippets = extract_snippets(nb_path, hoist_imports=hoist_imports, synth_imports=synth_imports)
        if not keep_invalid:
            snippets = [s for s in snippets if not s["unresolved"]]
        all_snippets.extend(snippets)

        # store steps for workflow assembly (keep original order as returned)
        workflows_by_notebook[str(nb_path)] = snippets

    if not all_snippets:
        raise RuntimeError("No code snippets found in provided notebooks")

    def _embed_text(s: Dict[str, Any]) -> str:
        preview = " ".join(s["code"].split()[:60])  # ~ first 60 tokens
        return (
            (s["markdown_context"] or "")
            + "\nimports: " + ", ".join(s["imports"])
            + "\ndefines: " + ", ".join(s["defined"][:20])
            + "\ncode_preview: " + preview
        )

    texts = [_embed_text(s) for s in all_snippets]
    model = _load_model()
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32, normalize_embeddings=True)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    faiss.write_index(index, str(index_path))

    # write snippet metadata line-by-line so line number == vector id
    with meta_path.open("w") as f:
        for meta in all_snippets:
            f.write(json.dumps(meta) + "\n")

    ############################
    # Build workflow documents #
    ############################

    workflow_docs: List[Dict[str, Any]] = []
    workflow_texts: List[str] = []
    step_docs: List[Dict[str, Any]] = []
    transitions: Dict[Tuple[str, str], int] = {}
    for nb_path_str, steps in workflows_by_notebook.items():
        if not steps:
            continue
        wf_id = str(uuid.uuid4())
        wf_meta = {
            "id": wf_id,
            "notebook": nb_path_str,
            "steps": [
                {
                    "id": s["id"],
                    "markdown_context": s["markdown_context"],
                }
                for s in steps
            ],
        }
        workflow_docs.append(wf_meta)

        # Embedding string: notebook name + ordered step headings
        step_lines = []
        for i, s in enumerate(steps):
            heading = s["markdown_context"].split("\n")[0]
            code_preview = " ".join(s["code"].split()[:40])  # first ~40 tokens
            step_lines.append(f"Step {i+1}: {heading} | {code_preview}")

        workflow_texts.append(pathlib.Path(nb_path_str).stem + "\n" + "\n".join(step_lines))

        # collect step-level docs & transitions
        for i, s in enumerate(steps):
            step_docs.append({
                "id": s["id"],
                "notebook": nb_path_str,
                "position": i,
                "heading": s["markdown_context"].split("\n")[0],
                "code_preview": " ".join(s["code"].split()[:40]),
            })
            if i < len(steps) - 1:
                a = s["markdown_context"].split("\n")[0]
                b = steps[i+1]["markdown_context"].split("\n")[0]
                transitions[(a, b)] = transitions.get((a, b), 0) + 1

    if workflow_docs:
        wf_index_path = out_dir / "workflows.faiss"
        wf_meta_path = out_dir / "workflows_meta.jsonl"

        wf_embeddings = model.encode(workflow_texts, show_progress_bar=False, batch_size=32, normalize_embeddings=True)

        dim = wf_embeddings.shape[1]
        wf_index = faiss.IndexFlatIP(dim)
        wf_index.add(wf_embeddings)
        faiss.write_index(wf_index, str(wf_index_path))

        with wf_meta_path.open("w") as f:
            for meta in workflow_docs:
                f.write(json.dumps(meta) + "\n")

        print(f"Indexed {len(workflow_docs)} workflows → {out_dir}")

    # ---------------- Step index ----------------
    if step_docs:
        step_texts = [f"{d['heading']} | {d['code_preview']}" for d in step_docs]
        step_embeddings = model.encode(step_texts, show_progress_bar=False, batch_size=32, normalize_embeddings=True)

        step_index_path = out_dir / "steps.faiss"
        step_meta_path = out_dir / "steps_meta.jsonl"

        dim = step_embeddings.shape[1]
        step_index = faiss.IndexFlatIP(dim)
        step_index.add(step_embeddings)
        faiss.write_index(step_index, str(step_index_path))

        with step_meta_path.open("w") as f:
            for meta in step_docs:
                f.write(json.dumps(meta) + "\n")

        # write transitions
        trans_path = out_dir / "step_transitions.json"
        # Convert tuple-key dict to nested mapping {from: {to: count}}
        trans_serializable: Dict[str, Dict[str, int]] = {}
        for (a, b), cnt in transitions.items():
            trans_serializable.setdefault(a, {})[b] = cnt
        with trans_path.open("w") as f:
            json.dump(trans_serializable, f)

        print(f"Indexed {len(step_docs)} workflow steps → {out_dir}")

    print(f"Indexed {len(all_snippets)} snippets → {out_dir}")
    return out_dir


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build snippet library from notebooks")
    parser.add_argument("paths", nargs="+", help="Notebook paths or directories (recursively scanned)")
    parser.add_argument("--out", default="notebook_index", help="Output directory for index files")
    parser.add_argument("--no-hoist-imports", action="store_true", help="Keep imports in original positions")
    parser.add_argument("--keep-invalid", action="store_true", help="Include snippets with unresolved names")
    parser.add_argument("--no-synth-imports", action="store_true", help="Do not create synthetic import lines for missing names")
    args = parser.parse_args()

    # collect notebooks
    collected: List[pathlib.Path] = []
    for p in args.paths:
        path = pathlib.Path(p)
        if path.is_dir():
            collected.extend(path.rglob("*.ipynb"))
        elif path.suffix == ".ipynb":
            collected.append(path)

    if not collected:
        raise SystemExit("No .ipynb files found in given paths")

    build_index(collected, pathlib.Path(args.out), hoist_imports=not args.no_hoist_imports, keep_invalid=args.keep_invalid, synth_imports=not args.no_synth_imports) 
