from __future__ import annotations

"""readthedocs_library.search_symbols

Query the Chroma symbol index built by `index_symbols.py` and return the top-k hits.
"""

from typing import List, Dict, Any, Tuple
import pathlib
import json

from langchain_chroma import Chroma

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    HuggingFaceEmbeddings = None  # type: ignore

# Optional lexical ranking
try:
    from rank_bm25 import BM25Okapi  # type: ignore
except ImportError:
    BM25Okapi = None  # type: ignore

DEFAULT_INDEX_DIR = pathlib.Path("rtd_symbol_index")


def _get_default_embeddings():
    if HuggingFaceEmbeddings is not None:
        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")  # type: ignore
    raise RuntimeError("No embedding backend available")


def search_symbols(query: str, *, top_k: int = 5, index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR) -> List[Dict[str, Any]]:
    vectordb = Chroma(persist_directory=str(index_dir), embedding_function=_get_default_embeddings())
    docs_and_scores = vectordb.similarity_search_with_score(query, k=top_k)

    results: List[Dict[str, Any]] = []
    for doc, score in docs_and_scores:
        meta = doc.metadata or {}
        narrative = meta.get("narrative", doc.page_content)
        meta.update({"content": narrative, "score": score})
        results.append(meta)
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search ReadTheDocs symbol index")
    parser.add_argument("query")
    parser.add_argument("--index", default="rtd_symbol_index")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--show-code", action="store_true", help="Include example code in output")
    args = parser.parse_args()

    hits = search_symbols(args.query, top_k=args.k, index_dir=args.index)
    for h in hits:
        print(f"Score {h['score']:.3f} | {h.get('symbol', '')}")
        print(h["content"][:400].replace("\n", " "))
        if args.show_code and h.get("code"):
            print("```python\n" + h["code"][:400] + "\n```")
        print("-" * 80)


# -----------------------------------------------------------------------------
# Hybrid dense + lexical search ------------------------------------------------
# -----------------------------------------------------------------------------

_BM25_CACHE: Dict[str, Tuple[BM25Okapi, List[Dict[str, Any]]]] = {}


def _get_bm25(index_dir: pathlib.Path):
    if BM25Okapi is None:
        raise RuntimeError("rank_bm25 is not installed: pip install rank_bm25")

    key = str(index_dir.resolve())
    if key in _BM25_CACHE:
        return _BM25_CACHE[key]

    # load metadata to build corpus
    _, metas = _load_dense_index(index_dir)

    corpus_tokens = []
    for m in metas:
        text = f"{m.get('symbol','')} {m.get('signature','')} {m.get('narrative','')}"
        tokens = text.lower().split()
        corpus_tokens.append(tokens)

    bm25 = BM25Okapi(corpus_tokens)
    _BM25_CACHE[key] = (bm25, metas)
    return bm25, metas


def _load_dense_index(index_dir: pathlib.Path):
    """Helper to load Chroma collection and metadata for bm25 builder."""
    vectordb = Chroma(persist_directory=str(index_dir), embedding_function=_get_default_embeddings())
    # Chroma can expose metadatas via _collection; but easier: reload meta jsonl saved by indexer.
    meta_path = index_dir / "symbols_meta.jsonl"
    metas: List[Dict[str, Any]] = []
    if meta_path.exists():
        with meta_path.open() as f:
            for line in f:
                metas.append(json.loads(line))
    return vectordb, metas


def search_symbols_hybrid(
    query: str,
    *,
    top_k_dense: int = 5,
    top_k_lex: int = 5,
    index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR,
) -> List[Dict[str, Any]]:
    """Return merged dense + BM25 results (deduplicated)."""
    index_dir = pathlib.Path(index_dir)

    dense_hits = search_symbols(query, top_k=top_k_dense, index_dir=index_dir)

    if top_k_lex and BM25Okapi is not None:
        bm25, metas = _get_bm25(index_dir)
        query_tokens = query.lower().split()
        scores = bm25.get_scores(query_tokens)
        top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k_lex]
        lex_hits: List[Dict[str, Any]] = []
        for i in top_idx:
            if scores[i] <= 0:
                continue
            m = metas[i].copy()
            m["score_lex"] = float(scores[i])
            lex_hits.append(m)
    else:
        lex_hits = []

    # merge by symbol id + signature
    out: List[Dict[str, Any]] = []
    seen_keys = set()

    def _key(h):
        return h.get("symbol") or h.get("signature")

    for h in dense_hits + lex_hits:
        k = _key(h)
        if k and k in seen_keys:
            continue
        seen_keys.add(k)
        out.append(h)

    # keep highest scoring dense first, then lex appended
    return out[: max(top_k_dense, top_k_lex)] 