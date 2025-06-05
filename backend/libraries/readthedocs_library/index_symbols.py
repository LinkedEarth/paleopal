from __future__ import annotations

"""readthedocs_library.index_symbols

Build a Qdrant vector store where **each document corresponds to a single class or function**
extracted from Sphinx Read-the-Docs HTML pages.

The resulting index stores:
    text = description + narrative example text (no code)
    metadata = {
        symbol, kind, signature, params, code, source, library, symbol_type
    }

Example usage:
    python -m readthedocs_library.index_symbols docs/pylipd/docs --collection readthedocs_symbols
"""

import pathlib
import argparse
import logging
import sys
import uuid
from typing import List, Dict, Any

# Add parent directory to path for imports
current_dir = pathlib.Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from qdrant_config import get_qdrant_manager, COLLECTION_NAMES

from bs4 import BeautifulSoup  # noqa: F401 – required by symbol_loader at runtime

# Local import that works both as package and as script
try:
    from .symbol_loader import SymbolExtractor
except ImportError:  # pragma: no cover
    from symbol_loader import SymbolExtractor  # type: ignore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rtd-symbol-index")


def _html_files_in(paths: List[pathlib.Path]):
    for root in paths:
        if root.is_dir():
            yield from root.rglob("*.html")
        elif root.suffix == ".html":
            yield root


def build_symbol_index(
    html_paths: List[pathlib.Path], 
    collection_name: str = None,
    *,
    force_recreate: bool = False
) -> str:
    """
    Build Qdrant index from ReadTheDocs symbol extraction.
    
    Args:
        html_paths: List of paths to ReadTheDocs HTML directories or files
        collection_name: Qdrant collection name (defaults to readthedocs_symbols)
        force_recreate: Whether to recreate the collection if it exists
        
    Returns:
        Name of the created collection
    """
    if collection_name is None:
        collection_name = COLLECTION_NAMES["readthedocs_symbols"]
    
    documents = []
    for html_path in _html_files_in(html_paths):
        try:
            html_text = html_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            logger.warning("Cannot read %s: %s", html_path, exc)
            continue

        extractor = SymbolExtractor(html_text, html_path)
        for doc in extractor.extract():
            # Create Qdrant document
            qdrant_doc = {
                "id": str(uuid.uuid4()),
                "text": doc.page_content,  # Use page_content as searchable text
                "content": doc.page_content,  # Alias for compatibility
                "narrative": doc.page_content  # Legacy alias
            }
            
            # Add metadata, ensuring all values are JSON-serializable
            if isinstance(doc.metadata, dict):
                for k, v in doc.metadata.items():
                    if not isinstance(v, (str, int, float, bool, list)):
                        qdrant_doc[k] = str(v)
                    else:
                        qdrant_doc[k] = v
            
            # Add symbol classification
            symbol = qdrant_doc.get("symbol", "")
            kind = qdrant_doc.get("kind", "")
            
            if "class" in kind.lower() or "Class" in symbol:
                qdrant_doc["symbol_type"] = "class"
            elif "function" in kind.lower() or "method" in kind.lower():
                qdrant_doc["symbol_type"] = "function"
            elif "attribute" in kind.lower() or "property" in kind.lower():
                qdrant_doc["symbol_type"] = "attribute"
            elif "module" in kind.lower():
                qdrant_doc["symbol_type"] = "module"
            else:
                qdrant_doc["symbol_type"] = "other"
            
            # Extract library information from symbol or source
            source = qdrant_doc.get("source", "")
            
            for lib in ["numpy", "pandas", "matplotlib", "scipy", "sklearn", "pyleoclim", "pylipd"]:
                if lib in symbol.lower() or lib in source.lower():
                    qdrant_doc["library"] = lib
                    break
            else:
                qdrant_doc["library"] = "unknown"
            
            documents.append(qdrant_doc)

    if not documents:
        raise RuntimeError("No symbol documents extracted – check input paths")

    logger.info(f"Extracted {len(documents)} symbols")
    
    # Get Qdrant manager
    qdrant_manager = get_qdrant_manager()
    
    # Create collection
    if not qdrant_manager.create_collection(collection_name, force_recreate=force_recreate):
        raise RuntimeError(f"Failed to create collection: {collection_name}")
    
    # Index documents
    indexed_count = qdrant_manager.index_documents(
        collection_name=collection_name,
        documents=documents,
        text_field="text"
    )
    
    logger.info(f"Indexed {indexed_count} symbols → {collection_name}")
    return collection_name


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index ReadTheDocs symbols into Qdrant")
    parser.add_argument("paths", nargs="+", help="One or more paths to ReadTheDocs HTML directories or files")
    parser.add_argument("--collection", default=None, help="Qdrant collection name (default: readthedocs_symbols)")
    parser.add_argument("--force-recreate", action="store_true", help="Force recreate collection if it exists")
    args = parser.parse_args()

    paths = [pathlib.Path(p) for p in args.paths]
    try:
        collection_name = build_symbol_index(
            paths, 
            collection_name=args.collection,
            force_recreate=args.force_recreate
        )
        print(f"✅ ReadTheDocs symbol index built successfully in collection: {collection_name}")
    except Exception as e:
        print(f"❌ Failed to build index: {e}")
        sys.exit(1) 