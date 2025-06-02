from __future__ import annotations

"""readthedocs_library.search_code

Query the Chroma **code** index built by `index_code.py`.
"""

from typing import List, Dict, Any
import pathlib

from langchain_chroma import Chroma

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    HuggingFaceEmbeddings = None  # type: ignore

DEFAULT_INDEX_DIR = pathlib.Path("rtd_code_index")
DEFAULT_MODEL = "microsoft/codebert-base"


def _get_embeddings(model_name: str | None = None):
    if HuggingFaceEmbeddings is None:
        raise RuntimeError("HuggingFaceEmbeddings not available")
    model_name = model_name or DEFAULT_MODEL
    return HuggingFaceEmbeddings(model_name=model_name)  # type: ignore


def search_code(query: str, *, top_k: int = 5, index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR, model_name: str | None = None) -> List[Dict[str, Any]]:
    vectordb = Chroma(persist_directory=str(index_dir), embedding_function=_get_embeddings(model_name))
    docs_and_scores = vectordb.similarity_search_with_score(query, k=top_k)

    results: List[Dict[str, Any]] = []
    for doc, score in docs_and_scores:
        meta = doc.metadata or {}
        meta.update({"code": doc.page_content, "score": score})
        results.append(meta)
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search ReadTheDocs code index")
    parser.add_argument("query")
    parser.add_argument("--index", default="rtd_code_index")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--model", default=None, help="Code embedding model name (defaults to microsoft/codebert-base)")
    args = parser.parse_args()

    hits = search_code(args.query, top_k=args.k, index_dir=args.index, model_name=args.model)
    for h in hits:
        print(f"Score {h['score']:.3f} | {h.get('symbol', '')}")
        print("```python\n" + h["code"][:400] + "\n```")
        print("-" * 80) 