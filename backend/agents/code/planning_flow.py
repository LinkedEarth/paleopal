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

_PLOT_STEP = "visualize"
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


_INTRO = f"""**Working with PaleoPAL**

I'm PaleoPAL, an AI assistant for paleoclimate analysis from the LinkedEarth project. I'm still learning, so please check my work.

- **Nothing runs on its own.** I add cells to your notebook, and you decide what to run, change or delete. One undo removes everything I just added.
- **Each step has an explanation above its code**, saying what it does and why.
- **I follow a guide for the steps.** It decides which steps an analysis needs and in what order. Code examples only show me how to write them.
- **Under each explanation, you can open two sections.** *Parameters* quotes the Pyleoclim documentation for the settings I used. *Sources* quotes the guide and names the examples I was shown. Those are quoted directly, and I wrote the explanations.

You can delete this cell once you've read it.

{workflow_writer.AUTHORSHIP_MARKDOWN}"""


_REGRID_STEP = "regrid"


def _resolve_regrid(meaning, state, workflow: dict, objective: str, answers: dict[str, str]) -> dict:
    """Settle regridding against the method before planning. May change `meaning`.

    A regrid asked for before a method that doesn't need it is explained and asked about.
    A regrid already in the researcher's cells is their choice, and with no method named,
    the guide picks a method that uses it.
    """
    registry = {m["id"]: m for m in workflow["method_registry"]}
    selection = workflow["method_selection"]
    done = {s.id for s in state.steps if s.status == "done"}
    method = meaning.method or selection["defaults_by_objective"][objective]
    found: dict = {"overrides": set()}

    if _REGRID_STEP in done:
        found["overrides"] |= {"no_unnecessary_regrid", "method_suits_uneven_data"}
        already = selection.get("when_already_regridded") or {}
        notes = already.get("must_say_by_default") or {}
        if meaning.method is None and method in notes:
            meaning.method = already["method"]
            found["method_note"] = " ".join(notes[method].split())
        return found

    if _REGRID_STEP not in meaning.steps or registry[method]["requires_even_spacing"]:
        return found
    rule = next(r for r in workflow["rules"] if r["id"] == "regrid_unnecessary_for_tolerant_methods")
    # Only this request's answer counts: a choice to insist is asked each time for now.
    answer = (answers.get(_REGRID_STEP) or "").strip().lower()
    if not answer:
        found["question"] = {
            "id": _REGRID_STEP, "choices": ["Yes", "No"],
            "question": f"`{method}` doesn't need regridding. Do you still want me to regrid "
                        f"`{state.target}` first?",
            "context": " ".join(rule["must_say"].split())}
    elif answer.startswith("y"):
        found["overrides"].add("no_unnecessary_regrid")
        found["decision"] = {"step": _REGRID_STEP, "answer": "yes", "method": method}
    else:
        meaning.steps.remove(_REGRID_STEP)
        found["decision"] = {"step": _REGRID_STEP, "answer": "no", "method": method}
    return found


def _note_regrid(plan, regrid: dict) -> None:
    """Record the regrid choice where the researcher will see it."""
    spectral = workflow_writer._SPECTRAL_STEP
    if regrid.get("method_note"):
        plan.notes.setdefault(spectral, []).insert(0, regrid["method_note"])
    decision = regrid.get("decision")
    if not decision:
        return
    plan.decisions.append({"step": decision["step"], "answer": decision["answer"]})
    method = f"`{decision['method']}`"
    if decision["answer"] == "yes":
        plan.notes.setdefault(_REGRID_STEP, []).append(
            f"I regridded because you confirmed it, after I explained that {method} doesn't need it.")
    else:
        # This replaces the general note that the method tolerates uneven sampling.
        notes = [n for n in plan.notes.get(spectral, []) if "tolerates uneven sampling" not in n]
        plan.notes[spectral] = notes + [
            f"You chose not to regrid, after I explained that {method} doesn't need it."]


def step_settings(workflow: dict, reference: dict) -> dict[str, list[str]]:
    """Argument names each step's functions take, from the Pyleoclim parameter reference.

    Saving a figure is a setting of the plot step, not a task the guide lacks.
    """
    methods = reference.get("methods", {})
    found = {}
    for step in workflow["steps"]:
        apis = step.get("core_api") or []
        names = [p["name"] for api in (apis if isinstance(apis, list) else [apis])
                 for p in [*methods.get(api, {}).get("parameters", []),
                           *methods.get(api, {}).get("passes_to", [])]]
        if names:
            found[step["id"]] = list(dict.fromkeys(names))
    return found


def _not_covered_cell(parts: list[str], workflow: dict) -> dict:
    """Never drop part of a request silently. Temporary: the model-only path will answer these."""
    analysis = workflow["workflow"]["id"].replace("_", " ")
    listed = "\n".join(f"- {p}" for p in parts)
    return {"kind": "markdown", "step": None,
            "text": f"I haven't done this part of your request, because my guide to {analysis} "
                    f"doesn't cover it yet:\n\n{listed}\n\nI'd rather tell you than guess. "
                    f"Everything below follows the guide.\n\n{workflow_writer.AUTHORSHIP_MARKDOWN}"}


def _has_paleopal_cells(history: list[dict]) -> bool:
    return any(m.get("agent_type") == "paleopal_note"
               or workflow_writer.AUTHORSHIP_CODE in (m.get("generated_content") or "")
               for m in history or [])


async def run(user_input: str, history: list[dict], workflow: dict,
              call_model: Callable[[str, str], str], searches: list, max_repairs: int = 3,
              on_repair: Callable[[dict], None] | None = None,
              answers: dict[str, str] | None = None) -> dict | None:
    """Return the cells for this request, or None if it isn't covered yet.

    People rarely read the docs, so a notebook's first cells from PaleoPAL explain how to read them.
    """
    seen: dict = {}
    result = await _plan_and_write(user_input, history, workflow, call_model, searches,
                                   max_repairs, on_repair, answers, seen)
    if result and result.get("cells") and not result["needs_user_input"] and seen.get("not_covered"):
        result["cells"].insert(0, _not_covered_cell(seen["not_covered"], workflow))
    if result and result.get("cells") and not _has_paleopal_cells(history):
        result["cells"].insert(0, {"kind": "markdown", "text": _INTRO, "step": None})
    return result


async def _plan_and_write(user_input: str, history: list[dict], workflow: dict,
                          call_model: Callable[[str, str], str], searches: list, max_repairs: int,
                          on_repair: Callable[[dict], None] | None,
                          answers: dict[str, str] | None, seen: dict) -> dict | None:
    cells = code_cells_from_history(history)
    series = workflow_detector.detect(cells, workflow).series
    if not series:
        return None

    meaning = await asyncio.to_thread(
        request_interpreter.interpret_request, user_input, workflow, series, call_model,
        step_settings(workflow, workflow_writer._parameter_reference()))
    seen["not_covered"] = meaning.not_covered
    # The method list comes from the workflow file, so naming one means this analysis.
    if meaning.analysis is None and meaning.method is None and not meaning.problems:
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

    regrid = _resolve_regrid(meaning, state, workflow, objective, answers or {})
    if regrid.get("question"):
        return {"generated_code": "", "needs_user_input": True,
                "clarification_questions": [regrid["question"]]}

    if state.level == "whole_workflow":
        plan = workflow_writer.build_plan(state, workflow, objective, meaning.method, meaning.steps)
        plan.start = state.current
    elif state.level == "next_step":
        all_answers = {**decisions_from_history(history), **(answers or {})}
        # "Run the analysis with a linear detrend" wants that step, the spectrum and, as on a
        # clean notebook, its plot. Naming an estimator alongside a step asks for the spectrum.
        also = []
        if meaning.whole_analysis:
            also = [workflow_writer._SPECTRAL_STEP, _PLOT_STEP]
        elif meaning.method and meaning.steps:
            also = [workflow_writer._SPECTRAL_STEP]
        requested = meaning.steps + [s for s in also if s not in meaning.steps]
        next_step = workflow_writer.plan_next_step(
            state, workflow, requested, meaning.objective, meaning.method, all_answers)
        if next_step.question:
            return {"generated_code": "", "needs_user_input": True,
                    "clarification_questions": [next_step.question]}
        if next_step.message:
            return _ask(next_step.message)
        plan = next_step.plan
    else:
        return None
    plan.notebook_code = cells
    plan.request = user_input
    _note_regrid(plan, regrid)

    snippets = {step["id"]: await step_snippets.find_step_snippets(step, searches)
                for step in plan.steps}
    # A method the user named is their choice, not PaleoPAL's mistake.
    overrides = {"cwt_not_first_choice"} if meaning.method == "cwt" else set()
    overrides |= regrid.get("overrides", set())
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


NO_GUIDE_NOTE = ("None of my guides covers this request yet, so this answer comes from the underlying "
                 "AI model only. It has had fewer checks than LinkedEarth workflows, so please check it "
                 "before relying on it.")


async def answer_uncovered(user_input: str, history: list[dict], workflow: dict, reference: dict,
                           call_model: Callable[[str, str], str]) -> dict:
    """A request no guide covers, answered by the model with the note, never by the old pipeline."""
    from . import chat_session
    answer = await asyncio.to_thread(
        chat_session.reply, history, [{"role": "user", "content": user_input}], workflow, reference,
        call_model, True)
    parts = [answer.reply, NO_GUIDE_NOTE]
    if answer.problems:
        listed = "\n".join(f"- {p}" for p in answer.problems)
        parts.append("I'm still learning and can't get this right yet, but I'm learning! Please check "
                     f"the code below, because these problems remain:\n\n{listed}")
    block = chat_session._sources_block([asdict(s) for s in answer.sources])
    parts += [*([block] if block else []), workflow_writer.AUTHORSHIP_MARKDOWN
              + (" Sources are quoted directly, not written by the AI." if block else "")]
    cells = [{"kind": "markdown", "text": "\n\n".join(p for p in parts if p), "step": None}]
    if answer.code:
        cells.append({"kind": "code", "text": f"{workflow_writer.AUTHORSHIP_CODE}\n{answer.code}",
                      "step": None})
    if not _has_paleopal_cells(history):
        cells.insert(0, {"kind": "markdown", "text": _INTRO, "step": None})
    return {"generated_code": answer.code, "cells": cells, "needs_user_input": False,
            "checker_findings": answer.problems, "model_only": True}


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

    history = (request.context or {}).get("conversation_history", [])
    workflow = workflow_detector.load_workflow()
    result = await run(request.user_input, history, workflow, call_model,
                       [search_service.search_snippets, search_service.search_code_examples],
                       max_repairs=MAX_REFINEMENTS, on_repair=record_repair,
                       answers={r["id"]: r["answer"]
                                for r in metadata.get("clarification_responses") or []})
    if result is None:
        result = await answer_uncovered(request.user_input, history, workflow,
                                        workflow_writer._parameter_reference(), call_model)
    message = ("I need one more detail from you." if result["needs_user_input"]
               else "Answered by the underlying AI model only." if result.get("model_only")
               else "Built from PaleoPAL's guide.")
    questions = result.get("clarification_questions")
    return AgentResponse(
        status=AgentStatus.NEEDS_CLARIFICATION if questions else AgentStatus.SUCCESS,
        result=result, message=message, clarification_questions=questions,
        conversation_id=request.conversation_id)
