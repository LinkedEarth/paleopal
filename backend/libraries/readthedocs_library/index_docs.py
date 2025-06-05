"""readthedocs_library.index_docs

Build a Qdrant vector store from one or more Read-the-Docs HTML directories.

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

try:
    from langchain_community.document_loaders import ReadTheDocsLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except ImportError as e:  # pragma: no cover
    raise ImportError("langchain and langchain_community are required: pip install langchain langchain_community") from e

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rtd-index")


def build_index(
    doc_paths: List[pathlib.Path], 
    collection_name: str = None,
    *,
    chunk_size: int = 800, 
    chunk_overlap: int = 100,
    force_recreate: bool = False
) -> str:
    """
    Build Qdrant index from ReadTheDocs HTML directories.
    
    Args:
        doc_paths: List of paths to ReadTheDocs HTML directories
        collection_name: Qdrant collection name (defaults to readthedocs_docs)
        chunk_size: Size of text chunks
        chunk_overlap: Overlap between chunks
        force_recreate: Whether to recreate the collection if it exists
        
    Returns:
        Name of the created collection
    """
    if collection_name is None:
        collection_name = COLLECTION_NAMES["readthedocs_docs"]
    
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
    
    # Load and split documents
    docs = []
    for p in doc_paths:
        logger.info(f"Loading documents from {p}")
        loader = ReadTheDocsLoader(str(p))
        docs.extend(loader.load_and_split(text_splitter=text_splitter))

    if not docs:
        raise RuntimeError("No docs found to index")

    logger.info(f"Loaded {len(docs)} document chunks")
    
    # Convert LangChain documents to Qdrant format
    qdrant_docs = []
    for doc in docs:
        doc_dict = {
            "id": str(uuid.uuid4()),
            "text": doc.page_content,
            "content": doc.page_content,  # Alias for compatibility
            **doc.metadata  # Include all metadata fields
        }
        
        # Add document type classification
        content = doc.page_content.lower()
        if "```" in content or "def " in content or "class " in content:
            doc_dict["doc_type"] = "code_example"
        elif "api" in content or "function" in content or "method" in content:
            doc_dict["doc_type"] = "api_reference"
        elif "tutorial" in content or "example" in content or "how to" in content:
            doc_dict["doc_type"] = "tutorial"
        else:
            doc_dict["doc_type"] = "general"
        
        # Extract source information for better filtering
        source = doc.metadata.get("source", "")
        if source:
            # Extract library name from path (e.g., pyleoclim, pylipd)
            path_parts = pathlib.Path(source).parts
            for part in path_parts:
                if part in ["pyleoclim", "pylipd", "numpy", "pandas", "matplotlib"]:
                    doc_dict["library"] = part
                    break
            else:
                doc_dict["library"] = "unknown"
            
            # Extract section from URL/path
            if "#" in source:
                doc_dict["section"] = source.split("#")[-1]
            else:
                doc_dict["section"] = ""
        
        qdrant_docs.append(doc_dict)
    
    # Get Qdrant manager
    qdrant_manager = get_qdrant_manager()
    
    # Create collection
    if not qdrant_manager.create_collection(collection_name, force_recreate=force_recreate):
        raise RuntimeError(f"Failed to create collection: {collection_name}")
    
    # Index documents
    indexed_count = qdrant_manager.index_documents(
        collection_name=collection_name,
        documents=qdrant_docs,
        text_field="text"
    )
    
    logger.info(f"Indexed {indexed_count} document chunks → {collection_name}")
    return collection_name


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