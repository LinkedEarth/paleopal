"""sparql_library.index_queries

Parse SPARQL queries from markdown documentation and create a searchable Qdrant index.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
from typing import List, Dict, Any, Optional
import uuid
import sys
from sparql_query_loader import SparqlQueryParser

# Add parent directory to path for imports
current_dir = pathlib.Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from qdrant_config import get_qdrant_manager, COLLECTION_NAMES

DEFAULT_QUERIES_DIR = pathlib.Path("queries")


def build_index(
    queries_dir: pathlib.Path = DEFAULT_QUERIES_DIR,
    collection_name: str = None,
    force_recreate: bool = False
) -> bool:
    """Build Qdrant index from SPARQL queries in markdown files."""
    
    if not queries_dir.exists():
        raise FileNotFoundError(f"Queries directory not found: {queries_dir}")
    
    # Use default collection name if not provided
    if collection_name is None:
        collection_name = COLLECTION_NAMES["sparql"]
    
    # Load queries
    parser = SparqlQueryParser(queries_dir)
    all_queries = parser.load_queries()
    
    if not all_queries:
        raise ValueError("No SPARQL queries found in any markdown files")
    
    print(f"Found {len(all_queries)} SPARQL queries")
    
    # Get Qdrant manager
    qdrant_manager = get_qdrant_manager()
    
    # Create collection
    if not qdrant_manager.create_collection(collection_name, force_recreate=force_recreate):
        raise RuntimeError(f"Failed to create collection: {collection_name}")
    
    # Index documents
    indexed_count = qdrant_manager.index_documents(
        collection_name=collection_name,
        documents=all_queries,
        text_field="text"
    )
    
    print(f"Built index with {indexed_count} queries in collection: {collection_name}")
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Index SPARQL queries from markdown files into Qdrant")
    parser.add_argument("--queries-dir", default="queries", help="Directory containing markdown files with SPARQL queries")
    parser.add_argument("--collection", default=None, help="Qdrant collection name (default: sparql_queries)")
    parser.add_argument("--force-recreate", action="store_true", help="Force recreate collection if it exists")
    parser.add_argument("--test-search", type=str, help="Test search with a query")
    
    args = parser.parse_args()
    
    queries_dir = pathlib.Path(args.queries_dir)
    
    if args.test_search:
        # Test search functionality
        from search_queries import search_queries
        results = search_queries(args.test_search, limit=5)
        print(f"\nSearch results for '{args.test_search}':")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result['title']} (score: {result['score']:.3f})")
            print(f"   Type: {result['query_type']}")
            print(f"   Query: {result['sparql_query'][:100]}...")
            print()
    else:
        # Build index
        try:
            build_index(
                queries_dir=queries_dir,
                collection_name=args.collection,
                force_recreate=args.force_recreate
            )
            print("✅ SPARQL query index built successfully")
        except Exception as e:
            print(f"❌ Failed to build index: {e}")
            sys.exit(1) 