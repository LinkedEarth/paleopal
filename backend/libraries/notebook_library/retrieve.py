"""notebook_library.retrieve

High-level API for retrieving code snippets, workflows, summaries, and
parent-child notebook context from the Qdrant indexes.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
import pathlib
import sys

# Add current directory to path for imports
current_dir = pathlib.Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from search_snippets import (
    search_snippets,
    search_workflows,
    search_steps,
    search_summaries,
    search_with_parent_context,
)


def retrieve_code_snippets(
    query: str,
    top_k: int = 5,
    notebook_filter: Optional[str] = None,
    complexity_filter: Optional[str] = None,
    has_imports_filter: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Retrieve relevant code snippets (children) for a query."""
    return search_snippets(
        query=query,
        limit=top_k,
        notebook_filter=notebook_filter,
        complexity_filter=complexity_filter,
        has_imports_filter=has_imports_filter,
        expand_parent=True,
    )


def retrieve_notebook_summaries(
    query: str,
    top_k: int = 5,
    content_type: Optional[str] = None,
    project_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve notebook/project parent summaries."""
    return search_summaries(
        query=query,
        limit=top_k,
        content_type=content_type,
        project_id=project_id,
    )


def retrieve_with_parent_context(
    query: str,
    *,
    summary_limit: int = 3,
    snippets_per_parent: int = 3,
    direct_snippet_limit: int = 3,
) -> Dict[str, Any]:
    """
    Parent-child retrieval: search summaries to select notebooks/projects,
    then expand to child snippets; also return direct snippet hits.
    """
    return search_with_parent_context(
        query,
        summary_limit=summary_limit,
        snippets_per_parent=snippets_per_parent,
        direct_snippet_limit=direct_snippet_limit,
    )


def retrieve_workflows(
    query: str,
    top_k: int = 5,
    complexity_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve relevant workflows for a query."""
    return search_workflows(
        query=query,
        limit=top_k,
        complexity_filter=complexity_filter,
    )


def retrieve_computational_steps(
    query: str,
    top_k: int = 5,
    step_type_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve relevant computational steps (snippet-backed; legacy name)."""
    return search_steps(
        query=query,
        limit=top_k,
        step_type_filter=step_type_filter,
    )


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="High-level notebook retrieval")
    parser.add_argument("query")
    parser.add_argument("-k", "--k", type=int, default=5)
    parser.add_argument(
        "--type",
        choices=["snippets", "workflows", "summaries", "parent-child", "steps"],
        default="parent-child",
    )
    args = parser.parse_args()

    if args.type == "snippets":
        print(json.dumps(retrieve_code_snippets(args.query, top_k=args.k), indent=2, default=str)[:6000])
    elif args.type == "workflows":
        print(json.dumps(retrieve_workflows(args.query, top_k=args.k), indent=2, default=str)[:6000])
    elif args.type == "summaries":
        print(json.dumps(retrieve_notebook_summaries(args.query, top_k=args.k), indent=2, default=str)[:6000])
    elif args.type == "steps":
        print(json.dumps(retrieve_computational_steps(args.query, top_k=args.k), indent=2, default=str)[:6000])
    else:
        print(json.dumps(retrieve_with_parent_context(args.query, summary_limit=args.k), indent=2, default=str)[:8000])
