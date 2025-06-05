"""sparql_library.retrieve

High-level API for retrieving SPARQL queries from the Qdrant index.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
import pathlib
import sys

# Add current directory to path for imports
current_dir = pathlib.Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from search_queries import (
    search_queries, 
    find_queries_by_type, 
    find_queries_by_concept,
    get_query_by_id,
    get_all_query_types,
    get_all_concepts
)


def retrieve_sparql_queries(
    user_query: str, 
    top_k: int = 5,
    query_type_filter: Optional[str] = None,
    concept_filter: Optional[List[str]] = None,
    score_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant SPARQL queries for a user's natural language query.
    
    Args:
        user_query: Natural language description of what the user wants to query
        top_k: Maximum number of queries to return
        query_type_filter: Filter by SPARQL query type (SELECT, CONSTRUCT, etc.)
        concept_filter: Filter by paleoclimate concepts (temperature, proxy, etc.)
        score_threshold: Minimum similarity score threshold
        
    Returns:
        List of relevant SPARQL queries with metadata and scores
    """
    return search_queries(
        query=user_query,
        limit=top_k,
        query_type_filter=query_type_filter,
        concept_filter=concept_filter,
        score_threshold=score_threshold
    )


def get_sparql_query(query_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific SPARQL query by its ID.
    
    Args:
        query_id: Unique identifier for the query
        
    Returns:
        Query metadata and content if found, None otherwise
    """
    return get_query_by_id(query_id)


def find_queries_for_datasets(top_k: int = 10) -> List[Dict[str, Any]]:
    """Find queries related to dataset operations."""
    return find_queries_by_concept("dataset", limit=top_k)


def find_queries_for_variables(top_k: int = 10) -> List[Dict[str, Any]]:
    """Find queries related to paleoclimate variables."""
    return find_queries_by_concept("variable", limit=top_k)


def find_queries_for_locations(top_k: int = 10) -> List[Dict[str, Any]]:
    """Find queries related to geographic locations."""
    return find_queries_by_concept("location", limit=top_k)


def find_queries_for_proxies(top_k: int = 10) -> List[Dict[str, Any]]:
    """Find queries related to paleoclimate proxies."""
    return find_queries_by_concept("proxy", limit=top_k)


def find_select_queries(top_k: int = 20) -> List[Dict[str, Any]]:
    """Find all SELECT queries."""
    return find_queries_by_type("SELECT", limit=top_k)


def find_construct_queries(top_k: int = 20) -> List[Dict[str, Any]]:
    """Find all CONSTRUCT queries."""
    return find_queries_by_type("CONSTRUCT", limit=top_k)


def list_available_query_types() -> List[str]:
    """List all available SPARQL query types in the index."""
    return get_all_query_types()


def list_available_concepts() -> List[str]:
    """List all available paleoclimate concepts in the index."""
    return get_all_concepts()


def search_by_keywords(keywords: List[str], top_k: int = 10) -> List[Dict[str, Any]]:
    """
    Search for queries using multiple keywords.
    
    Args:
        keywords: List of keywords to search for
        top_k: Maximum number of results to return
        
    Returns:
        List of matching queries
    """
    query = " ".join(keywords)
    return retrieve_sparql_queries(query, top_k=top_k)


def find_related_queries(reference_query_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Find queries similar to a reference query.
    
    Args:
        reference_query_id: ID of the reference query
        top_k: Maximum number of similar queries to return
        
    Returns:
        List of similar queries (excluding the reference query itself)
    """
    # Get the reference query
    ref_query = get_sparql_query(reference_query_id)
    if not ref_query:
        return []
    
    # Use the reference query's title and description to find similar ones
    search_text = f"{ref_query.get('title', '')} {ref_query.get('description', '')}"
    
    # Search for similar queries
    similar = retrieve_sparql_queries(search_text, top_k=top_k + 1)
    
    # Filter out the reference query itself
    return [q for q in similar if q.get('id') != reference_query_id][:top_k]


def get_query_statistics() -> Dict[str, Any]:
    """
    Get statistics about the SPARQL query collection.
    
    Returns:
        Dictionary with collection statistics
    """
    # Get basic statistics by fetching queries and analyzing them
    all_queries = search_queries("", limit=1000)  # Get many queries for analysis
    
    stats = {
        "total_queries": len(all_queries),
        "query_types": {},
        "top_concepts": {},
        "source_files": set()
    }
    
    # Analyze query types
    for query in all_queries:
        query_type = query.get("query_type", "unknown")
        stats["query_types"][query_type] = stats["query_types"].get(query_type, 0) + 1
        
        # Collect concepts
        for concept in query.get("concepts", []):
            stats["top_concepts"][concept] = stats["top_concepts"].get(concept, 0) + 1
        
        # Collect source files
        source_file = query.get("source_file")
        if source_file:
            stats["source_files"].add(source_file)
    
    # Convert source files set to count
    stats["source_files"] = len(stats["source_files"])
    
    # Sort concepts by frequency
    stats["top_concepts"] = dict(sorted(
        stats["top_concepts"].items(), 
        key=lambda x: x[1], 
        reverse=True
    ))
    
    return stats


# Convenience aliases for backward compatibility
get_similar_queries = retrieve_sparql_queries
find_sparql_queries = retrieve_sparql_queries


if __name__ == "__main__":
    # Demo and testing
    print("SPARQL Library Demo")
    print("==================")
    
    # Test basic search
    print("\n1. Basic search for 'temperature datasets':")
    results = retrieve_sparql_queries("temperature datasets", top_k=3)
    for i, result in enumerate(results, 1):
        print(f"   {i}. {result['title']} (score: {result['score']:.3f})")
    
    # Test concept-based search
    print("\n2. Finding queries related to 'proxy' concept:")
    proxy_queries = find_queries_for_proxies(top_k=3)
    for i, result in enumerate(proxy_queries, 1):
        print(f"   {i}. {result['title']} (type: {result['query_type']})")
    
    # Test query type filtering
    print("\n3. Finding SELECT queries:")
    select_queries = find_select_queries(top_k=3)
    for i, result in enumerate(select_queries, 1):
        print(f"   {i}. {result['title']}")
    
    # Show available types and concepts
    print("\n4. Available query types:")
    types = list_available_query_types()
    print(f"   {', '.join(types)}")
    
    print("\n5. Top concepts:")
    concepts = list_available_concepts()[:10]  # Show first 10
    print(f"   {', '.join(concepts)}")
    
    # Show statistics
    print("\n6. Collection statistics:")
    stats = get_query_statistics()
    print(f"   Total queries: {stats['total_queries']}")
    print(f"   Query types: {dict(list(stats['query_types'].items())[:5])}")
    print(f"   Top concepts: {dict(list(stats['top_concepts'].items())[:5])}")
    print(f"   Source files: {stats['source_files']}") 