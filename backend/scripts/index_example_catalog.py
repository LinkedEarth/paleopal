#!/usr/bin/env python3
"""
index_example_catalog.py — put the example catalog (one record per code cell) into Qdrant.

Run inside the redesign backend container, where Qdrant and the embedding model are reachable:

    python scripts/index_example_catalog.py /tmp/catalog.jsonl --collection clean_examples

Each cell's facts are stored as payload, so a search can filter on them exactly
(`call_names` contains "Series.detrend"; `steps` contains "spectral_analysis:detrend"; `kind` is
"tutorial"), and similarity on heading + markdown + code only ranks what the filter kept.
No model is called; the embeddings are the local sentence model's.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "libraries"))

_TEXT_CHARS = 2000


def documents(path: Path) -> list[dict]:
    docs = []
    for line in path.read_text().splitlines():
        record = json.loads(line)
        if not record["calls"]:
            continue  # a cell calling none of the packages teaches nothing about them
        text = "\n\n".join(p for p in (record.get("heading"), record.get("markdown"), record["code"]) if p)
        docs.append({**record,
                     "id": str(uuid.uuid5(uuid.NAMESPACE_URL, record["id"])),
                     "example_id": record["id"],
                     "call_names": sorted({c["call"] for c in record["calls"]}),
                     "text": text[-_TEXT_CHARS:]})
    return docs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--collection", default="clean_examples")
    args = parser.parse_args()
    from qdrant_config import get_qdrant_manager
    manager = get_qdrant_manager()
    docs = documents(args.catalog)
    manager.create_collection(args.collection, force_recreate=True)
    count = manager.index_documents(args.collection, docs)
    print(f"Indexed {count} of {len(docs)} cells into {args.collection}")


if __name__ == "__main__":
    main()
