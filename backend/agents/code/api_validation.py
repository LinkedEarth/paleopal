"""
Validate generated code against the REAL Pyleoclim API.

This is the check that distinguishes "structurally sensible" from "actually
runs". Two failures it catches that nothing else does:

    ts.spectrum(method='multitaper')     # Series.spectrum does not exist
    psd.signif_test(null_model='ar1sim') # the parameter is `method`

Both look plausible. Both raise on the first line. Neither is visible to a
structural check.

The symbols come from references/pyleoclim_api.json, built from an installed Pyleoclim by
scripts/build_api_reference.py and rebuilt when Pyleoclim releases a new version. (The backend
doesn't have Pyleoclim installed, and a researcher's kernel may hold another version.) Names are
matched by method, not yet by class.
"""

from __future__ import annotations

import ast
import json
import pathlib

_REFERENCE = pathlib.Path(__file__).resolve().parents[2] / "references" / "pyleoclim_api.json"

# Method names that legitimately belong to other libraries and should not be
# validated against Pyleoclim.
_FOREIGN = {
    "plot", "subplots", "figure", "show", "savefig", "legend", "set_xlim",
    "set_ylim", "set_xlabel", "set_ylabel", "set_title", "flatten", "append",
    "copy", "keys", "values", "items", "get", "format", "join", "split",
    "strip", "range", "len", "print", "loglog", "semilogx", "semilogy",
}


def _load(path: pathlib.Path = _REFERENCE) -> dict:
    """Method and function names, each with its argument names and whether it takes extra
    keyword settings. A name defined in several classes gets the union of their arguments."""
    reference = json.loads(path.read_text(encoding="utf-8"))
    methods: dict[str, dict] = {}
    entries = [(name, d) for c in reference["classes"].values() for name, d in c["methods"].items()]
    entries += [(path_.rsplit(".", 1)[-1], d) for path_, d in reference["functions"].items()]
    for name, described in entries:
        if name.startswith("_"):
            continue
        known = methods.setdefault(name, {"params": set(), "accepts_kwargs": False})
        known["params"] |= {p["name"] for p in described["params"]}
        known["accepts_kwargs"] |= described["accepts_kwargs"]
    return {"methods": methods,
            "source": f"{path.name} (Pyleoclim {reference.get('version')}, built {reference.get('built')})"}


_API_CACHE: dict | None = None


def get_api() -> dict:
    global _API_CACHE
    if _API_CACHE is None:
        _API_CACHE = _load()
    return _API_CACHE


def validate(code: str) -> tuple[list[str], list[str], str]:
    """Return (unknown_methods, bad_kwargs, api_source)."""
    api = get_api()
    known = api["methods"]

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return [], [], api["source"]

    unknown: list[str] = []
    bad_kwargs: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        name = node.func.attr
        if name.startswith("_") or name in _FOREIGN:
            continue

        # Only judge names that look like Pyleoclim usage: either the name is
        # known, or it is close enough to a known name to be a hallucination.
        if name not in known:
            near = [k for k in known if k.startswith(name[:4]) and len(name) > 3]
            if near:
                unknown.append(
                    f"line {node.lineno}: .{name}() does not exist "
                    f"(did you mean {', '.join(sorted(near)[:3])}?)"
                )
            continue

        # Extra keyword settings are passed on to pyleoclim.utils (e.g. bin(bin_size=...)), so a
        # method that accepts them can't have its keywords judged by name.
        if known[name]["accepts_kwargs"]:
            continue
        valid = known[name]["params"]
        if not valid:
            continue
        for kw in node.keywords:
            if kw.arg and kw.arg not in valid:
                near = [v for v in valid if v[:3] == kw.arg[:3]]
                hint = f" (valid: {', '.join(sorted(valid)[:6])})" if not near \
                    else f" (did you mean {near[0]}?)"
                bad_kwargs.append(
                    f"line {node.lineno}: .{name}({kw.arg}=...) is not a "
                    f"parameter{hint}"
                )

    return unknown, bad_kwargs, api["source"]
