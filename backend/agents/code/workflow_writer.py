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
import pathlib
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable

import yaml

AUTHORSHIP_MARKDOWN = "*Written by PaleoPAL*"
AUTHORSHIP_CODE = "# Written by PaleoPAL"

_SNIPPETS_PER_STEP = 2
_SNIPPET_CHARS = 800
_CONTEXT_CHARS = 400
_NO_MARKDOWN = "Notebook start"  # the indexer's placeholder for a section with no text
_SPECTRAL_STEP = "spectral_estimate"
_PARAMETERS_FILE = pathlib.Path(__file__).parents[2] / "workflows" / "pyleoclim_parameters.json"

_SYSTEM_PROMPT = """You write the code for one paleoclimate workflow, step by step, for a notebook.
The steps are already decided. Write exactly these steps, in this order, one entry each.
Add nothing else: no slicing, no extra methods, no extra plots, no printing, no saving.

Rules for the code:
- `{series}` is already loaded and pyleoclim is already imported. Never import or load anything.
- Start from `{start}`. Each step continues from the previous step's result.
- Give each result a new variable name. Never reassign an existing variable.
- Use straight-line code: no `if`, no `try`.
- Plot through the object's own `.plot()`. Never pass `.time`, `.value`, `.frequency` or `.amplitude` to pyplot.
{method_rule}
- Field names in the step definitions describe a schema. They are not Python arguments.

The researcher's request comes first in the message. Use any arguments or choices it states for
these steps, such as a bin size or which way to regrid. It never adds, removes or reorders steps.

Examples are labelled per step. They show how to write that step, and their arguments can guide
yours, because Pyleoclim's defaults aren't always the scientifically right choice. They may also
contain other steps: ignore those. An example never adds a step.

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
    start: str | None = None  # the variable to continue from; defaults to the series
    notebook_code: list[str] = field(default_factory=list)
    # True when a new chain is built from the series, leaving the user's cells as they are.
    fresh_chain: bool = False
    decisions: list[dict] = field(default_factory=list)  # the user's yes/no answers
    request: str = ""  # the researcher's words, which can set arguments but not steps


@dataclass
class NextStep:
    """Exactly one is set: cells to write, a question to ask, or something to explain."""
    plan: Plan | None = None
    question: dict | None = None
    message: str | None = None


@dataclass
class Cell:
    kind: str  # markdown | code
    text: str
    step: str | None = None
    decisions: list[dict] = field(default_factory=list)


@dataclass
class WriteResult:
    cells: list[Cell] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    reply: str = ""  # the model's raw reply, needed to ask it for a repair


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


def _title(step: dict) -> str:
    return step["id"].replace("_", " ")


def _objective_for(requested: list[dict], objective: str | None) -> str:
    """Asking for a step only some objectives need, like the significance test, states that goal."""
    for step in requested:
        match = re.fullmatch(r"required_for\((\w+)\)", step["requiredness"])
        if match:
            return match.group(1)
    return objective or "exploratory"


def _dependent_steps(workflow: dict, step_ids: set[str]) -> list[dict]:
    """Steps to redo because their result depends on one being added, like a plot on a test."""
    return [s for s in workflow["steps"]
            if any(p.get("depends_on_step") in step_ids
                   for p in (s.get("parameters_by_objective") or {}).values())]


def _add_proposals(plan: Plan, workflow: dict, done: set[str]) -> None:
    if _SPECTRAL_STEP not in done:  # these statements are about a spectrum
        return
    steps_by_rule = {s.get("rule"): s["id"] for s in workflow["steps"]}
    for rule in workflow["rules"]:
        if (rule.get("kind") == "disclosure" and plan.objective in rule.get("applies_to_objectives", [])
                and steps_by_rule.get(rule.get("related")) not in done):
            plan.notes.setdefault("", []).append(" ".join(rule["must_say"].split()))


def plan_next_step(state, workflow: dict, requested_ids: list[str], objective: str | None = None,
                   method: str | None = None, answers: dict[str, str] | None = None) -> NextStep:
    """Apply the gap rules to a request made partway through a workflow.

    A missing required step is added with the reason. A missing recommended step is
    asked about, and answered through `answers` ({step id: "yes" | "no"}).
    """
    answers = {k: v.strip().lower() for k, v in (answers or {}).items()}
    by_id = {s["id"]: s for s in workflow["steps"]}
    done = {s.id for s in state.steps if s.status == "done"}
    if not requested_ids:
        requested_ids = [_SPECTRAL_STEP]
    # A stated goal reaches past the spectrum: finding peaks needs the significance test.
    if _SPECTRAL_STEP in requested_ids:
        requested_ids = [*requested_ids, *(s["id"] for s in workflow["steps"]
                                           if s["requiredness"] == f"required_for({objective})"
                                           and s["id"] not in requested_ids)]
    requested = [by_id[i] for i in requested_ids]
    objective = _objective_for(requested, objective)
    method = method or workflow["method_selection"]["defaults_by_objective"][objective]
    registry = {m["id"]: m for m in workflow["method_registry"]}

    already = [i for i in requested_ids if i in done]
    if already and len(already) == len(requested_ids):
        names = ", ".join(_title(by_id[i]) for i in already)
        return NextStep(message=f"Your notebook already has the {names} step for `{state.target}`. "
                                "I can't change an existing step yet, so I left it as it is.")

    plan = Plan(series=state.target, objective=objective, method=method, start=state.current)
    wanted = [s for s in requested if s["id"] not in done]
    last_order = max(s["order"] for s in wanted)
    before_spectrum = _SPECTRAL_STEP not in done and last_order >= by_id[_SPECTRAL_STEP]["order"]
    added, skipped = [], []

    # Checked first: if the record can't be regridded in place, asking about other steps is moot.
    if before_spectrum and registry[method]["requires_even_spacing"]:
        regrid = next((s for s in workflow["steps"] if s["requiredness"].startswith("determined_by")), None)
        asked_for_it = regrid in wanted  # then there's no doubt that the record needs it
        if regrid and not asked_for_it and regrid["id"] not in done \
                and any(by_id[d]["order"] > regrid["order"] for d in done):
            return NextStep(message=
                f"`{method}` needs evenly spaced data, and regridding has to come before the "
                f"steps your notebook has already run on `{state.target}`. I can't change "
                "existing cells yet. If your record is unevenly spaced, please add the "
                "regridding step earlier in your notebook, then ask me again.")

    for step in workflow["steps"]:
        step_id = step["id"]
        if step_id in done or step in wanted or step["order"] >= last_order:
            continue
        requiredness = step["requiredness"]
        if requiredness == "required":
            added.append(step)
        elif requiredness.startswith("determined_by") and before_spectrum:
            if not registry[method]["requires_even_spacing"]:
                plan.notes.setdefault(_SPECTRAL_STEP, []).append(
                    f"`{method}` tolerates uneven sampling, so I did not include a regridding step.")
            else:
                added.append(step)
        elif requiredness == "recommended" and before_spectrum:
            answer = answers.get(step_id)
            if answer is None:
                reason = " ".join((step.get("ask_reason") or "").split())
                return NextStep(question={
                    "id": step_id, "choices": ["Yes", "No"],
                    "question": f"Would you like me to add the {_title(step)} step first?",
                    "context": f"I recommend it, and your notebook doesn't have it yet. {reason}".strip()})
            if answer.startswith("y"):
                added.append(step)
                plan.decisions.append({"step": step_id, "answer": "yes"})
            else:
                skipped.append(step)
                plan.decisions.append({"step": step_id, "answer": "no"})

    # A preprocessing step that belongs before steps already run means a new chain,
    # whether it was recommended or the researcher asked for it.
    latest_done = max((by_id[d]["order"] for d in done), default=-1)
    spectrum_order = by_id[_SPECTRAL_STEP]["order"]
    earlier = [s for s in [*added, *wanted] if s["order"] < latest_done and s["order"] < spectrum_order]
    plan.fresh_chain = bool(earlier)
    if plan.fresh_chain:
        plan.start = state.target
        redo = [s for s in workflow["steps"] if s["id"] in done and s["order"] < last_order
                and s["order"] > min(e["order"] for e in earlier)]
        added += [s for s in redo if s not in added]

    chosen = {s["id"] for s in [*added, *wanted]}
    extras = [s for s in _dependent_steps(workflow, chosen) if s["id"] not in chosen]
    plan.steps = sorted([*added, *wanted, *extras], key=lambda s: s["order"])
    first = plan.steps[0]["id"]

    for step in added:
        if step in skipped or any(d["step"] == step["id"] for d in plan.decisions):
            continue
        if not plan.fresh_chain or step["requiredness"] == "required":
            plan.notes.setdefault(step["id"], []).append(
                "You didn't ask for this step, but I added it because the workflow requires it here.")
    for decision in plan.decisions:
        name = _title(by_id[decision["step"]])
        if decision["answer"] == "yes":
            plan.notes.setdefault(decision["step"], []).append(
                f"I added the {name} step because you confirmed it.")
        else:
            plan.notes.setdefault(first, []).append(
                f"You chose not to add the {name} step, after I recommended it.")
    if plan.fresh_chain:
        plan.notes.setdefault(first, []).append(
            f"That step has to come before ones your notebook has already run, so I started a "
            f"new chain from `{state.target}`. Your earlier cells are unchanged.")
    _add_proposals(plan, workflow, done | chosen)
    return NextStep(plan=plan)


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


@lru_cache(maxsize=1)
def _parameter_reference() -> dict:
    """Built by scripts/build_pyleoclim_parameters.py. Cells are still useful without it."""
    try:
        return json.loads(_PARAMETERS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _argument_line(entry: dict | None, name: str, value: str, indent: str = "") -> str:
    entry = entry or {}
    words = " ".join(w for w in (entry.get("type") and f"({entry['type']})", entry.get("definition")) if w)
    words = words or "I couldn't find a definition for this in the Pyleoclim documentation."
    default = f" *(default: {entry['default']})*" if entry.get("default") else ""
    return f"{indent}- `{name}={value}`: {words}{default}"


def _describe_call(call: ast.Call, method: dict) -> tuple[list[str], list[str]]:
    """Lines defining what one call sets, and the utils functions those definitions came from."""
    parameters = method.get("parameters", [])
    known = {p["name"]: p for p in [*method.get("passes_to", []), *parameters]}
    arguments = [(p["name"], v) for p, v in zip(parameters, call.args) if not isinstance(v, ast.Starred)]
    arguments += [(k.arg, k.value) for k in call.keywords if k.arg]
    chosen = dict(arguments).get("method")
    default = known.get("method", {}).get("default") or "None"
    estimator = chosen.value if isinstance(chosen, ast.Constant) else default.strip("'")
    settings = {p["name"]: p for p in method.get("settings_by_method", {}).get(estimator, [])}

    lines, sources = [], []
    for name, value in arguments:
        entry = known.get(name)
        lines.append(_argument_line(entry, name, ast.unparse(value)))
        sources.append((entry or {}).get("source"))
        if name == "settings" and isinstance(value, ast.Dict):
            for key, item in zip(value.keys, value.values):
                if isinstance(key, ast.Constant):
                    inner = settings.get(key.value)
                    lines.append(_argument_line(inner, key.value, ast.unparse(item), "  "))
                    sources.append((inner or {}).get("source"))
    return lines, [s for s in sources if s]


def _parameters_block(step: dict, code: str, reference: dict | None = None) -> str | None:
    """A collapsed section defining the arguments the code sets, copied from Pyleoclim's docs."""
    reference = _parameter_reference() if reference is None else reference
    if not reference:
        return None
    apis = step.get("core_api") or []
    by_name = {api.rsplit(".", 1)[-1]: api for api in (apis if isinstance(apis, list) else [apis])}
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr in by_name]

    lines, labels = [], []
    # Calls end in the order they run, so a chain reads left to right.
    for call in sorted(calls, key=lambda c: (c.end_lineno, c.end_col_offset)):
        api = by_name[call.func.attr]
        found, sources = _describe_call(call, reference.get("methods", {}).get(api, {}))
        if found:
            lines += found
            labels += [".".join(api.rsplit(".", 2)[-2:]), *sources]
    if not lines:
        return None

    links = reference.get("links", {})
    linked = [f"[`{label}`]({links[label]})" for label in dict.fromkeys(labels) if label in links]
    return "\n".join(["<details><summary>Parameters</summary>", "",
                      f"From the documentation of Pyleoclim {reference['pyleoclim_version']}. "
                      "Your installed version may differ.", "", *lines, "",
                      *([f"Full documentation: {', '.join(linked)}", ""] if linked else []),
                      "</details>"])


def build_user_message(plan: Plan, workflow: dict, snippets: dict[str, list[dict]]) -> str:
    parts = []
    if plan.request:
        parts.append(f"## The researcher's request\n{plan.request}")
    if plan.notebook_code:
        parts.append("## Code already in the notebook. Reuse its variable names.\n```python\n"
                     + "\n\n".join(plan.notebook_code) + "\n```")
    for step in plan.steps:
        definition = {k: v for k, v in step.items() if k not in ("container_api", "rationale")}
        parts.append(f"## Step: {step['id']}\n{yaml.safe_dump(definition, sort_keys=False)}")
        source = source_text(step, plan, workflow)
        parts.append(f"Source text: {source or 'none. Say only what this step does.'}")
        for example in _examples_for(step, snippets):
            context = " ".join((example.get("markdown_context") or "").split())
            context = "" if context == _NO_MARKDOWN else context[:_CONTEXT_CHARS]
            parts.append(f"Example for {step['id']}:\n"
                         + (f"Its notebook's text: {context}\n" if context else "")
                         + f"```python\n{example.get('code', '')[:_SNIPPET_CHARS]}\n```")
    return "\n\n".join(parts)


def _parse_reply(reply: str) -> list[dict]:
    match = re.search(r"\{.*\}", reply, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in the reply")
    steps = json.loads(match.group(0)).get("steps")
    if not isinstance(steps, list) or not all(isinstance(s, dict) for s in steps):
        raise ValueError("the reply has no list of steps")
    return steps


def _methods(step: dict) -> set[str]:
    apis = step.get("core_api") or []
    return {api.rsplit(".", 1)[-1] for api in (apis if isinstance(apis, list) else [apis])}


def _code_problems(step: dict, code: str, workflow: dict) -> list[str]:
    step_id = step["id"]
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"{step_id}: the code doesn't parse ({exc.msg})"]
    if any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(tree)):
        return [f"{step_id}: the code repeats an import"]
    # A step's code doing another step's work would hide it from that step's explanation.
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    others = {m for s in workflow["steps"] if s["id"] != step_id for m in _methods(s)}
    return [f"{step_id}: this step's code also calls `{m}`, which belongs to another step. "
            "Each step's code must do only that step." for m in sorted((called & others) - _methods(step))]


def _repair_request(previous: str, problems: list[str]) -> str:
    listed = "\n".join(f"- {p}" for p in problems)
    return (f"\n\n## Your previous reply\n{previous}\n\n## Problems to fix\n{listed}\n\n"
            "Reply with the complete corrected JSON, for all the steps. "
            "Change only what these problems require.")


def write_workflow(plan: Plan, workflow: dict, snippets: dict[str, list[dict]],
                   call_model: Callable[[str, str], str], previous: str | None = None,
                   problems: list[str] | None = None) -> WriteResult:
    """`call_model(system_prompt, user_message)` returns the model's text reply.

    Pass `previous` and `problems` to ask the model to repair an earlier reply.
    """
    result = WriteResult()
    system = _SYSTEM_PROMPT.format(
        series=plan.series,
        start=plan.start or plan.series,
        method_rule=f"- In the spectral step, use method='{plan.method}'.",
    )
    message = build_user_message(plan, workflow, snippets)
    if previous is not None:
        message += _repair_request(previous, problems or [])
    try:
        result.reply = call_model(system, message)
        written = _parse_reply(result.reply)
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
        result.problems.extend(_code_problems(step, code, workflow))
        explanation = " ".join(str(reply.get("explanation", "")).split())
        if not explanation:
            result.problems.append(f"{step['id']}: the reply has no explanation")
        title = step["id"].replace("_", " ").capitalize()
        if step["requiredness"] == "recommended":
            title += " (recommended)"
        parameters = _parameters_block(step, code)
        lines = [f"### {title}", explanation, *plan.notes.get(step["id"], []),
                 *([parameters] if parameters else []),
                 _sources_block(step, plan, workflow, snippets), AUTHORSHIP_MARKDOWN]
        decisions = plan.decisions if step is plan.steps[0] else []
        result.cells.append(Cell("markdown", "\n\n".join(lines), step["id"], decisions))
        result.cells.append(Cell("code", f"{AUTHORSHIP_CODE}\n{code}", step["id"]))

    for note in plan.notes.get("", []):
        result.cells.append(Cell("markdown", f"{note}\n\n{AUTHORSHIP_MARKDOWN}"))
    return result
