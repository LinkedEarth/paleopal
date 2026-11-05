"""
planning_flow.py — the new path for a request, connecting the planning pieces.

    interpret the request -> read the notebook -> compare with the workflow file
    -> gather snippets per step -> write markdown + code cells -> run the checker

Covers a spectral analysis on a notebook with a loaded series, whether it needs the
whole workflow or a next step. Anything else returns None and goes to the old pipeline. When a
request can't be resolved, such as a series that isn't in the notebook, PaleoPAL
asks rather than guessing. PaleoPAL's own mistakes go back to the model and are
fixed quietly; each repair is recorded for improving PaleoPAL, not shown to the
user. If they survive the last repair, the code is shown with a warning.

Off unless USE_PLANNING_FLOW=true.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Callable

from . import request_interpreter, step_snippets, verification, workflow_detector, workflow_writer

logger = logging.getLogger(__name__)

# The check that demands each step, which a plan stopping short of that step must not trigger.
_CHECK_DEMANDING = {"significance": "significance_tested", "beta_estimate": "beta_estimated",
                    "spectral_estimate": "required_steps_present"}


def is_enabled() -> bool:
    return os.getenv("USE_PLANNING_FLOW", "false").lower() == "true"


def code_cells_from_history(history: list[dict]) -> list[str]:
    """The extension sends code cells as assistant messages with `generated_content`."""
    return [m["generated_content"] for m in history or []
            if m.get("role") == "assistant" and m.get("generated_content")]


def record_repair(entry: dict, path: str | None = None) -> None:
    """Append to the internal repair history. A failure here must never affect the user."""
    path = path or os.getenv("REPAIR_HISTORY_PATH", "data/repair_history.jsonl")
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(), **entry}) + "\n")
    except OSError as exc:
        logger.warning("Couldn't record the repair: %s", exc)


def _problems_with(written, cells: list[str], task: dict, user_overrides: set[str]) -> list[str]:
    """Everything that should go back to the model, as text it can act on."""
    problems = list(written.problems)
    if written.cells:
        code = "\n\n".join(c.text for c in written.cells if c.kind == "code")
        gate = verification.gate(verification.check_new_code(cells, code, task), user_overrides)
        problems += [f"{v.rule}: {v.detail}" if v.detail else v.rule for v in gate["violations"]]
    return problems


def _warning_cell(problems: list[str]) -> dict:
    listed = "\n".join(f"- {p}" for p in problems)
    return {"kind": "markdown", "step": None,
            "text": "I'm still learning and can't get this right yet, but I'm learning! Please "
                    f"check the code below, because these problems remain:\n\n{listed}\n\n"
                    f"{workflow_writer.AUTHORSHIP_MARKDOWN}"}


def decisions_from_history(history: list[dict]) -> dict[str, str]:
    """Yes/no answers recorded on PaleoPAL's earlier cells, so it doesn't ask twice."""
    found = {}
    for message in history or []:
        for decision in message.get("decisions") or []:
            found[decision["step"]] = decision["answer"]
    return found


def _ask(*questions: str) -> dict:
    text = " ".join(questions) + f"\n\n{workflow_writer.AUTHORSHIP_MARKDOWN}"
    return {"generated_code": "", "cells": [{"kind": "markdown", "text": text, "step": None}],
            "needs_user_input": True}


async def run(user_input: str, history: list[dict], workflow: dict,
              call_model: Callable[[str, str], str], searches: list, max_repairs: int = 3,
              on_repair: Callable[[dict], None] | None = None,
              answers: dict[str, str] | None = None) -> dict | None:
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
    if any(p.startswith("series") for p in meaning.problems):
        return _ask(f"I couldn't find that series in your notebook. The series I can see are: "
                    f"{', '.join(f'`{s}`' for s in series)}. Which one should I use?")
    if meaning.problems:
        return _ask("I'm not sure I understood that request. Could you rephrase it?")

    by_id = {s["id"]: s for s in workflow["steps"]}
    objective = workflow_writer._objective_for([by_id[i] for i in meaning.steps], meaning.objective)
    state = workflow_detector.detect(cells, workflow, target=meaning.series, objective=objective)
    if state.uncertain:
        return _ask("I'm not sure what some of your code does, so I'd rather check before "
                    "building on it:", "; ".join(state.uncertain) + ".",
                    "Could you tell me what it does?")
    if state.level == "unclear":
        return _ask(f"Your notebook has several series: {', '.join(f'`{s}`' for s in series)}. "
                    "Which one should I analyze?")
    if state.level == "whole_workflow":
        plan = workflow_writer.build_plan(state, workflow, objective, meaning.method)
        plan.start = state.current
    elif state.level == "next_step":
        all_answers = {**decisions_from_history(history), **(answers or {})}
        next_step = workflow_writer.plan_next_step(
            state, workflow, meaning.steps, meaning.objective, meaning.method, all_answers)
        if next_step.question:
            return {"generated_code": "", "needs_user_input": True,
                    "clarification_questions": [next_step.question]}
        if next_step.message:
            return _ask(next_step.message)
        plan = next_step.plan
    else:
        return None
    plan.notebook_code = cells

    snippets = {step["id"]: await step_snippets.find_step_snippets(step, searches)
                for step in plan.steps}
    # A method the user named is their choice, not PaleoPAL's mistake.
    overrides = {"cwt_not_first_choice"} if meaning.method == "cwt" else set()
    # A next-step snippet is one call in a longer analysis; it needn't display its result.
    if state.level == "next_step":
        overrides.add("result_displayed")
    # The checker can't demand a step the plan leaves for later, as in "just standardize it".
    planned = {s["id"] for s in plan.steps}
    overrides.update(rule for step_id, rule in _CHECK_DEMANDING.items() if step_id not in planned)
    # New code continues from `start`, which may be derived from the series the user named.
    task = {"objective": plan.objective, "expected_object": plan.start or plan.series,
            "expects_plot": True}

    written = await asyncio.to_thread(
        workflow_writer.write_workflow, plan, workflow, snippets, call_model)
    # A fresh chain isn't judged against the steps it deliberately starts over from.
    checked_cells = [] if plan.fresh_chain else cells
    problems = _problems_with(written, checked_cells, task, overrides)
    repairs = 0
    while problems and repairs < max_repairs:
        repairs += 1
        if on_repair:
            on_repair({"request": user_input, "plan": [s["id"] for s in plan.steps],
                       "attempt": repairs, "problems": problems, "reply": written.reply})
        logger.info("Planning flow repair %d: %s", repairs, problems)
        previous = written
        written = await asyncio.to_thread(
            workflow_writer.write_workflow, plan, workflow, snippets, call_model,
            previous.reply, problems)
        if not written.cells and previous.cells:
            written.cells = previous.cells  # an unusable repair must not lose the code
        problems = _problems_with(written, checked_cells, task, overrides)
    if repairs and on_repair:
        on_repair({"request": user_input, "outcome": "failed" if problems else "repaired",
                   "repairs": repairs, "problems": problems, "reply": written.reply})

    if not written.cells:
        logger.warning("Planning flow couldn't write the workflow: %s", problems)
        return _ask("I'm still learning and can't get this right yet, but I'm learning! "
                    "I wasn't able to write this workflow, so please try rephrasing your request.")

    code = "\n\n".join(c.text for c in written.cells if c.kind == "code")
    new_cells = [asdict(c) for c in written.cells]
    if problems:
        new_cells.insert(0, _warning_cell(problems))
    return {"generated_code": code, "cells": new_cells,
            "needs_user_input": False, "checker_findings": problems, "repairs": repairs,
            "plan": {"series": plan.series, "objective": plan.objective, "method": plan.method,
                     "steps": [s["id"] for s in plan.steps]}}


async def handle(request):
    """Adapter for the agent router. Returns an AgentResponse, or None for the old pipeline."""
    from agents.base_agent import AgentResponse, AgentStatus
    from agents.base_state import MAX_REFINEMENTS
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
                       [search_service.search_snippets, search_service.search_code_examples],
                       max_repairs=MAX_REFINEMENTS, on_repair=record_repair,
                       answers={r["id"]: r["answer"]
                                for r in metadata.get("clarification_responses") or []})
    if result is None:
        return None
    message = ("I need one more detail from you." if result["needs_user_input"]
               else "Built from the PaleoPAL workflow file.")
    questions = result.get("clarification_questions")
    return AgentResponse(
        status=AgentStatus.NEEDS_CLARIFICATION if questions else AgentStatus.SUCCESS,
        result=result, message=message, clarification_questions=questions,
        conversation_id=request.conversation_id)
