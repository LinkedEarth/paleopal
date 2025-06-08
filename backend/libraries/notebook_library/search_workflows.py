from __future__ import annotations

"""notebook_library.search_workflows

API to query the Qdrant workflow index built by `index_notebooks.py`.
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


def search_workflows(
    query: str,
    limit: int = 5,
    collection_name: str = None,
    complexity_filter: Optional[str] = None,
    workflow_type_filter: Optional[str] = None,
    has_imports_filter: Optional[bool] = None,
    min_cell_count: Optional[int] = None,
    score_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Search for complete notebook workflows.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return
        collection_name: Qdrant collection name (defaults to notebook_workflows)
        complexity_filter: Filter by complexity (simple, medium, complex)
        workflow_type_filter: Filter by workflow type (data_analysis, visualization, etc.)
        has_imports_filter: Filter by whether workflow has imports
        min_cell_count: Minimum number of cells in workflow
        score_threshold: Minimum similarity score threshold
        
    Returns:
        List of matching complete workflows with full step structure and metadata
    """
    if collection_name is None:
        collection_name = COLLECTION_NAMES["notebook_workflows"]
    
    # Prepare filters
    filters = {"content_type": "complete_workflow"}
    if complexity_filter:
        filters["complexity"] = complexity_filter
    if workflow_type_filter:
        filters["workflow_type"] = workflow_type_filter
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
        
        # Apply additional filtering that's not directly supported by Qdrant
        if min_cell_count is not None:
            results = [r for r in results if r.get("cell_count", 0) >= min_cell_count]
        
        # Format results with complete workflow structure
        formatted_results = []
        for result in results:
            workflow_steps = result.get("workflow_steps", [])
            
            # Create rich result format
            formatted_result = {
                "id": result["id"],
                "score": result["score"],
                "similarity_score": result["score"],  # Alias for compatibility
                
                # Workflow identification
                "title": result.get("title", ""),
                "description": result.get("description", ""),
                "notebook_path": result.get("notebook_path", ""),
                
                # Content classification
                "content_type": "complete_workflow",
                "workflow_type": result.get("workflow_type", "general"),
                "complexity": result.get("complexity", "simple"),
                
                # Workflow metadata
                "num_steps": result.get("num_steps", 0),
                "step_types": result.get("step_types", []),
                "has_imports": result.get("has_imports", False),
                "cell_count": result.get("cell_count", 0),
                "keywords": result.get("keywords", []),
                "all_keywords": result.get("all_keywords", []),
                
                # Complete workflow structure
                "workflow_steps": workflow_steps,
                "steps": workflow_steps,  # Direct access to steps array
                
                # Aggregated step metadata
                "defined_names": result.get("defined_names", []),
                "used_names": result.get("used_names", []),
                "all_dependencies": result.get("all_dependencies", []),
                
                # For UI display - step preview
                "steps_preview": result.get("steps_preview", []),
                
                # Legacy compatibility fields
                "text": result.get("text", ""),
                "raw": result.get("text", "")
            }
            
            formatted_results.append(formatted_result)
        
        return formatted_results
        
    except Exception as e:
        print(f"Workflow search failed: {e}")
        return []


def find_workflows_by_type(workflow_type: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Find workflows by type (data_analysis, visualization, preprocessing, etc.)."""
    return search_workflows(
        query="",  # Empty query to get all results
        limit=limit,
        workflow_type_filter=workflow_type
    )


def find_complete_workflows(limit: int = 20) -> List[Dict[str, Any]]:
    """Find all complete workflow documents."""
    return search_workflows(
        query="",  # Empty query to get all results
        limit=limit
    )


def find_workflows_by_complexity(complexity: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Find workflows by complexity level."""
    return search_workflows(
        query="",  # Empty query to get all results
        limit=limit,
        complexity_filter=complexity
    )


def find_workflows_with_imports(limit: int = 10) -> List[Dict[str, Any]]:
    """Find workflows that include import statements."""
    return search_workflows(
        query="",  # Empty query to get all results
        limit=limit,
        has_imports_filter=True
    )


def get_workflow_by_id(workflow_id: str, collection_name: str = None) -> Optional[Dict[str, Any]]:
    """Get a specific workflow by its ID."""
    if collection_name is None:
        collection_name = COLLECTION_NAMES["notebook_workflows"]
    
    qdrant_manager = get_qdrant_manager()
    
    try:
        # Search by ID (exact match)
        results = qdrant_manager.search(
            collection_name=collection_name,
            query="",  # Empty query
            limit=1,
            filters={"id": workflow_id}
        )
        
        return results[0] if results else None
        
    except Exception as e:
        print(f"Failed to get workflow by ID: {e}")
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search notebook workflows")
    parser.add_argument("query", help="Natural language query describing the workflow")
    parser.add_argument("--collection", default=None, help="Collection name")
    parser.add_argument("--k", type=int, default=5, help="Number of results to return")
    parser.add_argument("--complexity", choices=["simple", "medium", "complex"], help="Filter by complexity")
    parser.add_argument("--has-imports", action="store_true", help="Filter workflows with imports")
    parser.add_argument("--min-cells", type=int, help="Minimum number of cells")
    args = parser.parse_args()

    hits = search_workflows(
        args.query,
        limit=args.k,
        collection_name=args.collection,
        complexity_filter=args.complexity,
        has_imports_filter=args.has_imports if args.has_imports else None,
        min_cell_count=args.min_cells
    )
    
    if not hits:
        print("No workflows found.")
    else:
        for h in hits:
            print(f"Score {h['score']:.3f} | {h.get('title', 'Untitled Workflow')}")
            print(f"  Description: {h.get('description', 'No description')}")
            print(f"  Complexity: {h.get('complexity', 'unknown')}")
            print(f"  Cell count: {h.get('cell_count', 0)}")
            print(f"  Has imports: {h.get('has_imports', False)}")
            print(f"  Keywords: {', '.join(h.get('keywords', []))}")
            print(f"  Notebook: {h.get('notebook_path', 'unknown')}")
            print("-" * 80) 