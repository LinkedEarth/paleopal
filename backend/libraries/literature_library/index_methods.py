from __future__ import annotations

"""literature_library.index_methods

Build a FAISS vector store for semantic search from extracted method JSON files.
Reads structured method files and creates embeddings for efficient similarity search.
"""

import pathlib
import re
import json
import logging
from typing import List, Dict, Any

try:
    import faiss  # type: ignore
except ImportError as e:
    raise ImportError("faiss-cpu is required: pip install faiss-cpu") from e

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except ImportError as e:
    raise ImportError("sentence-transformers is required: pip install sentence-transformers") from e

import os

LOG = logging.getLogger("lit-index")
logging.basicConfig(level=logging.INFO)

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"


def _load_model():
    if not hasattr(_load_model, "_m"):
        _load_model._m = SentenceTransformer(EMBED_MODEL_NAME)  # type: ignore
    return _load_model._m  # type: ignore


def clean_text(text: str) -> str:
    """Clean and normalize text for embedding."""
    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def extract_searchable_content(method_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract searchable content from method JSON data.
    Returns a list of records with text and metadata for indexing.
    """
    records = []
    
    if not method_data.get("methods_found", False):
        return records
    
    source_file = method_data.get("source_file", "")
    paper_title = method_data.get("paper_title", "Unknown")
    
    for method in method_data.get("methods", []):
        method_name = method.get("method_name", "")
        method_description = method.get("description", "")
        
        # Create a record for the overall method
        method_text = f"{method_name}. {method_description}"
        method_record = {
            "text": clean_text(method_text),
            "source_file": source_file,
            "paper_title": paper_title,
            "method_name": method_name,
            "method_description": method_description,
            "content_type": "method_overview",
            "step_number": None,
            "category": "method",
            "searchable_summary": f"Implement {method_name.lower()} methodology",
            "keywords": [],
            "inputs": [],
            "outputs": []
        }
        records.append(method_record)
        
        # Create records for each step
        for step in method.get("steps", []):
            step_text = " ".join([
                step.get("searchable_summary", ""),
                step.get("description", ""),
                " ".join(step.get("keywords", [])),
                method_name,
                method_description
            ])
            
            step_record = {
                "text": clean_text(step_text),
                "source_file": source_file,
                "paper_title": paper_title,
                "method_name": method_name,
                "method_description": method_description[:200] + "..." if len(method_description) > 200 else method_description,
                "content_type": "method_step",
                "step_number": step.get("step_number"),
                "category": step.get("category", "other"),
                "searchable_summary": step.get("searchable_summary", ""),
                "keywords": step.get("keywords", []),
                "inputs": step.get("inputs", []),
                "outputs": step.get("outputs", []),
                "step_description": step.get("description", "")
            }
            records.append(step_record)
    
    return records


def build_index_from_json_files(json_dir: pathlib.Path, out_dir: pathlib.Path) -> pathlib.Path:
    """
    Build FAISS index from extracted method JSON files.
    
    Args:
        json_dir: Directory containing *_methods.json files
        out_dir: Output directory for the index
    
    Returns:
        Path to the created index directory
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "methods_meta.jsonl"
    index_path = out_dir / "methods.faiss"
    
    # Find all method JSON files
    json_files = list(json_dir.glob("*_methods.json"))
    if not json_files:
        raise RuntimeError(f"No *_methods.json files found in {json_dir}")
    
    LOG.info(f"Found {len(json_files)} method JSON files")
    
    all_records: List[Dict[str, Any]] = []
    all_texts: List[str] = []
    
    for json_file in json_files:
        LOG.info(f"Processing {json_file.name}")
        
        try:
            with json_file.open(encoding='utf-8') as f:
                method_data = json.load(f)
            
            # Extract searchable content
            records = extract_searchable_content(method_data)
            
            if not records:
                LOG.warning(f"No searchable content extracted from {json_file.name}")
                continue
            
            # Add records and texts
            all_records.extend(records)
            all_texts.extend([record["text"] for record in records])
            
            LOG.info(f"Extracted {len(records)} searchable items from {json_file.name}")
            
        except Exception as e:
            LOG.error(f"Error processing {json_file.name}: {e}")
            continue
    
    if not all_records:
        raise RuntimeError("No searchable content extracted from JSON files")
    
    LOG.info(f"Total searchable items: {len(all_records)}")
    
    # Create embeddings
    LOG.info("Creating embeddings...")
    model = _load_model()
    embs = model.encode(all_texts, show_progress_bar=True, batch_size=32, normalize_embeddings=True)
    
    # Build FAISS index
    LOG.info("Building FAISS index...")
    dim = embs.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embs)
    faiss.write_index(index, str(index_path))
    
    # Save metadata
    LOG.info("Saving metadata...")
    with meta_path.open("w", encoding='utf-8') as f:
        for record in all_records:
            f.write(json.dumps(record) + "\n")
    
    LOG.info(f"Index built successfully with {len(all_records)} items → {out_dir}")
    return out_dir


def search_methods_index(
    query: str, 
    index_dir: pathlib.Path, 
    top_k: int = 10,
    category_filter: str = None
) -> List[Dict[str, Any]]:
    """
    Search the methods index for similar content.
    
    Args:
        query: Search query
        index_dir: Directory containing the index
        top_k: Number of results to return
        category_filter: Optional category filter (e.g., "data_fetch", "data_analysis")
    
    Returns:
        List of search results with metadata
    """
    index_path = index_dir / "methods.faiss"
    meta_path = index_dir / "methods_meta.jsonl"
    
    if not index_path.exists() or not meta_path.exists():
        raise RuntimeError(f"Index not found in {index_dir}")
    
    # Load index and metadata
    index = faiss.read_index(str(index_path))
    
    metadata = []
    with meta_path.open(encoding='utf-8') as f:
        for line in f:
            metadata.append(json.loads(line))
    
    # Create query embedding
    model = _load_model()
    query_embedding = model.encode([clean_text(query)], normalize_embeddings=True)
    
    # Search
    scores, indices = index.search(query_embedding, min(top_k * 2, len(metadata)))  # Get extra for filtering
    
    # Prepare results
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:  # No more results
            break
            
        result = metadata[idx].copy()
        result["similarity_score"] = float(score)
        
        # Apply category filter if specified
        if category_filter and result.get("category") != category_filter:
            continue
            
        results.append(result)
        
        if len(results) >= top_k:
            break
    
    return results


def create_index_summary(index_dir: pathlib.Path) -> Dict[str, Any]:
    """Create a summary of the index contents."""
    meta_path = index_dir / "methods_meta.jsonl"
    
    if not meta_path.exists():
        return {"error": "Metadata file not found"}
    
    # Load metadata
    metadata = []
    with meta_path.open(encoding='utf-8') as f:
        for line in f:
            metadata.append(json.loads(line))
    
    # Calculate statistics
    total_items = len(metadata)
    unique_papers = len(set(item.get("source_file", "") for item in metadata))
    unique_methods = len(set(item.get("method_name", "") for item in metadata if item.get("content_type") == "method_overview"))
    
    # Category distribution
    categories = {}
    content_types = {}
    
    for item in metadata:
        cat = item.get("category", "unknown")
        content_type = item.get("content_type", "unknown")
        
        categories[cat] = categories.get(cat, 0) + 1
        content_types[content_type] = content_types.get(content_type, 0) + 1
    
    summary = {
        "total_items": total_items,
        "unique_papers": unique_papers,
        "unique_methods": unique_methods,
        "categories": categories,
        "content_types": content_types,
        "papers": list(set(item.get("paper_title", "Unknown") for item in metadata if item.get("paper_title")))
    }
    
    return summary


if __name__ == "__main__":
    import argparse, sys
    
    parser = argparse.ArgumentParser(description="Build FAISS index from extracted method JSON files")
    parser.add_argument("json_dir", help="Directory containing *_methods.json files")
    parser.add_argument("--out", default="methods_index", help="Output index directory")
    parser.add_argument("--search", type=str, help="Search the index for similar methods")
    parser.add_argument("--top-k", type=int, default=10, help="Number of search results to return")
    parser.add_argument("--category", type=str, help="Filter results by category")
    parser.add_argument("--summary", action="store_true", help="Show index summary")
    
    args = parser.parse_args()
    
    json_dir = pathlib.Path(args.json_dir)
    out_dir = pathlib.Path(args.out)
    
    if not json_dir.exists():
        sys.exit(f"Directory {json_dir} does not exist")
    
    # Handle search functionality
    if args.search:
        if not out_dir.exists():
            sys.exit(f"Index directory {out_dir} does not exist. Build index first.")
        
        try:
            results = search_methods_index(
                args.search, 
                out_dir, 
                top_k=args.top_k,
                category_filter=args.category
            )
            
            print(f"\nFound {len(results)} results for '{args.search}':")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. [{result['similarity_score']:.3f}] {result['paper_title']}")
                print(f"   Method: {result['method_name']}")
                if result['content_type'] == 'method_step':
                    print(f"   Step {result['step_number']}: {result['searchable_summary']}")
                    print(f"   Category: {result['category']}")
                else:
                    print(f"   Description: {result['method_description']}")
                print(f"   Source: {result['source_file']}")
                
        except Exception as e:
            sys.exit(f"Search failed: {e}")
        
        sys.exit(0)
    
    # Handle summary functionality
    if args.summary:
        if not out_dir.exists():
            sys.exit(f"Index directory {out_dir} does not exist. Build index first.")
        
        summary = create_index_summary(out_dir)
        print("\nIndex Summary:")
        print(f"Total items: {summary['total_items']}")
        print(f"Unique papers: {summary['unique_papers']}")
        print(f"Unique methods: {summary['unique_methods']}")
        print(f"\nContent types: {summary['content_types']}")
        print(f"\nCategories: {summary['categories']}")
        print(f"\nPapers indexed:")
        for paper in summary['papers'][:10]:  # Show first 10
            print(f"  - {paper}")
        if len(summary['papers']) > 10:
            print(f"  ... and {len(summary['papers']) - 10} more")
        
        sys.exit(0)
    
    # Build index
    try:
        build_index_from_json_files(json_dir, out_dir)
        print(f"\nIndex built successfully in {out_dir}")
        
        # Show summary
        summary = create_index_summary(out_dir)
        print(f"\nIndexed {summary['total_items']} items from {summary['unique_papers']} papers")
        print(f"Found {summary['unique_methods']} unique methods")
        
    except Exception as e:
        sys.exit(f"Index building failed: {e}") 