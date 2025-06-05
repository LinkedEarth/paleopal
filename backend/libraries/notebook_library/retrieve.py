"""notebook_library.retrieve

High-level API for retrieving code snippets, workflows, and steps from the Qdrant indexes.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
import pathlib
import sys

# Add current directory to path for imports
current_dir = pathlib.Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from search_snippets import search_snippets, search_workflows, search_steps


def retrieve_code_snippets(
    query: str,
    top_k: int = 5,
    notebook_filter: Optional[str] = None,
    complexity_filter: Optional[str] = None,
    has_imports_filter: Optional[bool] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant code snippets for a user's query.
    
    Args:
        query: Natural language description of desired code functionality
        top_k: Maximum number of snippets to return
        notebook_filter: Filter by notebook path
        complexity_filter: Filter by complexity (simple, medium, complex)
        has_imports_filter: Filter by whether snippet has imports
        
    Returns:
        List of relevant code snippets with metadata and scores
    """
    return search_snippets(
        query=query,
        limit=top_k,
        notebook_filter=notebook_filter,
        complexity_filter=complexity_filter,
        has_imports_filter=has_imports_filter
    )


def retrieve_workflows(
    query: str,
    top_k: int = 5,
    complexity_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant workflows for a user's query.
    
    Args:
        query: Natural language description of desired workflow
        top_k: Maximum number of workflows to return
        complexity_filter: Filter by complexity (simple, medium, complex)
        
    Returns:
        List of relevant workflows with metadata and scores
    """
    return search_workflows(
        query=query,
        limit=top_k,
        complexity_filter=complexity_filter
    )


def retrieve_computational_steps(
    query: str,
    top_k: int = 5,
    step_type_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant computational steps for a user's query.
    
    Args:
        query: Natural language description of desired step
        top_k: Maximum number of steps to return
        step_type_filter: Filter by step type (import, data_loading, visualization, etc.)
        
    Returns:
        List of relevant steps with metadata and scores
    """
    return search_steps(
        query=query,
        limit=top_k,
        step_type_filter=step_type_filter
    )


def find_simple_snippets(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Find simple code snippets."""
    return retrieve_code_snippets(
        query=query,
        top_k=top_k,
        complexity_filter="simple"
    )


def find_complex_workflows(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Find complex workflows."""
    return retrieve_workflows(
        query=query,
        top_k=top_k,
        complexity_filter="complex"
    )


def find_visualization_steps(query: str = "", top_k: int = 5) -> List[Dict[str, Any]]:
    """Find visualization-related steps."""
    return retrieve_computational_steps(
        query=query,
        top_k=top_k,
        step_type_filter="visualization"
    )


def find_data_loading_steps(query: str = "", top_k: int = 5) -> List[Dict[str, Any]]:
    """Find data loading steps."""
    return retrieve_computational_steps(
        query=query,
        top_k=top_k,
        step_type_filter="data_loading"
    )


# Convenience aliases for backward compatibility
get_code_snippets = retrieve_code_snippets
get_workflows = retrieve_workflows


if __name__ == "__main__":
    # Demo and testing
    print("Notebook Library Demo")
    print("====================")
    
    # Test basic snippet search
    print("\n1. Basic search for 'data visualization':")
    snippets = retrieve_code_snippets("data visualization", top_k=3)
    for i, snippet in enumerate(snippets, 1):
        print(f"   {i}. {snippet.get('title', 'Untitled')} (score: {snippet['score']:.3f})")
    
    # Test workflow search
    print("\n2. Finding workflows for 'machine learning':")
    workflows = retrieve_workflows("machine learning", top_k=3)
    for i, workflow in enumerate(workflows, 1):
        print(f"   {i}. {workflow.get('title', 'Untitled')} (complexity: {workflow.get('complexity', 'unknown')})")
    
    # Test step search
    print("\n3. Finding visualization steps:")
    steps = find_visualization_steps(top_k=3)
    for i, step in enumerate(steps, 1):
        print(f"   {i}. {step.get('description', 'No description')} (type: {step.get('step_type', 'unknown')})")
    
    print("\n4. Finding simple snippets for 'pandas dataframe':")
    simple_snippets = find_simple_snippets("pandas dataframe", top_k=3)
    for i, snippet in enumerate(simple_snippets, 1):
        print(f"   {i}. {snippet.get('title', 'Untitled')}")
        if snippet.get('imports'):
            print(f"      Imports: {', '.join(snippet['imports'])}") 