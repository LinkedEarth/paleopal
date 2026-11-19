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


PER_NOTEBOOK = 2


def spread_over_notebooks(results: list[dict], per_notebook: int = PER_NOTEBOOK) -> list[dict]:
    """Best example of each notebook first, then each one's second best, and so on.

    One tutorial often holds several cells calling the same method, so ranking by similarity
    alone can show the writer two cells from one notebook. Spreading them shows two ways of
    writing the step when two exist, and keeps at most `per_notebook` from any one notebook.
    """
    rank: dict[str, int] = {}
    placed = []
    for order, r in enumerate(results):
        notebook = r.get("notebook") or f"unnamed-{order}"
        rank[notebook] = rank.get(notebook, -1) + 1
        if rank[notebook] < per_notebook:
            placed.append((rank[notebook], order, r))
    return [r for _, _, r in sorted(placed, key=lambda t: (t[0], t[1]))]


async def find_step_snippets(step: dict, searches: list[Search], top_k: int = 10) -> list[dict]:
    """Run each search for one step and keep the results that call the step's method."""
    results = []
    for query in step_queries(step):
        for search in searches:
            results.extend(await search(query, top_k=top_k))
    kept = [r for r in results if calls_step(r.get("code", ""), step)]
    # The same cell can match two of a step's methods; keep it once.
    unique = {(r.get("example_id") or r.get("code")): r for r in kept}
    ranked = sorted(unique.values(), key=lambda r: r.get("similarity_score", 0), reverse=True)
    return spread_over_notebooks(ranked)
