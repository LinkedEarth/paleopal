"""readthedocs_library.index_docs

Build a Chroma vector store from one or more Read-the-Docs HTML directories.

Usage:
    python -m readthedocs_library.index_docs my_docs/pyleoclim/docs my_docs/pylipd/docs --out rtd_index
"""
from __future__ import annotations

import pathlib
import argparse
import logging
from typing import List
import os

try:
    from langchain_community.document_loaders import ReadTheDocsLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_chroma import Chroma
except ImportError as e:  # pragma: no cover
    raise ImportError("langchain and langchain_community are required: pip install langchain langchain_community") from e

try:
    from sentence_transformers import SentenceTransformer
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    SentenceTransformer = None  # type: ignore
    HuggingFaceEmbeddings = None  # type: ignore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rtd-index")


def _get_default_embeddings():
    """Return an embedding object; local model."""
    if HuggingFaceEmbeddings is not None:
        logger.info("Using HuggingFaceEmbeddings (all-MiniLM-L6-v2) for doc index")
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        return HuggingFaceEmbeddings(model_name=model_name)  # type: ignore
    else:
        raise RuntimeError("No embeddings backend available; install sentence-transformers or set OPENAI key")


def build_index(doc_paths: List[pathlib.Path], out_dir: pathlib.Path, *, chunk_size: int = 800, chunk_overlap: int = 100):
    # Use separators that respect fenced code blocks so examples are not split mid-block
    code_aware_separators = [
        "\n```",   # split just before a fenced code block
        "```",      # fallback fence separator
        "\n\n",   # paragraph boundary
        "\n",      # line boundary
        " ",        # space
        ""          # fallback char-level
    ]
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=code_aware_separators,
    )
    docs = []
    for p in doc_paths:
        loader = ReadTheDocsLoader(str(p))
        docs.extend(loader.load_and_split(text_splitter=text_splitter))

    if not docs:
        raise RuntimeError("No docs found to index")

    embeddings = _get_default_embeddings()
    vectordb = Chroma.from_documents(docs, embeddings, persist_directory=str(out_dir))
    logger.info("Indexed %d document chunks → %s", len(docs), out_dir)
    return out_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index ReadTheDocs folders into Chroma")
    parser.add_argument("paths", nargs="+", help="One or more paths to ReadTheDocs HTML directories")
    parser.add_argument("--out", default="rtd_index", help="Output directory for Chroma index")
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--chunk-overlap", type=int, default=100)
    args = parser.parse_args()

    paths = [pathlib.Path(p) for p in args.paths]
    build_index(paths, pathlib.Path(args.out), chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap) 