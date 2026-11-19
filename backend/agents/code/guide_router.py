"""
guide_router.py — choose which of PaleoPAL's guides a request needs.

The first step for every `@agent code` request. A model reads the request and
picks from the guides' ids; Python rejects anything else. No guide means the
request is answered by the model alone, with the note that says so.

This is the seed of the single front door (the plan step): today it only
chooses guides; later it also decides data versus analysis.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

GUIDES_DIR = Path(__file__).resolve().parents[2] / "workflows"
GUIDE_FILES = {
    "spectral_analysis": "spectral_full.yml",
    "visualization": "visualization.yml",
}

_SYSTEM_PROMPT = """You choose which of PaleoPAL's guides a researcher's request needs.
Each guide covers one kind of work in a paleoclimate notebook. Reply with one JSON object and nothing else:
{{"guides": [...]}}, listing the ids of the guides the request needs, in the order they apply.

- List a guide only if the request asks for something it covers.
- An analysis guide already plots its own result: "run a spectral analysis and plot it" needs only that analysis guide.
- The visualization guide is for plots on their own ("plot lr04", "plot the spectrum", "make a dashboard"), and for plots an analysis doesn't make ("plot the series, then run a spectral analysis" needs both).
- Plotting something that already exists in the notebook needs only the visualization guide, even when its
name mentions an analysis step: "plot the detrended series" is a plot of an existing detrended series, not a
request to detrend. Use an analysis guide only when the request asks for something to be computed.
- If no guide covers the request, reply {{"guides": []}}.

Guides:
{guides}

Objects already in the notebook (name and type):
{objects}"""


@dataclass
class Route:
    guides: list[str] = field(default_factory=list)
    # Why a value was dropped, or why the reply couldn't be read.
    problems: list[str] = field(default_factory=list)
    # True when the reply couldn't be read at all: the caller falls back to the old behaviour.
    failed: bool = False


def load_guides(directory: Path = GUIDES_DIR) -> dict[str, dict]:
    import yaml
    guides = {}
    for guide_id, name in GUIDE_FILES.items():
        with open(directory / name, encoding="utf-8") as f:
            guides[guide_id] = yaml.safe_load(f)
    return guides


def describe(guide: dict) -> str:
    """One guide for the prompt: its id, title, goal and what its entries cover."""
    head = guide["workflow"]
    entries = []
    for step in guide.get("steps", []):
        asked = step.get("asked_as")
        types = step.get("for_types")
        entries.append(step["id"] + (f" (for {', '.join(types)})" if types else "")
                       + (f" (asked as: {', '.join(asked)})" if asked else ""))
    return (f"- {head['id']}: {head['title']}. {' '.join(head['goal'].split())}\n"
            f"  Covers: {'; '.join(entries)}")


def build_system_prompt(guides: dict[str, dict], objects: dict[str, str] | None = None) -> str:
    listed = "\n".join(f"- {name} ({kind})" for name, kind in (objects or {}).items()) or "(none)"
    return _SYSTEM_PROMPT.format(guides="\n".join(describe(g) for g in guides.values()), objects=listed)


def route_request(request: str, guides: dict[str, dict],
                  call_model: Callable[[str, str], str], objects: dict[str, str] | None = None) -> Route:
    """`call_model(system_prompt, user_message)` returns the model's text reply.

    `objects` maps the notebook's Pyleoclim objects to their type names (never values), so a request to
    plot an existing object isn't mistaken for a request to compute it."""
    route = Route()
    try:
        match = re.search(r"\{.*\}", call_model(build_system_prompt(guides, objects), request), re.DOTALL)
        if not match:
            raise ValueError("no JSON object in the reply")
        chosen = json.loads(match.group(0)).get("guides")
        if not isinstance(chosen, list):
            raise ValueError("'guides' isn't a list")
    except (ValueError, AttributeError) as exc:
        route.problems.append(f"couldn't read the model's reply: {exc}")
        route.failed = True
        return route
    for guide_id in chosen:
        if guide_id in guides and guide_id not in route.guides:
            route.guides.append(guide_id)
        elif guide_id not in guides:
            route.problems.append(f"guide {guide_id!r} isn't one of {sorted(guides)}")
    return route
