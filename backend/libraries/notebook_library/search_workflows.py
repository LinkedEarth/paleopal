from __future__ import annotations

"""notebook_library.search_workflows

Query the FAISS index of notebook *workflows* produced by `index_notebooks.py`.
Each workflow corresponds to a whole notebook and its ordered recipe headings.
"""

from typing import List, Dict, Any
import pathlib
import json
import sys

import faiss  # type: ignore
from sentence_transformers import SentenceTransformer  # type: ignore

DEFAULT_INDEX_DIR = pathlib.Path("notebook_index")
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"


def _load_model() -> SentenceTransformer:  # type: ignore
    if not hasattr(_load_model, "_model"):
        _load_model._model = SentenceTransformer(EMBED_MODEL_NAME)  # type: ignore
    return _load_model._model  # type: ignore


def _load_index(index_dir: pathlib.Path):
    index_path = index_dir / "workflows.faiss"
    meta_path = index_dir / "workflows_meta.jsonl"
    if not index_path.exists() or not meta_path.exists():
        raise FileNotFoundError(f"workflow index not found in {index_dir}; run index_notebooks.py first")

    index = faiss.read_index(str(index_path))
    metas: List[Dict[str, Any]] = []
    with meta_path.open() as f:
        for line in f:
            metas.append(json.loads(line))
    return index, metas


def search_workflows(query: str, *, top_k: int = 5, index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR) -> List[Dict[str, Any]]:
    index_dir = pathlib.Path(index_dir)
    index, metas = _load_index(index_dir)

    model = _load_model()
    q_emb = model.encode([query], normalize_embeddings=True)
    scores, ids = index.search(q_emb, top_k)
    results: List[Dict[str, Any]] = []
    for score, idx in zip(scores[0], ids[0]):
        if idx == -1:
            continue
        m = metas[int(idx)].copy()
        m["score"] = float(score)
        m["similarity_score"] = float(score)  # Add alias for consistency
        
        # Enhanced metadata for workflow manager integration
        m["title"] = pathlib.Path(m.get("notebook", "")).stem
        m["step_count"] = len(m.get("steps", []))
        
        # Extract workflow steps for better context
        workflow_steps = []
        for step in m.get("steps", []):
            step_desc = step.get("markdown_context", "").split('\n')[0]
            workflow_steps.append({
                "step_description": step_desc,
                "code_cell": bool(step.get("code_cell")),
                "code_preview": step.get("code_cell", "")[:100] + "..." if len(step.get("code_cell", "")) > 100 else step.get("code_cell", "")
            })
        m["workflow_steps"] = workflow_steps
        
        # Add description from notebook context
        if "description" not in m and m.get("steps"):
            first_step = m["steps"][0]
            m["description"] = first_step.get("markdown_context", "").split('\n')[0]
        
        results.append(m)
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search notebook workflow index")
    parser.add_argument("index_dir", nargs="?", default="notebook_index", help="Index directory path")
    parser.add_argument("--search", type=str, help="Search query")
    parser.add_argument("--query", type=str, help="Search query (alias for --search)")
    parser.add_argument("--top-k", "--k", type=int, default=5, help="Number of results to return")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    
    args = parser.parse_args()
    
    # Handle positional query argument for backward compatibility
    query = args.search or args.query
    if not query and len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        # If first non-flag argument looks like a query, use it
        if args.index_dir and not pathlib.Path(args.index_dir).exists():
            query = args.index_dir
            args.index_dir = "notebook_index"

    if not query:
        parser.error("Search query is required. Use --search 'your query' or --query 'your query'")

    try:
        hits = search_workflows(query, top_k=args.top_k, index_dir=args.index_dir)
        
        if args.format == "json":
            print(json.dumps(hits, indent=2))
        else:
            # Original text format
            for h in hits:
                print(f"Score {h['score']:.3f} | {pathlib.Path(h['notebook']).name}")
                steps_preview = ", ".join(step['markdown_context'].split('\n')[0] for step in h['steps'][:6])
                print("Steps:", steps_preview)
                print("-" * 80)
                
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1) 