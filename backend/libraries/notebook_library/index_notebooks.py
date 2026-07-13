"""notebook_library.index_notebooks

Scan Jupyter notebooks under my_notebooks, extract hierarchical documents
(parent summaries, child code/comment snippets, workflows), embed them, and
persist to Qdrant.

Uses structural extraction from preview_extraction.py (no cell outputs).
Optional --llm for notebook/project summaries and workflow extraction.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    def tqdm(iterable, **kwargs):  # type: ignore
        return iterable

# Add parent directory to path for imports
current_dir = pathlib.Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from qdrant_config import get_qdrant_manager, COLLECTION_NAMES

try:
    from notebook_library.preview_extraction import (  # noqa: E402
        MY_NOTEBOOKS,
        PHASE_FOLDERS,
        combine_project,
        detect_project,
        extract_notebook,
        is_build_artifact,
        load_provenance,
        llm_cache_stats,
        set_llm_cache,
        cache_put,
        content_hash,
    )
except ImportError:  # running as a script inside notebook_library/
    from preview_extraction import (  # noqa: E402
        MY_NOTEBOOKS,
        PHASE_FOLDERS,
        combine_project,
        detect_project,
        extract_notebook,
        is_build_artifact,
        load_provenance,
        llm_cache_stats,
        set_llm_cache,
        cache_put,
        content_hash,
    )

# ---------------------------------------------------------------------------
# Stable IDs
# ---------------------------------------------------------------------------


def _stable_id(*parts: str) -> str:
    """Deterministic UUID for Qdrant point IDs."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "::".join(parts)))


def _rel_path(nb_path: pathlib.Path) -> str:
    try:
        return nb_path.resolve().relative_to(MY_NOTEBOOKS.resolve()).as_posix()
    except ValueError:
        return str(nb_path)


# ---------------------------------------------------------------------------
# Backward-compatible extraction helpers (used by NotebookExtractor)
# ---------------------------------------------------------------------------


def extract_snippets(
    nb_path: pathlib.Path,
    *,
    hoist_imports: bool = True,
    synth_imports: bool = True,
) -> List[Dict[str, Any]]:
    """Extract child code/comment sections from a notebook (no outputs)."""
    del hoist_imports, synth_imports  # retained for API compatibility
    doc = extract_notebook(nb_path, {}, llm=None, truncate_sections=False)
    snippets = []
    for section in doc.get("sections_preview") or []:
        if not section.get("code_chars"):
            continue
        snippets.append(
            {
                "id": _stable_id("snippet", str(nb_path), section.get("heading", ""), str(section.get("cell_indices"))),
                "notebook": str(nb_path),
                "notebook_path": str(nb_path),
                "title": section.get("heading", ""),
                "markdown_context": section.get("markdown_context", ""),
                "markdown": section.get("markdown_context", ""),
                "code": section.get("code", ""),
                "comments": section.get("comments", []),
                "cell_indices": section.get("cell_indices", []),
                "defined": section.get("defined", []),
                "used": section.get("used", []),
                "imports": section.get("imports", []),
                "unresolved": section.get("unresolved", []),
            }
        )
    return snippets


def extract_complete_workflows(
    nb_path: pathlib.Path,
    snippets: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Extract a notebook-level workflow document."""
    del snippets
    doc = extract_notebook(nb_path, {}, llm=None, truncate_sections=False)
    wf = doc.get("workflow") or {}
    steps = []
    for step in wf.get("steps") or []:
        steps.append(
            {
                "step_number": step.get("step_number"),
                "step_type": "computation",
                "description": step.get("description") or step.get("title", ""),
                "title": step.get("title", ""),
                "code": step.get("code_preview", ""),
                "cell_indices": step.get("cell_indices", []),
                "dependencies": step.get("imports") or step.get("depends_on") or [],
                "defined_names": [],
                "used_names": [],
                "keywords": [],
            }
        )
    return [
        {
            "title": wf.get("title") or doc.get("top_metadata", {}).get("title") or "Untitled",
            "description": wf.get("description") or "",
            "content_type": "complete_workflow",
            "workflow_type": wf.get("phase") or "general",
            "keywords": (doc.get("notebook_summary") or {}).get("keywords") or [],
            "complexity": "medium",
            "has_imports": any(s.get("imports") for s in doc.get("sections_preview") or []),
            "cell_count": doc.get("stats", {}).get("code_cells", 0),
            "workflow_steps": steps,
            "num_steps": len(steps),
            "notebook_path": str(nb_path),
        }
    ]


def cluster_notebook_cells(
    nb_path: pathlib.Path,
    *,
    hoist_imports: bool = True,
    synth_imports: bool = True,
    snippet_mode: bool = True,
    workflow_title: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Compatibility wrapper — returns snippet-like clusters."""
    del hoist_imports, synth_imports, snippet_mode, workflow_title
    return extract_snippets(nb_path)


# ---------------------------------------------------------------------------
# Document builders
# ---------------------------------------------------------------------------


def _summary_embed_text(summary: Dict[str, Any], meta: Dict[str, Any]) -> str:
    parts = [
        summary.get("title") or meta.get("title") or "",
        summary.get("summary") or "",
        " ".join(summary.get("goals") or meta.get("goals") or []),
        " ".join(summary.get("libraries") or []),
        " ".join(summary.get("techniques") or []),
        " ".join(summary.get("keywords") or []),
        (meta.get("preamble") or "")[:800],
    ]
    return "\n".join(p for p in parts if p).strip()


def _snippet_embed_text(section: Dict[str, Any], parent_summary: str) -> str:
    parts = [
        section.get("heading") or "",
        (section.get("markdown_context") or "")[:600],
    ]
    comments = section.get("comments") or []
    if comments:
        parts.append("Comments: " + " | ".join(comments[:12]))
    if parent_summary:
        parts.append(parent_summary[:400])
    code = section.get("code") or ""
    if code:
        parts.append(code[:2000])
    return "\n".join(p for p in parts if p).strip()


def _workflow_embed_text(workflow: Dict[str, Any]) -> str:
    parts = [
        workflow.get("title") or "",
        workflow.get("description") or "",
        workflow.get("phase") or workflow.get("workflow_type") or "",
    ]
    for step in workflow.get("steps") or workflow.get("workflow_steps") or []:
        parts.append(step.get("title") or "")
        parts.append(step.get("description") or "")
    return "\n".join(p for p in parts if p).strip()


def documents_from_extraction(doc: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    """Build (summary_doc, snippet_docs, workflow_doc) from extract_notebook output."""
    rel = doc["relative_path"]
    abs_path = doc["path"]
    meta = doc.get("top_metadata") or {}
    summary = doc.get("notebook_summary") or {}
    workflow = doc.get("workflow") or {}
    project = doc.get("project") or {}
    provenance = doc.get("provenance") or {}

    notebook_id = _stable_id("notebook", rel)
    project_id = project.get("project_id")
    phase = project.get("phase")
    parent_summary_text = summary.get("summary") or meta.get("preamble") or ""

    summary_doc = {
        "id": notebook_id,
        "content_type": "notebook_summary",
        "notebook_id": notebook_id,
        "notebook_path": abs_path,
        "relative_path": rel,
        "title": summary.get("title") or meta.get("title") or pathlib.Path(rel).stem,
        "summary": parent_summary_text,
        "goals": summary.get("goals") or meta.get("goals") or [],
        "authors": meta.get("authors") or [],
        "libraries": summary.get("libraries") or [],
        "techniques": summary.get("techniques") or [],
        "keywords": summary.get("keywords") or [],
        "section_outline": summary.get("section_outline") or [],
        "section_blurbs": summary.get("section_blurbs") or [],
        "inputs": summary.get("inputs") or [],
        "outputs": summary.get("outputs") or [],
        "project_id": project_id,
        "phase": phase,
        "provenance": {
            k: provenance.get(k)
            for k in ("source_name", "repo_name", "repo", "commit", "landingpage_url", "license")
            if provenance.get(k)
        },
        "stats": doc.get("stats") or {},
        "summary_source": summary.get("source"),
        "content_hash": doc.get("content_hash"),
        "text": _summary_embed_text(summary, meta),
    }

    # Prefer full sections from a fresh extract with high preview limit
    sections = doc.get("sections_preview") or []
    snippet_docs: List[Dict[str, Any]] = []
    for i, section in enumerate(sections):
        if not section.get("code_chars"):
            continue
        heading = section.get("heading") or f"section_{i}"
        snippet_id = _stable_id("snippet", rel, heading, str(section.get("cell_indices")))
        # Prefer LLM section blurb when present
        blurb = ""
        for sb in summary.get("section_blurbs") or []:
            if isinstance(sb, dict) and sb.get("heading") == heading:
                blurb = sb.get("blurb") or ""
                break
        embed_section = dict(section)
        if blurb:
            embed_section["markdown_context"] = (
                (blurb + "\n\n" + (section.get("markdown_context") or "")).strip()
            )
        snippet_docs.append(
            {
                "id": snippet_id,
                "content_type": "code_snippet",
                "parent_id": notebook_id,
                "notebook_id": notebook_id,
                "notebook_path": abs_path,
                "relative_path": rel,
                "project_id": project_id,
                "phase": phase,
                "title": heading,
                "heading": heading,
                "heading_level": section.get("heading_level", 0),
                "markdown": section.get("markdown_context") or "",
                "markdown_context": section.get("markdown_context") or "",
                "comments": section.get("comments") or [],
                "code": section.get("code") or "",
                "cell_indices": section.get("cell_indices") or [],
                "defined": section.get("defined") or [],
                "used": section.get("used") or [],
                "imports": section.get("imports") or [],
                "unresolved": section.get("unresolved") or [],
                "parent_title": summary_doc["title"],
                "parent_summary": parent_summary_text[:800],
                "text": _snippet_embed_text(embed_section, parent_summary_text),
            }
        )

    steps = []
    for step in workflow.get("steps") or []:
        steps.append(
            {
                "step_number": step.get("step_number"),
                "title": step.get("title"),
                "description": step.get("description") or step.get("title") or "",
                "step_type": step.get("step_type") or "computation",
                "cell_indices": step.get("cell_indices") or [],
                "dependencies": step.get("imports") or step.get("depends_on") or [],
                "code": step.get("code_preview") or step.get("code") or "",
            }
        )

    workflow_doc = {
        "id": _stable_id("workflow", rel),
        "content_type": "notebook_workflow",
        "notebook_id": notebook_id,
        "notebook_path": abs_path,
        "relative_path": rel,
        "project_id": project_id,
        "phase": phase or workflow.get("phase") or "other",
        "title": workflow.get("title") or summary_doc["title"],
        "description": workflow.get("description") or parent_summary_text[:800],
        "workflow_type": workflow.get("phase") or "general",
        "keywords": summary.get("keywords") or [],
        "complexity": "medium",
        "has_imports": any(s.get("imports") for s in sections),
        "cell_count": (doc.get("stats") or {}).get("code_cells", 0),
        "workflow_steps": steps,
        "num_steps": len(steps),
        "parent_summary": parent_summary_text[:800],
        "workflow_source": workflow.get("source"),
        "text": _workflow_embed_text(
            {
                "title": workflow.get("title"),
                "description": workflow.get("description"),
                "phase": phase,
                "workflow_steps": steps,
            }
        ),
    }

    return summary_doc, snippet_docs, workflow_doc


def documents_from_project_combine(project_entry: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Build project-level summary + workflow from combine_project output."""
    project_id = project_entry["project_id"]
    llm_wf = project_entry.get("combined_workflow_llm")
    heur = project_entry.get("combined_workflow_heuristic") or {}
    source = llm_wf if isinstance(llm_wf, dict) else heur

    title = source.get("title") or f"{project_id} end-to-end pipeline"
    summary_text = source.get("summary") or source.get("description") or ""
    keywords = source.get("keywords") or []

    steps = []
    if source.get("end_to_end_steps"):
        for st in source["end_to_end_steps"]:
            steps.append(
                {
                    "step_number": st.get("step_number") or st.get("order"),
                    "phase": st.get("phase"),
                    "title": st.get("title"),
                    "description": st.get("description") or "",
                    "notebook": st.get("notebook"),
                }
            )
    elif source.get("steps"):
        for st in source["steps"]:
            steps.append(
                {
                    "step_number": st.get("order") or st.get("step_number"),
                    "phase": st.get("phase"),
                    "title": st.get("title"),
                    "description": st.get("description") or "",
                    "notebook": st.get("notebook"),
                    "num_internal_steps": st.get("num_internal_steps"),
                }
            )

    summary_doc = {
        "id": _stable_id("project_summary", project_id),
        "content_type": "project_summary",
        "project_id": project_id,
        "title": title,
        "summary": summary_text,
        "phases": project_entry.get("phases_on_disk") or project_entry.get("phases_in_sample") or [],
        "notebooks": project_entry.get("notebooks") or [],
        "keywords": keywords,
        "summary_source": source.get("source"),
        "text": "\n".join(
            p
            for p in [
                title,
                summary_text,
                " ".join(project_entry.get("phases_on_disk") or []),
                " ".join(keywords),
            ]
            if p
        ),
    }

    workflow_doc = {
        "id": _stable_id("project_workflow", project_id),
        "content_type": "project_workflow",
        "project_id": project_id,
        "title": title,
        "description": summary_text,
        "workflow_type": "paleobook_pipeline",
        "phase": "project",
        "keywords": keywords,
        "workflow_steps": steps,
        "num_steps": len(steps),
        "phases": summary_doc["phases"],
        "notebooks": project_entry.get("notebooks") or [],
        "workflow_source": source.get("source"),
        "text": _workflow_embed_text(
            {"title": title, "description": summary_text, "workflow_steps": steps}
        ),
    }
    return summary_doc, workflow_doc


# ---------------------------------------------------------------------------
# Corpus collection
# ---------------------------------------------------------------------------


def collect_notebooks(paths: List[pathlib.Path]) -> List[pathlib.Path]:
    collected: List[pathlib.Path] = []
    for p in paths:
        path = pathlib.Path(p)
        if path.is_dir():
            for nb in path.rglob("*.ipynb"):
                if ".ipynb_checkpoints" in nb.parts:
                    continue
                if is_build_artifact(nb):
                    continue
                collected.append(nb)
        elif path.suffix == ".ipynb":
            if not is_build_artifact(path):
                collected.append(path)

    # Expand projects: if any notebook is in a 3-phase paleobook, include all phase notebooks
    extras: List[pathlib.Path] = []
    seen: Set[pathlib.Path] = {c.resolve() for c in collected}
    for nb in list(collected):
        project = detect_project(nb)
        if not project:
            continue
        for phase_paths in (project.get("phase_notebooks") or {}).values():
            for p in phase_paths:
                rp = pathlib.Path(p).resolve()
                if rp not in seen and not is_build_artifact(rp):
                    seen.add(rp)
                    extras.append(pathlib.Path(p))
    collected.extend(extras)

    # de-dupe preserve order
    out: List[pathlib.Path] = []
    ordered: Set[pathlib.Path] = set()
    for p in collected:
        rp = p.resolve()
        if rp in ordered:
            continue
        ordered.add(rp)
        out.append(p)
    return out


# ---------------------------------------------------------------------------
# Index build
# ---------------------------------------------------------------------------


def build_index(
    notebook_paths: List[pathlib.Path],
    collection_name_prefix: Optional[str] = None,
    *,
    hoist_imports: bool = True,
    keep_invalid: bool = False,
    synth_imports: bool = True,
    force_recreate: bool = False,
    llm: Optional[str] = None,
) -> Dict[str, str]:
    """
    Build Qdrant indexes: summaries (parents), snippets (children), workflows.

    Returns mapping of logical collection type → collection name.
    """
    del hoist_imports, synth_imports  # API compatibility; extraction no longer uses these

    if collection_name_prefix is None:
        collections = {
            "summaries": COLLECTION_NAMES["notebook_summaries"],
            "snippets": COLLECTION_NAMES["notebook_snippets"],
            "workflows": COLLECTION_NAMES["notebook_workflows"],
        }
    else:
        collections = {
            "summaries": f"{collection_name_prefix}_summaries",
            "snippets": f"{collection_name_prefix}_snippets",
            "workflows": f"{collection_name_prefix}_workflows",
        }

    paths = collect_notebooks(notebook_paths)
    if not paths:
        raise ValueError("No notebooks found to index (after excluding build artifacts)")

    provenance = load_provenance()
    all_summaries: List[Dict[str, Any]] = []
    all_snippets: List[Dict[str, Any]] = []
    all_workflows: List[Dict[str, Any]] = []
    extracted_docs: List[Dict[str, Any]] = []

    for nb_path in tqdm(paths, desc="Extracting notebooks"):
        try:
            doc = extract_notebook(
                nb_path,
                provenance,
                llm=llm,
                truncate_sections=False,
            )
            extracted_docs.append(doc)
            summary_doc, snippet_docs, workflow_doc = documents_from_extraction(doc)

            if not keep_invalid:
                snippet_docs = [s for s in snippet_docs if not s.get("unresolved")]

            all_summaries.append(summary_doc)
            all_snippets.extend(snippet_docs)
            all_workflows.append(workflow_doc)
        except Exception as e:
            print(f"Error processing {nb_path}: {e}")
            continue

    # Project-level parents (data_assembly + data_assimilation + validation)
    project_combine = combine_project(extracted_docs, llm=llm)
    if project_combine:
        for project_entry in project_combine.get("projects") or []:
            # Prefer projects that expose at least 2 of the 3 CFR phases
            phases = set(project_entry.get("phases_on_disk") or [])
            if len(phases & set(PHASE_FOLDERS)) < 2:
                continue
            p_summary, p_workflow = documents_from_project_combine(project_entry)
            all_summaries.append(p_summary)
            all_workflows.append(p_workflow)

    if not all_summaries and not all_snippets and not all_workflows:
        raise ValueError("No documents extracted from notebooks")

    qdrant_manager = get_qdrant_manager()
    results: Dict[str, str] = {}

    if all_summaries:
        print(f"Indexing {len(all_summaries)} notebook/project summaries (parents)...")
        if qdrant_manager.create_collection(collections["summaries"], force_recreate=force_recreate):
            qdrant_manager.index_documents(
                collection_name=collections["summaries"],
                documents=all_summaries,
                text_field="text",
            )
            results["summaries"] = collections["summaries"]

    if all_snippets:
        print(f"Indexing {len(all_snippets)} code/comment snippets (children)...")
        if qdrant_manager.create_collection(collections["snippets"], force_recreate=force_recreate):
            qdrant_manager.index_documents(
                collection_name=collections["snippets"],
                documents=all_snippets,
                text_field="text",
            )
            results["snippets"] = collections["snippets"]

    if all_workflows:
        print(f"Indexing {len(all_workflows)} workflows...")
        if qdrant_manager.create_collection(collections["workflows"], force_recreate=force_recreate):
            qdrant_manager.index_documents(
                collection_name=collections["workflows"],
                documents=all_workflows,
                text_field="text",
            )
            results["workflows"] = collections["workflows"]

    print(
        f"Notebook indexing completed. "
        f"summaries={len(all_summaries)} snippets={len(all_snippets)} "
        f"workflows={len(all_workflows)} collections={list(results.values())}"
    )
    stats = llm_cache_stats()
    print(
        f"LLM cache: hits={stats['hits']} misses={stats['misses']} writes={stats['writes']}"
    )
    return results


def bootstrap_llm_cache_from_qdrant(
    provider: str = "openai",
    *,
    cache_dir: Optional[pathlib.Path] = None,
) -> Dict[str, int]:
    """
    Seed the LLM disk cache from already-indexed Qdrant payloads.

    Use after a successful --llm index so the next reindex can skip API calls
    for unchanged notebooks.
    """
    set_llm_cache(enabled=True, cache_dir=cache_dir)
    qdrant_manager = get_qdrant_manager()
    counts = {"summaries": 0, "workflows": 0, "skipped": 0}

    summaries_name = COLLECTION_NAMES["notebook_summaries"]
    workflows_name = COLLECTION_NAMES["notebook_workflows"]

    # Map relative_path -> content_hash from summaries
    path_to_hash: Dict[str, str] = {}
    if summaries_name in qdrant_manager.list_collections():
        points = qdrant_manager.scroll_by_filter(
            collection_name=summaries_name,
            filters={"content_type": "notebook_summary"},
            limit=10_000,
        )
        for p in points:
            ch = p.get("content_hash")
            rel = p.get("relative_path")
            src = str(p.get("summary_source") or "")
            if not ch or not src.startswith("llm:"):
                counts["skipped"] += 1
                continue
            if rel:
                path_to_hash[rel] = ch
            payload = {
                "title": p.get("title"),
                "summary": p.get("summary"),
                "goals": p.get("goals") or [],
                "libraries": p.get("libraries") or [],
                "techniques": p.get("techniques") or [],
                "keywords": p.get("keywords") or [],
                "section_outline": p.get("section_outline") or [],
                "section_blurbs": p.get("section_blurbs") or [],
                "inputs": p.get("inputs") or [],
                "outputs": p.get("outputs") or [],
                "source": src,
            }
            cache_put("notebook_summary", provider, payload, ch)
            counts["summaries"] += 1

    if workflows_name in qdrant_manager.list_collections():
        points = qdrant_manager.scroll_by_filter(
            collection_name=workflows_name,
            filters={"content_type": "notebook_workflow"},
            limit=10_000,
        )
        for p in points:
            rel = p.get("relative_path")
            src = str(p.get("workflow_source") or "")
            ch = path_to_hash.get(rel or "")
            if not ch:
                # Fall back to hashing the notebook file if present
                if rel and (MY_NOTEBOOKS / rel).exists():
                    ch = content_hash(MY_NOTEBOOKS / rel)
                else:
                    counts["skipped"] += 1
                    continue
            if not src.startswith("llm:"):
                counts["skipped"] += 1
                continue
            steps = p.get("workflow_steps") or p.get("steps") or []
            payload = {
                "title": p.get("title"),
                "description": p.get("description"),
                "phase": p.get("phase") or p.get("workflow_type"),
                "steps": steps,
                "num_steps": p.get("num_steps") or len(steps),
                "source": src,
            }
            cache_put("notebook_workflow", provider, payload, ch)
            counts["workflows"] += 1

    print(
        f"Bootstrapped LLM cache → summaries={counts['summaries']} "
        f"workflows={counts['workflows']} skipped={counts['skipped']} "
        f"dir={cache_dir or 'default'}"
    )
    return counts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build hierarchical notebook indexes (summaries / snippets / workflows)"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Notebook paths or directories (recursively scanned; _build artifacts skipped)",
    )
    parser.add_argument("--out", default=None, help="Optional collection name prefix")
    parser.add_argument(
        "--no-hoist-imports",
        action="store_true",
        help="(compat no-op) Kept for older scripts",
    )
    parser.add_argument(
        "--keep-invalid",
        action="store_true",
        help="Include snippets with unresolved names",
    )
    parser.add_argument(
        "--no-synth-imports",
        action="store_true",
        help="(compat no-op) Kept for older scripts",
    )
    parser.add_argument(
        "--force-recreate",
        action="store_true",
        help="Force recreate collections if they exist",
    )
    parser.add_argument(
        "--llm",
        choices=["openai", "grok"],
        default=None,
        help="Use an LLM for notebook/project summaries and workflows",
    )
    parser.add_argument(
        "--llm-cache-dir",
        type=pathlib.Path,
        default=None,
        help="Directory for LLM response cache (default: notebook_library/.llm_cache)",
    )
    parser.add_argument(
        "--no-llm-cache",
        action="store_true",
        help="Disable LLM disk cache (always call the API)",
    )
    parser.add_argument(
        "--bootstrap-llm-cache",
        action="store_true",
        help="Seed LLM cache from existing Qdrant LLM payloads, then exit",
    )
    args = parser.parse_args()

    set_llm_cache(enabled=not args.no_llm_cache, cache_dir=args.llm_cache_dir)

    if args.bootstrap_llm_cache:
        provider = args.llm or "openai"
        bootstrap_llm_cache_from_qdrant(provider, cache_dir=args.llm_cache_dir)
        raise SystemExit(0)

    if not args.paths:
        raise SystemExit("No notebook paths given (or use --bootstrap-llm-cache)")

    collected = [pathlib.Path(p) for p in args.paths]
    build_index(
        collected,
        args.out,
        hoist_imports=not args.no_hoist_imports,
        keep_invalid=args.keep_invalid,
        synth_imports=not args.no_synth_imports,
        force_recreate=args.force_recreate,
        llm=args.llm,
    )
