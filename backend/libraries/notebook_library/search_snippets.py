"""notebook_library.search_snippets

API to query the Qdrant snippet index built by `index_notebooks.py`.
"""
from __future__ import annotations

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


def search_snippets(
    query: str, 
    limit: int = 5,
    collection_name: str = None,
    notebook_filter: Optional[str] = None,
    complexity_filter: Optional[str] = None,
    has_imports_filter: Optional[bool] = None,
    score_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Search for code snippets.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return
        collection_name: Qdrant collection name (defaults to notebook_snippets)
        notebook_filter: Filter by notebook path
        complexity_filter: Filter by complexity (simple, medium, complex)
        has_imports_filter: Filter by whether snippet has imports
        score_threshold: Minimum similarity score threshold
        
    Returns:
        List of matching snippets with metadata and similarity scores
    """
    if collection_name is None:
        collection_name = COLLECTION_NAMES["notebook_snippets"]
    
    # Prepare filters
    filters = {}
    if notebook_filter:
        filters["notebook_path"] = notebook_filter
    if complexity_filter:
        filters["complexity"] = complexity_filter
    if has_imports_filter is not None:
        filters["has_imports"] = has_imports_filter
    
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
            formatted_result = {
                "id": result["id"],
                "title": result.get("title", ""),
                "code": result.get("code", ""),
                "markdown": result.get("markdown", ""),
                "notebook": result.get("notebook_path", ""),
                "notebook_path": result.get("notebook_path", ""),
                "cell_indices": result.get("cell_indices", []),
                "cell_index": result.get("cell_index"),
                "imports": result.get("imports", []),
                "defined": result.get("defined", []),
                "used": result.get("used", []),
                "unresolved": result.get("unresolved", []),
                "dependencies": result.get("dependencies", []),
                "score": result["score"],
                "similarity_score": result["score"]  # Alias for compatibility
            }
            formatted_results.append(formatted_result)
        
        return formatted_results
        
    except Exception as e:
        print(f"Search failed: {e}")
        return []


def search_workflows(
    query: str,
    limit: int = 5,
    collection_name: str = None,
    complexity_filter: Optional[str] = None,
    score_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """Search for workflows."""
    if collection_name is None:
        collection_name = COLLECTION_NAMES["notebook_workflows"]
    
    # Prepare filters
    filters = {}
    if complexity_filter:
        filters["complexity"] = complexity_filter
    
    qdrant_manager = get_qdrant_manager()
    
    try:
        results = qdrant_manager.search(
            collection_name=collection_name,
            query=query,
            limit=limit,
            filters=filters if filters else None,
            score_threshold=score_threshold
        )
        
        return results
        
    except Exception as e:
        print(f"Workflow search failed: {e}")
        return []


def search_steps(
    query: str,
    limit: int = 5,
    collection_name: str = None,
    step_type_filter: Optional[str] = None,
    score_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """Search for individual computational steps."""
    if collection_name is None:
        collection_name = COLLECTION_NAMES["notebook_steps"]
    
    # Prepare filters
    filters = {}
    if step_type_filter:
        filters["step_type"] = step_type_filter
    
    qdrant_manager = get_qdrant_manager()
    
    try:
        results = qdrant_manager.search(
            collection_name=collection_name,
            query=query,
            limit=limit,
            filters=filters if filters else None,
            score_threshold=score_threshold
        )
        
        return results
        
    except Exception as e:
        print(f"Step search failed: {e}")
        return []


# Backward compatibility aliases
search = search_snippets
load_index = lambda index_dir: None  # Legacy function, no longer needed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search code snippet library")
    parser.add_argument("query", help="Natural language or code query")
    parser.add_argument("--collection", default=None, help="Collection name")
    parser.add_argument("--k", type=int, default=5, help="Number of results to return")
    parser.add_argument("--type", choices=["snippets", "workflows", "steps"], default="snippets", help="Search type")
    parser.add_argument("--notebook", help="Filter by notebook path")
    parser.add_argument("--complexity", choices=["simple", "medium", "complex"], help="Filter by complexity")
    parser.add_argument("--step-type", help="Filter by step type (for step search)")
    args = parser.parse_args()

    if args.type == "snippets":
        hits = search_snippets(
            args.query, 
            limit=args.k, 
            collection_name=args.collection,
            notebook_filter=args.notebook,
            complexity_filter=args.complexity
        )
        for h in hits:
            ref = f"{h['notebook']}#cells{h.get('cell_indices') or h.get('cell_index')}"
            print(f"Score {h['score']:.3f} | {ref}")
            print(h['code'])
            if 'imports' in h:
                print(f"Imports: {', '.join(h['imports'])}")
            if 'unresolved' in h and h['unresolved']:
                print(f"Warning: unresolved names → {', '.join(h['unresolved'])}")
            print("-"*80)
    
    elif args.type == "workflows":
        hits = search_workflows(
            args.query,
            limit=args.k,
            collection_name=args.collection,
            complexity_filter=args.complexity
        )
        for h in hits:
            print(f"Score {h['score']:.3f} | {h.get('title', 'Untitled')}")
            print(f"Description: {h.get('description', '')}")
            print(f"Keywords: {', '.join(h.get('keywords', []))}")
            print(f"Complexity: {h.get('complexity', 'unknown')}")
            print("-"*80)
    
    elif args.type == "steps":
        hits = search_steps(
            args.query,
            limit=args.k,
            collection_name=args.collection,
            step_type_filter=args.step_type
        )
        for h in hits:
            print(f"Score {h['score']:.3f} | {h.get('description', '')}")
            print(f"Type: {h.get('step_type', 'unknown')}")
            print(f"Code: {h.get('code', '')}")
            print("-"*80) 