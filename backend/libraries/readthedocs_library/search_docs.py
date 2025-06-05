"""readthedocs_library.search_docs

Query the Qdrant index of ReadTheDocs embeddings and return top-k chunks.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
import pathlib
import sys

# Add parent directory to path for imports
current_dir = pathlib.Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from qdrant_config import get_qdrant_manager, COLLECTION_NAMES

DEFAULT_COLLECTION = COLLECTION_NAMES["readthedocs_docs"]


def search_docs(
    query: str,
    limit: int = 5,
    collection_name: str = None,
    doc_type_filter: Optional[str] = None,
    library_filter: Optional[str] = None,
    section_filter: Optional[str] = None,
    score_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Search ReadTheDocs documentation.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return
        collection_name: Qdrant collection name (defaults to readthedocs_docs)
        doc_type_filter: Filter by document type (code_example, api_reference, tutorial, general)
        library_filter: Filter by library name (pyleoclim, pylipd, etc.)
        section_filter: Filter by section
        score_threshold: Minimum similarity score threshold
        
    Returns:
        List of matching documents with metadata and similarity scores
    """
    if collection_name is None:
        collection_name = DEFAULT_COLLECTION
    
    # Prepare filters
    filters = {}
    if doc_type_filter:
        filters["doc_type"] = doc_type_filter
    if library_filter:
        filters["library"] = library_filter
    if section_filter:
        filters["section"] = section_filter
    
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
                "content": result.get("content", result.get("text", "")),
                "score": result["score"],
                "source": result.get("source", ""),
                "title": result.get("title", ""),
                "doc_type": result.get("doc_type", ""),
                "library": result.get("library", ""),
                "section": result.get("section", ""),
                # Include any additional metadata
                **{k: v for k, v in result.items() if k not in ["id", "content", "text", "score"]}
            }
            formatted_results.append(formatted_result)
        
        return formatted_results
        
    except Exception as e:
        print(f"Search failed: {e}")
        return []


def find_code_examples(query: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """Find code examples in documentation."""
    return search_docs(
        query=query,
        limit=limit,
        doc_type_filter="code_example"
    )


def find_api_docs(query: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """Find API reference documentation."""
    return search_docs(
        query=query,
        limit=limit,
        doc_type_filter="api_reference"
    )


def find_tutorials(query: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """Find tutorial documentation."""
    return search_docs(
        query=query,
        limit=limit,
        doc_type_filter="tutorial"
    )


def search_by_library(library: str, query: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """Search within a specific library's documentation."""
    return search_docs(
        query=query,
        limit=limit,
        library_filter=library
    )


def get_all_libraries(collection_name: str = None) -> List[str]:
    """Get all available library names in the collection."""
    if collection_name is None:
        collection_name = DEFAULT_COLLECTION
    
    # Get sample of documents to analyze
    sample_results = search_docs("", limit=100, collection_name=collection_name)
    
    libraries = set()
    for result in sample_results:
        if result.get("library"):
            libraries.add(result["library"])
    
    return sorted(list(libraries))


def get_all_doc_types(collection_name: str = None) -> List[str]:
    """Get all available document types in the collection."""
    if collection_name is None:
        collection_name = DEFAULT_COLLECTION
    
    # Get sample of documents to analyze
    sample_results = search_docs("", limit=100, collection_name=collection_name)
    
    doc_types = set()
    for result in sample_results:
        if result.get("doc_type"):
            doc_types.add(result["doc_type"])
    
    return sorted(list(doc_types))


# Legacy function for backward compatibility
def search(query: str, *, top_k: int = 5, index_dir: str | pathlib.Path = None) -> List[Dict[str, Any]]:
    """Legacy search function for backward compatibility."""
    return search_docs(query, limit=top_k)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search ReadTheDocs Qdrant index")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--collection", default=None, help="Collection name")
    parser.add_argument("--k", type=int, default=5, help="Number of results to return")
    parser.add_argument("--doc-type", choices=["code_example", "api_reference", "tutorial", "general"], help="Filter by document type")
    parser.add_argument("--library", help="Filter by library name")
    parser.add_argument("--section", help="Filter by section")
    parser.add_argument("--preview", type=int, default=200, help="Number of characters to preview (0 for full)")
    parser.add_argument("--list-libraries", action="store_true", help="List all available libraries")
    parser.add_argument("--list-doc-types", action="store_true", help="List all available document types")
    args = parser.parse_args()

    if args.list_libraries:
        libraries = get_all_libraries(args.collection)
        print("Available libraries:")
        for lib in libraries:
            print(f"  - {lib}")
        sys.exit(0)
    
    if args.list_doc_types:
        doc_types = get_all_doc_types(args.collection)
        print("Available document types:")
        for doc_type in doc_types:
            print(f"  - {doc_type}")
        sys.exit(0)

    hits = search_docs(
        query=args.query,
        limit=args.k,
        collection_name=args.collection,
        doc_type_filter=args.doc_type,
        library_filter=args.library,
        section_filter=args.section
    )
    
    if not hits:
        print("No results found.")
    else:
        preview_len = args.preview
        for h in hits:
            print(f"Score {h['score']:.3f} | {h.get('source', 'Unknown source')}")
            if h.get('library'):
                print(f"  Library: {h['library']}")
            if h.get('doc_type'):
                print(f"  Type: {h['doc_type']}")
            if h.get('section'):
                print(f"  Section: {h['section']}")
            
            content = h['content']
            if preview_len > 0:
                content = content[:preview_len]
            print(content)
            print("-" * 80) 