from __future__ import annotations

"""notebook_library.synthesize_workflow

Given a natural-language query, propose a high-level workflow outline by:
1. Finding top relevant *steps* (individual recipe cells) via embedding search.
2. Ordering them using transition statistics learned from existing notebooks.
"""

from typing import List, Dict, Any, Tuple
import pathlib, json, collections

import faiss  # type: ignore
from sentence_transformers import SentenceTransformer  # type: ignore

DEFAULT_INDEX_DIR = pathlib.Path("notebook_index")
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"


def _load_model() -> SentenceTransformer:  # type: ignore
    if not hasattr(_load_model, "_m"):
        _load_model._m = SentenceTransformer(EMBED_MODEL_NAME)  # type: ignore
    return _load_model._m  # type: ignore


def _load_steps(index_dir: pathlib.Path):
    index_path = index_dir / "steps.faiss"
    meta_path = index_dir / "steps_meta.jsonl"
    if not index_path.exists() or not meta_path.exists():
        raise FileNotFoundError("Step index missing; re-run index_notebooks.py")

    index = faiss.read_index(str(index_path))
    metas: List[Dict[str, Any]] = []
    with meta_path.open() as f:
        for line in f:
            metas.append(json.loads(line))
    return index, metas


def _load_transitions(index_dir: pathlib.Path):
    path = index_dir / "step_transitions.json"
    if not path.exists():
        return {}
    with path.open() as f:
        nested: Dict[str, Dict[str, int]] = json.load(f)
    # flatten into tuple-key dict
    flat: Dict[Tuple[str, str], int] = {}
    for a, sub in nested.items():
        for b, cnt in sub.items():
            flat[(a, b)] = cnt
    return flat


def search_steps(query: str, *, top_k: int = 10, index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR) -> List[Dict[str, Any]]:
    index_dir = pathlib.Path(index_dir)
    index, metas = _load_steps(index_dir)
    model = _load_model()
    q_emb = model.encode([query], normalize_embeddings=True)
    scores, ids = index.search(q_emb, top_k)
    results: List[Dict[str, Any]] = []
    for score, idx in zip(scores[0], ids[0]):
        if idx == -1:
            continue
        m = metas[int(idx)].copy()
        m["score"] = float(score)
        results.append(m)
    return results


def propose_workflow(query: str, *, max_steps: int = 5, index_dir: str | pathlib.Path = DEFAULT_INDEX_DIR) -> List[str]:
    """Return list of step headings forming a workflow outline."""
    index_dir = pathlib.Path(index_dir)
    top_steps = search_steps(query, top_k=max_steps * 3, index_dir=index_dir)
    if not top_steps:
        return []

    # Start with highest-scoring step
    selected = [top_steps[0]]
    transitions = _load_transitions(index_dir)

    while len(selected) < max_steps:
        last_heading = selected[-1]["heading"]
        # candidates not yet chosen
        remaining = [s for s in top_steps if s not in selected]
        if not remaining:
            break

        # score remaining by transition frequency from last_heading *and* embedding score
        best = None
        best_score = -1.0
        for s in remaining:
            trans_score = transitions.get((last_heading, s["heading"]), 0)
            combined = trans_score + s["score"]  # simple additive fusion
            if combined > best_score:
                best_score = combined
                best = s
        if best is None:
            break
        selected.append(best)
    return [s["heading"] for s in selected]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Propose workflow outline from query")
    parser.add_argument("query")
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--index", default="notebook_index")
    args = parser.parse_args()

    outline = propose_workflow(args.query, max_steps=args.steps, index_dir=args.index)
    if not outline:
        print("No proposal found")
    else:
        for i, h in enumerate(outline, 1):
            print(f"Step {i}: {h}") 