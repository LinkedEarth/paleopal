"""notebook_library.search_snippets

API to query the FAISS snippet index built by `index_notebooks.py`.
"""
from __future__ import annotations

import json
import pathlib
from typing import List, Dict, Any

import numpy as np

try:
    import faiss  # type: ignore
except ImportError as e:
    raise ImportError("faiss-cpu is required: pip install faiss-cpu") from e

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except ImportError as e:
    raise ImportError("sentence-transformers is required: pip install sentence-transformers") from e

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"


def _load_model() -> SentenceTransformer:  # type: ignore
    if not hasattr(_load_model, "_model"):
        _load_model._model = SentenceTransformer(EMBED_MODEL_NAME)  # type: ignore
    return _load_model._model  # type: ignore


def load_index(index_dir: str | pathlib.Path):
    index_dir = pathlib.Path(index_dir)
    index_path = index_dir / "snippets.faiss"
    meta_path = index_dir / "snippets_meta.jsonl"

    if not index_path.exists() or not meta_path.exists():
        raise FileNotFoundError("Index files not found in provided directory")

    index = faiss.read_index(str(index_path))

    metadata: List[Dict[str, Any]] = []
    with meta_path.open() as f:
        for line in f:
            metadata.append(json.loads(line))

    return index, metadata


def search(query: str, index_dir: str | pathlib.Path, top_k: int = 5) -> List[Dict[str, Any]]:
    """Return top_k snippet dicts ranked by similarity."""
    model = _load_model()
    index, metadata = load_index(index_dir)

    q_emb = model.encode([query], normalize_embeddings=True)
    scores, ids = index.search(q_emb.astype(np.float32), top_k)

    results: List[Dict[str, Any]] = []
    for score, idx in zip(scores[0], ids[0]):
        if idx == -1:
            continue
        meta = metadata[idx].copy()
        meta["score"] = float(score)
        results.append(meta)
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search code snippet library")
    parser.add_argument("query", help="Natural language or code query")
    parser.add_argument("--index", default="notebook_index", help="Directory with FAISS + metadata files")
    parser.add_argument("--k", type=int, default=5, help="Number of results to return")
    args = parser.parse_args()

    hits = search(args.query, args.index, args.k)
    for h in hits:
        ref = (
            f"{h['notebook']}#cells{h.get('cell_indices') or h.get('cell_index')}"
        )
        print(f"Score {h['score']:.3f} | {ref}")
        print(h['code'])
        if 'imports' in h:
            print(f"Imports: {', '.join(h['imports'])}")
        if 'unresolved' in h and h['unresolved']:
            print(f"Warning: unresolved names → {', '.join(h['unresolved'])}")
        print("-"*80) 
 