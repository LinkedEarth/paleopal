from __future__ import annotations

"""readthedocs_library.search_code

Query the Qdrant index of ReadTheDocs code examples and return relevant snippets.
"""

from typing import List, Dict, Any, Optional
import pathlib
import sys

# Add parent directory to path for imports
current_dir = pathlib.Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from qdrant_config import get_qdrant_manager, COLLECTION_NAMES

DEFAULT_COLLECTION = COLLECTION_NAMES["readthedocs_code"]


def search_code(
    query: str,
    limit: int = 5,
    collection_name: str = None,
    code_type_filter: Optional[str] = None,
    library_filter: Optional[str] = None,
    symbol_filter: Optional[str] = None,
    score_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Search ReadTheDocs code examples.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return
        collection_name: Qdrant collection name (defaults to readthedocs_code)
        code_type_filter: Filter by code type (class_definition, function_definition, plotting_example, etc.)
        library_filter: Filter by library name (numpy, pandas, matplotlib, etc.)
        symbol_filter: Filter by symbol name
        score_threshold: Minimum similarity score threshold
        
    Returns:
        List of matching code examples with metadata and similarity scores
    """
    if collection_name is None:
        collection_name = DEFAULT_COLLECTION
    
    # Prepare filters
    filters = {}
    if code_type_filter:
        filters["code_type"] = code_type_filter
    if library_filter:
        filters["library"] = library_filter
    if symbol_filter:
        filters["symbol"] = symbol_filter
    
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
                "code": result.get("code", result.get("text", "")),
                "content": result.get("content", result.get("text", "")),
                "score": result["score"],
                "symbol": result.get("symbol", ""),
                "signature": result.get("signature", ""),
                "params": result.get("params", ""),
                "source": result.get("source", ""),
                "code_type": result.get("code_type", ""),
                "library": result.get("library", ""),
                # Include any additional metadata
                **{k: v for k, v in result.items() if k not in ["id", "code", "content", "text", "score"]}
            }
            formatted_results.append(formatted_result)
        
        return formatted_results
        
    except Exception as e:
        print(f"Search failed: {e}")
        return []


def find_plotting_examples(query: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """Find plotting/visualization code examples."""
    return search_code(
        query=query,
        limit=limit,
        code_type_filter="plotting_example"
    )


def find_function_examples(query: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """Find function definition examples."""
    return search_code(
        query=query,
        limit=limit,
        code_type_filter="function_definition"
    )


def find_class_examples(query: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """Find class definition examples."""
    return search_code(
        query=query,
        limit=limit,
        code_type_filter="class_definition"
    )


def find_import_examples(query: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """Find import statement examples."""
    return search_code(
        query=query,
        limit=limit,
        code_type_filter="import_example"
    )


def search_by_library(library: str, query: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """Search code examples from a specific library."""
    return search_code(
        query=query,
        limit=limit,
        library_filter=library
    )


def search_by_symbol(symbol: str, query: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """Search code examples for a specific symbol."""
    return search_code(
        query=query,
        limit=limit,
        symbol_filter=symbol
    )


def get_all_libraries(collection_name: str = None) -> List[str]:
    """Get all available library names in the collection."""
    if collection_name is None:
        collection_name = DEFAULT_COLLECTION
    
    # Get sample of documents to analyze
    sample_results = search_code("", limit=100, collection_name=collection_name)
    
    libraries = set()
    for result in sample_results:
        if result.get("library"):
            libraries.add(result["library"])
    
    return sorted(list(libraries))


def get_all_code_types(collection_name: str = None) -> List[str]:
    """Get all available code types in the collection."""
    if collection_name is None:
        collection_name = DEFAULT_COLLECTION
    
    # Get sample of documents to analyze
    sample_results = search_code("", limit=100, collection_name=collection_name)
    
    code_types = set()
    for result in sample_results:
        if result.get("code_type"):
            code_types.add(result["code_type"])
    
    return sorted(list(code_types))


# Legacy function for backward compatibility
def search(query: str, *, top_k: int = 5, index_dir: str | pathlib.Path = None) -> List[Dict[str, Any]]:
    """Legacy search function for backward compatibility."""
    return search_code(query, limit=top_k)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search ReadTheDocs code examples")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--collection", default=None, help="Collection name")
    parser.add_argument("--k", type=int, default=5, help="Number of results to return")
    parser.add_argument("--code-type", choices=["class_definition", "function_definition", "import_example", "plotting_example", "general_example"], help="Filter by code type")
    parser.add_argument("--library", help="Filter by library name")
    parser.add_argument("--symbol", help="Filter by symbol name")
    parser.add_argument("--list-libraries", action="store_true", help="List all available libraries")
    parser.add_argument("--list-code-types", action="store_true", help="List all available code types")
    args = parser.parse_args()

    if args.list_libraries:
        libraries = get_all_libraries(args.collection)
        print("Available libraries:")
        for lib in libraries:
            print(f"  - {lib}")
        sys.exit(0)
    
    if args.list_code_types:
        code_types = get_all_code_types(args.collection)
        print("Available code types:")
        for code_type in code_types:
            print(f"  - {code_type}")
        sys.exit(0)

    hits = search_code(
        query=args.query,
        limit=args.k,
        collection_name=args.collection,
        code_type_filter=args.code_type,
        library_filter=args.library,
        symbol_filter=args.symbol
    )
    
    if not hits:
        print("No results found.")
    else:
        for h in hits:
            print(f"Score {h['score']:.3f} | {h.get('symbol', 'Unknown symbol')}")
            if h.get('library'):
                print(f"  Library: {h['library']}")
            if h.get('code_type'):
                print(f"  Type: {h['code_type']}")
            if h.get('signature'):
                print(f"  Signature: {h['signature']}")
            if h.get('source'):
                print(f"  Source: {h['source']}")
            
            print("Code:")
            print(h['code'])
            print("-" * 80) 