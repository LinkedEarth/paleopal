"""ontology_library.search_ontology

Query the Qdrant index of ontology entities and return relevant matches.
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


def search_entities(
    query: str,
    limit: int = 10,
    collection_name: str = None,
    category_filter: Optional[str] = None,
    entity_type_filter: Optional[str] = None,
    namespace_filter: Optional[str] = None,
    score_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Search for similar ontology entities.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return
        collection_name: Qdrant collection name (defaults to ontology_entities)
        category_filter: Filter by category (archive, proxy, variable, etc.)
        entity_type_filter: Filter by entity type (ArchiveType, PaleoProxy, etc.)
        namespace_filter: Filter by namespace
        score_threshold: Minimum similarity score threshold
        
    Returns:
        List of matching entities with metadata and similarity scores
    """
    if collection_name is None:
        collection_name = COLLECTION_NAMES["ontology"]
    
    # Prepare filters
    filters = {}
    if category_filter:
        filters["category"] = category_filter
    if entity_type_filter:
        filters["type"] = entity_type_filter
    if namespace_filter:
        filters["namespace"] = namespace_filter
    
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
                "entity_id": result.get("entity_id", ""),
                "name": result.get("name", ""),
                "type": result.get("type", ""),
                "category": result.get("category", ""),
                "description": result.get("description", ""),
                "synonyms": result.get("synonyms", []),
                "namespace": result.get("namespace", ""),
                "full_text": result.get("full_text", ""),
                "synonyms_count": result.get("synonyms_count", 0),
                "score": result["score"],
                "similarity_score": result["score"]  # Alias for compatibility
            }
            formatted_results.append(formatted_result)
        
        return formatted_results
        
    except Exception as e:
        print(f"Search failed: {e}")
        return []


def find_entities_by_category(category: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Find entities by category (archive, proxy, variable, etc.)."""
    return search_entities(
        query="",  # Empty query to get all results
        limit=limit,
        category_filter=category
    )


def find_entities_by_type(entity_type: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Find entities by specific type (ArchiveType, PaleoProxy, etc.)."""
    return search_entities(
        query="",  # Empty query to get all results
        limit=limit,
        entity_type_filter=entity_type
    )


def find_entities_by_synonym(synonym: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Find entities that have a specific synonym."""
    # Search with the synonym term as query
    return search_entities(
        query=synonym,
        limit=limit
    )


def get_entity_by_id(entity_id: str, collection_name: str = None) -> Optional[Dict[str, Any]]:
    """Get a specific entity by its ID."""
    if collection_name is None:
        collection_name = COLLECTION_NAMES["ontology"]
    
    qdrant_manager = get_qdrant_manager()
    
    try:
        # Search by ID (exact match)
        results = qdrant_manager.search(
            collection_name=collection_name,
            query="",  # Empty query
            limit=1,
            filters={"id": entity_id}
        )
        
        return results[0] if results else None
        
    except Exception as e:
        print(f"Failed to get entity by ID: {e}")
        return None


def get_entity_by_name(name: str, collection_name: str = None) -> Optional[Dict[str, Any]]:
    """Get a specific entity by its exact name."""
    if collection_name is None:
        collection_name = COLLECTION_NAMES["ontology"]
    
    qdrant_manager = get_qdrant_manager()
    
    try:
        # Search by name (exact match)
        results = qdrant_manager.search(
            collection_name=collection_name,
            query="",  # Empty query
            limit=1,
            filters={"name": name}
        )
        
        return results[0] if results else None
        
    except Exception as e:
        print(f"Failed to get entity by name: {e}")
        return None


def get_all_categories(collection_name: str = None) -> List[str]:
    """Get all available categories in the collection."""
    if collection_name is None:
        collection_name = COLLECTION_NAMES["ontology"]
    
    # This is a simple implementation - in a real scenario you might want 
    # to use Qdrant's aggregation features or cache this information
    all_entities = search_entities("", limit=1000)  # Get many entities
    categories = set()
    
    for entity in all_entities:
        if entity.get("category"):
            categories.add(entity["category"])
    
    return sorted(list(categories))


def get_all_entity_types(collection_name: str = None) -> List[str]:
    """Get all available entity types in the collection."""
    if collection_name is None:
        collection_name = COLLECTION_NAMES["ontology"]
    
    # This is a simple implementation - in a real scenario you might want 
    # to use Qdrant's aggregation features or cache this information
    all_entities = search_entities("", limit=1000)  # Get many entities
    entity_types = set()
    
    for entity in all_entities:
        if entity.get("type"):
            entity_types.add(entity["type"])
    
    return sorted(list(entity_types))


def get_all_namespaces(collection_name: str = None) -> List[str]:
    """Get all available namespaces in the collection."""
    if collection_name is None:
        collection_name = COLLECTION_NAMES["ontology"]
    
    # This is a simple implementation - in a real scenario you might want 
    # to use Qdrant's aggregation features or cache this information
    all_entities = search_entities("", limit=1000)  # Get many entities
    namespaces = set()
    
    for entity in all_entities:
        if entity.get("namespace"):
            namespaces.add(entity["namespace"])
    
    return sorted(list(namespaces))


def find_archive_types(query: str = "", limit: int = 20) -> List[Dict[str, Any]]:
    """Find archive type entities."""
    return search_entities(
        query=query,
        limit=limit,
        category_filter="archive"
    )


def find_paleo_variables(query: str = "", limit: int = 20) -> List[Dict[str, Any]]:
    """Find paleo variable entities."""
    return search_entities(
        query=query,
        limit=limit,
        category_filter="variable"
    )


def find_paleo_proxies(query: str = "", limit: int = 20) -> List[Dict[str, Any]]:
    """Find paleo proxy entities."""
    return search_entities(
        query=query,
        limit=limit,
        category_filter="proxy"
    )


def find_interpretation_variables(query: str = "", limit: int = 20) -> List[Dict[str, Any]]:
    """Find interpretation variable entities."""
    return search_entities(
        query=query,
        limit=limit,
        category_filter="interpretation"
    )


def find_units(query: str = "", limit: int = 20) -> List[Dict[str, Any]]:
    """Find unit entities."""
    return search_entities(
        query=query,
        limit=limit,
        category_filter="unit"
    )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Search ontology entities in Qdrant")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--limit", type=int, default=5, help="Number of results to return")
    parser.add_argument("--collection", default=None, help="Collection name")
    parser.add_argument("--category", help="Filter by category")
    parser.add_argument("--type", help="Filter by entity type")
    parser.add_argument("--namespace", help="Filter by namespace")
    parser.add_argument("--threshold", type=float, help="Minimum similarity score")
    parser.add_argument("--list-categories", action="store_true", help="List all available categories")
    parser.add_argument("--list-types", action="store_true", help="List all available entity types")
    parser.add_argument("--list-namespaces", action="store_true", help="List all available namespaces")
    
    args = parser.parse_args()
    
    if args.list_categories:
        categories = get_all_categories(args.collection)
        print("Available categories:")
        for cat in categories:
            print(f"  - {cat}")
        sys.exit(0)
    
    if args.list_types:
        types = get_all_entity_types(args.collection)
        print("Available entity types:")
        for et in types:
            print(f"  - {et}")
        sys.exit(0)
    
    if args.list_namespaces:
        namespaces = get_all_namespaces(args.collection)
        print("Available namespaces:")
        for ns in namespaces:
            print(f"  - {ns}")
        sys.exit(0)
    
    # Perform search
    results = search_entities(
        query=args.query,
        limit=args.limit,
        collection_name=args.collection,
        category_filter=args.category,
        entity_type_filter=args.type,
        namespace_filter=args.namespace,
        score_threshold=args.threshold
    )
    
    if not results:
        print("No results found.")
        sys.exit(0)
    
    print(f"Found {len(results)} results for '{args.query}':")
    print()
    
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['name']} (score: {result['score']:.3f})")
        print(f"   Type: {result['type']} | Category: {result['category']}")
        if result['namespace']:
            print(f"   Namespace: {result['namespace']}")
        print(f"   Description: {result['description'][:100]}...")
        if result['synonyms']:
            print(f"   Synonyms: {', '.join(result['synonyms'][:3])}")
        print(f"   Entity ID: {result['entity_id']}")
        print() 