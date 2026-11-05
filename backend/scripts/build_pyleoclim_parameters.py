#!/usr/bin/env python3
"""Build pyleoclim_parameters.json: what each workflow method's parameters mean.

The backend doesn't have Pyleoclim installed, so run this once in an environment
that does. The file records the version it came from, because definitions and
defaults belong to a version, and PaleoPAL shows that version in the notebook.

  ~/anaconda3/envs/pyleo/bin/python backend/scripts/build_pyleoclim_parameters.py

Definitions are copied word for word from the docstrings, apart from line breaks.
Links are checked against the published documentation while building, so this needs
internet access.
"""
from __future__ import annotations

import importlib
import inspect
import json
import pathlib
import re
import urllib.request

import yaml

_WORKFLOWS = pathlib.Path(__file__).parents[1] / "workflows"
_DOCS = "https://pyleoclim-util.readthedocs.io/en"
_SERIES = "pyleoclim.core.series.Series"
_TSUTILS = "pyleoclim.utils.tsutils"
_SPECTRAL = "pyleoclim.utils.spectral"
# Where Pyleoclim sends arguments a method doesn't name itself. Written by hand from its
# source, so update this if Pyleoclim adds or moves one.
_PASSES_ARGUMENTS_TO = {f"{_SERIES}.bin": f"{_TSUTILS}.bin", f"{_SERIES}.interp": f"{_TSUTILS}.interp",
                        f"{_SERIES}.detrend": f"{_TSUTILS}.detrend",
                        f"{_SERIES}.standardize": f"{_TSUTILS}.standardize"}
_SETTINGS_GO_TO = {f"{_SERIES}.spectral": {
    "lomb_scargle": f"{_SPECTRAL}.lomb_scargle", "mtm": f"{_SPECTRAL}.mtm", "wwz": f"{_SPECTRAL}.wwz_psd",
    "welch": f"{_SPECTRAL}.welch", "periodogram": f"{_SPECTRAL}.periodogram", "cwt": f"{_SPECTRAL}.cwt_psd"}}
# The Series fills these in itself, so a researcher can't set them.
_SUPPLIED_BY_SERIES = {"x", "y", "ys", "ts", "interp_type"}
_ENTRY = re.compile(r"^(\w+(?:\s*,\s*\w+)*)\s*(?::\s*(.*))?$")


def parse_parameters(docstring: str, known: set[str] = frozenset()) -> dict[str, dict]:
    """Read a numpy-style "Parameters" section into {name: {"type", "definition"}}.

    Some docstrings indent their parameters unevenly, so a line starting with a name
    from `known`, the function's real parameters, starts an entry at any indent.
    """
    lines = inspect.cleandoc(docstring or "").splitlines()
    try:
        start = next(i for i, line in enumerate(lines[:-1])
                     if line.strip() == "Parameters" and set(lines[i + 1].strip()) == {"-"}) + 2
    except StopIteration:
        return {}

    found: dict[str, dict] = {}
    current: list[str] = []
    base = None
    for i in range(start, len(lines)):
        line = lines[i]
        if not line.strip():
            continue
        # The next section's title sits on a line of dashes.
        if i + 1 < len(lines) and lines[i + 1].strip() and set(lines[i + 1].strip()) == {"-"}:
            break
        indent = len(line) - len(line.lstrip())
        base = indent if base is None else base
        match = _ENTRY.match(line.strip())
        if match and indent != base and not (":" in line and match.group(1).split(",")[0].strip() in known):
            match = None
        if match:
            current = []
            for name in match.group(1).split(","):
                found[name.strip()] = {"type": match.group(2) or None, "words": current}
        else:
            current.append(line.strip())
    return {name: {"type": entry["type"], "definition": " ".join(entry["words"]) or None}
            for name, entry in found.items()}


def _label(api: str) -> str:
    return ".".join(api.rsplit(".", 2)[-2:])


def _function(api: str):
    owner, name = api.rsplit(".", 1)
    try:
        return getattr(importlib.import_module(owner), name)
    except ImportError:  # a method: the owner is a class
        module, cls = owner.rsplit(".", 1)
        return getattr(getattr(importlib.import_module(module), cls), name)


def _parameters(api: str) -> list[dict]:
    """A function's parameters, in the order they can be passed by position."""
    function = _function(api)
    signature = inspect.signature(function).parameters
    definitions = parse_parameters(function.__doc__, set(signature))
    parameters = []
    for name, parameter in signature.items():
        if name == "self" or parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        has_default = parameter.default is not parameter.empty
        parameters.append({"name": name, **definitions.get(name, {"type": None, "definition": None}),
                           "default": repr(parameter.default) if has_default else None})
    return parameters


def _utility_parameters(api: str) -> list[dict]:
    """A utils function's settable parameters, each saying which function defines it."""
    return [{**p, "source": _label(api)} for p in _parameters(api) if p["name"] not in _SUPPLIED_BY_SERIES]


def describe(api: str) -> dict:
    parameters = _parameters(api)
    entry = {"parameters": parameters}
    if api in _PASSES_ARGUMENTS_TO:
        passed = _utility_parameters(_PASSES_ARGUMENTS_TO[api])
        own = {p["name"]: p for p in parameters}
        # A parameter the method's docstring leaves undefined may be defined where it's passed.
        for other in passed:
            if other["name"] in own and not own[other["name"]]["definition"]:
                own[other["name"]].update(type=other["type"], definition=other["definition"],
                                          source=other["source"])
        entry["passes_to"] = [p for p in passed if p["name"] not in own]
    if api in _SETTINGS_GO_TO:
        entry["settings_by_method"] = {method: _utility_parameters(target)
                                       for method, target in _SETTINGS_GO_TO[api].items()}
    return entry


def docs_version(version: str) -> str:
    """A released version has its own pages. A beta is ahead of them, so it uses `latest`."""
    return "latest" if "b" in version else f"v{version}"


def _page(api: str) -> str:
    return "core/api.html" if ".core." in api else "utils/introduction.html"


def build_links(apis: list[str], version: str, fetch) -> dict[str, str]:
    """Links to the documentation, keeping only those whose target really exists."""
    pages: dict[str, str | None] = {}
    links = {}
    for api in apis:
        page = _page(api)
        if page not in pages:
            url = f"{_DOCS}/{docs_version(version)}/{page}"
            try:
                pages[page] = fetch(url)
            except OSError as exc:
                print(f"Couldn't read {url}: {exc}")
                pages[page] = None
        if pages[page] and f'id="{api}"' in pages[page]:
            links[_label(api)] = f"{_DOCS}/{docs_version(version)}/{page}#{api}"
        else:
            print(f"No link for {_label(api)}: no target in {page}")
    return links


def _fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "paleopal-build"})
    with urllib.request.urlopen(request, timeout=60) as reply:
        return reply.read().decode("utf-8", "replace")


def workflow_methods(workflow: dict) -> list[str]:
    apis: list[str] = []
    for step in workflow["steps"]:
        core = step.get("core_api") or []
        apis += core if isinstance(core, list) else [core]
    return sorted(set(apis))


def main() -> None:
    import pyleoclim

    workflow = yaml.safe_load((_WORKFLOWS / "spectral_full.yml").read_text())
    apis = workflow_methods(workflow)
    utilities = {*(_PASSES_ARGUMENTS_TO.values()),
                 *(target for targets in _SETTINGS_GO_TO.values() for target in targets.values())}
    output = {"pyleoclim_version": pyleoclim.__version__,
              "links": build_links([*apis, *sorted(utilities)], pyleoclim.__version__, _fetch),
              "methods": {api: describe(api) for api in apis}}
    path = _WORKFLOWS / "pyleoclim_parameters.json"
    path.write_text(json.dumps(output, indent=1) + "\n")
    print(f"Wrote {path.name} from Pyleoclim {pyleoclim.__version__}: {len(output['methods'])} methods, {len(output['links'])} links")


if __name__ == "__main__":
    main()
