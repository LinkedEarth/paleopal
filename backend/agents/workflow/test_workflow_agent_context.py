#!/usr/bin/env python3
"""Test the Workflow agent against notebook summaries + workflows retrieval.

Shows:
  1) raw planning context (workflows + notebook/project summaries)
  2) the formatted context string generate_workflow_plan_node sends to the LLM
  3) optionally the generated workflow JSON (--generate)

Run from the backend directory (with paleopal env + Qdrant up):

  cd backend
  python -m agents.workflow.test_workflow_agent_context \\
      "Reproduce LMR data assimilation and validate GMST"

  python -m agents.workflow.test_workflow_agent_context \\
      "Build a proxy database then run DA and validate" --generate \\
      --out /tmp/workflow_agent_test.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
LIBRARIES_DIR = BACKEND_DIR / "libraries"
if str(LIBRARIES_DIR) not in sys.path:
    sys.path.insert(0, str(LIBRARIES_DIR))

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


def print_section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _summarize_workflow(w: Dict[str, Any]) -> Dict[str, Any]:
    steps = w.get("workflow_steps") or w.get("steps") or []
    return {
        "id": w.get("id"),
        "score": w.get("score") or w.get("similarity_score"),
        "content_type": w.get("content_type"),
        "title": w.get("title"),
        "description": _truncate(w.get("description") or "", 300),
        "project_id": w.get("project_id"),
        "phase": w.get("phase"),
        "notebook_path": w.get("notebook_path") or w.get("relative_path"),
        "num_steps": w.get("num_steps") or len(steps),
        "step_titles": [
            (s.get("title") or s.get("description") or f"step {i+1}")[:80]
            for i, s in enumerate(steps[:8])
            if isinstance(s, dict)
        ],
        "parent_summary": _truncate(w.get("parent_summary") or "", 200),
    }


def _summarize_summary(s: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": s.get("id"),
        "score": s.get("score") or s.get("similarity_score"),
        "content_type": s.get("content_type"),
        "title": s.get("title"),
        "summary": _truncate(s.get("summary") or "", 300),
        "project_id": s.get("project_id"),
        "phase": s.get("phase"),
        "relative_path": s.get("relative_path"),
        "keywords": (s.get("keywords") or [])[:10],
    }


async def collect_context(query: str, top_k: int) -> Dict[str, Any]:
    from services.search_integration_service import search_service
    from libraries.notebook_library.search_snippets import search_summaries

    context_data = await search_service.get_context_for_planning(query)
    # Ensure depth matches -k for the explicit architecture dump
    workflows = await search_service.search_notebook_workflows(query, top_k=top_k)
    summaries = search_summaries(query, limit=top_k)
    # Prefer service context, but fall back to direct searches if empty
    if not context_data.get("workflows"):
        context_data["workflows"] = workflows
    if not context_data.get("summaries"):
        context_data["summaries"] = summaries

    formatted = search_service.format_workflow_context_for_llm(context_data)
    return {
        "query": query,
        "context_data": context_data,
        "direct_workflows": [ _summarize_workflow(w) for w in (workflows or []) ],
        "direct_summaries": [ _summarize_summary(s) for s in (summaries or []) ],
        "formatted_context_for_llm": formatted,
    }


async def run_generate(
    query: str,
    context_bundle: Dict[str, Any],
    *,
    provider: str,
    model: Optional[str],
) -> Dict[str, Any]:
    from agents.workflow.state import WorkflowAgentState
    from agents.workflow.handlers import generate_workflow_plan_node
    from services.service_manager import service_manager

    llm = service_manager.get_llm_provider(provider=provider, model=model)
    conversation_id = f"test-workflow-agent-{uuid.uuid4().hex[:8]}"

    state = WorkflowAgentState(
        user_input=query,
        conversation_id=conversation_id,
        needs_clarification=False,
        contextual_search_data=context_bundle["context_data"],
        agent_type="workflow_generation",
    )
    config = {
        "configurable": {
            "llm": llm,
            "enable_clarification": False,
            "owner_message_id": None,
        }
    }

    gen_out = await asyncio.to_thread(generate_workflow_plan_node, state, config)
    plan_raw = gen_out.get("generated_code") or ""
    plan_parsed = None
    try:
        plan_parsed = json.loads(plan_raw) if plan_raw else None
    except json.JSONDecodeError:
        plan_parsed = None

    return {
        "conversation_id": conversation_id,
        "generate_node": {
            "workflow_id": gen_out.get("workflow_id"),
            "estimated_steps": gen_out.get("estimated_steps"),
            "agents_involved": gen_out.get("agents_involved"),
            "context_used": gen_out.get("context_used"),
            "error_message": gen_out.get("error_message"),
            "generated_workflow_json": plan_raw,
            "parsed_workflow": plan_parsed,
            "raw_keys": sorted(gen_out.keys()),
        },
    }


def print_human_report(bundle: Dict[str, Any], generate_result: Optional[Dict[str, Any]]) -> None:
    ctx = bundle["context_data"]
    formatted = bundle["formatted_context_for_llm"]

    print_section("1) QUERY")
    print(bundle["query"])

    print_section("2) NOTEBOOK SUMMARIES (parents for planning)")
    summaries = ctx.get("summaries") or []
    print(f"summaries={len(summaries)}")
    for i, s in enumerate(summaries, 1):
        print(
            f"\n  [{i}] score={s.get('score', s.get('similarity_score', 0)):.3f} "
            f"| {s.get('content_type')} | {s.get('title')}"
        )
        if s.get("project_id") or s.get("phase"):
            print(f"      project={s.get('project_id')} phase={s.get('phase')}")
        print(f"      {_truncate(s.get('summary') or '', 240)}")

    print_section("3) NOTEBOOK WORKFLOWS (examples for planning)")
    workflows = ctx.get("workflows") or []
    print(f"workflows={len(workflows)}")
    for i, w in enumerate(workflows, 1):
        steps = w.get("workflow_steps") or w.get("steps") or []
        print(
            f"\n  [{i}] score={w.get('score', w.get('similarity_score', 0)):.3f} "
            f"| {w.get('content_type')} | {w.get('title')}"
        )
        print(f"      steps={w.get('num_steps', len(steps))} "
              f"project={w.get('project_id')} phase={w.get('phase')}")
        print(f"      {_truncate(w.get('description') or '', 220)}")
        for j, step in enumerate(steps[:5], 1):
            if not isinstance(step, dict):
                continue
            print(f"        {j}. {step.get('title') or step.get('description') or step}")

    print_section("4) FORMATTED CONTEXT SENT TO LLM (format_workflow_context_for_llm)")
    print(formatted if formatted.strip() else "(empty)")
    print(f"\n[formatted context chars: {len(formatted)}]")

    if generate_result:
        print_section("5) WORKFLOW AGENT RESPONSE (generate_workflow_plan_node)")
        gen = generate_result.get("generate_node") or {}
        print(f"conversation_id: {generate_result.get('conversation_id')}")
        print(f"workflow_id: {gen.get('workflow_id')}")
        print(f"estimated_steps: {gen.get('estimated_steps')}")
        print(f"agents_involved: {gen.get('agents_involved')}")
        print(f"context_used: {gen.get('context_used')}")
        if gen.get("error_message"):
            print(f"ERROR: {gen['error_message']}")
        else:
            print("\n--- generated workflow JSON ---")
            print(gen.get("generated_workflow_json") or "(none)")
            print("--- end workflow ---")


def build_json_report(
    bundle: Dict[str, Any],
    generate_result: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    ctx = bundle["context_data"]
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": bundle["query"],
        "architecture": {
            "summaries": [_summarize_summary(s) for s in (ctx.get("summaries") or [])],
            "workflows": [_summarize_workflow(w) for w in (ctx.get("workflows") or [])],
            "direct_summaries": bundle.get("direct_summaries"),
            "direct_workflows": bundle.get("direct_workflows"),
        },
        "workflow_agent_context": {
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
        default="Assemble a PAGES2k proxy database, run data assimilation, and validate GMST",
        help="Natural-language planning request for the Workflow agent",
    )
    parser.add_argument("-k", "--k", type=int, default=3, help="Retrieval depth")
    parser.add_argument("--generate", action="store_true", help="Also run generate_workflow_plan_node")
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model", default=None)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    print(f"Collecting Workflow-agent context for: {args.query!r}")
    bundle = await collect_context(args.query, args.k)

    generate_result = None
    if args.generate:
        print("Running generate_workflow_plan_node...")
        generate_result = await run_generate(
            args.query,
            bundle,
            provider=args.provider,
            model=args.model,
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
