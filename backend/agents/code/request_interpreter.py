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

"analysis": "{analysis_id}" if the request asks for this analysis ({analysis_title}), otherwise null.
"series": the series the request refers to, from {series}. If it names something that is not in that list, return the name as written. If it names no series and doesn't point to one, null.
"objective": one of the objectives below if the request states that goal, otherwise null.
"method": one of {methods} if the request names that estimator, otherwise null.

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
    # Why a value was dropped. The planner should ask rather than guess.
    problems: list[str] = field(default_factory=list)


def build_system_prompt(workflow: dict, series_names: list[str]) -> str:
    objectives = "\n".join(f"- {o['id']}: {o['description']}" for o in workflow["objectives"])
    terminology = "\n".join(f"- {t['term']}: {t['disambiguation'].strip()}"
                            for t in workflow.get("terminology", []))
    return _SYSTEM_PROMPT.format(
        analysis_id=workflow["workflow"]["id"],
        analysis_title=workflow["workflow"]["title"],
        series=json.dumps(series_names),
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
                      call_model: Callable[[str, str], str]) -> Interpretation:
    """`call_model(system_prompt, user_message)` returns the model's text reply."""
    result = Interpretation()
    try:
        reply = _parse_reply(call_model(build_system_prompt(workflow, series_names), request))
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
    return result
