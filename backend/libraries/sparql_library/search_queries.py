"""sparql_library.search_queries

Query the Qdrant index of SPARQL queries and return relevant matches.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
import pathlib
import json
import sys
import re

# Add parent directory to path for imports
current_dir = pathlib.Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from qdrant_config import get_qdrant_manager, COLLECTION_NAMES


def search_queries(
    query: str,
    limit: int = 10,
    collection_name: str = None,
    query_type_filter: Optional[str] = None,
    concept_filter: Optional[List[str]] = None,
    score_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Search for similar SPARQL queries.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return
        collection_name: Qdrant collection name (defaults to sparql_queries)
        query_type_filter: Filter by query type (SELECT, CONSTRUCT, ASK, DESCRIBE)
        concept_filter: Filter by concepts (temperature, proxy, dataset, etc.)
        score_threshold: Minimum similarity score threshold
        
    Returns:
        List of matching queries with metadata and similarity scores
    """
    if collection_name is None:
        collection_name = COLLECTION_NAMES["sparql"]
    
    # Prepare filters
    filters = {}
    if query_type_filter:
        filters["query_type"] = query_type_filter
    if concept_filter:
        filters["concepts"] = concept_filter
    
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
                "description": result.get("description", ""),
                "sparql_query": result.get("sparql_query", ""),
                "query_type": result.get("query_type", ""),
                "concepts": result.get("concepts", []),
                "source_file": result.get("source_file", ""),
                "score": result["score"],
                "similarity_score": result["score"]  # Alias for compatibility
            }
            formatted_results.append(formatted_result)
        
        return formatted_results
        
    except Exception as e:
        print(f"Search failed: {e}")
        return []


def find_queries_by_type(query_type: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Find all queries of a specific type."""
    return search_queries(
        query="",  # Empty query to get all results
        limit=limit,
        query_type_filter=query_type
    )


def find_queries_by_concept(concept: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Find queries related to a specific concept."""
    return search_queries(
        query=concept,
        limit=limit,
        concept_filter=[concept]
    )


def get_query_by_id(query_id: str, collection_name: str = None) -> Optional[Dict[str, Any]]:
    """Get a specific query by its ID."""
    if collection_name is None:
        collection_name = COLLECTION_NAMES["sparql"]
    
    qdrant_manager = get_qdrant_manager()
    
    try:
        # Search by ID (exact match)
        results = qdrant_manager.search(
            collection_name=collection_name,
            query="",  # Empty query
            limit=1,
            filters={"id": query_id}
        )
        
        return results[0] if results else None
        
    except Exception as e:
        print(f"Failed to get query by ID: {e}")
        return None


def get_all_query_types(collection_name: str = None) -> List[str]:
    """Get all available query types in the collection."""
    if collection_name is None:
        collection_name = COLLECTION_NAMES["sparql"]
    
    # This is a simple implementation - in a real scenario you might want 
    # to use Qdrant's aggregation features or cache this information
    all_queries = search_queries("", limit=1000)  # Get many queries
    query_types = set()
    
    for query in all_queries:
        if query.get("query_type"):
            query_types.add(query["query_type"])
    
    return sorted(list(query_types))


def get_all_concepts(collection_name: str = None) -> List[str]:
    """Get all available concepts in the collection."""
    if collection_name is None:
        collection_name = COLLECTION_NAMES["sparql"]
    
    # This is a simple implementation - in a real scenario you might want 
    # to use Qdrant's aggregation features or cache this information
    all_queries = search_queries("", limit=1000)  # Get many queries
    concepts = set()
    
    for query in all_queries:
        if query.get("concepts"):
            concepts.update(query["concepts"])
    
    return sorted(list(concepts))


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Search SPARQL queries in Qdrant")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--limit", type=int, default=5, help="Number of results to return")
    parser.add_argument("--collection", default=None, help="Collection name")
    parser.add_argument("--type", help="Filter by query type")
    parser.add_argument("--concept", help="Filter by concept")
    parser.add_argument("--threshold", type=float, help="Minimum similarity score")
    parser.add_argument("--list-types", action="store_true", help="List all available query types")
    parser.add_argument("--list-concepts", action="store_true", help="List all available concepts")
    
    args = parser.parse_args()
    
    if args.list_types:
        types = get_all_query_types(args.collection)
        print("Available query types:")
        for qt in types:
            print(f"  - {qt}")
        sys.exit(0)
    
    if args.list_concepts:
        concepts = get_all_concepts(args.collection)
        print("Available concepts:")
        for concept in concepts:
            print(f"  - {concept}")
        sys.exit(0)
    
    # Perform search
    concept_filter = [args.concept] if args.concept else None
    
    results = search_queries(
        query=args.query,
        limit=args.limit,
        collection_name=args.collection,
        query_type_filter=args.type,
        concept_filter=concept_filter,
        score_threshold=args.threshold
    )
    
    if not results:
        print("No results found.")
        sys.exit(0)
    
    print(f"Found {len(results)} results for '{args.query}':")
    print()
    
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['title']} (score: {result['score']:.3f})")
        print(f"   Type: {result['query_type']}")
        if result['concepts']:
            print(f"   Concepts: {', '.join(result['concepts'])}")
        print(f"   Description: {result['description'][:100]}...")
        print(f"   Query: {result['sparql_query'][:100]}...")
        print(f"   Source: {result['source_file']}")
        print() 