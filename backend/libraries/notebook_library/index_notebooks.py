"""notebook_library.index_notebooks

CLI / importable function to scan Jupyter notebooks, extract code (and nearby
markdown) snippets, embed them, and persist a Qdrant index.
"""
from __future__ import annotations

import json
import os
import pathlib
import uuid
import ast
import sys
from typing import List, Dict, Any, Tuple, Set
import re
import builtins

import nbformat
from tqdm import tqdm

# Add parent directory to path for imports
current_dir = pathlib.Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from qdrant_config import get_qdrant_manager, COLLECTION_NAMES

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
    collection_name_prefix: str = None,
    *,
    hoist_imports: bool = True,
    keep_invalid: bool = False,
    synth_imports: bool = True,
    force_recreate: bool = False,
) -> Dict[str, str]:
    """
    Build Qdrant indexes from notebooks.
    
    Returns:
        Dictionary mapping collection types to collection names created
    """
    if collection_name_prefix is None:
        collections = {
            "snippets": COLLECTION_NAMES["notebook_snippets"],
            "workflows": COLLECTION_NAMES["notebook_workflows"], 
            "steps": COLLECTION_NAMES["notebook_steps"]
        }
    else:
        collections = {
            "snippets": f"{collection_name_prefix}_snippets",
            "workflows": f"{collection_name_prefix}_workflows",
            "steps": f"{collection_name_prefix}_steps"
        }

    all_snippets: List[Dict[str, Any]] = []
    all_workflows: List[Dict[str, Any]] = []
    all_steps: List[Dict[str, Any]] = []

    def _embed_text(s: Dict[str, Any]) -> str:
        """Extract text for embedding from snippet metadata."""
        parts = [s.get("title", "")]
        if s.get("code"):
            parts.append(s["code"])
        if s.get("markdown"):
            parts.append(s["markdown"])
        return "\n".join(p for p in parts if p)

    def _workflow_embed_text(w: Dict[str, Any]) -> str:
        """Extract text for embedding from workflow metadata."""
        parts = [w.get("title", "")]
        if w.get("description"):
            parts.append(w["description"])
        if w.get("keywords"):
            parts.extend(w["keywords"])
        return " ".join(p for p in parts if p)

    def _step_embed_text(step: Dict[str, Any]) -> str:
        """Extract text for embedding from step metadata."""
        parts = [step.get("description", "")]
        if step.get("code"):
            parts.append(step["code"])
        if step.get("dependencies"):
            parts.extend(step["dependencies"])
        return " ".join(p for p in parts if p)

    for nb_path in tqdm(notebook_paths, desc="Processing notebooks"):
        try:
            snippets = extract_snippets(
                nb_path, 
                hoist_imports=hoist_imports, 
                synth_imports=synth_imports
            )
            
            if keep_invalid:
                # Keep all snippets even if they have unresolved dependencies
                valid_snippets = snippets
            else:
                # Filter out snippets with unresolved dependencies
                valid_snippets = [s for s in snippets if not s.get("unresolved")]
            
            # Add embedding text to each snippet
            for snippet in valid_snippets:
                snippet["text"] = _embed_text(snippet)
                snippet["id"] = str(uuid.uuid4())
                snippet["notebook_path"] = str(nb_path)
                
            all_snippets.extend(valid_snippets)
            
            # Extract workflow information
            workflows = extract_workflows(nb_path)
            for workflow in workflows:
                workflow["text"] = _workflow_embed_text(workflow)
                workflow["id"] = str(uuid.uuid4())
                workflow["notebook_path"] = str(nb_path)
                
            all_workflows.extend(workflows)
            
            # Extract individual steps
            steps = extract_individual_steps(snippets)
            for step in steps:
                step["text"] = _step_embed_text(step)
                step["id"] = str(uuid.uuid4())
                step["notebook_path"] = str(nb_path)
                
            all_steps.extend(steps)
            
        except Exception as e:
            print(f"Error processing {nb_path}: {e}")
            continue

    if not all_snippets and not all_workflows and not all_steps:
        raise ValueError("No valid snippets, workflows, or steps extracted from notebooks")

    # Get Qdrant manager
    qdrant_manager = get_qdrant_manager()
    
    # Create collections and index documents
    results = {}
    
    if all_snippets:
        print(f"Indexing {len(all_snippets)} snippets...")
        if qdrant_manager.create_collection(collections["snippets"], force_recreate=force_recreate):
            qdrant_manager.index_documents(
                collection_name=collections["snippets"],
                documents=all_snippets,
                text_field="text"
            )
            results["snippets"] = collections["snippets"]
    
    if all_workflows:
        print(f"Indexing {len(all_workflows)} workflows...")
        if qdrant_manager.create_collection(collections["workflows"], force_recreate=force_recreate):
            qdrant_manager.index_documents(
                collection_name=collections["workflows"],
                documents=all_workflows,
                text_field="text"
            )
            results["workflows"] = collections["workflows"]
    
    if all_steps:
        print(f"Indexing {len(all_steps)} steps...")
        if qdrant_manager.create_collection(collections["steps"], force_recreate=force_recreate):
            qdrant_manager.index_documents(
                collection_name=collections["steps"],
                documents=all_steps,
                text_field="text"
            )
            results["steps"] = collections["steps"]
    
    print(f"Notebook indexing completed. Created collections: {list(results.values())}")
    return results


def extract_workflows(nb_path: pathlib.Path) -> List[Dict[str, Any]]:
    """Extract workflow-level information from a notebook."""
    nb = nbformat.read(nb_path, as_version=4)
    cells = nb.cells
    
    workflows = []
    current_workflow = None
    
    for cell in cells:
        if cell.cell_type == "markdown":
            source = cell.source.strip()
            
            # Look for workflow headers (# or ##)
            if source.startswith("#"):
                # Start new workflow
                if current_workflow:
                    workflows.append(current_workflow)
                
                title_match = re.match(r'^#+\s*(.+)', source)
                title = title_match.group(1) if title_match else "Unnamed Workflow"
                
                # Extract description from remaining markdown
                lines = source.split('\n')[1:]  # Skip title line
                description = '\n'.join(lines).strip()
                
                current_workflow = {
                    "title": title,
                    "description": description,
                    "keywords": extract_keywords_from_text(f"{title} {description}"),
                    "cell_count": 0,
                    "has_imports": False,
                    "complexity": "simple"
                }
        
        elif cell.cell_type == "code" and current_workflow:
            current_workflow["cell_count"] += 1
            
            # Check for imports
            if re.search(r'^\s*(?:import|from)\s', cell.source, re.MULTILINE):
                current_workflow["has_imports"] = True
            
            # Assess complexity based on code patterns
            if any(pattern in cell.source for pattern in ['for ', 'while ', 'def ', 'class ', 'if ']):
                current_workflow["complexity"] = "complex"
            elif current_workflow["complexity"] == "simple" and len(cell.source.split('\n')) > 5:
                current_workflow["complexity"] = "medium"
    
    # Don't forget the last workflow
    if current_workflow:
        workflows.append(current_workflow)
    
    return workflows


def extract_individual_steps(snippets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract individual computational steps from snippets."""
    steps = []
    
    for snippet in snippets:
        code = snippet.get("code", "")
        if not code:
            continue
            
        # Split code into logical steps (by empty lines or comments)
        code_blocks = re.split(r'\n\s*\n|\n\s*#[^\n]*\n', code)
        
        for i, block in enumerate(code_blocks):
            block = block.strip()
            if not block or len(block) < 10:  # Skip very short blocks
                continue
            
            step = {
                "description": f"Step {i+1} from {snippet.get('title', 'unknown snippet')}",
                "code": block,
                "step_number": i + 1,
                "snippet_id": snippet.get("id"),
                "dependencies": snippet.get("dependencies", []),
                "defined_names": extract_defined_names(block),
                "used_names": extract_used_names(block),
                "step_type": classify_step_type(block)
            }
            steps.append(step)
    
    return steps


def extract_keywords_from_text(text: str) -> List[str]:
    """Extract keywords from text using simple heuristics."""
    # Common data science keywords
    keywords = set()
    
    keyword_patterns = [
        r'\b(pandas|numpy|matplotlib|seaborn|sklearn|scipy)\b',
        r'\b(dataframe|array|plot|chart|model|analysis)\b',
        r'\b(load|save|read|write|import|export)\b',
        r'\b(filter|sort|group|merge|join|pivot)\b',
        r'\b(visualization|statistics|machine learning|deep learning)\b'
    ]
    
    text_lower = text.lower()
    for pattern in keyword_patterns:
        matches = re.findall(pattern, text_lower)
        keywords.update(matches)
    
    return list(keywords)


def extract_defined_names(code: str) -> List[str]:
    """Extract variable names defined in code block."""
    defined = set()
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined.add(target.id)
            elif isinstance(node, ast.FunctionDef):
                defined.add(node.name)
    except:
        pass  # Skip parsing errors
    
    return list(defined)


def extract_used_names(code: str) -> List[str]:
    """Extract variable names used in code block."""
    used = set()
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used.add(node.id)
    except:
        pass  # Skip parsing errors
    
    return list(used)


def classify_step_type(code: str) -> str:
    """Classify the type of computational step."""
    code_lower = code.lower()
    
    if any(pattern in code_lower for pattern in ['import ', 'from ']):
        return "import"
    elif any(pattern in code_lower for pattern in ['read_csv', 'load', 'open(']):
        return "data_loading"
    elif any(pattern in code_lower for pattern in ['plot', 'show()', 'figure', 'subplot']):
        return "visualization"
    elif any(pattern in code_lower for pattern in ['def ', 'class ']):
        return "definition"
    elif any(pattern in code_lower for pattern in ['for ', 'while ']):
        return "iteration"
    elif any(pattern in code_lower for pattern in ['if ', 'else', 'elif']):
        return "conditional"
    else:
        return "computation"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build snippet library from notebooks")
    parser.add_argument("paths", nargs="+", help="Notebook paths or directories (recursively scanned)")
    parser.add_argument("--out", default="notebook", help="Output prefix for collections")
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

    build_index(collected, args.out, hoist_imports=not args.no_hoist_imports, keep_invalid=args.keep_invalid, synth_imports=not args.no_synth_imports) 
