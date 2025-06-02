from __future__ import annotations

"""notebook_library.workflow_context

Utilities to build a rich, LLM-ready markdown prompt for a synthesized workflow.
For each step we include:
  • Step heading (name)
  • Step description (markdown heading line)
  • Example code from the originating notebook step
  • Top matching example code from the ReadTheDocs code index
"""

from typing import List, Dict, Any
import pathlib
import json

from synthesize_workflow import propose_workflow, search_steps, _load_steps

# Import readthedocs code search lazily to avoid hard dependency if not present
try:
    from readthedocs_library.search_code import search_code  # type: ignore
except ImportError:  # pragma: no cover
    search_code = None  # type: ignore


DEFAULT_NOTEBOOK_INDEX = pathlib.Path("notebook_index")
DEFAULT_RTD_CODE_INDEX = pathlib.Path("rtd_code_index")


def _load_snippet_code(index_dir: pathlib.Path, snippet_id: str) -> str:
    meta_path = index_dir / "snippets_meta.jsonl"
    if not meta_path.exists():
        return ""
    with meta_path.open() as f:
        for line in f:
            meta = json.loads(line)
            if meta.get("id") == snippet_id:
                return meta.get("code", "")
    return ""


def build_workflow_markdown(
    query: str,
    *,
    steps: int = 5,
    notebook_index: str | pathlib.Path = DEFAULT_NOTEBOOK_INDEX,
    rtd_code_index: str | pathlib.Path = DEFAULT_RTD_CODE_INDEX,
) -> str:
    nb_index = pathlib.Path(notebook_index)
    outline_ids = propose_workflow(query, max_steps=steps, index_dir=nb_index)

    if not outline_ids:
        return "No workflow could be synthesized."

    # Need mapping from heading to step meta to get ids
    # Retrieve top step metas again to access snippet ids
    step_results = search_steps(query, top_k=steps * 3, index_dir=nb_index)
    heading_to_meta = {s["heading"]: s for s in step_results}

    md_parts: List[str] = [f"## Proposed Workflow for: {query}\n"]

    for i, heading in enumerate(outline_ids, 1):
        meta = heading_to_meta.get(heading, {})
        md_parts.append(f"### Step {i}: {heading}\n")

        # Notebook example code
        nb_code = _load_snippet_code(nb_index, meta.get("id", "")) if meta else ""
        if nb_code:
            md_parts.append("*Example from notebooks:*\n")
            md_parts.append("```python\n" + nb_code.strip() + "\n```\n")

        # ReadTheDocs code example
        if search_code is not None:
            rtd_hits = search_code(heading, top_k=1, index_dir=rtd_code_index)
            if rtd_hits:
                md_parts.append("*Example from library docs:*\n")
                md_parts.append("```python\n" + rtd_hits[0]["code"].strip() + "\n```\n")

    return "\n".join(md_parts)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build workflow markdown for LLM context")
    parser.add_argument("query")
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--nb-index", default="notebook_index")
    parser.add_argument("--rtd-code-index", default="rtd_code_index")
    args = parser.parse_args()

    md = build_workflow_markdown(
        args.query,
        steps=args.steps,
        notebook_index=args.nb_index,
        rtd_code_index=args.rtd_code_index,
    )
    print(md) 