from __future__ import annotations

"""readthedocs_library.search_symbols

Query the Qdrant symbol index built by `index_symbols.py` and return the top-k hits.
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

# Optional lexical ranking for hybrid search
try:
    from rank_bm25 import BM25Okapi  # type: ignore
except ImportError:
    BM25Okapi = None  # type: ignore

DEFAULT_COLLECTION = COLLECTION_NAMES["readthedocs_symbols"]


def search_symbols(
    query: str,
    limit: int = 5,
    collection_name: str = None,
    symbol_type_filter: Optional[str] = None,
    library_filter: Optional[str] = None,
    kind_filter: Optional[str] = None,
    score_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Search ReadTheDocs symbols.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return
        collection_name: Qdrant collection name (defaults to readthedocs_symbols)
        symbol_type_filter: Filter by symbol type (class, function, attribute, module, other)
        library_filter: Filter by library name (numpy, pandas, matplotlib, etc.)
        kind_filter: Filter by original kind field from documentation
        score_threshold: Minimum similarity score threshold
        
    Returns:
        List of matching symbols with metadata and similarity scores
    """
    if collection_name is None:
        collection_name = DEFAULT_COLLECTION
    
    # Prepare filters
    filters = {}
    if symbol_type_filter:
        filters["symbol_type"] = symbol_type_filter
    if library_filter:
        filters["library"] = library_filter
    if kind_filter:
        filters["kind"] = kind_filter
    
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
                "narrative": result.get("narrative", result.get("text", "")),
                "score": result["score"],
                "symbol": result.get("symbol", ""),
                "kind": result.get("kind", ""),
                "signature": result.get("signature", ""),
                "params": result.get("params", ""),
                "code": result.get("code", ""),
                "source": result.get("source", ""),
                "symbol_type": result.get("symbol_type", ""),
                "library": result.get("library", ""),
                # Include any additional metadata
                **{k: v for k, v in result.items() if k not in [
                    "id", "content", "narrative", "text", "score", "symbol", "kind", 
                    "signature", "params", "code", "source", "symbol_type", "library"
                ]}
            }
            formatted_results.append(formatted_result)
        
        return formatted_results
        
    except Exception as e:
        print(f"Search failed: {e}")
        return []


def find_classes(query: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """Find class symbols."""
    return search_symbols(
        query=query,
        limit=limit,
        symbol_type_filter="class"
    )


def find_functions(query: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """Find function/method symbols."""
    return search_symbols(
        query=query,
        limit=limit,
        symbol_type_filter="function"
    )


def find_attributes(query: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """Find attribute/property symbols."""
    return search_symbols(
        query=query,
        limit=limit,
        symbol_type_filter="attribute"
    )


def search_by_library(library: str, query: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """Search symbols from a specific library."""
    return search_symbols(
        query=query,
        limit=limit,
        library_filter=library
    )


def get_all_libraries(collection_name: str = None) -> List[str]:
    """Get all available library names in the collection."""
    if collection_name is None:
        collection_name = DEFAULT_COLLECTION
    
    # Get sample of documents to analyze
    sample_results = search_symbols("", limit=100, collection_name=collection_name)
    
    libraries = set()
    for result in sample_results:
        if result.get("library"):
            libraries.add(result["library"])
    
    return sorted(list(libraries))


def get_all_symbol_types(collection_name: str = None) -> List[str]:
    """Get all available symbol types in the collection."""
    if collection_name is None:
        collection_name = DEFAULT_COLLECTION
    
    # Get sample of documents to analyze
    sample_results = search_symbols("", limit=100, collection_name=collection_name)
    
    symbol_types = set()
    for result in sample_results:
        if result.get("symbol_type"):
            symbol_types.add(result["symbol_type"])
    
    return sorted(list(symbol_types))


# Legacy function for backward compatibility
def search(query: str, *, top_k: int = 5, index_dir: str | pathlib.Path = None) -> List[Dict[str, Any]]:
    """Legacy search function for backward compatibility."""
    return search_symbols(query, limit=top_k)


# -----------------------------------------------------------------------------
# Hybrid dense + lexical search ------------------------------------------------
# -----------------------------------------------------------------------------

_BM25_CACHE: Dict[str, BM25Okapi] = {}


def _get_bm25(collection_name: str):
    """Get or create BM25 index for hybrid search."""
    if BM25Okapi is None:
        raise RuntimeError("rank_bm25 is not installed: pip install rank_bm25")

    if collection_name in _BM25_CACHE:
        return _BM25_CACHE[collection_name]

    # Get all documents to build corpus
    all_symbols = search_symbols("", limit=1000, collection_name=collection_name)

    corpus_tokens = []
    for symbol in all_symbols:
        text = f"{symbol.get('symbol','')} {symbol.get('signature','')} {symbol.get('narrative','')}"
        tokens = text.lower().split()
        corpus_tokens.append(tokens)

    bm25 = BM25Okapi(corpus_tokens)
    _BM25_CACHE[collection_name] = bm25
    return bm25, all_symbols


def search_symbols_hybrid(
    query: str,
    *,
    top_k_dense: int = 5,
    top_k_lex: int = 5,
    collection_name: str = None,
    symbol_type_filter: Optional[str] = None,
    library_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Return merged dense + BM25 results (deduplicated)."""
    if collection_name is None:
        collection_name = DEFAULT_COLLECTION

    # Get dense search results
    dense_hits = search_symbols(
        query, 
        limit=top_k_dense, 
        collection_name=collection_name,
        symbol_type_filter=symbol_type_filter,
        library_filter=library_filter
    )

    # Get lexical search results if BM25 is available
    lex_hits: List[Dict[str, Any]] = []
    if top_k_lex and BM25Okapi is not None:
        try:
            bm25, all_symbols = _get_bm25(collection_name)
            query_tokens = query.lower().split()
            scores = bm25.get_scores(query_tokens)
            top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k_lex]
            
            for i in top_idx:
                if i < len(all_symbols) and scores[i] > 0:
                    symbol = all_symbols[i].copy()
                    symbol["score_lex"] = float(scores[i])
                    symbol["score"] = float(scores[i])  # Override for consistency
                    
                    # Apply filters
                    if symbol_type_filter and symbol.get("symbol_type") != symbol_type_filter:
                        continue
                    if library_filter and symbol.get("library") != library_filter:
                        continue
                    
                    lex_hits.append(symbol)
                    
        except Exception as e:
            print(f"BM25 search failed: {e}")

    # Merge results by symbol name, avoiding duplicates
    merged_results: List[Dict[str, Any]] = []
    seen_symbols = set()

    def get_symbol_key(hit: Dict[str, Any]) -> str:
        return hit.get("symbol", "") or hit.get("signature", "")

    # Add dense hits first (they're usually better quality)
    for hit in dense_hits:
        symbol_key = get_symbol_key(hit)
        if symbol_key and symbol_key not in seen_symbols:
            seen_symbols.add(symbol_key)
            merged_results.append(hit)

    # Add lexical hits if not already included
    for hit in lex_hits:
        symbol_key = get_symbol_key(hit)
        if symbol_key and symbol_key not in seen_symbols:
            seen_symbols.add(symbol_key)
            merged_results.append(hit)

    return merged_results[:max(top_k_dense, top_k_lex)]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search ReadTheDocs symbol index")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--collection", default=None, help="Collection name")
    parser.add_argument("--k", type=int, default=5, help="Number of results to return")
    parser.add_argument("--symbol-type", choices=["class", "function", "attribute", "module", "other"], help="Filter by symbol type")
    parser.add_argument("--library", help="Filter by library name")
    parser.add_argument("--kind", help="Filter by kind field")
    parser.add_argument("--show-code", action="store_true", help="Include example code in output")
    parser.add_argument("--hybrid", action="store_true", help="Use hybrid dense+lexical search")
    parser.add_argument("--list-libraries", action="store_true", help="List all available libraries")
    parser.add_argument("--list-symbol-types", action="store_true", help="List all available symbol types")
    args = parser.parse_args()

    if args.list_libraries:
        libraries = get_all_libraries(args.collection)
        print("Available libraries:")
        for lib in libraries:
            print(f"  - {lib}")
        sys.exit(0)
    
    if args.list_symbol_types:
        symbol_types = get_all_symbol_types(args.collection)
        print("Available symbol types:")
        for symbol_type in symbol_types:
            print(f"  - {symbol_type}")
        sys.exit(0)

    if args.hybrid:
        hits = search_symbols_hybrid(
            args.query,
            top_k_dense=args.k,
            top_k_lex=args.k,
            collection_name=args.collection,
            symbol_type_filter=args.symbol_type,
            library_filter=args.library
        )
    else:
        hits = search_symbols(
            query=args.query,
            limit=args.k,
            collection_name=args.collection,
            symbol_type_filter=args.symbol_type,
            library_filter=args.library,
            kind_filter=args.kind
        )
    
    if not hits:
        print("No results found.")
    else:
        for h in hits:
            print(f"Score {h['score']:.3f} | {h.get('symbol', 'Unknown symbol')}")
            if h.get('library'):
                print(f"  Library: {h['library']}")
            if h.get('symbol_type'):
                print(f"  Type: {h['symbol_type']}")
            if h.get('kind'):
                print(f"  Kind: {h['kind']}")
            if h.get('signature'):
                print(f"  Signature: {h['signature']}")
            if h.get('source'):
                print(f"  Source: {h['source']}")
            
            content = h['content'][:400].replace("\n", " ")
            print(content)
            
            if args.show_code and h.get("code"):
                print("```python\n" + h["code"][:400] + "\n```")
            print("-" * 80) 