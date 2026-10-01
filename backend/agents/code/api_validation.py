"""
Validate generated code against the REAL Pyleoclim API.

This is the check that distinguishes "structurally sensible" from "actually
runs". Two failures it catches that nothing else does:

    ts.spectrum(method='multitaper')     # Series.spectrum does not exist
    psd.signif_test(null_model='ar1sim') # the parameter is `method`

Both look plausible. Both raise on the first line. Neither is visible to a
structural check.

Symbol source, in order of preference:
  1. the installed pyleoclim, introspected live (authoritative, tracks your
     version)
  2. pyleoclim_api.json bundled next to this file (fallback for environments
     without pyleoclim)
"""

from __future__ import annotations

import ast
import inspect
import json
import pathlib

_BUNDLED = pathlib.Path(__file__).parent / "pyleoclim_api.json"

# Method names that legitimately belong to other libraries and should not be
# validated against Pyleoclim.
_FOREIGN = {
    "plot", "subplots", "figure", "show", "savefig", "legend", "set_xlim",
    "set_ylim", "set_xlabel", "set_ylabel", "set_title", "flatten", "append",
    "copy", "keys", "values", "items", "get", "format", "join", "split",
    "strip", "range", "len", "print", "loglog", "semilogx", "semilogy",
}


def _from_installed() -> dict | None:
    try:
        import pyleoclim  # noqa: F401
    except Exception:
        return None

    import pyleoclim as pyleo

    methods: dict[str, set[str]] = {}
    for cls_name in dir(pyleo):
        cls = getattr(pyleo, cls_name, None)
        if not inspect.isclass(cls):
            continue
        for meth_name, meth in inspect.getmembers(cls, callable):
            if meth_name.startswith("_"):
                continue
            try:
                sig = inspect.signature(meth)
            except (ValueError, TypeError):
                continue
            params = {p for p in sig.parameters if p != "self"}
            methods.setdefault(meth_name, set()).update(params)
    return {"methods": {k: sorted(v) for k, v in methods.items()},
            "source": f"installed pyleoclim {getattr(pyleo, '__version__', '?')}"}


def _from_bundle() -> dict:
    data = json.loads(_BUNDLED.read_text(encoding="utf-8"))
    data["source"] = f"bundled {_BUNDLED.name}"
    return data


_API_CACHE: dict | None = None


def get_api() -> dict:
    global _API_CACHE
    if _API_CACHE is None:
        _API_CACHE = _from_installed() or _from_bundle()
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

        valid = set(known[name])
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
