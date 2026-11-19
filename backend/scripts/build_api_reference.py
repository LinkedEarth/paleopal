#!/usr/bin/env python3
"""
build_api_reference.py — record a package's public API for PaleoPAL's "will it run?" checks.

Run in an environment where the package is installed (for Deborah: the `pyleo` conda env):

    python scripts/build_api_reference.py pyleoclim
    python scripts/build_api_reference.py pylipd

Writes backend/references/<package>_api.json. A researcher never runs this; it's rerun when a
package releases a new version. No model is involved: everything is read from the installed
package by introspection and from its docstrings.

For each class: its methods, each with its arguments (name, default, kind), whether it accepts
extra keyword settings (**kwargs), and the type its docstring says it returns. For each module:
its public functions, recorded the same way.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pkgutil
import re
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

_OUT = Path(__file__).resolve().parents[1] / "references"
_DEFAULT_CHARS = 80
# The "Returns" section of a numpydoc docstring: the header, its underline, then "name : Type".
_RETURNS = re.compile(r"\n\s*Returns\s*\n\s*-{3,}\s*\n(?P<body>.*?)(?:\n\s*\n\s*\S[^\n]*\n\s*-{3,}|\Z)", re.S)


def _default(value) -> str | None:
    if value is inspect.Parameter.empty:
        return None
    text = repr(value)
    return text if len(text) <= _DEFAULT_CHARS else text[:_DEFAULT_CHARS] + "…"


def _returns(doc: str | None, classes: set[str]) -> dict | None:
    """What the docstring says comes back: its own words, and the package class it names, if any."""
    match = _RETURNS.search("\n" + (doc or ""))
    if not match:
        return None
    first = next((l.strip() for l in match.group("body").splitlines() if l.strip()), "")
    if not first:
        return None
    kind = first.split(":", 1)[1].strip() if ":" in first else first
    named = next((w for w in re.findall(r"[A-Za-z_][\w.]*", kind) if w.rsplit(".", 1)[-1] in classes), None)
    return {"text": first, "type": named.rsplit(".", 1)[-1] if named else None}


def describe_callable(func, classes: set[str]) -> dict | None:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return None
    params = [p for p in signature.parameters.values() if p.name not in ("self", "cls")]
    return {
        "params": [{"name": p.name, "default": _default(p.default), "kind": p.kind.name.lower()}
                   for p in params if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)],
        "accepts_kwargs": any(p.kind is p.VAR_KEYWORD for p in params),
        "accepts_args": any(p.kind is p.VAR_POSITIONAL for p in params),
        "returns": _returns(inspect.getdoc(func), classes),
    }


def _modules(package):
    yield package
    for info in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        if any(part.startswith("_") or part in ("tests", "test") for part in info.name.split(".")):
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                yield importlib.import_module(info.name)
        except Exception as exc:  # a module that can't import isn't part of what users can call
            print(f"Skipped {info.name}: {exc}", file=sys.stderr)


def build(name: str) -> dict:
    package = importlib.import_module(name)
    modules = list(_modules(package))
    found_classes = {}
    for module in modules:
        for attr, obj in vars(module).items():
            if inspect.isclass(obj) and not attr.startswith("_") and obj.__module__ == module.__name__:
                found_classes[f"{module.__name__}.{attr}"] = obj
    class_names = {path.rsplit(".", 1)[-1] for path in found_classes}

    classes = {}
    for path, cls in sorted(found_classes.items()):
        methods = {}
        for meth_name, member in inspect.getmembers(cls):
            if meth_name.startswith("_") and meth_name != "__init__":
                continue
            raw = inspect.getattr_static(cls, meth_name, None)
            if isinstance(raw, property) or not callable(member):
                continue
            owner = next((k for k in cls.__mro__ if meth_name in vars(k)), cls)
            if not (owner.__module__ or "").startswith(name):
                continue  # inherited from another library, e.g. a pandas or dict method
            described = describe_callable(member, class_names)
            if described:
                described["defined_in"] = f"{owner.__module__}.{owner.__qualname__}"
                methods[meth_name] = described
        classes[path] = {"bases": [f"{b.__module__}.{b.__qualname__}" for b in cls.__bases__],
                         "methods": methods}

    functions = {}
    for module in modules:
        for attr, obj in vars(module).items():
            if (inspect.isfunction(obj) and not attr.startswith("_")
                    and obj.__module__ == module.__name__):
                described = describe_callable(obj, class_names)
                if described:
                    functions[f"{module.__name__}.{attr}"] = described

    return {"package": name, "version": getattr(package, "__version__", None),
            "built": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "classes": classes, "functions": dict(sorted(functions.items()))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("package")
    parser.add_argument("--out", type=Path, default=_OUT)
    args = parser.parse_args()
    reference = build(args.package)
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{args.package}_api.json"
    path.write_text(json.dumps(reference, indent=1) + "\n")
    methods = sum(len(c["methods"]) for c in reference["classes"].values())
    print(f"Wrote {path.name} from {args.package} {reference['version']}: {len(reference['classes'])} "
          f"classes, {methods} methods, {len(reference['functions'])} functions")


if __name__ == "__main__":
    main()
