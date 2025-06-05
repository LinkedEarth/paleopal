from __future__ import annotations

"""literature_library.index_methods

Build a Qdrant vector store for semantic search from extracted method JSON files.
Reads structured method files and creates embeddings for efficient similarity search.
"""

import pathlib
import re
import json
import logging
import sys
from typing import List, Dict, Any
import uuid

# Add parent directory to path for imports
current_dir = pathlib.Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from qdrant_config import get_qdrant_manager, COLLECTION_NAMES

import os

LOG = logging.getLogger("lit-index")
logging.basicConfig(level=logging.INFO)

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"


def clean_text(text: str) -> str:
    """Clean and normalize text for embedding."""
    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def extract_searchable_content(method_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract searchable content from method JSON data.
    Returns a list of records with text and metadata for indexing.
    """
    records = []
    
    if not method_data.get("methods_found", False):
        return records
    
    source_file = method_data.get("source_file", "")
    paper_title = method_data.get("paper_title", "Unknown")
    
    for method in method_data.get("methods", []):
        method_name = method.get("method_name", "")
        method_description = method.get("description", "")
        
        # Create a record for the overall method
        method_text = f"{method_name}. {method_description}"
        method_record = {
            "id": str(uuid.uuid4()),
            "text": clean_text(method_text),
            "source_file": source_file,
            "paper_title": paper_title,
            "method_name": method_name,
            "method_description": method_description,
            "content_type": "method_overview",
            "step_number": None,
            "category": "method",
            "searchable_summary": f"Implement {method_name.lower()} methodology",
            "keywords": [],
            "inputs": [],
            "outputs": []
        }
        records.append(method_record)
        
        # Create records for each step
        for step in method.get("steps", []):
            step_text = " ".join([
                step.get("searchable_summary", ""),
                step.get("description", ""),
                " ".join(step.get("keywords", [])),
                method_name,
                method_description
            ])
            
            step_record = {
                "id": str(uuid.uuid4()),
                "text": clean_text(step_text),
                "source_file": source_file,
                "paper_title": paper_title,
                "method_name": method_name,
                "method_description": method_description[:200] + "..." if len(method_description) > 200 else method_description,
                "content_type": "method_step",
                "step_number": step.get("step_number"),
                "category": step.get("category", "other"),
                "searchable_summary": step.get("searchable_summary", ""),
                "keywords": step.get("keywords", []),
                "inputs": step.get("inputs", []),
                "outputs": step.get("outputs", []),
                "step_description": step.get("description", "")
            }
            records.append(step_record)
    
    return records


def build_index_from_json_files(
    json_dir: pathlib.Path, 
    collection_name: str = None,
    force_recreate: bool = False
) -> str:
    """
    Build Qdrant index from extracted method JSON files.
    
    Args:
        json_dir: Directory containing *_methods.json files
        collection_name: Qdrant collection name (defaults to literature_methods)
        force_recreate: Whether to recreate the collection if it exists
    
    Returns:
        Name of the created collection
    """
    if collection_name is None:
        collection_name = COLLECTION_NAMES["literature"]
    
    # Find all method JSON files
    json_files = list(json_dir.glob("*_methods.json"))
    if not json_files:
        raise RuntimeError(f"No *_methods.json files found in {json_dir}")
    
    LOG.info(f"Found {len(json_files)} method JSON files")
    
    all_records: List[Dict[str, Any]] = []
    
    for json_file in json_files:
        LOG.info(f"Processing {json_file.name}")
        
        try:
            with json_file.open(encoding='utf-8') as f:
                method_data = json.load(f)
            
            # Extract searchable content
            records = extract_searchable_content(method_data)
            
            if not records:
                LOG.warning(f"No searchable content extracted from {json_file.name}")
                continue
            
            all_records.extend(records)
            LOG.info(f"Extracted {len(records)} searchable items from {json_file.name}")
            
        except Exception as e:
            LOG.error(f"Error processing {json_file.name}: {e}")
            continue
    
    if not all_records:
        raise RuntimeError("No searchable content extracted from JSON files")
    
    LOG.info(f"Total searchable items: {len(all_records)}")
    
    # Get Qdrant manager
    qdrant_manager = get_qdrant_manager()
    
    # Create collection
    if not qdrant_manager.create_collection(collection_name, force_recreate=force_recreate):
        raise RuntimeError(f"Failed to create collection: {collection_name}")
    
    # Index documents
    indexed_count = qdrant_manager.index_documents(
        collection_name=collection_name,
        documents=all_records,
        text_field="text"
    )
    
    LOG.info(f"Index built successfully with {indexed_count} items → {collection_name}")
    return collection_name


def search_methods_index(
    query: str, 
    collection_name: str = None,
    top_k: int = 10,
    category_filter: str = None,
    content_type_filter: str = None,
    score_threshold: float = None
) -> List[Dict[str, Any]]:
    """
    Search the methods index for similar content.
    
    Args:
        query: Search query
        collection_name: Qdrant collection name (defaults to literature_methods)
        top_k: Number of results to return
        category_filter: Optional category filter (e.g., "data_fetch", "data_analysis")
        content_type_filter: Filter by content type ("method_overview", "method_step")
        score_threshold: Minimum similarity score threshold
        
    Returns:
        List of matching records with similarity scores
    """
    if collection_name is None:
        collection_name = COLLECTION_NAMES["literature"]
    
    # Prepare filters
    filters = {}
    if category_filter:
        filters["category"] = category_filter
    if content_type_filter:
        filters["content_type"] = content_type_filter
    
    # Get Qdrant manager and search
    qdrant_manager = get_qdrant_manager()
    
    try:
        results = qdrant_manager.search(
            collection_name=collection_name,
            query=query,
            limit=top_k,
            filters=filters if filters else None,
            score_threshold=score_threshold
        )
        
        return results
        
    except Exception as e:
        LOG.error(f"Search failed: {e}")
        return []


def create_index_summary(collection_name: str = None) -> Dict[str, Any]:
    """
    Create a summary of the indexed methods.
    
    Args:
        collection_name: Qdrant collection name (defaults to literature_methods)
        
    Returns:
        Dictionary with collection statistics
    """
    if collection_name is None:
        collection_name = COLLECTION_NAMES["literature"]
    
    qdrant_manager = get_qdrant_manager()
    
    # Get collection info
    collection_info = qdrant_manager.get_collection_info(collection_name)
    if not collection_info:
        return {"error": "Collection not found"}
    
    # Get sample of documents to analyze content
    sample_results = qdrant_manager.search(
        collection_name=collection_name,
        query="",  # Empty query to get sample
        limit=100
    )
    
    # Analyze categories and content types
    categories = {}
    content_types = {}
    methods = set()
    papers = set()
    
    for result in sample_results:
        # Count categories
        category = result.get("category", "unknown")
        categories[category] = categories.get(category, 0) + 1
        
        # Count content types
        content_type = result.get("content_type", "unknown")
        content_types[content_type] = content_types.get(content_type, 0) + 1
        
        # Collect unique methods and papers
        if result.get("method_name"):
            methods.add(result["method_name"])
        if result.get("paper_title"):
            papers.add(result["paper_title"])
    
    return {
        "collection_name": collection_name,
        "total_documents": collection_info.get("points_count", 0),
        "indexed_documents": collection_info.get("indexed_vectors_count", 0),
        "categories": categories,
        "content_types": content_types,
        "unique_methods": len(methods),
        "unique_papers": len(papers),
        "sample_methods": list(methods)[:10],  # First 10 methods
        "sample_papers": list(papers)[:5]  # First 5 papers
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Index literature methods from JSON into Qdrant")
    parser.add_argument("--json-dir", default="my_documents", help="Directory containing *_methods.json files")
    parser.add_argument("--collection", default=None, help="Qdrant collection name (default: literature_methods)")
    parser.add_argument("--force-recreate", action="store_true", help="Force recreate collection if it exists")
    parser.add_argument("--test-search", type=str, help="Test search with a query")
    parser.add_argument("--summary", action="store_true", help="Show index summary")
    
    args = parser.parse_args()
    
    json_dir = pathlib.Path(args.json_dir)
    
    if args.summary:
        # Show index summary
        summary = create_index_summary(args.collection)
        print("Literature Methods Index Summary:")
        print("=" * 40)
        for key, value in summary.items():
            if isinstance(value, dict):
                print(f"{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            elif isinstance(value, list):
                print(f"{key}: {', '.join(map(str, value))}")
            else:
                print(f"{key}: {value}")
    
    elif args.test_search:
        # Test search functionality
        results = search_methods_index(args.test_search, collection_name=args.collection, top_k=5)
        print(f"\nSearch results for '{args.test_search}':")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result.get('method_name', 'Unknown')} (score: {result['score']:.3f})")
            print(f"   Paper: {result.get('paper_title', 'Unknown')}")
            print(f"   Type: {result.get('content_type', 'unknown')}")
            print(f"   Category: {result.get('category', 'unknown')}")
            if result.get('searchable_summary'):
                print(f"   Summary: {result['searchable_summary']}")
            print()
    
    else:
        # Build index
        try:
            collection_name = build_index_from_json_files(
                json_dir=json_dir,
                collection_name=args.collection,
                force_recreate=args.force_recreate
            )
            print(f"✅ Literature methods index built successfully in collection: {collection_name}")
        except Exception as e:
            print(f"❌ Failed to build index: {e}")
            sys.exit(1) 