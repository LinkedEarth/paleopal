#!/usr/bin/env python3
"""Test the Code agent against the new notebook parent-child architecture.

Shows:
  1) raw retrieval payloads (snippets + parent summaries / expand path)
  2) the formatted context string that generate_code_node sends to the LLM
  3) optionally the generated code response (--generate)

Run from the backend directory (with paleopal env + Qdrant up):

  cd backend
  python -m agents.code.test_code_agent_context \\
      "load a LiPD dataset from a URL with PyLiPD"

  python -m agents.code.test_code_agent_context \\
      "run spectral analysis with pyleoclim Series" --generate --out /tmp/code_agent_test.json

  python -m agents.code.test_code_agent_context \\
      "validate GMST reconstruction against HadCRUT" -k 3 --generate --provider openai
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
import textwrap
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Ensure backend/ is on sys.path when run as a script or module
BACKEND_DIR = pathlib.Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
LIBRARIES_DIR = BACKEND_DIR / "libraries"
if str(LIBRARIES_DIR) not in sys.path:
    sys.path.insert(0, str(LIBRARIES_DIR))

# Prefer local embedding cache (avoids HuggingFace downloads during tests)
_MODEL_CACHE = BACKEND_DIR / "models_cache"
if _MODEL_CACHE.is_dir():
    import os

    os.environ.setdefault("MODEL_CACHE_DIR", str(_MODEL_CACHE))
    os.environ.setdefault("HF_HOME", str(_MODEL_CACHE))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(_MODEL_CACHE))
    os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(_MODEL_CACHE))
    local_model = _MODEL_CACHE / "all-MiniLM-L6-v2"
    if local_model.is_dir():
        os.environ.setdefault("EMBED_MODEL", str(local_model))
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def _truncate(text: str, n: int = 400) -> str:
    text = text or ""
    return text if len(text) <= n else text[: n - 1] + "…"


def _summarize_snippet(s: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": s.get("id"),
        "score": s.get("score") or s.get("similarity_score"),
        "retrieval": s.get("retrieval"),
        "title": s.get("title") or s.get("heading"),
        "notebook_path": s.get("notebook_path") or s.get("notebook") or s.get("relative_path"),
        "project_id": s.get("project_id"),
        "phase": s.get("phase"),
        "parent_title": s.get("parent_title"),
        "parent_summary": _truncate(s.get("parent_summary") or "", 240),
        "comments": (s.get("comments") or [])[:5],
        "imports": (s.get("imports") or [])[:8],
        "cell_indices": s.get("cell_indices"),
        "code_preview": _truncate(s.get("code") or "", 350),
    }


def print_section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


async def collect_context(query: str, top_k: int) -> Dict[str, Any]:
    from services.search_integration_service import search_service
    from libraries.notebook_library.search_snippets import search_with_parent_context

    # What the Code agent actually calls
    context_data = await search_service.get_context_for_code_generation(
        user_query=query,
        previous_code="",
    )

    # Explicit parent-child view (architecture under test)
    parent_child = search_with_parent_context(
        query,
        summary_limit=max(2, top_k),
        snippets_per_parent=2,
        direct_snippet_limit=top_k,
    )

    formatted = search_service.format_code_context_for_llm(context_data)

    return {
        "query": query,
        "context_data": context_data,
        "parent_child": parent_child,
        "formatted_context_for_llm": formatted,
    }


async def run_generate(
    query: str,
    context_bundle: Dict[str, Any],
    *,
    provider: str,
    model: Optional[str],
    use_two_step: bool,
) -> Dict[str, Any]:
    from agents.code.state import CodeAgentState
    from agents.code.handlers import search_code_examples_node, generate_code_node
    from services.service_manager import service_manager

    llm = service_manager.get_llm_provider(provider=provider, model=model)
    conversation_id = f"test-code-agent-{uuid.uuid4().hex[:8]}"

    state = CodeAgentState(
        user_input=query,
        analysis_request=query,
        analysis_type="general",
        output_format="notebook",
        conversation_id=conversation_id,
        needs_clarification=False,
        contextual_search_data=context_bundle["context_data"],
    )

    config = {
        "configurable": {
            "llm": llm,
            "enable_clarification": False,
            "clarification_threshold": "conservative",
            "symbols_optimization_level": "aggressive",
            "use_two_step_llm": use_two_step,
            "owner_message_id": None,
        }
    }

    # Re-run search node so similar_code / code_examples_used match production path
    search_out = await search_code_examples_node(state, config)
    for k, v in search_out.items():
        setattr(state, k, v)

    gen_out = await asyncio.to_thread(generate_code_node, state, config)
    return {
        "conversation_id": conversation_id,
        "search_node": {
            "similar_results_count": len(search_out.get("similar_results") or []),
            "code_examples_used": search_out.get("code_examples_used") or [],
            "error_message": search_out.get("error_message"),
        },
        "generate_node": {
            "generated_code": gen_out.get("generated_code") or gen_out.get("code"),
            "analysis_description": gen_out.get("analysis_description")
            or gen_out.get("description"),
            "required_libraries": gen_out.get("required_libraries") or gen_out.get("libraries"),
            "expected_outputs": gen_out.get("expected_outputs") or gen_out.get("outputs"),
            "error_message": gen_out.get("error_message"),
            "raw_keys": sorted(gen_out.keys()),
        },
    }


def print_human_report(bundle: Dict[str, Any], generate_result: Optional[Dict[str, Any]]) -> None:
    query = bundle["query"]
    ctx = bundle["context_data"]
    pc = bundle["parent_child"]
    formatted = bundle["formatted_context_for_llm"]

    print_section("1) QUERY")
    print(query)

    print_section("2) PARENT-CHILD RETRIEVAL (architecture view)")
    parents = pc.get("parents") or []
    print(f"Parents selected: {len(parents)}")
    for i, block in enumerate(parents, 1):
        parent = block.get("parent") or {}
        children = block.get("children") or []
        print(
            f"\n  [{i}] {parent.get('content_type')} | score={parent.get('score', 0):.3f} | "
            f"{parent.get('title')}"
        )
        if parent.get("project_id") or parent.get("phase"):
            print(f"      project={parent.get('project_id')} phase={parent.get('phase')}")
        print(f"      summary: {_truncate(parent.get('summary') or '', 220)}")
        print(f"      children expanded: {len(children)}")
        for c in children[:2]:
            print(
                f"        - score={c.get('score', 0):.3f} {c.get('title') or c.get('heading')} "
                f"({c.get('relative_path') or c.get('notebook_path')})"
            )

    direct = pc.get("direct_snippets") or []
    print(f"\nDirect child snippet hits: {len(direct)}")
    for s in direct[:3]:
        print(
            f"  - score={s.get('score', 0):.3f} retrieval={s.get('retrieval')} "
            f"| {s.get('title')}"
        )
        if s.get("parent_summary"):
            print(f"    parent: {s.get('parent_title')} — {_truncate(s.get('parent_summary'), 160)}")

    print_section("3) CODE AGENT CONTEXT PAYLOAD (get_context_for_code_generation)")
    snippets = ctx.get("snippets") or []
    docs = ctx.get("documentation") or []
    examples = ctx.get("code_examples") or []
    learned = ctx.get("learned_code") or []
    print(f"snippets={len(snippets)} documentation={len(docs)} "
          f"code_examples={len(examples)} learned_code={len(learned)}")
    for i, s in enumerate(snippets, 1):
        print(f"\n  Snippet {i}:")
        print(textwrap.indent(json.dumps(_summarize_snippet(s), indent=2), "    "))

    print_section("4) FORMATTED CONTEXT SENT TO LLM (format_code_context_for_llm)")
    print(formatted if formatted.strip() else "(empty)")
    print(f"\n[formatted context chars: {len(formatted)}]")

    if generate_result:
        print_section("5) CODE AGENT RESPONSE (generate_code_node)")
        search_meta = generate_result.get("search_node") or {}
        gen = generate_result.get("generate_node") or {}
        print(f"conversation_id: {generate_result.get('conversation_id')}")
        print(f"examples used: {len(search_meta.get('code_examples_used') or [])}")
        for ex in (search_meta.get("code_examples_used") or [])[:5]:
            print(
                f"  - [{ex.get('source_type')}] {ex.get('name')} "
                f"(score={ex.get('relevance_score', 0):.3f})"
            )
        if gen.get("error_message"):
            print(f"ERROR: {gen['error_message']}")
        else:
            print(f"\nlibraries: {gen.get('required_libraries')}")
            print(f"description: {_truncate(str(gen.get('analysis_description') or ''), 400)}")
            print("\n--- generated code ---")
            print(gen.get("generated_code") or "(no code)")
            print("--- end code ---")


def build_json_report(
    bundle: Dict[str, Any],
    generate_result: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    ctx = bundle["context_data"]
    pc = bundle["parent_child"]
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": bundle["query"],
        "architecture": {
            "parents": [
                {
                    "content_type": (b.get("parent") or {}).get("content_type"),
                    "title": (b.get("parent") or {}).get("title"),
                    "score": (b.get("parent") or {}).get("score"),
                    "project_id": (b.get("parent") or {}).get("project_id"),
                    "phase": (b.get("parent") or {}).get("phase"),
                    "summary": (b.get("parent") or {}).get("summary"),
                    "children": [_summarize_snippet(c) for c in (b.get("children") or [])],
                }
                for b in (pc.get("parents") or [])
            ],
            "direct_snippets": [_summarize_snippet(s) for s in (pc.get("direct_snippets") or [])],
        },
        "code_agent_context": {
            "snippets": [_summarize_snippet(s) for s in (ctx.get("snippets") or [])],
            "documentation_count": len(ctx.get("documentation") or []),
            "code_examples_count": len(ctx.get("code_examples") or []),
            "learned_code_count": len(ctx.get("learned_code") or []),
            "formatted_context_for_llm": bundle["formatted_context_for_llm"],
            "formatted_context_chars": len(bundle["formatted_context_for_llm"] or ""),
        },
        "generate_result": generate_result,
    }


async def amain(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="Load a LiPD dataset from a URL using PyLiPD and list available variables",
        help="Natural-language analysis request for the Code agent",
    )
    parser.add_argument("-k", "--k", type=int, default=3, help="Retrieval depth hint")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Also run Code agent generate_code_node and print the response",
    )
    parser.add_argument("--provider", default="openai", help="LLM provider for --generate")
    parser.add_argument("--model", default=None, help="Optional model override")
    parser.add_argument(
        "--two-step",
        action="store_true",
        help="Use the production 2-step symbol planning path (slower)",
    )
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=None,
        help="Write full JSON report to this path",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only write JSON (--out or stdout), skip human printout",
    )
    args = parser.parse_args(argv)

    print(f"Collecting Code-agent context for: {args.query!r}")
    bundle = await collect_context(args.query, args.k)

    generate_result = None
    if args.generate:
        print("Running search_code_examples_node + generate_code_node...")
        generate_result = await run_generate(
            args.query,
            bundle,
            provider=args.provider,
            model=args.model,
            use_two_step=args.two_step,
        )

    report = build_json_report(bundle, generate_result)

    if not args.quiet:
        print_human_report(bundle, generate_result)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"\nWrote JSON report → {args.out}")
    elif args.quiet:
        print(json.dumps(report, indent=2, default=str))

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    return asyncio.run(amain(argv))


if __name__ == "__main__":
    raise SystemExit(main())
