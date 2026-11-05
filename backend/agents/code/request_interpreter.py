"""
request_interpreter.py — turn a researcher's words into facts the planner can use.

This is the only part of planning that uses a model, because people phrase the
same request in many ways. The model only picks from lists: the workflow file's
objectives and methods, and the series the detector found in the notebook. Plain
Python then rejects anything off those lists, so a made-up value can't reach the
planner. A fact the request doesn't state stays None.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

_SYSTEM_PROMPT = """You read one request from a paleoclimate researcher working in a notebook.
Report only what the request states. Never infer a goal the researcher did not express.
Reply with one JSON object and nothing else, with exactly these keys:

"analysis": "{analysis_id}" if the request asks for this analysis ({analysis_title}) or any of its steps, otherwise null.
"steps": a list of the steps below that the request explicitly asks for, otherwise []. A request for the whole analysis, or naming only a method, is [].
"whole_analysis": true if the request asks for the analysis itself, even when it also specifies a step ("run a spectral analysis with a linear detrend"); false if it only asks for particular steps ("detrend this record").
"series": the series the request refers to, from {series}. If it names something that is not in that list, return the name as written. If it names no series and doesn't point to one, null.
"objective": one of the objectives below if the request matches how it is asked for, otherwise null.
"method": one of {methods} if the request names that estimator, otherwise null.
"not_covered": a list of the parts of the request that are none of the above, each in the researcher's own words ("save the figure as a PDF"), otherwise []. Anything a step's settings can do is covered, so never list it: a bin size, a detrending method, a time range, or saving a plot (visualize's savefig_settings). Check the steps' settings before listing anything.

Steps:
{steps}

Objectives:
{objectives}

Terminology to resolve before answering:
{terminology}"""


@dataclass
class Interpretation:
    analysis: str | None = None
    series: str | None = None
    objective: str | None = None
    method: str | None = None
    steps: list[str] = field(default_factory=list)
    whole_analysis: bool = False
    # Parts of the request outside this analysis, in the researcher's words. Python can't check
    # these, only repeat them, so they are never acted on.
    not_covered: list[str] = field(default_factory=list)
    # Why a value was dropped. The planner should ask rather than guess.
    problems: list[str] = field(default_factory=list)


def _steps_text(workflow: dict, settings: dict[str, list[str]] | None) -> str:
    """Each step with the settings its functions take, so a setting isn't mistaken for a new task."""
    if not settings:
        return ", ".join(s["id"] for s in workflow["steps"])
    return "\n".join(f"- {s['id']}" + (f" (settings: {', '.join(settings[s['id']])})"
                                       if settings.get(s["id"]) else "")
                     for s in workflow["steps"])


def build_system_prompt(workflow: dict, series_names: list[str],
                        settings: dict[str, list[str]] | None = None) -> str:
    objectives = "\n".join(
        f"- {o['id']}: {o['description']}" + (f" Asked for as: {o['asked_as']}" if o.get("asked_as") else "")
        for o in workflow["objectives"])
    terminology = "\n".join(f"- {t['term']}: {t['disambiguation'].strip()}"
                            for t in workflow.get("terminology", []))
    return _SYSTEM_PROMPT.format(
        analysis_id=workflow["workflow"]["id"],
        analysis_title=workflow["workflow"]["title"],
        series=json.dumps(series_names),
        steps=_steps_text(workflow, settings),
        methods=json.dumps([m["id"] for m in workflow["method_registry"]]),
        objectives=objectives,
        terminology=terminology,
    )


def _parse_reply(reply: str) -> dict:
    match = re.search(r"\{.*\}", reply, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in the reply")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("the reply is not a JSON object")
    return parsed


def interpret_request(request: str, workflow: dict, series_names: list[str],
                      call_model: Callable[[str, str], str],
                      settings: dict[str, list[str]] | None = None) -> Interpretation:
    """`call_model(system_prompt, user_message)` returns the model's text reply.

    `settings` maps a step id to the argument names its functions take.
    """
    result = Interpretation()
    try:
        reply = _parse_reply(call_model(build_system_prompt(workflow, series_names, settings), request))
    except ValueError as exc:
        result.problems.append(f"couldn't read the model's reply: {exc}")
        return result

    allowed = {
        "analysis": {workflow["workflow"]["id"]},
        "series": set(series_names),
        "objective": {o["id"] for o in workflow["objectives"]},
        "method": {m["id"] for m in workflow["method_registry"]},
    }
    for key, values in allowed.items():
        value = reply.get(key)
        if value is None:
            continue
        if isinstance(value, str) and value in values:
            setattr(result, key, value)
        else:
            result.problems.append(f"{key} {value!r} isn't one of {sorted(values)}")

    result.whole_analysis = reply.get("whole_analysis") is True
    not_covered = reply.get("not_covered") or []
    result.not_covered = [" ".join(p.split()) for p in (not_covered if isinstance(not_covered, list) else [])
                          if isinstance(p, str) and p.strip()]
    known_steps = {s["id"] for s in workflow["steps"]}
    steps = reply.get("steps") or []
    for step in steps if isinstance(steps, list) else [steps]:
        if step in known_steps:
            result.steps.append(step)
        else:
            result.problems.append(f"step {step!r} isn't one of {sorted(known_steps)}")
    return result
