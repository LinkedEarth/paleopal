from __future__ import annotations

"""readthedocs_library.index_code

Build a Qdrant vector store that **only** indexes example *code* blocks extracted from
Read-the-Docs Sphinx HTML pages.  Each document corresponds to a single class/function
symbol; its `page_content` is the concatenated example code for that symbol and its
metadata mirrors the symbol index (symbol, signature, params, source, etc.).

Typical usage:
    python -m readthedocs_library.index_code path/to/docs --collection rtd_code
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

# Prefer a code-specialised model if available
DEFAULT_MODEL = "microsoft/codebert-base"

# Local import that works both as package and as script
try:
    from .rtd_loader import RTDExtractor
except ImportError:  # pragma: no cover
    from rtd_loader import RTDExtractor  # type: ignore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rtd-code-index")


def _html_files_in(paths: List[pathlib.Path]):
    for root in paths:
        if root.is_dir():
            yield from root.rglob("*.html")
        elif root.suffix == ".html":
            yield root


def build_code_index(
    html_paths: List[pathlib.Path], 
    collection_name: str = None,
    *,
    force_recreate: bool = False
) -> str:
    """
    Build Qdrant index from ReadTheDocs code examples.
    
    Args:
        html_paths: List of paths to ReadTheDocs HTML directories or files
        collection_name: Qdrant collection name (defaults to readthedocs_code)
        force_recreate: Whether to recreate the collection if it exists
        
    Returns:
        Name of the created collection
    """
    if collection_name is None:
        collection_name = COLLECTION_NAMES["readthedocs_code"]
    
    documents = []
    for html_path in _html_files_in(html_paths):
        try:
            html_text = html_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            logger.warning("Cannot read %s: %s", html_path, exc)
            continue

        extractor = RTDExtractor(html_text, html_path)
        result = extractor.extract()
        
        # Process all symbols (classes, functions, constants) that have example code
        for symbol in result.classes + result.functions + result.constants:
            if not symbol.example_code:
                continue  # skip symbols without example code
            
            # Create Qdrant document using description and example code for indexing
            index_text = f"{symbol.description}\n\n{symbol.example_code}"
            
            qdrant_doc = {
                "id": str(uuid.uuid4()),
                "text": index_text,  # Use description + code as the main searchable text
                "code": symbol.example_code,  # Store code separately
                "content": index_text,  # Alias for compatibility
                "symbol": symbol.name,
                "kind": symbol.kind,
                "signature": symbol.signature,
                "description": symbol.description,
                "narrative": symbol.full_narrative,
                "source": str(html_path),
            }
            
            # Add code classification
            code_lower = symbol.example_code.lower()
            if "class " in code_lower:
                qdrant_doc["code_type"] = "class_definition"
            elif "def " in code_lower:
                qdrant_doc["code_type"] = "function_definition"
            elif "import " in code_lower:
                qdrant_doc["code_type"] = "import_example"
            elif any(plot_term in code_lower for plot_term in ["plot", "figure", "show()", "savefig"]):
                qdrant_doc["code_type"] = "plotting_example"
            else:
                qdrant_doc["code_type"] = "general_example"
            
            # Extract library information from symbol or source
            symbol_name = symbol.name.lower()
            source = str(html_path).lower()
            
            for lib in ["numpy", "pandas", "matplotlib", "scipy", "sklearn", "pyleoclim", "pylipd"]:
                if lib in symbol_name or lib in source:
                    qdrant_doc["library"] = lib
                    break
            else:
                qdrant_doc["library"] = "unknown"
            
            documents.append(qdrant_doc)

    if not documents:
        raise RuntimeError("No code documents extracted – check input paths")

    logger.info(f"Extracted {len(documents)} code snippets")
    
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
    
    logger.info(f"Indexed {indexed_count} code snippets → {collection_name}")
    return collection_name


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index ReadTheDocs example code into Qdrant")
    parser.add_argument("paths", nargs="+", help="One or more paths to ReadTheDocs HTML directories or files")
    parser.add_argument("--collection", default=None, help="Qdrant collection name (default: readthedocs_code)")
    parser.add_argument("--force-recreate", action="store_true", help="Force recreate collection if it exists")
    args = parser.parse_args()

    paths = [pathlib.Path(p) for p in args.paths]
    try:
        collection_name = build_code_index(
            paths, 
            collection_name=args.collection,
            force_recreate=args.force_recreate
        )
        print(f"✅ ReadTheDocs code index built successfully in collection: {collection_name}")
    except Exception as e:
        print(f"❌ Failed to build index: {e}")
        sys.exit(1) 