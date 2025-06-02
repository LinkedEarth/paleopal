from __future__ import annotations

"""readthedocs_library.index_code

Build a Chroma vector store that **only** indexes example *code* blocks extracted from
Read-the-Docs Sphinx HTML pages.  Each document corresponds to a single class/function
symbol; its `page_content` is the concatenated example code for that symbol and its
metadata mirrors the symbol index (symbol, signature, params, source, etc.).

Typical usage:
    python -m readthedocs_library.index_code path/to/docs --out rtd_code_index
"""

import pathlib
import argparse
import logging
from typing import List

from bs4 import BeautifulSoup  # noqa: F401 – required by symbol_loader at runtime

try:
    from langchain_chroma import Chroma
except ImportError as e:  # pragma: no cover
    raise ImportError("langchain_chroma is required: pip install langchain_chroma") from e

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    HuggingFaceEmbeddings = None  # type: ignore

# Prefer a code-specialised model.  If unavailable, users can pass --model.
DEFAULT_MODEL = "microsoft/codebert-base"

# Local import that works both as package and as script
try:
    from .symbol_loader import SymbolExtractor
except ImportError:  # pragma: no cover
    from symbol_loader import SymbolExtractor  # type: ignore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rtd-code-index")


# -----------------------------------------------------------------------------
# embeddings helper ------------------------------------------------------------
# -----------------------------------------------------------------------------

def _get_embeddings(model_name: str | None = None):
    if HuggingFaceEmbeddings is None:
        raise RuntimeError("HuggingFaceEmbeddings not available – install langchain_huggingface")
    model_name = model_name or DEFAULT_MODEL
    logger.info("Using code embedding model: %s", model_name)
    return HuggingFaceEmbeddings(model_name=model_name)  # type: ignore


# -----------------------------------------------------------------------------
# index builder ----------------------------------------------------------------
# -----------------------------------------------------------------------------

def _html_files_in(paths: List[pathlib.Path]):
    for root in paths:
        if root.is_dir():
            yield from root.rglob("*.html")
        elif root.suffix == ".html":
            yield root


def build_code_index(html_paths: List[pathlib.Path], out_dir: pathlib.Path, *, model_name: str | None = None):
    documents = []
    for html_path in _html_files_in(html_paths):
        try:
            html_text = html_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            logger.warning("Cannot read %s: %s", html_path, exc)
            continue

        extractor = SymbolExtractor(html_text, html_path)
        for doc in extractor.extract():
            code = doc.metadata.get("code", "") if isinstance(doc.metadata, dict) else ""
            if not code:
                continue  # skip symbols without example code
            # Build a new Document with code as page_content
            from langchain.docstore.document import Document  # local import to keep dependency optional

            # Ensure metadata values are primitives
            meta = {
                k: (str(v) if not isinstance(v, (str, int, float, bool)) else v)
                for k, v in doc.metadata.items()
            }
            documents.append(Document(page_content=code, metadata=meta))

    if not documents:
        raise RuntimeError("No code documents extracted – check input paths")

    embeddings = _get_embeddings(model_name)
    vectordb = Chroma.from_documents(documents, embeddings, persist_directory=str(out_dir))
    logger.info("Indexed %d code snippets → %s", len(documents), out_dir)
    return out_dir


# -----------------------------------------------------------------------------
# CLI -------------------------------------------------------------------------
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index ReadTheDocs example code into Chroma")
    parser.add_argument("paths", nargs="+", help="One or more paths to ReadTheDocs HTML directories or files")
    parser.add_argument("--out", default="rtd_code_index", help="Output directory for Chroma index")
    parser.add_argument("--model", default=None, help="Hugging Face model name for code embeddings (default: microsoft/codebert-base)")
    args = parser.parse_args()

    paths = [pathlib.Path(p) for p in args.paths]
    build_code_index(paths, pathlib.Path(args.out), model_name=args.model) 