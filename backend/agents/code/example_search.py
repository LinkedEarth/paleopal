"""
example_search.py — find code examples in the example catalog (one record per notebook cell).

The lookup is exact: only cells that call the method (`Series.detrend`) are kept, read from the
facts the catalog recorded by Python. Similarity to the researcher's request only ranks them, so a
request naming a value ("with Savitzky-Golay") brings the examples using it first.

Built by scripts/build_example_catalog.py and scripts/index_example_catalog.py.
"""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

COLLECTION = os.getenv("EXAMPLES_COLLECTION", "clean_examples")


def _as_example(hit: dict) -> dict:
    """In the shape the writer and the Sources section read."""
    return {"code": hit.get("code", ""), "markdown_context": hit.get("markdown") or "",
            "notebook": hit.get("notebook"), "url": hit.get("url"), "kind": hit.get("kind"),
            "heading": hit.get("heading"), "example_id": hit.get("example_id"),
            "section_url": hit.get("section_url"),
            "similarity_score": hit.get("score", 0.0)}


def _search(call: str, request: str, top_k: int) -> list[dict]:
    from libraries.qdrant_config import get_qdrant_manager
    manager = get_qdrant_manager()
    if COLLECTION not in manager.list_collections():
        logger.warning("Example collection %s doesn't exist", COLLECTION)
        return []
    hits = manager.search(COLLECTION, request or call, limit=top_k, filters={"call_names": call})
    return [_as_example(h) for h in hits]


async def search(call: str, top_k: int = 5, request: str = "") -> list[dict]:
    """Examples calling `call` (e.g. "Series.detrend"), ranked by similarity to `request`."""
    return await asyncio.to_thread(_search, call, request, top_k)
