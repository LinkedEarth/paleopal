"""ontology_library.index_ontology

Parse ontology entities from JSON data and create a searchable Qdrant index.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
from typing import List, Dict, Any, Optional
import uuid
import sys

# Add parent directory to path for imports
current_dir = pathlib.Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from qdrant_config import get_qdrant_manager, COLLECTION_NAMES

DEFAULT_DATA_FILE = pathlib.Path("ontology/indexing_data.json")


def map_entity_type_to_category(entity_type: str) -> str:
    """Map ontology entity types to broader categories."""
    type_mapping = {
        "ArchiveType": "archive",
        "InterpretationSeasonality": "interpretation", 
        "InterpretationVariable": "interpretation",
        "PaleoProxy": "proxy",
        "PaleoProxyGeneral": "proxy",
        "PaleoUnit": "unit",
        "PaleoVariable": "variable"
    }
    return type_mapping.get(entity_type, "other")


def clean_text(text: str) -> str:
    """Clean and normalize text for better indexing."""
    if not text:
        return ""
    
    # Remove extra whitespace and normalize
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Remove special characters but keep important ones
    text = re.sub(r'[^\w\s\-\.\(\)\/]', ' ', text)
    
    return text


def extract_namespace_from_uri(uri: str) -> str:
    """Extract namespace from a URI."""
    if not uri:
        return ""
    
    # Common patterns for extracting namespace
    if "#" in uri:
        return uri.split("#")[0].split("/")[-1]
    elif "/" in uri:
        parts = uri.split("/")
        return parts[-2] if len(parts) > 1 else parts[-1]
    
    return uri


def parse_ontology_entities(data_file: pathlib.Path) -> List[Dict[str, Any]]:
    """Parse ontology entities from JSON file."""
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    entities = []
    
    for item in data:
        entity_type = item.get("type", "")
        entity_id = item.get("id", "")
        name = clean_text(item.get("name", ""))
        description = clean_text(item.get("description", ""))
        synonyms = item.get("synonyms", [])
        full_text = clean_text(item.get("full_text", ""))
        
        if not name and not description:
            continue  # Skip entities without useful text
        
        # Clean synonyms
        clean_synonyms = [clean_text(syn) for syn in synonyms if syn and syn.strip()]
        
        # Extract namespace from URI-like IDs
        namespace = extract_namespace_from_uri(entity_id)
        
        # Create comprehensive search text
        search_components = [name, description, full_text]
        search_components.extend(clean_synonyms)
        search_text = " ".join([comp for comp in search_components if comp])
        
        # Map to category
        category = map_entity_type_to_category(entity_type)
        
        # Create entity document
        entity = {
            "id": str(uuid.uuid4()),
            "entity_id": entity_id,
            "name": name,
            "type": entity_type,
            "category": category,
            "description": description,
            "synonyms": clean_synonyms,
            "namespace": namespace,
            "full_text": full_text,
            "text": search_text,  # For Qdrant indexing
            "synonyms_count": len(clean_synonyms)
        }
        
        entities.append(entity)
    
    return entities


def build_index(
    data_file: pathlib.Path = DEFAULT_DATA_FILE,
    collection_name: str = None,
    force_recreate: bool = False
) -> bool:
    """Build Qdrant index from ontology entities in JSON file."""
    
    if not data_file.exists():
        raise FileNotFoundError(f"Ontology data file not found: {data_file}")
    
    # Use default collection name if not provided
    if collection_name is None:
        collection_name = COLLECTION_NAMES["ontology"]
    
    # Parse ontology entities
    print(f"Parsing {data_file.name}...")
    entities = parse_ontology_entities(data_file)
    
    if not entities:
        raise ValueError("No ontology entities found in JSON file")
    
    print(f"Found {len(entities)} ontology entities")
    
    # Print category breakdown
    category_counts = {}
    type_counts = {}
    for entity in entities:
        category = entity["category"]
        entity_type = entity["type"]
        category_counts[category] = category_counts.get(category, 0) + 1
        type_counts[entity_type] = type_counts.get(entity_type, 0) + 1
    
    print("Entity breakdown by category:")
    for category, count in sorted(category_counts.items()):
        print(f"  {category}: {count} entities")
    
    print("Entity breakdown by type:")
    for entity_type, count in sorted(type_counts.items()):
        print(f"  {entity_type}: {count} entities")
    
    # Get Qdrant manager
    qdrant_manager = get_qdrant_manager()
    
    # Create collection
    if not qdrant_manager.create_collection(collection_name, force_recreate=force_recreate):
        raise RuntimeError(f"Failed to create collection: {collection_name}")
    
    # Index documents
    indexed_count = qdrant_manager.index_documents(
        collection_name=collection_name,
        documents=entities,
        text_field="text"
    )
    
    print(f"Built index with {indexed_count} entities in collection: {collection_name}")
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Index ontology entities from JSON into Qdrant")
    parser.add_argument("--data-file", default="ontology/indexing_data.json", help="Path to ontology JSON data file")
    parser.add_argument("--collection", default=None, help="Qdrant collection name (default: ontology_entities)")
    parser.add_argument("--force-recreate", action="store_true", help="Force recreate collection if it exists")
    parser.add_argument("--test-search", type=str, help="Test search with a query")
    
    args = parser.parse_args()
    
    data_file = pathlib.Path(args.data_file)
    
    if args.test_search:
        # Test search functionality
        from search_ontology import search_entities
        results = search_entities(args.test_search, limit=5)
        print(f"\nSearch results for '{args.test_search}':")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result['name']} (score: {result['score']:.3f})")
            print(f"   Type: {result['type']} | Category: {result['category']}")
            print(f"   Description: {result['description'][:100]}...")
            if result['synonyms']:
                print(f"   Synonyms: {', '.join(result['synonyms'][:3])}")
            print()
    else:
        # Build index
        try:
            build_index(
                data_file=data_file,
                collection_name=args.collection,
                force_recreate=args.force_recreate
            )
            print("✅ Ontology entity index built successfully")
        except Exception as e:
            print(f"❌ Failed to build index: {e}")
            sys.exit(1) 