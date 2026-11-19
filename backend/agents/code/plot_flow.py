"""
plot_flow.py — a request answered from PaleoPAL's guide to visualization.

    find the objects the notebook can plot -> the model picks the object and the plot
    -> Python checks both against the guide -> examples -> write one markdown + code pair
    -> Python adds the cone-of-influence and significance sentences -> code-only checks

Covers a plot on its own ("plot lr04") and a plot of a result ("plot the spectrum").
A plot inside an analysis, planned together with it, comes later (case 3).

Each object's type comes from the kernel read when there is one (type names only, never
values), otherwise from the cell text. The cell text is the truth for what exists: an
object only the kernel has isn't offered.
"""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Callable

from . import planning_flow, step_snippets, verification, workflow_writer

logger = logging.getLogger(__name__)

# Calls that make a Pyleoclim object, by the type they return.
_CONSTRUCTORS = {"load_dataset": "Series", "Series": "Series", "GeoSeries": "GeoSeries",
                 "MultipleSeries": "MultipleSeries", "MultipleGeoSeries": "MultipleGeoSeries"}
# Methods whose result has a new type, by the type they're called on.
_TRANSFORMS = {
    "spectral": {"Series": "PSD", "GeoSeries": "PSD", "MultipleSeries": "MultiplePSD",
                 "MultipleGeoSeries": "MultiplePSD"},
    "wavelet": {"Series": "Scalogram", "GeoSeries": "Scalogram"},
    "wavelet_coherence": {"Series": "Coherence", "GeoSeries": "Coherence"},
    "pca": {"MultipleSeries": "MultivariateDecomp", "MultipleGeoSeries": "MultivariateDecomp"},
}
# Methods that return an object of the same type.
_SAME_TYPE = {"detrend", "standardize", "interp", "bin", "gkernel", "slice", "outliers", "filter",
              "convert_time_unit", "copy", "flip", "center", "clean", "sort", "resample",
              "common_time", "signif_test", "beta_est"}
_SIGNIFICANCE_DEFAULTS = {"method": "ar1sim", "qs": [0.95]}

_INTERPRETER_PROMPT = """You read one plotting request from a paleoclimate researcher working in a notebook.
Reply with one JSON object and nothing else, with exactly these keys:

"object": the object the request asks to plot, from the list below. Match it by name ("plot lr04") or by
description ("the spectrum" is a PSD, "the scalogram" or "the wavelet" a Scalogram). If the request names
something that is not in the list, return the name as written. If it doesn't point to one, null.
"plot": one of the plots below if the request asks for that kind of plot (for example by one of its
"asked as" phrases), otherwise null. Never choose a plot the request doesn't ask for: null means the
default plot for the object.

Objects in the notebook:
{objects}

Plots:
{plots}"""


@dataclass
class PlotObject:
    name: str
    type: str
    # The significance test it carries, from a `signif_test` call in its making.
    significance: dict | None = None


@dataclass
class PlotRequest:
    object: str | None = None
    plot: str | None = None
    problems: list[str] = field(default_factory=list)


# --- reading the cells ------------------------------------------------------------------------

def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None


def _evaluate(node, known: dict[str, PlotObject]) -> PlotObject | None:
    """The type a chain like `lr04.detrend().spectral()` produces, or None if it isn't known."""
    if isinstance(node, ast.Name):
        return known.get(node.id)
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else None
    if name in _CONSTRUCTORS and not (isinstance(func, ast.Attribute) and _evaluate(func.value, known)):
        return PlotObject("", _CONSTRUCTORS[name])
    if not isinstance(func, ast.Attribute):
        return None
    base = _evaluate(func.value, known)
    if base is None:
        return None
    significance = base.significance
    if name == "signif_test":
        found = dict(_SIGNIFICANCE_DEFAULTS)
        for keyword in node.keywords:
            if keyword.arg in found:
                value = _literal(keyword.value)
                found[keyword.arg] = value if value is not None else found[keyword.arg]
        significance = found
    if name in _TRANSFORMS:
        new_type = _TRANSFORMS[name].get(base.type)
        return PlotObject("", new_type) if new_type else None
    if name in _SAME_TYPE:
        return PlotObject("", base.type, significance)
    return None


def objects_from_cells(cells: list[str]) -> dict[str, PlotObject]:
    """Every variable the cells make that's a Pyleoclim object, with its type."""
    known: dict[str, PlotObject] = {}
    for cell in cells:
        try:
            tree = ast.parse(cell)
        except SyntaxError:
            continue
        for statement in tree.body:
            if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name)):
                found = _evaluate(statement.value, known)
                name = statement.targets[0].id
                if found:
                    known[name] = PlotObject(name, found.type, found.significance)
                else:
                    known.pop(name, None)  # reassigned to something else
    return known


def plottable(cells: list[str], guide: dict, kernel: dict | None) -> dict[str, PlotObject]:
    """The objects a plot in the guide applies to. The kernel's type names win over the text."""
    types = {t for step in guide["steps"] for t in step["for_types"]}
    variables = (kernel or {}).get("variables") or {}
    found = {}
    for name, item in objects_from_cells(cells).items():
        kind = variables.get(name, item.type)
        if kind in types:
            found[name] = PlotObject(name, kind, item.significance)
    return found


# --- reading the request ----------------------------------------------------------------------

def build_prompt(objects: dict[str, PlotObject], guide: dict) -> str:
    listed = "\n".join(f"- {o.name} ({o.type})" for o in objects.values())
    present = {o.type for o in objects.values()}
    plots = "\n".join(
        f"- {s['id']}: {s['title']}, for {', '.join(s['for_types'])}"
        + (f"; asked as: {', '.join(s['asked_as'])}" if s.get("asked_as") else "")
        for s in guide["steps"] if s["use"] == "on_request" and present & set(s["for_types"]))
    return _INTERPRETER_PROMPT.format(objects=listed, plots=plots or "(none)")


def interpret(request: str, objects: dict[str, PlotObject], guide: dict,
              call_model: Callable[[str, str], str]) -> PlotRequest:
    result = PlotRequest()
    try:
        match = re.search(r"\{.*\}", call_model(build_prompt(objects, guide), request), re.DOTALL)
        if not match:
            raise ValueError("no JSON object in the reply")
        reply = json.loads(match.group(0))
        if not isinstance(reply, dict):
            raise ValueError("the reply is not a JSON object")
    except ValueError as exc:
        result.problems.append(f"couldn't read the model's reply: {exc}")
        return result
    chosen = reply.get("object")
    if isinstance(chosen, str):
        result.object = chosen  # checked against the notebook by the caller
    plot = reply.get("plot")
    if isinstance(plot, str):
        result.plot = plot
    return result


def choose_entry(item: PlotObject, plot: str | None, guide: dict) -> tuple[dict | None, str | None]:
    """The guide's entry for this object, and a message when the asked-for plot doesn't fit it."""
    entries = {s["id"]: s for s in guide["steps"]}
    if plot in entries:
        entry = entries[plot]
        if item.type in entry["for_types"]:
            return entry, None
        return None, (f"A {entry['title'].lower()} is for {' or '.join(entry['for_types'])} objects, "
                      f"and `{item.name}` is a {item.type}. Could you tell me which object to plot?")
    default = next((s for s in guide["steps"] if s["use"] == "default" and item.type in s["for_types"]), None)
    return default, None


# --- what Python adds -------------------------------------------------------------------------

def _levels(qs) -> str:
    values = [f"{round(q * 100)}%" for q in (qs if isinstance(qs, (list, tuple)) else [qs])
              if isinstance(q, (int, float))] or ["95%"]
    return values[0] if len(values) == 1 else ", ".join(values[:-1]) + " and " + values[-1]


def statements_for(entry: dict, plotted: list[PlotObject], guide: dict) -> list[str]:
    """The guide's fixed sentences for this plot: the cone of influence, and the significance
    lines of each plotted object that carries a test."""
    texts = guide.get("statements", {})
    found = []
    for kind in entry.get("adds", []):
        if kind == "cone_of_influence":
            found.append(" ".join(texts["cone_of_influence"].split()))
        elif kind == "significance_lines":
            for item in plotted:
                if not item.significance:
                    continue
                text = texts["significance_lines"].get(item.significance["method"])
                if isinstance(text, dict):
                    text = text["text"] if entry["id"] in text.get("only_for", []) else None
                if text:
                    sentence = " ".join(text.split()).format(levels=_levels(item.significance["qs"]))
                    if sentence not in found:
                        found.append(sentence)
    return found


def plotted_objects(code: str, entry: dict, objects: dict[str, PlotObject]) -> list[PlotObject]:
    """The objects the written plot call draws: its receiver and, for a summary plot, its arguments."""
    methods = workflow_writer._methods(entry)
    found = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return found
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in methods:
            names = [node.func.value, *node.args, *(k.value for k in node.keywords)]
            found += [objects[n.id] for n in names if isinstance(n, ast.Name) and n.id in objects]
    return list({o.name: o for o in found}.values())


def _add_statements(cell: workflow_writer.Cell, sentences: list[str]) -> None:
    """Python's sentences go right after the model's explanation (the heading, then the explanation)."""
    if sentences:
        parts = cell.text.split("\n\n")
        cell.text = "\n\n".join(parts[:2] + sentences + parts[2:])


# --- the flow ---------------------------------------------------------------------------------

def _which(objects: dict[str, PlotObject]) -> str:
    return ", ".join(f"`{o.name}` ({o.type})" for o in objects.values())


async def run(user_input: str, history: list[dict], guide: dict,
              call_model: Callable[[str, str], str], searches: list, max_repairs: int = 3,
              on_repair: Callable[[dict], None] | None = None,
              kernel: dict | None = None) -> dict | None:
    """Cells for a plot request, a question, or None when there's nothing this guide can plot."""
    cells = planning_flow.code_cells_from_history(history)
    objects = plottable(cells, guide, kernel)
    if not objects:
        return None

    meaning = await asyncio.to_thread(interpret, user_input, objects, guide, call_model)
    logger.info("Plot flow read the request as: object=%s plot=%s problems=%s",
                meaning.object, meaning.plot, meaning.problems)
    if meaning.problems:
        return planning_flow._ask("I'm not sure I understood that request. Could you rephrase it?")
    if meaning.object and meaning.object not in objects:
        return planning_flow._ask(f"I couldn't find `{meaning.object}` among the things I can plot in "
                                  f"your notebook: {_which(objects)}. Which one should I plot?")
    if not meaning.object and len(objects) > 1:
        return planning_flow._ask(f"I can plot several things in your notebook: {_which(objects)}. "
                                  "Which one should I plot?")
    item = objects[meaning.object] if meaning.object else next(iter(objects.values()))

    variables = (kernel or {}).get("variables")
    if variables is not None and item.name not in variables:
        return planning_flow._ask(f"The cell that creates `{item.name}` hasn't been run, so I couldn't "
                                  "check it. Could you run it, then ask me again?")

    entry, message = choose_entry(item, meaning.plot, guide)
    if message:
        return planning_flow._ask(message)
    if entry is None:
        return None
    missing = [t for t in entry.get("needs", []) if not any(o.type == t for o in objects.values())]
    if missing:
        return planning_flow._ask(f"A {entry['title'].lower()} needs a {' and a '.join(missing)} of "
                                  f"`{item.name}`, and I couldn't find them in your notebook. Could you "
                                  "compute them first, or ask me to, then ask me again?")

    plan = workflow_writer.Plan(series=item.name, objective="exploratory", method="", steps=[entry],
                                start=item.name, notebook_code=cells, request=user_input, kernel=kernel,
                                version_noted=planning_flow._version_noted(history))
    snippets = {entry["id"]: workflow_writer.prefer_asked(
        entry, await step_snippets.find_step_snippets(entry, searches), user_input)}
    task = {"objective": "exploratory", "expected_object": item.name, "expects_plot": True}

    written = await asyncio.to_thread(workflow_writer.write_workflow, plan, guide, snippets, call_model)
    problems = _problems(written, task)
    repairs = 0
    while problems and repairs < max_repairs:
        repairs += 1
        if on_repair:
            on_repair({"request": user_input, "plan": [entry["id"]], "attempt": repairs,
                       "problems": problems, "reply": written.reply})
        logger.info("Plot flow repair %d: %s", repairs, problems)
        previous = written
        written = await asyncio.to_thread(workflow_writer.write_workflow, plan, guide, snippets,
                                          call_model, previous.reply, problems)
        if not written.cells and previous.cells:
            written.cells = previous.cells  # an unusable repair must not lose the code
        problems = _problems(written, task)
    if repairs and on_repair:
        on_repair({"request": user_input, "outcome": "failed" if problems else "repaired",
                   "repairs": repairs, "problems": problems, "reply": written.reply})
    if not written.cells:
        return planning_flow._ask("I'm still learning and can't get this right yet, but I'm learning! "
                                  "I wasn't able to write this plot, so please try rephrasing your request.")

    code = next(c.text for c in written.cells if c.kind == "code")
    _add_statements(written.cells[0], statements_for(entry, plotted_objects(code, entry, objects), guide))
    new_cells = [asdict(c) for c in written.cells]
    if problems:
        new_cells.insert(0, planning_flow._warning_cell(problems))
    if not planning_flow._has_paleopal_cells(history):
        new_cells.insert(0, {"kind": "markdown", "text": planning_flow._INTRO, "step": None})
    return {"generated_code": code, "cells": new_cells, "needs_user_input": False,
            "checker_findings": problems, "repairs": repairs,
            "plan": {"series": item.name, "steps": [entry["id"]]}}


def _problems(written, task: dict) -> list[str]:
    """Only the code-only checks: a plot doesn't change the analysis, so the workflow checks
    would judge the researcher's earlier cells, not this one."""
    problems = list(written.problems)
    if written.cells:
        code = "\n\n".join(c.text for c in written.cells if c.kind == "code")
        findings = [f for f in verification.run_checks(code, task) if f.rule in verification.CODE_ONLY_CHECKS]
        problems += [f"{v.rule}: {v.detail}" if v.detail else v.rule
                     for v in verification.gate(findings)["violations"]]
    return problems
