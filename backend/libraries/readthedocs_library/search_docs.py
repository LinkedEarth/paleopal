"""readthedocs_library.search_docs

Query the Chroma index of ReadTheDocs embeddings and return top-k chunks.
"""
from __future__ import annotations

from typing import List, Dict, Any
import pathlib

from langchain_chroma import Chroma

try:
    from sentence_transformers import SentenceTransformer
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    SentenceTransformer = None  # type: ignore
    HuggingFaceEmbeddings = None  # type: ignore

DEFAULT_INDEX_DIR = pathlib.Path("rtd_index")


def _get_default_embeddings():
    if HuggingFaceEmbeddings is not None:
        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")  # type: ignore
    else:
        raise RuntimeError("No embedding backend available")


def search(query: str, *, top_k: int = 5, index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR) -> List[Dict[str, Any]]:
    vectordb = Chroma(persist_directory=str(index_dir), embedding_function=_get_default_embeddings())
    docs_and_scores = vectordb.similarity_search_with_score(query, k=top_k)
    results: List[Dict[str, Any]] = []
    for doc, score in docs_and_scores:
        meta = doc.metadata or {}
        meta.update({"content": doc.page_content, "score": score})
        results.append(meta)
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search ReadTheDocs Chroma index")
    parser.add_argument("query")
    parser.add_argument("--index", default="rtd_index")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--preview", type=int, default=200, help="Number of characters to preview (0 for full)")
    args = parser.parse_args()

    hits = search(args.query, top_k=args.k, index_dir=args.index)
    preview_len = args.preview
    for h in hits:
        print(f"Score {h['score']:.3f} | {h.get('source', '')}")
        content = h['content']#.replace("\n", " ")
        if preview_len > 0:
            content = content[:preview_len]
        print(content)
        print("-"*80) 