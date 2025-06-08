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
        category_filter: Filter by step category (e.g., "data_analysis", "sample_preparation")
        content_type_filter: Filter by content type (now always "complete_method")
        method_filter: Filter by specific method name
        score_threshold: Minimum similarity score threshold
        
    Returns:
        List of matching complete methods with full step structure and metadata
    """
    if collection_name is None:
        collection_name = COLLECTION_NAMES["literature"]
    
    # Prepare filters
    filters = {}
    if category_filter:
        # For complete methods, filter by step categories
        filters["step_categories"] = category_filter
    if content_type_filter and content_type_filter != "complete_method":
        # Legacy compatibility - map old content types to new structure
        if content_type_filter in ["method_overview", "method_step"]:
            filters["content_type"] = "complete_method"
    else:
        filters["content_type"] = "complete_method"
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
        
        # Format results with complete method structure
        formatted_results = []
        for result in results:
            # Extract the complete method structure
            method_structure = result.get("method_structure", {})
            steps = method_structure.get("steps", [])
            
            # Create rich result format
            formatted_result = {
                "id": result["id"],
                "score": result["score"],
                "similarity_score": result["score"],  # Alias for compatibility
                
                # Method identification
                "method_name": result.get("method_name", ""),
                "description": result.get("description", ""),
                "paper_title": result.get("paper_title", ""),
                "source_file": result.get("source_file", ""),
                
                # Content classification
                "content_type": "complete_method",
                "category": "method",
                "num_steps": result.get("num_steps", 0),
                "step_categories": result.get("step_categories", []),
                
                # Aggregated metadata
                "keywords": result.get("keywords", []),
                "inputs": result.get("inputs", []),
                "outputs": result.get("outputs", []),
                "step_summaries": result.get("step_summaries", []),
                
                # Complete method structure
                "method_structure": method_structure,
                "steps": steps,  # Direct access to steps array
                
                # Legacy compatibility fields
                "title": result.get("paper_title", ""),
                "file": result.get("source_file", ""),
                "method_description": result.get("description", ""),
                "text": result.get("text", ""),
                "raw": result.get("text", ""),
                
                # For UI display - formatted step information
                "steps_preview": [
                    {
                        "step_number": step.get("step_number"),
                        "category": step.get("category"),
                        "summary": step.get("searchable_summary", ""),
                        "description": step.get("description", "")[:200] + "..." if len(step.get("description", "")) > 200 else step.get("description", "")
                    }
                    for step in steps[:3]  # Show first 3 steps as preview
                ]
            }
            
            formatted_results.append(formatted_result)
        
        return formatted_results
        
    except Exception as e:
        print(f"Search failed: {e}")
        return []


def find_methods_by_category(category: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Find methods that contain steps of a specific category."""
    return search_methods(
        query="",  # Empty query to get all results
        limit=limit,
        category_filter=category
    )


def find_complete_methods(limit: int = 20) -> List[Dict[str, Any]]:
    """Find all complete method documents."""
    return search_methods(
        query="",  # Empty query to get all results
        limit=limit,
        content_type_filter="complete_method"
    )


# Legacy functions updated for backward compatibility
def find_method_overviews(limit: int = 20) -> List[Dict[str, Any]]:
    """Legacy function - now returns complete methods."""
    return find_complete_methods(limit)


def find_method_steps(limit: int = 20) -> List[Dict[str, Any]]:
    """Legacy function - now returns complete methods."""
    return find_complete_methods(limit)


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