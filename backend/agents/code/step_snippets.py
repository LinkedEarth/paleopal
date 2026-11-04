"""
step_snippets.py — find examples of how to write one workflow step.

The workflow file decides which steps run. Snippets only show how to write them,
so the search is built from each step's API path, not the user's wording, and a
snippet is kept only if it actually calls one of that step's methods.
"""

from __future__ import annotations

import re
from typing import Awaitable, Callable

Search = Callable[..., Awaitable[list[dict]]]


def _apis(step: dict) -> list[str]:
    api = step.get("core_api") or []
    return api if isinstance(api, list) else [api]


def step_queries(step: dict) -> list[str]:
    """One query per method: `...series.Series.standardize` -> `Series.standardize`.

    Searching a step's methods together blurs the embedding and finds neither.
    """
    return [".".join(api.rsplit(".", 2)[-2:]) for api in _apis(step)]


def calls_step(code: str, step: dict) -> bool:
    methods = [api.rsplit(".", 1)[-1] for api in _apis(step)]
    return any(re.search(rf"\.{re.escape(m)}\(", code) for m in methods)


async def find_step_snippets(step: dict, searches: list[Search], top_k: int = 5) -> list[dict]:
    """Run each search for one step and keep the results that call the step's method."""
    results = []
    for query in step_queries(step):
        for search in searches:
            results.extend(await search(query, top_k=top_k))
    kept = [r for r in results if calls_step(r.get("code", ""), step)]
    return sorted(kept, key=lambda r: r.get("similarity_score", 0), reverse=True)
