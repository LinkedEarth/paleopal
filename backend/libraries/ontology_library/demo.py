"""ontology_library.demo

Demonstration of the ontology library functionality.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Dict, Any

# Add current directory to path for imports
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from retrieve import (
    retrieve_ontology_entities,
    get_ontology_entity,
    find_entities_by_synonym,
    list_ontology_categories,
    find_archive_types,
    find_paleo_variables,
    find_paleo_proxies,
    find_interpretation_variables,
    find_related_entities
)


def demo_basic_search():
    """Demonstrate basic ontology entity search."""
    print("🔍 Ontology Entity Search Demo")
    print("=" * 50)
    
    # Example searches
    searches = [
        "coral temperature proxy",
        "tree ring measurement",
        "lake sediment archive",
        "precipitation climate variable",
        "isotope analysis"
    ]
    
    for search_query in searches:
        print(f"\nSearch: '{search_query}'")
        try:
            results = retrieve_ontology_entities(search_query, top_k=3)
            for result in results:
                print(f"  ✓ {result['name']} [{result['entity_type']}] (score: {result['score']:.3f})")
                print(f"    Category: {result['category']}")
                print(f"    Description: {result['description'][:80]}...")
                if result.get('synonyms'):
                    syn_preview = result['synonyms'][:2]
                    print(f"    Synonyms: {', '.join(syn_preview)}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        print()


def demo_category_exploration():
    """Demonstrate exploring entities by category."""
    print("📂 Category Exploration Demo")
    print("=" * 50)
    
    try:
        categories = list_ontology_categories()
        print(f"Available categories: {', '.join(categories)}")
        print()
        
        # Show examples from each category
        category_functions = {
            'archive': find_archive_types,
            'variable': find_paleo_variables,
            'proxy': find_paleo_proxies,
            'interpretation': find_interpretation_variables
        }
        
        for category, func in category_functions.items():
            if category in categories:
                print(f"Sample {category} entities:")
                entities = func()[:3]  # Show first 3
                for e in entities:
                    syn_info = f" ({len(e['synonyms'])} synonyms)" if e.get('synonyms') else ""
                    print(f"  • {e['name']}{syn_info}")
                    print(f"    {e['description'][:60]}...")
                print()
                
    except Exception as e:
        print(f"❌ Error: {e}")


def demo_specific_entity():
    """Demonstrate getting a specific entity with details."""
    print("🎯 Specific Entity Demo")
    print("=" * 50)
    
    # Example: Get information about coral
    entity_name = "Coral"
    print(f"Getting entity: {entity_name}")
    
    try:
        entity = get_ontology_entity(entity_name)
        if entity:
            print(f"Name: {entity['name']}")
            print(f"Type: {entity['entity_type']}")
            print(f"Category: {entity['category']}")
            print(f"Description: {entity['description']}")
            print(f"Namespace: {entity.get('namespace', 'unknown')}")
            
            if entity.get('synonyms'):
                print(f"Synonyms ({len(entity['synonyms'])}): {', '.join(entity['synonyms'])}")
            
            print(f"URI: {entity.get('uri', 'No URI')}")
            print()
            
            # Find related entities
            print("Related entities:")
            related = find_related_entities(entity_name, top_k=3)
            for r in related:
                print(f"  → {r['name']} [{r['entity_type']}] (score: {r['score']:.3f})")
                
        else:
            print(f"Entity '{entity_name}' not found")
            
    except Exception as e:
        print(f"❌ Error: {e}")


def demo_synonym_search():
    """Demonstrate finding entities by synonyms."""
    print("🏷️ Synonym Search Demo")
    print("=" * 50)
    
    # Test different synonyms
    synonyms_to_test = ["ice cores", "SST", "tree", "d18O", "peat"]
    
    for synonym in synonyms_to_test:
        print(f"Searching for synonym: '{synonym}'")
        try:
            entities = find_entities_by_synonym(synonym, top_k=3)
            if entities:
                for e in entities:
                    print(f"  ✓ {e['name']} [{e['entity_type']}]")
                    print(f"    Matched synonym: '{e['matched_synonym']}'")
            else:
                print(f"  No entities found with synonym '{synonym}'")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        print()


def demo_practical_example():
    """Demonstrate a practical example of using the ontology."""
    print("🏗️ Practical Example Demo")
    print("=" * 50)
    
    print("Scenario: Finding information for coral-based temperature reconstruction")
    print()
    
    try:
        # Step 1: Find coral archive type
        print("1. Finding coral archive information...")
        coral_archives = find_archive_types("coral")
        if coral_archives:
            coral = coral_archives[0]
            print(f"   Archive Type: {coral['name']}")
            print(f"   Description: {coral['description']}")
            print(f"   Synonyms: {', '.join(coral.get('synonyms', []))}")
            print()
        
        # Step 2: Find temperature-related variables
        print("2. Finding temperature variables...")
        temp_vars = find_paleo_variables("temperature", top_k=2)
        for var in temp_vars:
            print(f"   Variable: {var['name']}")
            print(f"   Description: {var['description'][:80]}...")
        print()
        
        # Step 3: Find relevant proxies
        print("3. Finding coral-related proxies...")
        coral_proxies = find_paleo_proxies("coral", top_k=2)
        for proxy in coral_proxies:
            print(f"   Proxy: {proxy['name']}")
            print(f"   Description: {proxy['description'][:80]}...")
        print()
        
        # Step 4: Find interpretation variables
        print("4. Finding temperature interpretation...")
        temp_interp = find_interpretation_variables("temperature", top_k=2)
        for interp in temp_interp:
            print(f"   Interpretation: {interp['name']}")
            if interp.get('synonyms'):
                print(f"   Common synonyms: {', '.join(interp['synonyms'][:3])}")
        print()
        
        print("5. This information helps understand:")
        print("   - What coral archives are and their characteristics")
        print("   - How temperature can be measured and interpreted")
        print("   - What proxy measurements are relevant for coral")
        print("   - Standard terminology and synonyms used in the field")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def run_full_demo():
    """Run the complete demonstration."""
    print("🧪 Ontology Library Demo")
    print("=" * 60)
    print()
    
    # Check if index exists
    index_path = pathlib.Path(__file__).parent / "ontology_index"
    if not index_path.exists():
        print("❌ Ontology index not found!")
        print("Please run the following command first:")
        print("   python index_ontology.py")
        print()
        return
    
    try:
        demo_basic_search()
        print("\n" + "="*60 + "\n")
        
        demo_category_exploration() 
        print("\n" + "="*60 + "\n")
        
        demo_specific_entity()
        print("\n" + "="*60 + "\n")
        
        demo_synonym_search()
        print("\n" + "="*60 + "\n")
        
        demo_practical_example()
        
        print("\n" + "="*60)
        print("✅ Demo completed successfully!")
        print("\nNext steps:")
        print("- Use retrieve_ontology_entities() for semantic search")
        print("- Use get_ontology_entity() for specific entities")
        print("- Use find_entities_by_synonym() to explore terminology")
        print("- Use category-specific functions like find_archive_types()")
        print("- Use the CLI: python search_ontology.py")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        print("Make sure the ontology index has been built first.")


if __name__ == "__main__":
    run_full_demo() 