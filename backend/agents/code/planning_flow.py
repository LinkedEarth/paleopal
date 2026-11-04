"""
planning_flow.py — the new path for a request, connecting the planning pieces.

    interpret the request -> read the notebook -> compare with the workflow file
    -> gather snippets per step -> write markdown + code cells -> run the checker

First version: only a spectral analysis on a notebook with a loaded series and no
analysis yet. Anything else returns None and goes to the old pipeline. When a
request can't be resolved, such as a series that isn't in the notebook, PaleoPAL
asks rather than guessing. The checker reports findings; its repair loop isn't
built yet.

Off unless USE_PLANNING_FLOW=true.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import asdict
from typing import Awaitable, Callable

from . import request_interpreter, step_snippets, verification, workflow_detector, workflow_writer

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    return os.getenv("USE_PLANNING_FLOW", "false").lower() == "true"


def code_cells_from_history(history: list[dict]) -> list[str]:
    """The extension sends code cells as assistant messages with `generated_content`."""
    return [m["generated_content"] for m in history or []
            if m.get("role") == "assistant" and m.get("generated_content")]


def _ask(*questions: str) -> dict:
    text = " ".join(questions) + f"\n\n{workflow_writer.AUTHORSHIP_MARKDOWN}"
    return {"generated_code": "", "cells": [{"kind": "markdown", "text": text, "step": None}],
            "needs_user_input": True}


async def run(user_input: str, history: list[dict], workflow: dict,
              call_model: Callable[[str, str], str], searches: list) -> dict | None:
    """Return the cells for this request, or None if it isn't covered yet."""
    cells = code_cells_from_history(history)
    series = workflow_detector.detect(cells, workflow).series
    if not series:
        return None

    meaning = await asyncio.to_thread(
        request_interpreter.interpret_request, user_input, workflow, series, call_model)
    if meaning.analysis is None and not meaning.problems:
        return None
    if meaning.problems:
        logger.info("Planning flow asking the user: %s", meaning.problems)
        return _ask(f"I couldn't find that series in your notebook. The series I can see are: "
                    f"{', '.join(f'`{s}`' for s in series)}. Which one should I use?")

    objective = meaning.objective or "exploratory"
    state = workflow_detector.detect(cells, workflow, target=meaning.series, objective=objective)
    if state.uncertain:
        return _ask("I'm not sure what some of your code does, so I'd rather check before "
                    "building on it:", "; ".join(state.uncertain) + ".",
                    "Could you tell me what it does?")
    if state.level == "unclear":
        return _ask(f"Your notebook has several series: {', '.join(f'`{s}`' for s in series)}. "
                    "Which one should I analyze?")
    if state.level != "whole_workflow":
        return None

    plan = workflow_writer.build_plan(state, workflow, meaning.objective, meaning.method)
    snippets = {step["id"]: await step_snippets.find_step_snippets(step, searches)
                for step in plan.steps}
    written = await asyncio.to_thread(
        workflow_writer.write_workflow, plan, workflow, snippets, call_model)
    if written.problems or not written.cells:
        logger.warning("Planning flow couldn't write the workflow: %s", written.problems)
        return _ask("I'm still learning and can't get this right yet, but I'm learning! "
                    "I wasn't able to write this workflow, so please try rephrasing your request.")

    code = "\n\n".join(c.text for c in written.cells if c.kind == "code")
    findings = verification.run_checks(
        "\n\n".join([*cells, code]),
        {"objective": plan.objective, "expected_object": plan.series, "expects_plot": True})
    violations = [asdict(f) for f in findings if f.status == "violated"]
    if violations:
        logger.warning("Planning flow checker findings: %s", violations)
    return {"generated_code": code, "cells": [asdict(c) for c in written.cells],
            "needs_user_input": False, "checker_findings": violations,
            "plan": {"series": plan.series, "objective": plan.objective, "method": plan.method,
                     "steps": [s["id"] for s in plan.steps]}}


async def handle(request):
    """Adapter for the agent router. Returns an AgentResponse, or None for the old pipeline."""
    from agents.base_agent import AgentResponse, AgentStatus
    from langchain_core.messages import HumanMessage, SystemMessage
    from services.search_integration_service import search_service
    from services.service_manager import service_manager

    metadata = request.metadata or {}
    llm = service_manager.get_llm_provider(metadata.get("llm_provider", "openai"),
                                           model=metadata.get("model"))

    def call_model(system: str, user: str) -> str:
        return llm._call([SystemMessage(content=system), HumanMessage(content=user)])

    result = await run(request.user_input, (request.context or {}).get("conversation_history", []),
                       workflow_detector.load_workflow(), call_model,
                       [search_service.search_snippets, search_service.search_code_examples])
    if result is None:
        return None
    message = ("I need one more detail from you." if result["needs_user_input"]
               else "Built the workflow from the PaleoPAL workflow file.")
    return AgentResponse(status=AgentStatus.SUCCESS, result=result, message=message,
                         conversation_id=request.conversation_id)
