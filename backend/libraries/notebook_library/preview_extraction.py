#!/usr/bin/env python3
"""Preview what notebook indexing would extract — no Qdrant writes.

Run from backend/libraries:

  python notebook_library/preview_extraction.py
  python notebook_library/preview_extraction.py --sample tutorial
  python notebook_library/preview_extraction.py --sample paleobook-project
  python notebook_library/preview_extraction.py path/to/notebook.ipynb --out /tmp/preview.json
  python notebook_library/preview_extraction.py --sample paleobook-project --llm openai

By default uses heuristics only (no API calls). Pass --llm to also generate
notebook summaries and workflow extractions via an LLM.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import hashlib
import json
import os
import pathlib
import re
import sys
import textwrap
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HERE = pathlib.Path(__file__).resolve().parent
MY_NOTEBOOKS = HERE / "my_notebooks"
METADATA_PATH = MY_NOTEBOOKS / "_metadata" / "notebooks.json"

PHASE_FOLDERS = ("data_assembly", "data_assimilation", "validation")

SAMPLE_SETS: Dict[str, List[str]] = {
    "tutorial": [
        "pyleoclim_tutorials/notebooks/L0_a_quickstart.ipynb",
    ],
    "paleobook-single": [
        "paleobooks_gallery/reproduce_lmr_pb/notebooks/data_assembly/"
        "C01_a_db_assembly_Tardif2019_pickle.ipynb",
    ],
    "paleobook-project": [
        "paleobooks_gallery/reproduce_lmr_pb/notebooks/data_assembly/"
        "C01_a_db_assembly_Tardif2019_pickle.ipynb",
        "paleobooks_gallery/reproduce_lmr_pb/notebooks/data_assembly/"
        "C01_b_db_assembly_cfr_PAGES2k.ipynb",
        "paleobooks_gallery/reproduce_lmr_pb/notebooks/data_assimilation/"
        "C02_a_DA_with_class_based_seasonality.ipynb",
        "paleobooks_gallery/reproduce_lmr_pb/notebooks/validation/"
        "C03_a_validation.ipynb",
    ],
    "mixed": [
        "pyleoclim_tutorials/notebooks/L0_a_quickstart.ipynb",
        "pylipd_tutorials/notebooks/L0_a_loading_lipd_datasets.ipynb",
        "paleobooks_gallery/reproduce_lmr_pb/notebooks/data_assembly/"
        "C01_a_db_assembly_Tardif2019_pickle.ipynb",
        "paleobooks_gallery/reproduce_lmr_pb/notebooks/data_assimilation/"
        "C02_a_DA_with_class_based_seasonality.ipynb",
        "paleobooks_gallery/reproduce_lmr_pb/notebooks/validation/"
        "C03_a_validation.ipynb",
    ],
}

COMMENT_RE = re.compile(r"^\s*#")
IMPORT_RE = re.compile(r"^\s*(?:import\s+\w|from\s+\S+\s+import)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Notebook I/O (stdlib JSON — no nbformat required)
# ---------------------------------------------------------------------------


def load_notebook(path: pathlib.Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def cell_source(cell: Dict[str, Any]) -> str:
    src = cell.get("source", "")
    if isinstance(src, list):
        return "".join(src)
    return src or ""


def is_build_artifact(path: pathlib.Path) -> bool:
    parts = set(path.parts)
    junk = {
        "_build",
        "_sources",
        "jupyter_execute",
        ".virtual_documents",
        ".ipynb_checkpoints",
        "__pycache__",
    }
    if parts & junk:
        return True
    # Sphinx / JupyterBook rendered copies
    return "docs/notebooks" in str(path) or "/_build/" in str(path)


# ---------------------------------------------------------------------------
# Provenance / project detection
# ---------------------------------------------------------------------------


def load_provenance() -> Dict[str, Dict[str, Any]]:
    if not METADATA_PATH.exists():
        return {}
    try:
        records = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    by_dest: Dict[str, Dict[str, Any]] = {}
    if isinstance(records, list):
        for rec in records:
            dest = rec.get("destination_path") or rec.get("source_path")
            if dest:
                by_dest[dest.replace("\\", "/")] = rec
    return by_dest


def resolve_provenance(nb_path: pathlib.Path, provenance: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    try:
        rel = nb_path.resolve().relative_to(MY_NOTEBOOKS.resolve()).as_posix()
    except ValueError:
        rel = nb_path.as_posix()
    return provenance.get(rel)


def detect_project(nb_path: pathlib.Path) -> Optional[Dict[str, Any]]:
    """If notebook sits under .../notebooks/{phase}/, treat sibling phases as one project."""
    resolved = nb_path.resolve()
    phase_dir = resolved.parent
    phase = phase_dir.name
    if phase not in PHASE_FOLDERS:
        return None
    notebooks_root = phase_dir.parent
    if notebooks_root.name != "notebooks":
        return None
    present = {
        p: sorted((notebooks_root / p).glob("*.ipynb"))
        for p in PHASE_FOLDERS
        if (notebooks_root / p).is_dir()
    }
    if len(present) < 2:  # need at least two of the three phases
        return None
    project_id = notebooks_root.parent.name  # repo / paleobook name
    return {
        "project_id": project_id,
        "project_root": str(notebooks_root.parent),
        "notebooks_root": str(notebooks_root),
        "phase": phase,
        "phases_present": sorted(present.keys()),
        "phase_notebooks": {ph: [str(p) for p in paths] for ph, paths in present.items()},
    }


# ---------------------------------------------------------------------------
# Cell / comment / section extraction (no outputs)
# ---------------------------------------------------------------------------


def extract_inline_comments(code: str) -> List[str]:
    comments: List[str] = []
    for line in code.splitlines():
        if COMMENT_RE.match(line) and not IMPORT_RE.match(line):
            text = line.lstrip("#").strip()
            if text:
                comments.append(text)
        else:
            # trailing comments
            if "#" in line and not line.lstrip().startswith("#"):
                # naive: split on # outside strings is hard; keep simple strip
                before, _, after = line.partition("#")
                if after.strip() and ('"' not in before or before.count('"') % 2 == 0):
                    # skip if odd quotes before # (likely in string)
                    if before.count("'") % 2 == 0 and before.count('"') % 2 == 0:
                        comments.append(after.strip())
    return comments


def names_defined_used(code: str) -> Tuple[Set[str], Set[str], Set[str]]:
    defined: Set[str] = set()
    used: Set[str] = set()
    imports: Set[str] = set()
    cleaned = [
        ln
        for ln in code.splitlines()
        if not ln.lstrip().startswith("%") and not ln.lstrip().startswith("!")
    ]
    try:
        # Notebook code often contains invalid escape sequences in strings;
        # don't spam SyntaxWarnings during AST dependency analysis.
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse("\n".join(cleaned))
    except SyntaxError:
        return defined, used, imports

    class Collector(ast.NodeVisitor):
        def visit_Name(self, node):  # type: ignore[override]
            if isinstance(node.ctx, ast.Store):
                defined.add(node.id)
            elif isinstance(node.ctx, ast.Load):
                used.add(node.id)

        def visit_FunctionDef(self, node):  # type: ignore[override]
            defined.add(node.name)
            self.generic_visit(node)

        def visit_Import(self, node):  # type: ignore[override]
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                defined.add(name)
                imports.add(name)

        def visit_ImportFrom(self, node):  # type: ignore[override]
            for alias in node.names:
                name = alias.asname or alias.name
                defined.add(name)
                imports.add(name)

    Collector().visit(tree)
    return defined, used, imports


def heading_level_and_title(md: str) -> Optional[Tuple[int, str]]:
    m = HEADING_RE.search(md.lstrip())
    if not m:
        return None
    return len(m.group(1)), m.group(2).strip()


def extract_top_metadata(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Title, preamble, goals from the leading markdown cells (before first code)."""
    title = None
    preamble_parts: List[str] = []
    goals: List[str] = []
    authors: List[str] = []

    for cell in cells:
        if cell.get("cell_type") != "markdown":
            if cell.get("cell_type") == "code":
                break
            continue
        src = cell_source(cell).strip()
        if not src:
            continue

        # Pure logo/image cell with no prose heading — skip
        ht = heading_level_and_title(src)
        if src.lstrip().startswith("<img") and ht is None:
            continue

        if ht and ht[0] == 1 and title is None:
            title = ht[1]
            # Prefer prose after the H1; drop leading <img> lines
            lines = src.splitlines()
            rest_lines = []
            for i, line in enumerate(lines):
                if HEADING_RE.match(line.strip()) and line.strip().startswith("# "):
                    rest_lines = lines[i + 1 :]
                    break
            rest = "\n".join(rest_lines).strip()
            # If H1 shares a cell with only an image, don't treat image as preamble
            if rest and not rest.lstrip().startswith("<img"):
                preamble_parts.append(rest)
        else:
            # Strip leading image-only lines from preamble chunks
            cleaned = "\n".join(
                ln for ln in src.splitlines() if not ln.lstrip().startswith("<img")
            ).strip()
            if cleaned:
                preamble_parts.append(cleaned)

        if re.search(r"(?i)^#{1,6}\s*goals?\b", src, re.MULTILINE) or re.search(
            r"(?i)\*\*goals?\*\*", src
        ):
            for line in src.splitlines():
                m = re.match(r"^\s*[-*•]\s+(.+)", line)
                if m:
                    goals.append(m.group(1).strip())

        for m in re.finditer(r"\[([^\]]+)\]\(https?://orcid\.org/[^)]+\)", src):
            authors.append(m.group(1).strip())

        if title and len("\n".join(preamble_parts)) > 800:
            break

    preamble = "\n\n".join(preamble_parts).strip()
    return {
        "title": title,
        "preamble": preamble[:4000],
        "preamble_chars": len(preamble),
        "goals": goals,
        "authors": authors,
    }


def cluster_sections(cells: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Split on markdown headings; attach following code (source only, no outputs)."""
    sections: List[Dict[str, Any]] = []
    current = {
        "heading": "Notebook start",
        "heading_level": 0,
        "markdown": [],
        "code_cells": [],
    }

    def flush():
        if not current["code_cells"] and not current["markdown"]:
            return
        code_joined = "\n\n# ----\n".join(c["source"] for c in current["code_cells"])
        comments: List[str] = []
        defined: Set[str] = set()
        used: Set[str] = set()
        imports: Set[str] = set()
        for c in current["code_cells"]:
            comments.extend(c["comments"])
            defined.update(c["defined"])
            used.update(c["used"])
            imports.update(c["imports"])
        unresolved = sorted((used - defined) - set(dir(builtins)))
        sections.append(
            {
                "heading": current["heading"],
                "heading_level": current["heading_level"],
                "markdown_context": "\n\n".join(current["markdown"]).strip()[:2000],
                "cell_indices": [c["index"] for c in current["code_cells"]],
                "code": code_joined,
                "code_chars": len(code_joined),
                "comments": comments,
                "defined": sorted(defined),
                "used": sorted(used),
                "imports": sorted(imports),
                "unresolved": unresolved,
                # what would be embedded for this child chunk
                "embed_text_preview": _child_embed_preview(
                    current["heading"],
                    "\n\n".join(current["markdown"]).strip(),
                    comments,
                    code_joined,
                ),
            }
        )

    for idx, cell in enumerate(cells):
        ctype = cell.get("cell_type")
        src = cell_source(cell)
        if ctype == "markdown":
            ht = heading_level_and_title(src)
            if ht:
                flush()
                current = {
                    "heading": ht[1],
                    "heading_level": ht[0],
                    "markdown": [src],
                    "code_cells": [],
                }
            else:
                current["markdown"].append(src)
        elif ctype == "code":
            # intentionally ignore cell.get("outputs")
            d, u, imps = names_defined_used(src)
            current["code_cells"].append(
                {
                    "index": idx,
                    "source": src,
                    "comments": extract_inline_comments(src),
                    "defined": d,
                    "used": u,
                    "imports": imps,
                    "had_outputs": bool(cell.get("outputs")),
                }
            )

    flush()
    return sections


def _child_embed_preview(heading: str, markdown: str, comments: List[str], code: str) -> str:
    parts = [heading]
    if markdown:
        parts.append(markdown[:500])
    if comments:
        parts.append("Comments: " + " | ".join(comments[:10]))
    if code:
        parts.append(code[:1500])
    return "\n".join(p for p in parts if p)


def notebook_stats(nb: Dict[str, Any], sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    cells = nb.get("cells", [])
    n_md = sum(1 for c in cells if c.get("cell_type") == "markdown")
    n_code = sum(1 for c in cells if c.get("cell_type") == "code")
    n_with_outputs = sum(
        1
        for c in cells
        if c.get("cell_type") == "code" and c.get("outputs")
    )
    return {
        "total_cells": len(cells),
        "markdown_cells": n_md,
        "code_cells": n_code,
        "code_cells_with_outputs": n_with_outputs,
        "outputs_indexed": False,
        "sections": len(sections),
        "sections_with_code": sum(1 for s in sections if s["code_chars"] > 0),
        "total_comments": sum(len(s["comments"]) for s in sections),
    }


def content_hash(nb_path: pathlib.Path) -> str:
    data = nb_path.read_bytes()
    return hashlib.sha256(data).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Heuristic notebook summary / workflow (no LLM)
# ---------------------------------------------------------------------------


def heuristic_notebook_summary(meta: Dict[str, Any], sections: List[Dict[str, Any]], stats: Dict[str, Any]) -> Dict[str, Any]:
    imports: Set[str] = set()
    for s in sections:
        imports.update(s["imports"])
    step_headings = [s["heading"] for s in sections if s["code_chars"] > 0]
    summary = {
        "source": "heuristic",
        "title": meta.get("title") or (step_headings[0] if step_headings else "Untitled"),
        "summary": (meta.get("preamble") or "")[:600]
        or f"Notebook with {stats['code_cells']} code cells across {stats['sections']} sections.",
        "goals": meta.get("goals") or [],
        "libraries": sorted(imports),
        "section_outline": step_headings[:20],
        "keywords": sorted(
            {
                w.lower()
                for h in step_headings
                for w in re.findall(r"[A-Za-z][A-Za-z0-9_+-]{3,}", h)
            }
        )[:30],
    }
    return summary


def heuristic_workflow(meta: Dict[str, Any], sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    steps = []
    n = 1
    for s in sections:
        if s["code_chars"] == 0:
            continue
        steps.append(
            {
                "step_number": n,
                "title": s["heading"],
                "description": (s["markdown_context"] or s["heading"])[:400],
                "cell_indices": s["cell_indices"],
                "imports": s["imports"][:15],
                "code_preview": s["code"][:400],
            }
        )
        n += 1
    return {
        "source": "heuristic",
        "title": meta.get("title") or "Untitled workflow",
        "description": (meta.get("preamble") or "")[:800],
        "num_steps": len(steps),
        "steps": steps,
    }


# ---------------------------------------------------------------------------
# Optional LLM enrichment (+ disk cache)
# ---------------------------------------------------------------------------

LLM_CACHE_DIR = pathlib.Path(
    os.getenv(
        "NOTEBOOK_LLM_CACHE_DIR",
        str(HERE / ".llm_cache"),
    )
)
_LLM_CACHE_ENABLED = True
_LLM_CACHE_STATS = {"hits": 0, "misses": 0, "writes": 0}


def set_llm_cache(*, enabled: bool = True, cache_dir: Optional[pathlib.Path] = None) -> None:
    """Configure LLM disk cache (used by indexer / preview)."""
    global _LLM_CACHE_ENABLED, LLM_CACHE_DIR
    _LLM_CACHE_ENABLED = enabled
    if cache_dir is not None:
        LLM_CACHE_DIR = pathlib.Path(cache_dir)


def llm_cache_stats() -> Dict[str, int]:
    return dict(_LLM_CACHE_STATS)


def _llm_model_name(provider: str) -> str:
    if provider == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4o")
    if provider == "grok":
        return os.getenv("GROK_MODEL", "grok-4")
    return provider


def _cache_key(task: str, provider: str, *parts: str) -> str:
    raw = "::".join([task, provider, _llm_model_name(provider), *parts])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_path(key: str) -> pathlib.Path:
    return LLM_CACHE_DIR / f"{key}.json"


def cache_get(task: str, provider: str, *parts: str) -> Optional[Dict[str, Any]]:
    if not _LLM_CACHE_ENABLED:
        return None
    path = _cache_path(_cache_key(task, provider, *parts))
    if not path.exists():
        _LLM_CACHE_STATS["misses"] += 1
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        payload = data.get("payload")
        if isinstance(payload, dict):
            _LLM_CACHE_STATS["hits"] += 1
            return payload
    except Exception:
        pass
    _LLM_CACHE_STATS["misses"] += 1
    return None


def cache_put(task: str, provider: str, payload: Dict[str, Any], *parts: str) -> None:
    if not _LLM_CACHE_ENABLED:
        return
    LLM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(_cache_key(task, provider, *parts))
    record = {
        "task": task,
        "provider": provider,
        "model": _llm_model_name(provider),
        "parts": list(parts),
        "payload": payload,
    }
    path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    _LLM_CACHE_STATS["writes"] += 1


def _call_llm(prompt: str, provider: str) -> str:
    """Minimal LLM call aligned with literature_library patterns."""
    # Ensure backend config env is loaded when available
    backend_dir = HERE.parent.parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    try:
        import config as _cfg  # noqa: F401
    except Exception:
        pass

    system = (
        "You are an expert paleoclimate / scientific computing assistant. "
        "Return valid JSON only, no markdown fences."
    )

    if provider == "openai":
        import openai

        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY not set")
        model = _llm_model_name(provider)
        client = openai.OpenAI()
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        return resp.choices[0].message.content.strip()  # type: ignore

    if provider == "grok":
        import openai

        if not os.getenv("XAI_API_KEY"):
            raise RuntimeError("XAI_API_KEY not set")
        model = _llm_model_name(provider)
        client = openai.OpenAI(api_key=os.getenv("XAI_API_KEY"), base_url="https://api.x.ai/v1")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        return resp.choices[0].message.content.strip()  # type: ignore

    raise ValueError(f"Unsupported LLM provider: {provider} (use openai|grok)")


def _parse_json_response(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def llm_summarize_notebook(
    provider: str,
    meta: Dict[str, Any],
    sections: List[Dict[str, Any]],
    *,
    content_hash_key: str,
    max_code_chars: int = 6000,
) -> Dict[str, Any]:
    cached = cache_get("notebook_summary", provider, content_hash_key)
    if cached is not None:
        cached = dict(cached)
        cached["source"] = f"llm:{provider}:cache"
        return cached

    outline = []
    code_budget = max_code_chars
    for s in sections:
        entry = {
            "heading": s["heading"],
            "markdown": (s["markdown_context"] or "")[:300],
            "comments": s["comments"][:8],
            "imports": s["imports"][:10],
        }
        if s["code"] and code_budget > 0:
            snippet = s["code"][: min(800, code_budget)]
            entry["code_excerpt"] = snippet
            code_budget -= len(snippet)
        outline.append(entry)

    prompt = textwrap.dedent(
        f"""
        Summarize this Jupyter notebook for search indexing.
        Do NOT use cell outputs. Focus on purpose, inputs, methods, libraries, and outputs produced by the code.

        Top metadata:
        {json.dumps(meta, indent=2)[:2000]}

        Sections (markdown + comments + code excerpts only):
        {json.dumps(outline, indent=2)[:12000]}

        Return JSON with keys:
          title, summary (3-6 sentences), goals (string[]),
          libraries (string[]), techniques (string[]),
          inputs (string[]), outputs (string[]),
          keywords (string[]), section_blurbs (array of {{heading, blurb}})
        """
    ).strip()

    raw = _call_llm(prompt, provider)
    data = _parse_json_response(raw)
    data["source"] = f"llm:{provider}"
    cache_put("notebook_summary", provider, data, content_hash_key)
    return data


def llm_extract_workflow(
    provider: str,
    meta: Dict[str, Any],
    sections: List[Dict[str, Any]],
    summary: Optional[Dict[str, Any]] = None,
    *,
    content_hash_key: str,
) -> Dict[str, Any]:
    cached = cache_get("notebook_workflow", provider, content_hash_key)
    if cached is not None:
        cached = dict(cached)
        cached["source"] = f"llm:{provider}:cache"
        cached["num_steps"] = len(cached.get("steps") or [])
        return cached

    compact = [
        {
            "heading": s["heading"],
            "markdown": (s["markdown_context"] or "")[:250],
            "comments": s["comments"][:5],
            "imports": s["imports"][:8],
            "code_preview": s["code"][:500] if s["code"] else "",
            "cell_indices": s["cell_indices"],
        }
        for s in sections
        if s["code_chars"] > 0
    ]
    prompt = textwrap.dedent(
        f"""
        Extract an ordered scientific computing workflow from this notebook.
        Ignore outputs. Merge tiny cells into coherent steps when they belong together.

        Title/preamble:
        {json.dumps(meta, indent=2)[:1500]}

        Optional summary:
        {json.dumps(summary or {}, indent=2)[:1500]}

        Code sections:
        {json.dumps(compact, indent=2)[:12000]}

        Return JSON:
          title, description, phase (one of: data_assembly, data_assimilation,
          validation, tutorial, analysis, other),
          steps: [{{step_number, title, description, cell_indices, depends_on (string[])}}]
        """
    ).strip()
    raw = _call_llm(prompt, provider)
    data = _parse_json_response(raw)
    data["source"] = f"llm:{provider}"
    data["num_steps"] = len(data.get("steps") or [])
    cache_put("notebook_workflow", provider, data, content_hash_key)
    return data


def llm_project_summary(
    provider: str,
    project: Dict[str, Any],
    notebook_docs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    member_hashes = sorted(d.get("content_hash") or "" for d in notebook_docs)
    project_key = project.get("project_id", "project") + "|" + "|".join(member_hashes)
    cached = cache_get("project_summary", provider, project_key)
    if cached is not None:
        cached = dict(cached)
        cached["source"] = f"llm:{provider}:cache"
        cached["project_id"] = project.get("project_id")
        return cached

    compact = []
    for doc in notebook_docs:
        compact.append(
            {
                "path": doc["path"],
                "phase": (doc.get("project") or {}).get("phase"),
                "title": doc["top_metadata"].get("title"),
                "summary": (doc.get("notebook_summary") or {}).get("summary"),
                "workflow_title": (doc.get("workflow") or {}).get("title"),
                "num_steps": (doc.get("workflow") or {}).get("num_steps"),
            }
        )
    prompt = textwrap.dedent(
        f"""
        These notebooks belong to one paleobook project with phases
        data_assembly → data_assimilation → validation.
        Write a combined project-level summary and ordered workflow for indexing.

        Project id: {project.get('project_id')}
        Phases present: {project.get('phases_present')}

        Notebooks:
        {json.dumps(compact, indent=2)[:10000]}

        Return JSON:
          title, summary, phases (array of {{phase, notebook_paths, role}}),
          end_to_end_steps (array of {{step_number, phase, title, description, notebook}}),
          keywords (string[])
        """
    ).strip()
    raw = _call_llm(prompt, provider)
    data = _parse_json_response(raw)
    data["source"] = f"llm:{provider}"
    data["project_id"] = project.get("project_id")
    cache_put("project_summary", provider, data, project_key)
    return data

# ---------------------------------------------------------------------------
# Per-notebook + project extraction
# ---------------------------------------------------------------------------


def extract_notebook(
    nb_path: pathlib.Path,
    provenance: Dict[str, Dict[str, Any]],
    *,
    llm: Optional[str] = None,
    max_sections_in_preview: int = 8,
    truncate_sections: bool = True,
) -> Dict[str, Any]:
    nb = load_notebook(nb_path)
    cells = nb.get("cells", [])
    meta = extract_top_metadata(cells)
    sections = cluster_sections(cells)
    stats = notebook_stats(nb, sections)
    project = detect_project(nb_path)
    prov = resolve_provenance(nb_path, provenance)

    summary = heuristic_notebook_summary(meta, sections, stats)
    workflow = heuristic_workflow(meta, sections)
    nb_hash = content_hash(nb_path)

    if llm:
        try:
            summary = llm_summarize_notebook(
                llm, meta, sections, content_hash_key=nb_hash
            )
            workflow = llm_extract_workflow(
                llm, meta, sections, summary, content_hash_key=nb_hash
            )
        except Exception as e:
            summary["llm_error"] = str(e)
            workflow["llm_error"] = str(e)

    if truncate_sections:
        preview_sections = []
        for s in sections[:max_sections_in_preview]:
            preview_sections.append(
                {
                    **s,
                    "code": s["code"][:600] + ("…" if len(s["code"]) > 600 else ""),
                    "embed_text_preview": s["embed_text_preview"][:800]
                    + ("…" if len(s["embed_text_preview"]) > 800 else ""),
                }
            )
        sections_omitted = max(0, len(sections) - max_sections_in_preview)
    else:
        preview_sections = sections
        sections_omitted = 0

    return {
        "path": str(nb_path),
        "relative_path": (
            nb_path.resolve().relative_to(MY_NOTEBOOKS.resolve()).as_posix()
            if MY_NOTEBOOKS.resolve() in nb_path.resolve().parents
            or nb_path.resolve() == MY_NOTEBOOKS.resolve()
            else str(nb_path)
        ),
        "content_hash": nb_hash,
        "nbformat": nb.get("nbformat"),
        "kernelspec": (nb.get("metadata") or {}).get("kernelspec"),
        "provenance": prov,
        "project": project,
        "top_metadata": meta,
        "stats": stats,
        "notebook_summary": summary,
        "workflow": workflow,
        "sections_preview": preview_sections,
        "sections_omitted": sections_omitted,
        "index_candidates": {
            "parent_notebook": {
                "embed": (summary.get("summary") or "")[:500],
                "payload_keys": [
                    "title",
                    "summary",
                    "goals",
                    "libraries",
                    "keywords",
                    "provenance",
                    "project_id",
                    "phase",
                ],
            },
            "child_snippets": {
                "count": sum(1 for s in sections if s["code_chars"] > 0),
                "embed_fields": ["heading", "markdown_context", "comments", "code"],
                "note": "outputs are excluded",
            },
            "workflow": {
                "embed": f"{workflow.get('title', '')} {workflow.get('description', '')}"[:500],
                "num_steps": workflow.get("num_steps"),
            },
        },
    }


def combine_project(docs: List[Dict[str, Any]], *, llm: Optional[str] = None) -> Optional[Dict[str, Any]]:
    projects = [d.get("project") for d in docs if d.get("project")]
    if not projects:
        return None
    # Prefer a project that has all three phases among the docs
    by_id: Dict[str, List[Dict[str, Any]]] = {}
    for d in docs:
        p = d.get("project")
        if not p:
            continue
        by_id.setdefault(p["project_id"], []).append(d)

    combined = []
    for project_id, members in by_id.items():
        base = members[0]["project"]
        phases = sorted({(m.get("project") or {}).get("phase") for m in members if m.get("project")})
        entry = {
            "project_id": project_id,
            "phases_in_sample": phases,
            "phases_on_disk": base.get("phases_present"),
            "notebooks": [
                {
                    "path": m["relative_path"],
                    "phase": (m.get("project") or {}).get("phase"),
                    "title": m["top_metadata"].get("title"),
                    "summary": (m.get("notebook_summary") or {}).get("summary", "")[:300],
                    "workflow_steps": (m.get("workflow") or {}).get("num_steps"),
                }
                for m in members
            ],
            "combined_workflow_heuristic": {
                "source": "heuristic",
                "title": f"{project_id} end-to-end pipeline",
                "description": (
                    "Combined paleobook pipeline across "
                    + " → ".join(base.get("phases_present") or phases)
                ),
                "steps": [
                    {
                        "order": i + 1,
                        "phase": (m.get("project") or {}).get("phase"),
                        "notebook": m["relative_path"],
                        "title": m["top_metadata"].get("title"),
                        "num_internal_steps": (m.get("workflow") or {}).get("num_steps"),
                    }
                    for i, m in enumerate(
                        sorted(
                            members,
                            key=lambda x: PHASE_FOLDERS.index((x.get("project") or {}).get("phase"))
                            if (x.get("project") or {}).get("phase") in PHASE_FOLDERS
                            else 99,
                        )
                    )
                ],
            },
        }
        if llm:
            try:
                entry["combined_workflow_llm"] = llm_project_summary(llm, base, members)
            except Exception as e:
                entry["combined_workflow_llm_error"] = str(e)
        combined.append(entry)

    return {"projects": combined} if combined else None


# ---------------------------------------------------------------------------
# Pretty print
# ---------------------------------------------------------------------------


def print_human(report: Dict[str, Any]) -> None:
    print("=" * 72)
    print("NOTEBOOK EXTRACTION PREVIEW (nothing written to Qdrant)")
    print("=" * 72)
    for doc in report["notebooks"]:
        print(f"\n## {doc['relative_path']}")
        print(f"   hash={doc['content_hash']}  cells={doc['stats']['total_cells']}  "
              f"code={doc['stats']['code_cells']}  outputs_present={doc['stats']['code_cells_with_outputs']} "
              f"(not indexed)")
        tm = doc["top_metadata"]
        print(f"   title: {tm.get('title')}")
        if tm.get("goals"):
            print(f"   goals: {tm['goals'][:5]}")
        if doc.get("project"):
            print(f"   project: {doc['project']['project_id']}  phase={doc['project']['phase']}  "
                  f"phases={doc['project']['phases_present']}")
        ns = doc["notebook_summary"]
        print(f"   summary [{ns.get('source')}]:")
        print(textwrap.indent(textwrap.fill(str(ns.get("summary", "")), 88), "      "))
        wf = doc["workflow"]
        print(f"   workflow [{wf.get('source')}]: {wf.get('title')}  ({wf.get('num_steps')} steps)")
        for step in (wf.get("steps") or [])[:5]:
            print(f"      {step.get('step_number')}. {step.get('title')}")
        print(f"   child sections with code: {doc['index_candidates']['child_snippets']['count']} "
              f"(showing {len(doc['sections_preview'])})")
        for s in doc["sections_preview"][:4]:
            if s["code_chars"] == 0:
                continue
            print(f"      - [{s['heading_level']}] {s['heading'][:60]}  "
                  f"code={s['code_chars']}b comments={len(s['comments'])}")
            if s["comments"][:2]:
                print(f"        comments: {s['comments'][:2]}")

    proj = report.get("project_combine")
    if proj:
        print("\n" + "=" * 72)
        print("PROJECT COMBINE (data_assembly + data_assimilation + validation)")
        print("=" * 72)
        for p in proj.get("projects", []):
            print(f"\n## project {p['project_id']}")
            print(f"   phases in sample: {p['phases_in_sample']}")
            print(f"   phases on disk:   {p['phases_on_disk']}")
            for n in p["notebooks"]:
                print(f"   - [{n['phase']}] {n['title']}  ({n['workflow_steps']} steps)")
            cw = p.get("combined_workflow_heuristic") or {}
            print(f"   combined: {cw.get('title')}")
            for st in cw.get("steps", []):
                print(f"      {st['order']}. [{st['phase']}] {st['title']}")
            if p.get("combined_workflow_llm"):
                llm_p = p["combined_workflow_llm"]
                print(f"   LLM project summary: {llm_p.get('summary', '')[:400]}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def resolve_paths(args: argparse.Namespace) -> List[pathlib.Path]:
    paths: List[pathlib.Path] = []
    if args.sample:
        for rel in SAMPLE_SETS[args.sample]:
            paths.append(MY_NOTEBOOKS / rel)
    for p in args.paths:
        path = pathlib.Path(p)
        if not path.is_absolute():
            # try cwd, then my_notebooks-relative
            if not path.exists() and (MY_NOTEBOOKS / path).exists():
                path = MY_NOTEBOOKS / path
            elif not path.exists() and (HERE / path).exists():
                path = HERE / path
        if path.is_dir():
            for nb in sorted(path.rglob("*.ipynb")):
                if not is_build_artifact(nb) and ".ipynb_checkpoints" not in nb.parts:
                    paths.append(nb)
        else:
            paths.append(path)

    # de-dupe preserve order
    seen = set()
    out = []
    for p in paths:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        out.append(p)
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "paths",
        nargs="*",
        help="Notebook files or directories (optional if --sample is set)",
    )
    parser.add_argument(
        "--sample",
        choices=sorted(SAMPLE_SETS.keys()),
        default=None,
        help="Built-in sample set under my_notebooks",
    )
    parser.add_argument(
        "--llm",
        choices=["openai", "grok"],
        default=None,
        help="Also run LLM summary + workflow extraction (needs API key)",
    )
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=None,
        help="Write full JSON report to this path",
    )
    parser.add_argument(
        "--max-sections",
        type=int,
        default=8,
        help="Max sections per notebook in JSON preview (default 8)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only write JSON (--out or stdout), skip human summary",
    )
    args = parser.parse_args(argv)

    if not args.sample and not args.paths:
        args.sample = "mixed"

    paths = resolve_paths(args)
    missing = [p for p in paths if not p.exists()]
    if missing:
        for p in missing:
            print(f"ERROR: not found: {p}", file=sys.stderr)
        return 1
    if not paths:
        print("ERROR: no notebooks to process", file=sys.stderr)
        return 1

    provenance = load_provenance()
    docs = [
        extract_notebook(
            p,
            provenance,
            llm=args.llm,
            max_sections_in_preview=args.max_sections,
        )
        for p in paths
    ]
    project_combine = combine_project(docs, llm=args.llm)

    report = {
        "mode": "preview_only",
        "llm": args.llm,
        "notebook_root": str(MY_NOTEBOOKS),
        "notebook_count": len(docs),
        "notebooks": docs,
        "project_combine": project_combine,
    }

    if not args.quiet:
        print_human(report)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"\nWrote JSON report → {args.out}")
    elif args.quiet:
        print(json.dumps(report, indent=2, default=str))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
