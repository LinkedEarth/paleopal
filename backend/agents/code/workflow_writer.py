"""
workflow_writer.py — turn the detector's missing steps into notebook cells.

Python decides which steps run and in what order. The model only writes the code
and a short explanation for each one, and Python rejects a reply that adds, drops
or reorders steps, or repeats an import. So that a reader can check an explanation,
Python adds its source: the exact workflow-file text the model was given, and the
examples it received. The model can't change or misquote those. Statements PaleoPAL
must make come from the file too, never from the model.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from typing import Callable

import yaml

AUTHORSHIP_MARKDOWN = "*Written by PaleoPAL*"
AUTHORSHIP_CODE = "# Written by PaleoPAL"

_SNIPPETS_PER_STEP = 2
_SNIPPET_CHARS = 800
_SPECTRAL_STEP = "spectral_estimate"

_SYSTEM_PROMPT = """You write the code for one paleoclimate workflow, step by step, for a notebook.
The steps are already decided. Write exactly these steps, in this order, one entry each.
Add nothing else: no slicing, no extra methods, no extra plots, no printing, no saving.

Rules for the code:
- `{series}` is already loaded and pyleoclim is already imported. Never import or load anything.
- Start from `{series}`. Each step continues from the previous step's result.
- Give each result a new variable name. Never reassign `{series}`.
- Use straight-line code: no `if`, no `try`.
- Plot through the object's own `.plot()`. Never pass `.time`, `.value`, `.frequency` or `.amplitude` to pyplot.
{method_rule}
- Field names in the step definitions describe a schema. They are not Python arguments.

Examples are labelled per step. They only show how to write that step. They may contain other
steps and other parameters: ignore those. They never add a step.

For each step's "explanation", write 1-3 plain sentences in the first person, speaking directly
to the reader as "you", saying what the step does and why, for someone new to paleoclimate. Base
it only on that step's "Source text". Put it in your own words, and add no other claims.

Reply with one JSON object and nothing else:
{{"steps": [{{"id": "<step id>", "explanation": "<text>", "code": "<python>"}}]}}"""


@dataclass
class Plan:
    series: str
    objective: str
    method: str
    steps: list[dict] = field(default_factory=list)
    # User-facing lines Python adds, keyed by step id. "" means after the last step.
    notes: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class Cell:
    kind: str  # markdown | code
    text: str
    step: str | None = None


@dataclass
class WriteResult:
    cells: list[Cell] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def build_plan(state, workflow: dict, objective: str | None = None,
               method: str | None = None) -> Plan:
    """Choose the steps to write from the detector's report and the workflow file."""
    objective = objective or "exploratory"
    method = method or workflow["method_selection"]["defaults_by_objective"][objective]
    registry = {m["id"]: m for m in workflow["method_registry"]}
    status = {s.id: s.status for s in state.steps}
    plan = Plan(series=state.target, objective=objective, method=method)

    for step in workflow["steps"]:
        wanted = status[step["id"]] == "to_do"
        if status[step["id"]] == "depends_on_method" and step["id"] == "regrid":
            wanted = registry[method]["requires_even_spacing"]
            if not wanted:
                plan.notes.setdefault(_SPECTRAL_STEP, []).append(
                    f"`{method}` tolerates uneven sampling, so I did not include a regridding step."
                )
        if wanted:
            plan.steps.append(step)

    for rule in workflow["rules"]:
        if rule.get("kind") == "disclosure" and objective in rule.get("applies_to_objectives", []):
            plan.notes.setdefault("", []).append(" ".join(rule["must_say"].split()))
    return plan


def source_text(step: dict, plan: Plan, workflow: dict) -> str | None:
    """The workflow-file text an explanation must rest on, if the file has any."""
    text = step.get("rationale")
    if not text and step["id"] == _SPECTRAL_STEP:
        text = next((m.get("rationale") for m in workflow["method_registry"]
                     if m["id"] == plan.method), None)
    if not text and step.get("rule"):
        text = next((r["statement"] for r in workflow["rules"] if r["id"] == step["rule"]), None)
    return " ".join(text.split()) if text else None


def _examples_for(step: dict, snippets: dict[str, list[dict]]) -> list[dict]:
    return snippets.get(step["id"], [])[:_SNIPPETS_PER_STEP]


def _sources_block(step: dict, plan: Plan, workflow: dict, snippets: dict[str, list[dict]]) -> str:
    """A collapsed section showing what the explanation and code were given."""
    source = source_text(step, plan, workflow)
    lines = ["<details><summary>Sources</summary>", ""]
    if source:
        lines += [f"**PaleoPAL workflow file, `{step['id']}`:**", "", f"> {source}", ""]
    else:
        lines += ["The workflow file has no source text for this step yet.", ""]
    names = [str(e.get("notebook") or e.get("symbol") or "unnamed example").rsplit("/", 1)[-1]
             for e in _examples_for(step, snippets)]
    if names:
        lines += ["**Code examples given to the model:** "
                  + ", ".join(f"`{n}`" for n in names), ""]
    return "\n".join(lines + ["</details>"])


def build_user_message(plan: Plan, workflow: dict, snippets: dict[str, list[dict]]) -> str:
    parts = []
    for step in plan.steps:
        definition = {k: v for k, v in step.items() if k not in ("container_api", "rationale")}
        parts.append(f"## Step: {step['id']}\n{yaml.safe_dump(definition, sort_keys=False)}")
        source = source_text(step, plan, workflow)
        parts.append(f"Source text: {source or 'none. Say only what this step does.'}")
        for example in _examples_for(step, snippets):
            parts.append(f"Example for {step['id']}:\n```python\n"
                         f"{example.get('code', '')[:_SNIPPET_CHARS]}\n```")
    return "\n\n".join(parts)


def _parse_reply(reply: str) -> list[dict]:
    match = re.search(r"\{.*\}", reply, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in the reply")
    steps = json.loads(match.group(0)).get("steps")
    if not isinstance(steps, list) or not all(isinstance(s, dict) for s in steps):
        raise ValueError("the reply has no list of steps")
    return steps


def _code_problems(step_id: str, code: str) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"{step_id}: the code doesn't parse ({exc.msg})"]
    if any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(tree)):
        return [f"{step_id}: the code repeats an import"]
    return []


def write_workflow(plan: Plan, workflow: dict, snippets: dict[str, list[dict]],
                   call_model: Callable[[str, str], str]) -> WriteResult:
    """`call_model(system_prompt, user_message)` returns the model's text reply."""
    result = WriteResult()
    system = _SYSTEM_PROMPT.format(
        series=plan.series,
        method_rule=f"- In the spectral step, use method='{plan.method}'.",
    )
    try:
        written = _parse_reply(call_model(system, build_user_message(plan, workflow, snippets)))
    except ValueError as exc:
        result.problems.append(f"couldn't read the model's reply: {exc}")
        return result

    expected = [s["id"] for s in plan.steps]
    received = [s.get("id") for s in written]
    if received != expected:
        result.problems.append(f"expected steps {expected}, got {received}")
        return result

    for step, reply in zip(plan.steps, written):
        code = str(reply.get("code", "")).strip()
        result.problems.extend(_code_problems(step["id"], code))
        explanation = " ".join(str(reply.get("explanation", "")).split())
        if not explanation:
            result.problems.append(f"{step['id']}: the reply has no explanation")
        title = step["id"].replace("_", " ").capitalize()
        if step["requiredness"] == "recommended":
            title += " (recommended)"
        lines = [f"### {title}", explanation, *plan.notes.get(step["id"], []),
                 _sources_block(step, plan, workflow, snippets), AUTHORSHIP_MARKDOWN]
        result.cells.append(Cell("markdown", "\n\n".join(lines), step["id"]))
        result.cells.append(Cell("code", f"{AUTHORSHIP_CODE}\n{code}", step["id"]))

    for note in plan.notes.get("", []):
        result.cells.append(Cell("markdown", f"{note}\n\n{AUTHORSHIP_MARKDOWN}"))
    return result
