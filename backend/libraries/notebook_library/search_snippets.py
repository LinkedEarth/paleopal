"""notebook_library.search_snippets

API to query the Qdrant snippet / summary indexes built by `index_notebooks.py`.

Supports parent-child retrieval:
  - search summaries (parents) → expand to child snippets
  - search snippets (children) → include parent summary from payload
"""
from __future__ import annotations

import pathlib
import sys
from typing import List, Dict, Any, Optional

# Add parent directory to path for imports
current_dir = pathlib.Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from qdrant_config import get_qdrant_manager, COLLECTION_NAMES


def search_summaries(
    query: str,
    limit: int = 5,
    collection_name: Optional[str] = None,
    content_type: Optional[str] = None,
    project_id: Optional[str] = None,
    score_threshold: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Search notebook/project parent summaries."""
    if collection_name is None:
        collection_name = COLLECTION_NAMES["notebook_summaries"]

    filters: Dict[str, Any] = {}
    if content_type:
        filters["content_type"] = content_type
    if project_id:
        filters["project_id"] = project_id

    qdrant_manager = get_qdrant_manager()
    try:
        if collection_name not in qdrant_manager.list_collections():
            return []
        results = qdrant_manager.search(
            collection_name=collection_name,
            query=query,
            limit=limit,
            filters=filters or None,
            score_threshold=score_threshold,
        )
        for r in results:
            r["similarity_score"] = r.get("score", 0.0)
        return results
    except Exception as e:
        print(f"Summary search failed: {e}")
        return []


def get_snippets_for_parent(
    notebook_id: str,
    limit: int = 20,
    collection_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch child snippets belonging to a parent notebook_id."""
    if collection_name is None:
        collection_name = COLLECTION_NAMES["notebook_snippets"]
    qdrant_manager = get_qdrant_manager()
    try:
        if collection_name not in qdrant_manager.list_collections():
            return []
        return qdrant_manager.scroll_by_filter(
            collection_name=collection_name,
            filters={"notebook_id": notebook_id},
            limit=limit,
        )
    except Exception as e:
        print(f"Parent expand failed: {e}")
        return []


def search_snippets(
    query: str,
    limit: int = 5,
    collection_name: Optional[str] = None,
    notebook_filter: Optional[str] = None,
    complexity_filter: Optional[str] = None,
    has_imports_filter: Optional[bool] = None,
    score_threshold: Optional[float] = None,
    expand_parent: bool = True,
) -> List[Dict[str, Any]]:
    """
    Search for code snippets (children).

    When expand_parent=True, each hit includes parent_summary / parent_title
    from the indexed payload (written at index time).
    """
    if collection_name is None:
        collection_name = COLLECTION_NAMES["notebook_snippets"]

    filters: Dict[str, Any] = {}
    if notebook_filter:
        filters["notebook_path"] = notebook_filter
    if complexity_filter:
        filters["complexity"] = complexity_filter
    if has_imports_filter is not None:
        filters["has_imports"] = has_imports_filter

    qdrant_manager = get_qdrant_manager()

    try:
        if collection_name not in qdrant_manager.list_collections():
            return []

        results = qdrant_manager.search(
            collection_name=collection_name,
            query=query,
            limit=limit,
            filters=filters if filters else None,
            score_threshold=score_threshold,
        )

        formatted_results = []
        for result in results:
            formatted_result = {
                "id": result["id"],
                "title": result.get("title") or result.get("heading", ""),
                "heading": result.get("heading", ""),
                "code": result.get("code", ""),
                "markdown": result.get("markdown") or result.get("markdown_context", ""),
                "markdown_context": result.get("markdown_context", ""),
                "comments": result.get("comments", []),
                "notebook": result.get("notebook_path", ""),
                "notebook_path": result.get("notebook_path", ""),
                "relative_path": result.get("relative_path", ""),
                "cell_indices": result.get("cell_indices", []),
                "cell_index": result.get("cell_index"),
                "imports": result.get("imports", []),
                "defined": result.get("defined", []),
                "used": result.get("used", []),
                "unresolved": result.get("unresolved", []),
                "dependencies": result.get("dependencies", []),
                "notebook_id": result.get("notebook_id"),
                "parent_id": result.get("parent_id") or result.get("notebook_id"),
                "project_id": result.get("project_id"),
                "phase": result.get("phase"),
                "score": result["score"],
                "similarity_score": result["score"],
            }
            if expand_parent:
                formatted_result["parent_title"] = result.get("parent_title", "")
                formatted_result["parent_summary"] = result.get("parent_summary", "")
            formatted_results.append(formatted_result)

        return formatted_results

    except Exception as e:
        print(f"Search failed: {e}")
        return []


def search_with_parent_context(
    query: str,
    *,
    summary_limit: int = 3,
    snippets_per_parent: int = 3,
    direct_snippet_limit: int = 3,
) -> Dict[str, Any]:
    """
    Parent-child retrieval:
      1) Search summaries to select notebooks/projects
      2) Expand each selected parent to its best child snippets (re-ranked by query)
      3) Also search snippets directly for needle matches
    """
    qdrant_manager = get_qdrant_manager()
    parents = search_summaries(query, limit=summary_limit)

    expanded = []
    for parent in parents:
        notebook_id = parent.get("notebook_id") or parent.get("id")
        content_type = parent.get("content_type")
        children: List[Dict[str, Any]] = []

        if content_type == "project_summary":
            # Project parent: pull snippets by project_id
            project_id = parent.get("project_id")
            if project_id and COLLECTION_NAMES["notebook_snippets"] in qdrant_manager.list_collections():
                children = qdrant_manager.search(
                    collection_name=COLLECTION_NAMES["notebook_snippets"],
                    query=query,
                    limit=snippets_per_parent,
                    filters={"project_id": project_id},
                )
        elif notebook_id:
            # Rank children of this notebook by the same query
            if COLLECTION_NAMES["notebook_snippets"] in qdrant_manager.list_collections():
                children = qdrant_manager.search(
                    collection_name=COLLECTION_NAMES["notebook_snippets"],
                    query=query,
                    limit=snippets_per_parent,
                    filters={"notebook_id": notebook_id},
                )

        expanded.append(
            {
                "parent": parent,
                "children": children,
            }
        )

    direct = search_snippets(query, limit=direct_snippet_limit, expand_parent=True)
    return {
        "query": query,
        "parents": expanded,
        "direct_snippets": direct,
    }


def search_workflows(
    query: str,
    limit: int = 5,
    collection_name: Optional[str] = None,
    complexity_filter: Optional[str] = None,
    score_threshold: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Search for workflows (thin wrapper; prefer search_workflows module)."""
    if collection_name is None:
        collection_name = COLLECTION_NAMES["notebook_workflows"]

    filters: Dict[str, Any] = {}
    if complexity_filter:
        filters["complexity"] = complexity_filter

    qdrant_manager = get_qdrant_manager()

    try:
        results = qdrant_manager.search(
            collection_name=collection_name,
            query=query,
            limit=limit,
            filters=filters if filters else None,
            score_threshold=score_threshold,
        )
        return results
    except Exception as e:
        print(f"Workflow search failed: {e}")
        return []


def search_steps(
    query: str,
    limit: int = 5,
    collection_name: Optional[str] = None,
    step_type_filter: Optional[str] = None,
    score_threshold: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Deprecated: notebook_steps collection is no longer built. Searches snippets instead."""
    del collection_name
    results = search_snippets(query, limit=limit, score_threshold=score_threshold)
    if step_type_filter:
        return results  # step_type no longer stored separately
    return results


# Backward compatibility aliases
search = search_snippets
load_index = lambda index_dir: None  # Legacy function, no longer needed


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Search notebook indexes")
    parser.add_argument("query", help="Natural language or code query")
    parser.add_argument("--collection", default=None, help="Collection name")
    parser.add_argument("-k", "--k", type=int, default=5, help="Number of results")
    parser.add_argument(
        "--type",
        choices=["snippets", "workflows", "summaries", "parent-child"],
        default="snippets",
    )
    parser.add_argument("--notebook", help="Filter by notebook path")
    parser.add_argument("--complexity", choices=["simple", "medium", "complex"])
    args = parser.parse_args()

    if args.type == "snippets":
        hits = search_snippets(
            args.query,
            limit=args.k,
            collection_name=args.collection,
            notebook_filter=args.notebook,
            complexity_filter=args.complexity,
        )
        for h in hits:
            ref = f"{h['notebook']}#cells{h.get('cell_indices')}"
            print(f"Score {h['score']:.3f} | {ref}")
            if h.get("parent_summary"):
                print(f"Parent: {h.get('parent_title')} — {h['parent_summary'][:160]}")
            print(h["code"][:500])
            print("-" * 80)

    elif args.type == "summaries":
        hits = search_summaries(args.query, limit=args.k, collection_name=args.collection)
        for h in hits:
            print(f"Score {h['score']:.3f} | [{h.get('content_type')}] {h.get('title')}")
            print((h.get("summary") or "")[:300])
            print("-" * 80)

    elif args.type == "parent-child":
        result = search_with_parent_context(args.query, summary_limit=args.k)
        print(json.dumps(result, indent=2, default=str)[:8000])

    elif args.type == "workflows":
        hits = search_workflows(
            args.query,
            limit=args.k,
            collection_name=args.collection,
            complexity_filter=args.complexity,
        )
        for h in hits:
            print(f"Score {h.get('score', 0):.3f} | {h.get('title', 'Untitled')}")
            print(f"Description: {h.get('description', '')[:200]}")
            print("-" * 80)
