"""notebook_library.retrieve

Utility helpers that the CodeGenerationAgent (or other callers) can import to
fetch and format top-k code snippets from the FAISS index.
"""
from __future__ import annotations

import pathlib
from typing import List, Dict, Any

from search_snippets import search
from search_workflows import search_workflows

DEFAULT_INDEX_DIR = pathlib.Path("notebook_index")


def get_relevant_snippets(query: str, *, top_k: int = 5, index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR) -> List[Dict[str, Any]]:
    """Return raw snippet metadata dicts sorted by similarity."""
    return search(query, index_dir=index_dir, top_k=top_k)


def snippets_to_markdown(snippets: List[Dict[str, Any]]) -> str:
    """Turn a list of snippet dicts into markdown suitable for an LLM prompt."""
    md_parts: List[str] = []
    for i, s in enumerate(snippets, 1):
        heading = s.get("markdown_context", "Snippet")
        md_parts.append(f"### Retrieved Snippet {i}\n{heading}\n")
        md_parts.append("```python\n" + s["code"].strip() + "\n```\n")
    return "\n".join(md_parts)


def get_snippets_markdown_for_prompt(query: str, *, top_k: int = 5, index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR) -> str:
    """One-liner: retrieve and format snippets for prompt injection."""
    snippets = get_relevant_snippets(query, top_k=top_k, index_dir=index_dir)
    return snippets_to_markdown(snippets)


def get_workflow_markdown(query: str, *, k: int = 3) -> str:
    hits = search_workflows(query, top_k=k)
    md_parts: List[str] = []
    for i, h in enumerate(hits, 1):
        md_parts.append(f"### Workflow {i}: {pathlib.Path(h['notebook']).name}\n")
        for j, step in enumerate(h["steps"], 1):
            title_line = step["markdown_context"].split("\n")[0]
            md_parts.append(f"**Step {j}:** {title_line}\n")
        md_parts.append("\n")
    return "\n".join(md_parts)


def get_combined_markdown(query: str, *, k_snip: int = 5, k_wf: int = 3) -> str:
    """Return markdown with both top snippets and workflows for a query."""
    snip_md = get_snippets_markdown_for_prompt(query, top_k=k_snip)
    wf_md = get_workflow_markdown(query, k=k_wf)
    return snip_md + "\n---\n" + wf_md 