"""readthedocs_library.retrieve

Helper to fetch top-k documentation chunks as markdown for LLM prompts.
"""
from __future__ import annotations

from typing import List

from search_docs import search
from search_symbols import search_symbols
from search_code import search_code


def get_docs_markdown(query: str, *, k: int = 5) -> str:
    hits = search(query, top_k=k)
    md_parts: List[str] = []
    for i, h in enumerate(hits, 1):
        title = h.get("source", "doc")
        md_parts.append(f"### Doc Snippet {i} — {title}\n")
        md_parts.append(h["content"].strip() + "\n")
    return "\n".join(md_parts)


def get_symbol_markdown(query: str, *, k: int = 5, include_code: bool = True) -> str:
    hits = search_symbols(query, top_k=k)
    md_parts: List[str] = []
    for i, h in enumerate(hits, 1):
        md_parts.append(f"### Symbol {i}: {h.get('symbol', 'unknown')}\n")
        md_parts.append(f"**Signature:** `{h.get('signature', '')}`\n")
        if h.get("params"):
            params_val = h["params"]
            if isinstance(params_val, (list, tuple)):
                params_str = ", ".join(params_val)
            else:
                params_str = str(params_val)
            md_parts.append("**Parameters:** " + params_str + "\n")
        md_parts.append(h["content"].strip() + "\n")
        if include_code and h.get("code"):
            md_parts.append("```python\n" + h["code"].strip() + "\n```\n")
    return "\n".join(md_parts)


def get_code_markdown(query: str, *, k: int = 5) -> str:
    hits = search_code(query, top_k=k)
    md_parts: List[str] = []
    for i, h in enumerate(hits, 1):
        md_parts.append(f"### Code Snippet {i}: {h.get('symbol', '')}\n")
        md_parts.append("```python\n" + h["code"].strip() + "\n```\n")
    return "\n".join(md_parts) 
