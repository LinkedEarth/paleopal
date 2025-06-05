"""ontology_library.retrieve

High-level interface for retrieving ontology entities by semantic search.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
import pathlib

from search_ontology import (
    search_ontology, 
    get_entity_by_name, 
    list_all_entities, 
    get_categories,
    get_entity_types,
    get_namespaces,
    get_entities_by_synonym
)

DEFAULT_INDEX_DIR = pathlib.Path(__file__).parent / "ontology_index"


def retrieve_ontology_entities(
    query: str,
    *,
    top_k: int = 5,
    category: Optional[str] = None,
    entity_type: Optional[str] = None,
    namespace: Optional[str] = None,
    min_score: float = 0.3,
    index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR
) -> List[Dict[str, Any]]:
    """Retrieve ontology entities relevant to the given query.
    
    Args:
        query: Natural language description of what you're looking for
        top_k: Maximum number of entities to return
        category: Filter by category ('archive', 'interpretation', 'proxy', 'variable', 'unit')
        entity_type: Filter by specific entity type (e.g., 'PaleoVariable', 'ArchiveType')
        namespace: Filter by namespace (e.g., 'archive', 'paleo_variables')
        min_score: Minimum similarity score (0.0 to 1.0)
        index_dir: Path to the ontology index
        
    Returns:
        List of relevant ontology entities with metadata
        
    Example:
        >>> entities = retrieve_ontology_entities("coral temperature proxy")
        >>> for e in entities:
        ...     print(f"{e['name']}: {e['description']}")
    """
    return search_ontology(
        query,
        top_k=top_k,
        index_dir=index_dir,
        category_filter=category,
        entity_type_filter=entity_type,
        namespace_filter=namespace,
        min_score=min_score
    )


def get_ontology_entity(
    entity_name: str,
    *,
    exact_match: bool = True,
    index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR
) -> Optional[Dict[str, Any]]:
    """Get a specific ontology entity by name.
    
    Args:
        entity_name: Name of the entity to find
        exact_match: Whether to require exact name match
        index_dir: Path to the ontology index
        
    Returns:
        Entity metadata if found, None otherwise
        
    Example:
        >>> entity = get_ontology_entity('Coral')
        >>> print(f"Description: {entity['description']}")
        >>> print(f"Synonyms: {entity['synonyms']}")
    """
    return get_entity_by_name(entity_name, index_dir=index_dir, exact_match=exact_match)


def find_entities_by_synonym(
    synonym: str,
    *,
    top_k: int = 10,
    index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR
) -> List[Dict[str, Any]]:
    """Find entities that have the given synonym.
    
    Args:
        synonym: Synonym to search for
        top_k: Maximum number of results
        index_dir: Path to the ontology index
        
    Returns:
        List of entities with the matching synonym
        
    Example:
        >>> entities = find_entities_by_synonym('coral')
        >>> for e in entities:
        ...     print(f"{e['name']} (matched: {e['matched_synonym']})")
    """
    return get_entities_by_synonym(synonym, top_k=top_k, index_dir=index_dir)


def list_ontology_categories(*, index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR) -> List[str]:
    """List all available ontology categories.
    
    Returns:
        Sorted list of category names
    """
    return get_categories(index_dir=index_dir)


def list_entity_types(*, index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR) -> List[str]:
    """List all available entity types.
    
    Returns:
        Sorted list of entity type names
    """
    return get_entity_types(index_dir=index_dir)


def list_namespaces(*, index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR) -> List[str]:
    """List all available namespaces.
    
    Returns:
        Sorted list of namespace names
    """
    return get_namespaces(index_dir=index_dir)


def list_entities_by_category(
    category: str,
    *,
    index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR
) -> List[Dict[str, Any]]:
    """List all entities in a specific category.
    
    Args:
        category: Category name (e.g., 'archive', 'interpretation', 'proxy')
        index_dir: Path to the ontology index
        
    Returns:
        List of entities in the specified category
    """
    return list_all_entities(index_dir=index_dir, category_filter=category)


def list_entities_by_type(
    entity_type: str,
    *,
    index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR
) -> List[Dict[str, Any]]:
    """List all entities of a specific type.
    
    Args:
        entity_type: Entity type name (e.g., 'PaleoVariable', 'ArchiveType')
        index_dir: Path to the ontology index
        
    Returns:
        List of entities of the specified type
    """
    return list_all_entities(index_dir=index_dir, entity_type_filter=entity_type)


def list_entities_by_namespace(
    namespace: str,
    *,
    index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR
) -> List[Dict[str, Any]]:
    """List all entities in a specific namespace.
    
    Args:
        namespace: Namespace name (e.g., 'archive', 'paleo_variables')
        index_dir: Path to the ontology index
        
    Returns:
        List of entities in the specified namespace
    """
    return list_all_entities(index_dir=index_dir, namespace_filter=namespace)


# Convenience functions for common searches
def find_archive_types(
    description: str = "",
    *,
    top_k: int = 5,
    index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR
) -> List[Dict[str, Any]]:
    """Find archive types (data sources like coral, tree rings, etc.)."""
    if description:
        return retrieve_ontology_entities(
            description,
            top_k=top_k,
            category="archive",
            index_dir=index_dir
        )
    else:
        return list_entities_by_category("archive", index_dir=index_dir)


def find_paleo_variables(
    description: str = "",
    *,
    top_k: int = 5,
    index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR
) -> List[Dict[str, Any]]:
    """Find paleoclimate variables (temperature, precipitation, etc.)."""
    if description:
        return retrieve_ontology_entities(
            description,
            top_k=top_k,
            category="variable",
            index_dir=index_dir
        )
    else:
        return list_entities_by_category("variable", index_dir=index_dir)


def find_paleo_proxies(
    description: str = "",
    *,
    top_k: int = 5,
    index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR
) -> List[Dict[str, Any]]:
    """Find paleo proxies (measurement types)."""
    if description:
        return retrieve_ontology_entities(
            description,
            top_k=top_k,
            category="proxy",
            index_dir=index_dir
        )
    else:
        return list_entities_by_category("proxy", index_dir=index_dir)


def find_interpretation_variables(
    description: str = "",
    *,
    top_k: int = 5,
    index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR
) -> List[Dict[str, Any]]:
    """Find interpretation variables (what the proxy data represents)."""
    if description:
        return retrieve_ontology_entities(
            description,
            top_k=top_k,
            category="interpretation",
            index_dir=index_dir
        )
    else:
        return list_entities_by_category("interpretation", index_dir=index_dir)


def find_units(
    description: str = "",
    *,
    top_k: int = 5,
    index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR
) -> List[Dict[str, Any]]:
    """Find measurement units."""
    if description:
        return retrieve_ontology_entities(
            description,
            top_k=top_k,
            category="unit",
            index_dir=index_dir
        )
    else:
        return list_entities_by_category("unit", index_dir=index_dir)


# Advanced search functions
def find_related_entities(
    entity_name: str,
    *,
    top_k: int = 5,
    index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR
) -> List[Dict[str, Any]]:
    """Find entities semantically related to the given entity.
    
    Args:
        entity_name: Name of the entity to find related items for
        top_k: Maximum number of results
        index_dir: Path to the ontology index
        
    Returns:
        List of related entities
    """
    entity = get_ontology_entity(entity_name, index_dir=index_dir)
    if not entity:
        return []
    
    # Use the entity's description and synonyms to find related entities
    search_text = f"{entity['description']} {' '.join(entity.get('synonyms', []))}"
    
    # Search excluding the original entity
    results = retrieve_ontology_entities(search_text, top_k=top_k + 1, index_dir=index_dir)
    return [r for r in results if r['name'].lower() != entity_name.lower()][:top_k]


def search_entities_with_description_containing(
    keywords: str,
    *,
    top_k: int = 10,
    category: Optional[str] = None,
    index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR
) -> List[Dict[str, Any]]:
    """Find entities whose descriptions contain specific keywords.
    
    This is useful for finding entities that mention specific concepts.
    
    Args:
        keywords: Keywords to search for in descriptions
        top_k: Maximum number of results
        category: Optional category filter
        index_dir: Path to the ontology index
        
    Returns:
        List of entities with matching descriptions
    """
    return retrieve_ontology_entities(
        f"description contains {keywords}",
        top_k=top_k,
        category=category,
        min_score=0.2,  # Lower threshold for broader matching
        index_dir=index_dir
    ) 