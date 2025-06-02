from __future__ import annotations

"""readthedocs_library.index_symbols

Build a Chroma vector store where **each document corresponds to a single class or function**
extracted from Sphinx Read-the-Docs HTML pages.

The resulting index stores:
    page_content = description + narrative example text (no code)
    metadata     = {
        symbol, kind, signature, params, code, source
    }

Example usage:
    python -m readthedocs_library.index_symbols docs/pylipd/docs --out rtd_symbol_index
"""

import pathlib
import argparse
import logging
from typing import List
import json

from bs4 import BeautifulSoup  # noqa: F401 – required by symbol_loader at runtime

try:
    from langchain_chroma import Chroma
except ImportError as e:  # pragma: no cover
    raise ImportError("langchain_chroma is required: pip install langchain_chroma") from e

try:
    from sentence_transformers import SentenceTransformer  # noqa: F401 – optional
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    SentenceTransformer = None  # type: ignore
    HuggingFaceEmbeddings = None  # type: ignore

try:
    from .symbol_loader import SymbolExtractor  # type: ignore
except ImportError:
    from symbol_loader import SymbolExtractor  # type: ignore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rtd-symbol-index")


# -----------------------------------------------------------------------------
# embeddings helper ------------------------------------------------------------
# -----------------------------------------------------------------------------

def _get_default_embeddings():
    if HuggingFaceEmbeddings is not None:
        logger.info("Using HuggingFaceEmbeddings (all-MiniLM-L6-v2) for symbol index")
        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")  # type: ignore
    raise RuntimeError("No embeddings backend available – install sentence-transformers")


# -----------------------------------------------------------------------------
# index builder ----------------------------------------------------------------
# -----------------------------------------------------------------------------

def _html_files_in(paths: List[pathlib.Path]):
    for root in paths:
        if root.is_dir():
            yield from root.rglob("*.html")
        elif root.suffix == ".html":
            yield root


def build_symbol_index(html_paths: List[pathlib.Path], out_dir: pathlib.Path):
    documents = []
    for html_path in _html_files_in(html_paths):
        try:
            html_text = html_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:  # pragma: no cover – skip unreadable files
            logger.warning("Cannot read %s: %s", html_path, exc)
            continue

        extractor = SymbolExtractor(html_text, html_path)
        docs = extractor.extract()
        documents.extend(docs)

    if not documents:
        raise RuntimeError("No symbol documents extracted – check input paths")

    embeddings = _get_default_embeddings()
    # No chunking required – each symbol doc is already small.  But Chroma.from_documents
    # expects a list of `Document`s directly.
    vectordb = Chroma.from_documents(documents, embeddings, persist_directory=str(out_dir))
    # Persist metadata line-by-line so vector ID == line number
    meta_path = out_dir / "symbols_meta.jsonl"
    with meta_path.open("w") as f:
        for doc in documents:
            f.write(json.dumps(doc.metadata) + "\n")
    logger.info("Indexed %d symbols → %s", len(documents), out_dir)
    return out_dir


# -----------------------------------------------------------------------------
# CLI entrypoint ---------------------------------------------------------------
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index ReadTheDocs symbols into Chroma")
    parser.add_argument("paths", nargs="+", help="One or more paths to ReadTheDocs HTML directories or files")
    parser.add_argument("--out", default="rtd_symbol_index", help="Output directory for Chroma index")
    args = parser.parse_args()

    paths = [pathlib.Path(p) for p in args.paths]
    build_symbol_index(paths, pathlib.Path(args.out)) 