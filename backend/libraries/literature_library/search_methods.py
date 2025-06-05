from __future__ import annotations

"""literature_library.search_methods

CLI / API to query the Qdrant index built by `index_methods.py`.
Returns Methods / Procedure sections ranked by semantic similarity.
"""

import json
import pathlib
import sys
from typing import List, Dict, Any, Optional

# Add parent directory to path for imports
current_dir = pathlib.Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from qdrant_config import get_qdrant_manager, COLLECTION_NAMES

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"


def search_methods(
    query: str,
    limit: int = 5,
    collection_name: str = None,
    category_filter: Optional[str] = None,
    content_type_filter: Optional[str] = None,
    method_filter: Optional[str] = None,
    score_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Search for literature methods.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return
        collection_name: Qdrant collection name (defaults to literature_methods)
        category_filter: Filter by category (e.g., "data_analysis", "sample_preparation")
        content_type_filter: Filter by content type ("method_overview", "method_step")
        method_filter: Filter by specific method name
        score_threshold: Minimum similarity score threshold
        
    Returns:
        List of matching methods with metadata and similarity scores
    """
    if collection_name is None:
        collection_name = COLLECTION_NAMES["literature"]
    
    # Prepare filters
    filters = {}
    if category_filter:
        filters["category"] = category_filter
    if content_type_filter:
        filters["content_type"] = content_type_filter
    if method_filter:
        filters["method_name"] = method_filter
    
    # Get Qdrant manager and search
    qdrant_manager = get_qdrant_manager()
    
    try:
        results = qdrant_manager.search(
            collection_name=collection_name,
            query=query,
            limit=limit,
            filters=filters if filters else None,
            score_threshold=score_threshold
        )
        
        # Format results for backward compatibility
        formatted_results = []
        for result in results:
            # Create backward compatible format
            formatted_result = {
                "id": result["id"],
                "score": result["score"],
                "similarity_score": result["score"],  # Alias for compatibility
                "method_name": result.get("method_name", ""),
                "paper_title": result.get("paper_title", ""),
                "source_file": result.get("source_file", ""),
                "content_type": result.get("content_type", ""),
                "category": result.get("category", ""),
                "searchable_summary": result.get("searchable_summary", ""),
                "keywords": result.get("keywords", []),
                "inputs": result.get("inputs", []),
                "outputs": result.get("outputs", []),
                "method_description": result.get("method_description", ""),
                "step_description": result.get("step_description", ""),
                "step_number": result.get("step_number"),
                "text": result.get("text", "")
            }
            
            # Add legacy fields for compatibility
            formatted_result["title"] = result.get("paper_title", "")
            formatted_result["file"] = result.get("source_file", "")
            
            # Parse steps from method description for legacy compatibility
            if result.get("step_description"):
                formatted_result["steps"] = [result["step_description"]]
            else:
                formatted_result["steps"] = []
            
            # Add raw text field
            formatted_result["raw"] = result.get("text", "")
            
            formatted_results.append(formatted_result)
        
        return formatted_results
        
    except Exception as e:
        print(f"Search failed: {e}")
        return []


def find_methods_by_category(category: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Find methods by category."""
    return search_methods(
        query="",  # Empty query to get all results
        limit=limit,
        category_filter=category
    )


def find_method_overviews(limit: int = 20) -> List[Dict[str, Any]]:
    """Find method overview documents."""
    return search_methods(
        query="",  # Empty query to get all results
        limit=limit,
        content_type_filter="method_overview"
    )


def find_method_steps(limit: int = 20) -> List[Dict[str, Any]]:
    """Find individual method steps."""
    return search_methods(
        query="",  # Empty query to get all results
        limit=limit,
        content_type_filter="method_step"
    )


def search_by_method_name(method_name: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Find all content related to a specific method."""
    return search_methods(
        query=method_name,
        limit=limit,
        method_filter=method_name
    )


# Legacy function for backward compatibility
def load_index(index_dir: str | pathlib.Path):
    """Legacy function - no longer needed with Qdrant."""
    return None, []


def search(query: str, index_dir: str | pathlib.Path, top_k: int = 5) -> List[Dict[str, Any]]:
    """Legacy search function for backward compatibility."""
    return search_methods(query, limit=top_k)


if __name__ == "__main__":
    import argparse, textwrap

    parser = argparse.ArgumentParser(description="Semantic search over indexed Methods/Procedures")
    parser.add_argument("query", help="Natural language query, e.g. 'grain size analysis protocol'")
    parser.add_argument("--collection", default=None, help="Collection name")
    parser.add_argument("--k", type=int, default=5, help="Number of hits to show")
    parser.add_argument("--category", help="Filter by category")
    parser.add_argument("--content-type", choices=["method_overview", "method_step"], help="Filter by content type")
    parser.add_argument("--method", help="Filter by method name")
    parser.add_argument("--show-raw", action="store_true", help="Print raw section text as well")
    args = parser.parse_args()

    hits = search_methods(
        args.query, 
        limit=args.k,
        collection_name=args.collection,
        category_filter=args.category,
        content_type_filter=args.content_type,
        method_filter=args.method
    )
    
    if not hits:
        print("No results found")
        raise SystemExit

    for h in hits:
        title = h.get("title") or pathlib.Path(h.get("file", "")).stem
        print(f"Score {h['score']:.3f} | {title}")
        if h.get("method_name"):
            print(f" Method: {h['method_name']}")
        if h.get("content_type"):
            print(f" Type: {h['content_type']}")
        if h.get("category"):
            print(f" Category: {h['category']}")
        if h.get("searchable_summary"):
            print(f" Summary: {h['searchable_summary']}")
        if h.get("step_number"):
            print(f" Step {h['step_number']}: {h.get('step_description', '')}")
        
        # Show legacy steps format for compatibility
        steps = h.get("steps", [])
        if steps:
            print(" Steps:")
            for i, step in enumerate(steps[:10], 1):
                print(f"  {i}. {step}")
        
        if args.show_raw:
            print(textwrap.fill(h["raw"][:4000], width=100))
        print("-" * 80) 