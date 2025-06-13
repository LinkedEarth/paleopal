"""readthedocs_library.index_docs

Build a Qdrant vector store from one or more Read-the-Docs HTML directories.
Uses RTDExtractor to extract structured documentation and indexes the full narrative.

Usage:
    python -m readthedocs_library.index_docs my_docs/pyleoclim/docs my_docs/pylipd/docs --collection rtd_docs
"""
from __future__ import annotations

import pathlib
import argparse
import logging
import sys
import uuid
from typing import List, Dict, Any
import os

# Add parent directory to path for imports
current_dir = pathlib.Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from qdrant_config import get_qdrant_manager, COLLECTION_NAMES

# Local import that works both as package and as script
try:
    from .rtd_loader import RTDExtractor
except ImportError:  # pragma: no cover
    from rtd_loader import RTDExtractor  # type: ignore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rtd-docs-index")


def _html_files_in(paths: List[pathlib.Path]):
    for root in paths:
        if root.is_dir():
            yield from root.rglob("*.html")
        elif root.suffix == ".html":
            yield root


def build_index(
    doc_paths: List[pathlib.Path], 
    collection_name: str = None,
    *,
    chunk_size: int = 800, 
    chunk_overlap: int = 100,
    force_recreate: bool = False
) -> str:
    """
    Build Qdrant index from ReadTheDocs HTML directories using RTDExtractor.
    
    Args:
        doc_paths: List of paths to ReadTheDocs HTML directories
        collection_name: Qdrant collection name (defaults to readthedocs_docs)
        chunk_size: Size of text chunks (used for splitting long narratives)
        chunk_overlap: Overlap between chunks
        force_recreate: Whether to recreate the collection if it exists
        
    Returns:
        Name of the created collection
    """
    if collection_name is None:
        collection_name = COLLECTION_NAMES["readthedocs_docs"]
    
    documents = []
    for html_path in _html_files_in(doc_paths):
        try:
            html_text = html_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            logger.warning("Cannot read %s: %s", html_path, exc)
            continue

        extractor = RTDExtractor(html_text, html_path)
        result = extractor.extract()
        
        # Process all symbols (classes, functions, constants) using full narrative
        for symbol in result.classes + result.functions + result.constants:
            if not symbol.full_narrative.strip():
                continue  # skip symbols without narrative content
            
            # Split long narratives into chunks if needed
            narrative_chunks = _split_text_into_chunks(
                symbol.full_narrative, 
                chunk_size, 
                chunk_overlap
            )
            
            for i, chunk in enumerate(narrative_chunks):
                qdrant_doc = {
                    "id": str(uuid.uuid4()),
                    "text": chunk,  # Use full narrative chunk as searchable text
                    "content": chunk,  # Alias for compatibility
                    "symbol": symbol.name,
                    "kind": symbol.kind,
                    "signature": symbol.signature,
                    "description": symbol.description,
                    "code": symbol.example_code,
                    "source": str(html_path),
                    "chunk_index": i,
                    "total_chunks": len(narrative_chunks),
                }
                
                # Add document type classification based on content
                content_lower = chunk.lower()
                if "```" in chunk or "def " in content_lower or "class " in content_lower:
                    qdrant_doc["doc_type"] = "code_example"
                elif "api" in content_lower or "function" in content_lower or "method" in content_lower:
                    qdrant_doc["doc_type"] = "api_reference"
                elif "tutorial" in content_lower or "example" in content_lower or "how to" in content_lower:
                    qdrant_doc["doc_type"] = "tutorial"
                else:
                    qdrant_doc["doc_type"] = "general"
                
                # Extract library information from symbol or source
                symbol_name = symbol.name.lower()
                source = str(html_path).lower()
                
                for lib in ["pyleoclim", "pylipd", "numpy", "pandas", "matplotlib"]:
                    if lib in symbol_name or lib in source:
                        qdrant_doc["library"] = lib
                        break
                else:
                    qdrant_doc["library"] = "unknown"
                
                # Add section information if available
                qdrant_doc["section"] = symbol.name.split(".")[-1] if "." in symbol.name else symbol.name
                
                documents.append(qdrant_doc)

    if not documents:
        raise RuntimeError("No documentation found to index")

    logger.info(f"Extracted {len(documents)} document chunks")
    
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
    
    logger.info(f"Indexed {indexed_count} document chunks → {collection_name}")
    return collection_name


def _split_text_into_chunks(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Try to break at sentence boundaries
        if end < len(text):
            # Look for sentence endings within the last 100 characters
            search_start = max(start + chunk_size - 100, start)
            sentence_end = -1
            
            for i in range(end - 1, search_start - 1, -1):
                if text[i] in '.!?':
                    sentence_end = i + 1
                    break
            
            if sentence_end > start:
                end = sentence_end
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start position with overlap
        start = end - chunk_overlap
        if start >= len(text):
            break
    
    return chunks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index ReadTheDocs folders into Qdrant")
    parser.add_argument("paths", nargs="+", help="One or more paths to ReadTheDocs HTML directories")
    parser.add_argument("--collection", default=None, help="Qdrant collection name (default: readthedocs_docs)")
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--chunk-overlap", type=int, default=100)
    parser.add_argument("--force-recreate", action="store_true", help="Force recreate collection if it exists")
    args = parser.parse_args()

    paths = [pathlib.Path(p) for p in args.paths]
    try:
        collection_name = build_index(
            paths, 
            collection_name=args.collection,
            chunk_size=args.chunk_size, 
            chunk_overlap=args.chunk_overlap,
            force_recreate=args.force_recreate
        )
        print(f"✅ ReadTheDocs index built successfully in collection: {collection_name}")
    except Exception as e:
        print(f"❌ Failed to build index: {e}")
        sys.exit(1) 