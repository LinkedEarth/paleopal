"""sparql_library.demo

Demonstration of the SPARQL library functionality.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from retrieve import (
    retrieve_sparql_queries,
    get_sparql_query, 
    list_query_categories,
    list_queries_by_category,
    get_query_template
)


def demo_basic_search():
    """Demonstrate basic SPARQL query search."""
    print("🔍 SPARQL Query Search Demo")
    print("=" * 50)
    
    # Example searches
    searches = [
        "find datasets by geographic location",
        "filter data by time period",
        "get dataset metadata and bibliographic information",
        "find variables and proxy data",
        "ensemble model queries"
    ]
    
    for search_query in searches:
        print(f"\nSearch: '{search_query}'")
        try:
            results = retrieve_sparql_queries(search_query, top_k=2)
            for result in results:
                print(f"  ✓ {result['name']} (score: {result['score']:.3f})")
                print(f"    Category: {result['category']}")
                print(f"    Description: {result['description'][:100]}...")
                if result.get('parameters'):
                    print(f"    Parameters: {', '.join(result['parameters'])}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        print()


def demo_category_filtering():
    """Demonstrate filtering queries by category."""
    print("📂 Category Filtering Demo")
    print("=" * 50)
    
    try:
        categories = list_query_categories()
        print(f"Available categories: {', '.join(categories)}")
        print()
        
        for category in categories[:3]:  # Show first 3 categories
            print(f"Queries in '{category}' category:")
            queries = list_queries_by_category(category)
            for q in queries[:3]:  # Show first 3 queries per category
                params = f" ({len(q['parameters'])} params)" if q['parameters'] else ""
                print(f"  • {q['name']}{params}")
            print()
            
    except Exception as e:
        print(f"❌ Error: {e}")


def demo_specific_query():
    """Demonstrate getting a specific query with parameters."""
    print("🎯 Specific Query Demo")
    print("=" * 50)
    
    # Example: Get geographic filter query
    query_name = "QUERY_FILTER_GEO"
    print(f"Getting query: {query_name}")
    
    try:
        # First, get the template to see parameters
        template = get_query_template(query_name)
        if template:
            print(f"Description: {template['description']}")
            print(f"Parameters: {template.get('parameters', [])}")
            print()
            
            # Get query with parameter substitution
            parameters = {
                'latMin': '40.0',
                'latMax': '50.0', 
                'lonMin': '-120.0',
                'lonMax': '-110.0'
            }
            
            query = get_sparql_query(query_name, parameters=parameters)
            if query:
                print("SPARQL Query with parameters:")
                print(query)
            else:
                print("Query not found")
        else:
            print(f"Query '{query_name}' not found")
            
    except Exception as e:
        print(f"❌ Error: {e}")


def demo_practical_example():
    """Demonstrate a practical example of using SPARQL queries."""
    print("🏗️ Practical Example Demo")
    print("=" * 50)
    
    print("Scenario: Find coral datasets in the Pacific Ocean")
    print()
    
    try:
        # Step 1: Find relevant filter queries
        print("1. Finding geographic filter queries...")
        geo_queries = retrieve_sparql_queries("filter by geographic coordinates", category="filter", top_k=1)
        
        if geo_queries:
            geo_query = geo_queries[0]
            print(f"   Found: {geo_query['name']}")
            
            # Step 2: Get the actual query with Pacific Ocean coordinates
            pacific_params = {
                'latMin': '-30.0',
                'latMax': '30.0',
                'lonMin': '120.0', 
                'lonMax': '-80.0'
            }
            
            sparql_query = get_sparql_query(geo_query['name'], parameters=pacific_params)
            print("   Generated SPARQL query for Pacific Ocean:")
            print("   " + sparql_query.replace('\n', '\n   '))
            print()
        
        # Step 3: Find dataset name queries 
        print("2. Finding dataset name filter queries...")
        name_queries = retrieve_sparql_queries("filter datasets by name", category="filter", top_k=1)
        
        if name_queries:
            name_query = name_queries[0]
            print(f"   Found: {name_query['name']}")
            
            # Get query for coral datasets
            coral_params = {'datasetName': 'coral'}
            coral_query = get_sparql_query(name_query['name'], parameters=coral_params)
            print("   Generated SPARQL query for coral datasets:")
            print("   " + coral_query.replace('\n', '\n   '))
            print()
            
        print("3. These queries can now be combined or used with a SPARQL endpoint")
        print("   to find coral datasets in the Pacific Ocean region.")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def run_full_demo():
    """Run the complete demonstration."""
    print("🧪 SPARQL Library Demo")
    print("=" * 60)
    print()
    
    # Check if index exists
    index_path = pathlib.Path(__file__).parent / "sparql_index"
    if not index_path.exists():
        print("❌ SPARQL index not found!")
        print("Please run the following command first:")
        print("   python -m libraries.sparql_library.index_queries")
        print()
        return
    
    try:
        demo_basic_search()
        print("\n" + "="*60 + "\n")
        
        demo_category_filtering() 
        print("\n" + "="*60 + "\n")
        
        demo_specific_query()
        print("\n" + "="*60 + "\n")
        
        demo_practical_example()
        
        print("\n" + "="*60)
        print("✅ Demo completed successfully!")
        print("\nNext steps:")
        print("- Use retrieve_sparql_queries() for semantic search")
        print("- Use get_sparql_query() for specific queries")
        print("- Use the CLI: python -m libraries.sparql_library.search_queries")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        print("Make sure the SPARQL index has been built first.")


if __name__ == "__main__":
    run_full_demo() 