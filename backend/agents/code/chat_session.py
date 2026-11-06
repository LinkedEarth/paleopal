"""
chat_session.py — a conversation with a researcher about their notebook, for `@agent chat`.

The model answers in its own words and names what it drew on: steps of PaleoPAL's guide,
or parameters in the Pyleoclim reference. Python checks those names against the files and
adds the exact quoted text, so a researcher can check the answer. When nothing was drawn
from them, Python says the answer comes from the model only. Code proposed in the chat goes
through the checks that need only the new code. Nothing reaches the notebook until the
researcher agrees, and then as a summary written by `summarize`.

The conversation itself isn't kept: the summary is the record.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Callable

import yaml

from . import verification, workflow_writer

MAX_REPAIRS = 2
MODEL_ONLY_NOTE = ("This answer comes from the underlying AI model only, not from PaleoPAL's guide or "
                   "the Pyleoclim documentation, so it has had fewer checks than LinkedEarth workflows.")
PARTLY_MODEL_NOTE = ("Part of this answer comes from the underlying AI model only, not from the sources "
                     "below, so it has had fewer checks than LinkedEarth workflows.")
# Code-only checks that need something the chat doesn't have, like the series the plan chose.
_NOT_FOR_CHAT = {"correct_object"}

_SYSTEM_PROMPT = """You are PaleoPAL, an AI assistant for paleoclimate analysis from the LinkedEarth project.
You are having a conversation with a researcher about their notebook, the way a colleague would:
answer their questions, explain your reasoning, disagree gently when the science calls for it, and
help them reach a decision. Speak as "I" and to the researcher as "you". Be brief and gentle, and
always say why. Part of your audience is new to paleoclimate.

You have three sources. Prefer them, in this order, over your own knowledge:
1. PaleoPAL's guide to {analysis} (below). It decides which steps an analysis needs and why.
2. The Pyleoclim parameter reference (below): the documented parameters of the guide's methods.
3. The notebook (below), with who wrote each cell. A cell written by PaleoPAL is your own earlier
   note; a researcher's cell is their own work and choices.

When you suggest code: use the objects already in the notebook, never import or load anything
already there, plot through the object's own `.plot()` (matplotlib only to continue from the
`fig, ax` it returns), prefer a method's own parameters (such as `title` or `savefig_settings`) to
matplotlib calls, never take a Pyleoclim object apart into arrays for pyplot, and never reassign the
researcher's variables. Suggest code only when it helps; it is not run, and it only
reaches the notebook if the researcher agrees.

Cite a guide step or a parameter only when its text directly supports what you say. Set
"beyond_sources" to true if any part of your answer relies on your own knowledge instead.

When you and the researcher seem to have agreed on something, set "offer_summary" to true.

Reply with one JSON object and nothing else:
{{"reply": "<your answer, in Markdown>",
  "guide_steps": ["<ids of guide steps your answer relies on>"],
  "parameters": [{{"method": "<a method from the reference, e.g. pyleoclim.core.psds.PSD.plot>",
                   "names": ["<parameter names your answer relies on>"]}}],
  "code": "<python, or empty>",
  "beyond_sources": true,
  "offer_summary": false}}

## PaleoPAL's guide to {analysis}
{guide}

## Pyleoclim parameter reference (version {version})
{reference}"""

_SUMMARY_PROMPT = """You are PaleoPAL. Write the record of a conversation with a researcher, to be added to
their notebook. In 2-5 sentences, speaking to the researcher as "you" and of yourself as "I", say what
they asked, what you decided together, and why. Mention disagreements and how they were settled. Add
no new claims. If code was agreed, give the final version of it; otherwise leave it empty. The code
follows the same rules as before: no imports of what is already loaded, plots through the object's own
`.plot()`, no reassigning the researcher's variables.

Name only the guide steps and parameters the decision itself rests on. Always include every
parameter set in the code, under the method it belongs to. Set "beyond_sources" to true if the
decision relies on anything else.

Reply with one JSON object and nothing else:
{{"summary": "<Markdown>", "code": "<python, or empty>",
 "guide_steps": ["<step ids>"], "parameters": [{{"method": "<a method from the reference>", "names": ["<names>"]}}],
 "beyond_sources": true}}

## Guide steps
{steps}

## Pyleoclim parameter reference
{reference}"""


@dataclass
class Source:
    title: str
    text: str
    link: str | None = None


@dataclass
class ChatReply:
    reply: str = ""
    sources: list[Source] = field(default_factory=list)
    note: str | None = None  # the model-only note, added by Python
    code: str = ""
    problems: list[str] = field(default_factory=list)  # left after the repairs
    offer_summary: bool = False


def notebook_text(history: list[dict]) -> str:
    """The whole notebook, cell by cell, with who wrote each one."""
    lines = []
    for number, message in enumerate(history or [], start=1):
        if message.get("generated_content"):
            text = message["generated_content"]
            author = "PaleoPAL" if workflow_writer.AUTHORSHIP_CODE in text else "the researcher"
            lines.append(f"### Cell {number}: code, written by {author}\n```python\n{text}\n```")
        elif message.get("content"):
            author = "PaleoPAL" if message.get("agent_type") == "paleopal_note" else "the researcher"
            lines.append(f"### Cell {number}: markdown, written by {author}\n{message['content']}")
    return "\n\n".join(lines) or "(empty notebook)"


def _reference_text(reference: dict) -> str:
    parts = []
    for api, method in reference.get("methods", {}).items():
        entries = [*method.get("parameters", []), *method.get("passes_to", [])]
        listed = "\n".join(f"- {p['name']}: {p.get('definition') or 'no definition'}"
                           + (f" (default: {p['default']})" if p.get("default") else "") for p in entries)
        parts.append(f"### {api}\n{listed}")
    return "\n\n".join(parts)


def build_system_prompt(workflow: dict, reference: dict) -> str:
    return _SYSTEM_PROMPT.format(
        analysis=workflow["workflow"]["id"].replace("_", " "),
        guide=yaml.safe_dump(workflow, sort_keys=False),
        version=reference.get("pyleoclim_version", "unknown"),
        reference=_reference_text(reference) or "(not available)")


def _conversation(history: list[dict], messages: list[dict]) -> str:
    turns = "\n\n".join(f"**{'Researcher' if m.get('role') == 'user' else 'PaleoPAL'}:** {m.get('content', '')}"
                        for m in messages)
    return f"## The notebook\n{notebook_text(history)}\n\n## Our conversation so far\n{turns}"


def _parse(reply: str) -> dict:
    match = re.search(r"\{.*\}", reply, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in the reply")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("the reply is not a JSON object")
    return parsed


def sources_for(parsed: dict, workflow: dict, reference: dict) -> list[Source]:
    """The exact text behind what the model says it relied on. Names not in the files are dropped."""
    sources = []
    analysis = workflow["workflow"]["id"].replace("_", " ")
    by_id = {s["id"]: s for s in workflow["steps"]}
    plan = workflow_writer.Plan(series="", objective="exploratory",
                                method=workflow["method_selection"]["defaults_by_objective"]["exploratory"])
    for step_id in parsed.get("guide_steps") or []:
        step = by_id.get(step_id) if isinstance(step_id, str) else None
        text = step and workflow_writer.source_text(step, plan, workflow)
        if text:
            sources.append(Source(f"PaleoPAL's guide to {analysis}, on the "
                                  f"{workflow_writer._title(step)} step", text))
    methods, links = reference.get("methods", {}), reference.get("links", {})
    for cited in parsed.get("parameters") or []:
        if not isinstance(cited, dict) or cited.get("method") not in methods:
            continue
        api = cited["method"]
        method = methods[api]
        known = {p["name"]: p for p in [*method.get("passes_to", []), *method.get("parameters", [])]}
        label = ".".join(api.rsplit(".", 2)[-2:])
        for name in cited.get("names") or []:
            entry = known.get(name) if isinstance(name, str) else None
            if entry and entry.get("definition"):
                default = f" (default: {entry['default']})" if entry.get("default") else ""
                sources.append(Source(f"Pyleoclim documentation, `{label}`, parameter `{name}`",
                                      entry["definition"] + default, links.get(label)))
    return sources


def _code_problems(history: list[dict], code: str) -> list[str]:
    cells = [m["generated_content"] for m in history or [] if m.get("generated_content")]
    findings = [f for f in verification.check_new_code(cells, code, {})
                if f.rule in verification.CODE_ONLY_CHECKS and f.rule not in _NOT_FOR_CHAT]
    gate = verification.gate(findings)
    return [f"{v.rule}: {v.detail}" if v.detail else v.rule for v in gate["violations"]]


_REQUEST_CELL = """

## This is a request written in a notebook cell, not a conversation
Answer it directly: in "reply", 1-3 sentences saying what the code does and why, then the code.
Ask nothing back and don't offer a summary. Never import or load what the notebook already has."""


def reply(history: list[dict], messages: list[dict], workflow: dict, reference: dict,
          call_model: Callable[[str, str], str], request_cell: bool = False) -> ChatReply:
    """Answer the researcher's latest message. `messages` alternate user and assistant turns.

    With `request_cell`, the message is an `@agent code` request no guide covers, answered once.
    """
    system = build_system_prompt(workflow, reference)
    user = _conversation(history, messages) + (_REQUEST_CELL if request_cell else "")
    result = ChatReply()
    try:
        parsed = _parse(call_model(system, user))
    except ValueError:
        result.reply = "I'm still learning and couldn't put my answer together. Could you ask again?"
        return result

    code = str(parsed.get("code") or "").strip()
    problems = _code_problems(history, code) if code else []
    repairs = 0
    while problems and repairs < MAX_REPAIRS:
        repairs += 1
        listed = "\n".join(f"- {p}" for p in problems)
        try:
            fixed = _parse(call_model(system, f"{user}\n\n## Your draft reply\n{json.dumps(parsed)}\n\n"
                                              f"## Problems in its code\n{listed}\n\nReply with the "
                                              "complete corrected JSON. Change only what these require."))
        except ValueError:
            break
        parsed = fixed
        code = str(parsed.get("code") or "").strip()
        problems = _code_problems(history, code) if code else []

    result.reply = str(parsed.get("reply") or "").strip()
    result.sources = sources_for(parsed, workflow, reference)
    # The model can't be checked on this, so any doubt keeps the note.
    if not result.sources:
        result.note = MODEL_ONLY_NOTE
    elif parsed.get("beyond_sources") is not False:
        result.note = PARTLY_MODEL_NOTE
    result.code, result.problems = code, problems
    result.offer_summary = parsed.get("offer_summary") is True
    return result


def _sources_block(sources: list[dict]) -> str | None:
    unique = list({(s["title"], s["text"]): s for s in sources}.values())
    if not unique:
        return None
    lines = ["<details><summary>Sources</summary>", ""]
    for s in unique:
        title = f"[{s['title']}]({s['link']})" if s.get("link") else s["title"]
        lines += [f"**{title}:**", "", f"> {s['text']}", ""]
    return "\n".join(lines + ["</details>"])


def summarize(history: list[dict], messages: list[dict], workflow: dict, reference: dict,
              call_model: Callable[[str, str], str]) -> dict:
    """The cells recording the conversation: a summary, and the agreed code if any.

    The sources are quoted by Python from what the decision rests on. Any reply the researcher
    saw with a model-only note keeps that note in the record.
    """
    system = _SUMMARY_PROMPT.format(steps=", ".join(s["id"] for s in workflow["steps"]),
                                    reference=_reference_text(reference) or "(not available)")
    parsed = _parse(call_model(system, _conversation(history, messages)))
    sources = [asdict(s) for s in sources_for(parsed, workflow, reference)]
    model_only = (not sources or parsed.get("beyond_sources") is not False
                  or any(m.get("note") for m in messages if m.get("role") == "assistant"))
    parts = ["### Summary of our discussion", str(parsed.get("summary") or "").strip()]
    if model_only:
        parts.append("Part of this discussion came from the underlying AI model only, not from "
                     "PaleoPAL's guide or the Pyleoclim documentation, so it has had fewer checks "
                     "than LinkedEarth workflows.")
    block = _sources_block(sources)
    parts += [*([block] if block else []),
              f"{workflow_writer.AUTHORSHIP_MARKDOWN}"
              + (" Sources are quoted directly, not written by the AI." if block else "")]
    code = str(parsed.get("code") or "").strip()
    problems = _code_problems(history, code) if code else []
    if problems:
        listed = "\n".join(f"- {p}" for p in problems)
        parts.insert(2, "I'm still learning and can't get this right yet, but I'm learning! Please "
                        f"check the code below, because these problems remain:\n\n{listed}")
    cells = [{"kind": "markdown", "text": "\n\n".join(parts), "step": None}]
    if code:
        cells.append({"kind": "code", "text": f"{workflow_writer.AUTHORSHIP_CODE}\n{code}", "step": None})
    return {"cells": cells, "problems": problems}


def as_dict(result: ChatReply) -> dict:
    return asdict(result)
