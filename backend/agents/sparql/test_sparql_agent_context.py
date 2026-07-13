#!/usr/bin/env python3
"""Test the SPARQL agent context + generation path.

Shows:
  1) similar SPARQL queries + ontology entity matches
  2) the formatted context string generate_query_node sends to the LLM
  3) optionally the generated SPARQL query (--generate)

Run from the backend directory (with paleopal env + Qdrant up):

  cd backend
  python -m agents.sparql.test_sparql_agent_context \\
      "Find coral d18O records from the tropical Pacific"

  python -m agents.sparql.test_sparql_agent_context \\
      "Find coral d18O records from the tropical Pacific" --generate \\
      --out /tmp/sparql_agent_test.json
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


def _summarize_query(q: Dict[str, Any]) -> Dict[str, Any]:
    sparql = q.get("sparql") or q.get("sparql_query") or q.get("query") or q.get("text") or ""
    return {
        "id": q.get("id"),
        "score": q.get("score") or q.get("similarity_score"),
        "title": q.get("title") or q.get("name") or q.get("description"),
        "description": _truncate(str(q.get("description") or q.get("intent") or ""), 220),
        "result_type": q.get("result_type"),
        "tags": (q.get("tags") or [])[:8],
        "sparql_preview": _truncate(sparql, 400),
    }


def _summarize_entity(e: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": e.get("id"),
        "score": e.get("score") or e.get("similarity_score"),
        "label": e.get("label") or e.get("name") or e.get("entity"),
        "uri": e.get("uri") or e.get("iri") or e.get("id"),
        "type": e.get("type") or e.get("entity_type") or e.get("kind"),
        "description": _truncate(str(e.get("description") or e.get("comment") or ""), 200),
        "matched_term": e.get("matched_term") or e.get("term"),
    }


async def collect_context(
    query: str,
    top_k: int,
    *,
    provider: str,
    use_term_extraction: bool,
) -> Dict[str, Any]:
    from services.search_integration_service import search_service

    # Full SPARQL context path used by the agent ecosystem
    context_data = await search_service.get_context_for_sparql_generation(query)

    # Also expose the exact node-level retrievals with controllable depth
    similar_queries = await search_service.search_sparql_queries(query, top_k=top_k)
    entities = await search_service.search_ontology_entities(
        query=query,
        llm_provider=provider,
        use_term_extraction=use_term_extraction,
        top_k=max(5, top_k),
    )

    # Prefer richer node-level lists when service defaults are smaller
    if similar_queries:
        context_data["similar_queries"] = similar_queries
    if entities:
        context_data["entities"] = entities
    context_data["query"] = query

    formatted = search_service.format_sparql_context_for_llm(context_data)
    return {
        "query": query,
        "context_data": context_data,
        "formatted_context_for_llm": formatted,
    }


async def run_generate(
    query: str,
    context_bundle: Dict[str, Any],
    *,
    provider: str,
    model: Optional[str],
) -> Dict[str, Any]:
    from agents.sparql.state import SparqlAgentState
    from agents.sparql.handlers import generate_query_node
    from services.service_manager import service_manager

    # Ensure provider is warm (generate_query_node also fetches via service_manager)
    service_manager.get_llm_provider(provider=provider, model=model)
    conversation_id = f"test-sparql-agent-{uuid.uuid4().hex[:8]}"
    ctx = context_bundle["context_data"]

    state = SparqlAgentState(
        user_input=query,
        conversation_id=conversation_id,
        needs_clarification=False,
        llm_provider=provider,
        similar_code=ctx.get("similar_queries") or [],
        entity_matches=ctx.get("entities") or [],
        agent_type="sparql",
        metadata={"model": model} if model else {},
    )
    config = {
        "configurable": {
            "enable_clarification": False,
            "owner_message_id": None,
        }
    }

    gen_out = await asyncio.to_thread(generate_query_node, state, config)
    return {
        "conversation_id": conversation_id,
        "generate_node": {
            "generated_sparql": gen_out.get("generated_code"),
            "context_used": gen_out.get("context_used"),
            "error_message": gen_out.get("error_message"),
            "raw_keys": sorted(gen_out.keys()),
        },
    }


def print_human_report(bundle: Dict[str, Any], generate_result: Optional[Dict[str, Any]]) -> None:
    ctx = bundle["context_data"]
    formatted = bundle["formatted_context_for_llm"]

    print_section("1) QUERY")
    print(bundle["query"])

    print_section("2) SIMILAR SPARQL QUERIES")
    queries = ctx.get("similar_queries") or []
    print(f"similar_queries={len(queries)}")
    for i, q in enumerate(queries, 1):
        s = _summarize_query(q)
        print(f"\n  [{i}] score={s.get('score') or 0:.3f} | {s.get('title')}")
        print(f"      {_truncate(s.get('description') or '', 180)}")
        print("      SPARQL preview:")
        print(textwrap_indent(s.get("sparql_preview") or "", "        "))

    print_section("3) ONTOLOGY ENTITY MATCHES")
    entities = ctx.get("entities") or []
    print(f"entities={len(entities)}")
    for i, e in enumerate(entities[:10], 1):
        s = _summarize_entity(e)
        print(
            f"  [{i}] score={s.get('score') or 0:.3f} | {s.get('label')} "
            f"({s.get('type')}) term={s.get('matched_term')}"
        )
        if s.get("uri"):
            print(f"      uri={s['uri']}")

    print_section("4) FORMATTED CONTEXT SENT TO LLM (format_sparql_context_for_llm)")
    print(formatted if formatted.strip() else "(empty)")
    print(f"\n[formatted context chars: {len(formatted)}]")

    if generate_result:
        print_section("5) SPARQL AGENT RESPONSE (generate_query_node)")
        gen = generate_result.get("generate_node") or {}
        print(f"conversation_id: {generate_result.get('conversation_id')}")
        print(f"context_used: {gen.get('context_used')}")
        if gen.get("error_message"):
            print(f"ERROR: {gen['error_message']}")
        else:
            print("\n--- generated SPARQL ---")
            print(gen.get("generated_sparql") or "(none)")
            print("--- end SPARQL ---")


def textwrap_indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line if line else prefix.rstrip() for line in text.splitlines())


def build_json_report(
    bundle: Dict[str, Any],
    generate_result: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    ctx = bundle["context_data"]
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": bundle["query"],
        "architecture": {
            "similar_queries": [_summarize_query(q) for q in (ctx.get("similar_queries") or [])],
            "entities": [_summarize_entity(e) for e in (ctx.get("entities") or [])],
            "learned_queries_count": len(ctx.get("learned_queries") or []),
        },
        "sparql_agent_context": {
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
        default="Find coral d18O records from the tropical Pacific over the last 2000 years",
        help="Natural-language SPARQL request",
    )
    parser.add_argument("-k", "--k", type=int, default=3, help="Retrieval depth")
    parser.add_argument("--generate", action="store_true", help="Also run generate_query_node")
    parser.add_argument("--provider", default="openai", help="LLM provider (also used for ontology term extraction)")
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--no-term-extraction",
        action="store_true",
        help="Skip LLM ontology term extraction (faster context-only runs)",
    )
    parser.add_argument("--out", type=pathlib.Path, default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    print(f"Collecting SPARQL-agent context for: {args.query!r}")
    bundle = await collect_context(
        args.query,
        args.k,
        provider=args.provider,
        use_term_extraction=not args.no_term_extraction,
    )

    generate_result = None
    if args.generate:
        print("Running generate_query_node...")
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
