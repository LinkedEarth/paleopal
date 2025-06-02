from __future__ import annotations

"""literature_library.search_methods

CLI / API to query the FAISS index built by `index_methods.py`.
Returns Methods / Procedure sections ranked by semantic similarity.
"""

import json
import pathlib
from typing import List, Dict, Any

import numpy as np

try:
    import faiss  # type: ignore
except ImportError as e:  # pragma: no cover
    raise ImportError("faiss-cpu is required: pip install faiss-cpu") from e

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except ImportError as e:  # pragma: no cover
    raise ImportError("sentence-transformers is required: pip install sentence-transformers") from e

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"


def _load_model() -> SentenceTransformer:  # type: ignore
    if not hasattr(_load_model, "_m"):
        _load_model._m = SentenceTransformer(EMBED_MODEL_NAME)  # type: ignore
    return _load_model._m  # type: ignore


def load_index(index_dir: str | pathlib.Path):
    """Return (faiss_index, metadata_list)."""
    index_dir = pathlib.Path(index_dir)
    index_path = index_dir / "methods.faiss"
    meta_path = index_dir / "methods_meta.jsonl"

    if not index_path.exists() or not meta_path.exists():
        raise FileNotFoundError("Index files not found in provided directory")

    index = faiss.read_index(str(index_path))

    metadata: List[Dict[str, Any]] = []
    with meta_path.open() as f:
        for line in f:
            metadata.append(json.loads(line))

    return index, metadata


def search(query: str, index_dir: str | pathlib.Path, top_k: int = 5) -> List[Dict[str, Any]]:
    """Return top_k records with similarity scores."""
    model = _load_model()
    index, metadata = load_index(index_dir)

    q_emb = model.encode([query], normalize_embeddings=True)
    scores, ids = index.search(q_emb.astype(np.float32), top_k)

    results: List[Dict[str, Any]] = []
    for score, idx in zip(scores[0], ids[0]):
        if idx == -1:
            continue
        rec = metadata[idx].copy()
        rec["score"] = float(score)
        results.append(rec)
    return results


if __name__ == "__main__":
    import argparse, textwrap

    parser = argparse.ArgumentParser(description="Semantic search over indexed Methods/Procedures")
    parser.add_argument("query", help="Natural language query, e.g. 'grain size analysis protocol'")
    parser.add_argument("--index", default="literature_index", help="Directory containing methods.faiss & metadata")
    parser.add_argument("--k", type=int, default=5, help="Number of hits to show")
    parser.add_argument("--show-raw", action="store_true", help="Print raw section text as well")
    args = parser.parse_args()

    hits = search(args.query, args.index, args.k)
    if not hits:
        print("No results found")
        raise SystemExit

    for h in hits:
        title = h.get("title") or pathlib.Path(h["file"]).stem
        print(f"Score {h['score']:.3f} | {title} ({h.get('year','?')})")
        if h.get("doi"):
            print(f" DOI: {h['doi']}")
        if h.get("authors"):
            auth_str = ", ".join(h["authors"][:4]) + (" ..." if len(h["authors"]) > 4 else "")
            print(f" Authors: {auth_str}")
        print(" Section type:", h.get("section_type"))
        print(" Steps:")
        for i, step in enumerate(h.get("steps", [])[:10], 1):
            print(f"  {i}. {step}")
        if args.show_raw:
            print(textwrap.fill(h["raw"][:4000], width=100))
        print("-" * 80) 