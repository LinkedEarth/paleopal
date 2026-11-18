"""Automatic quality report on the notebook corpus, before a rebuild. No model, changes nothing.

For every example the indexer would make from the notebooks in the manifest, it records:
  - the notebook's last change in its source repository (recency);
  - calls on Pyleoclim objects that today's Pyleoclim doesn't have (API drift);
  - matplotlib fed with arrays pulled out of a Pyleoclim object (taking the object apart);
  - which libraries the notebook works with (matplotlib on pandas or xarray data is fine);
  - duplicates, exact and with variable names ignored;
  - the guide steps it could serve, and whether each argument is Pyleoclim's default.

Run from backend/ in the paleopal environment:
  python scripts/corpus_report.py --api <current_api.json> --repos <dir of clones> --out <dir>
The API file comes from the researcher-independent export of an installed Pyleoclim (methods, their
parameters and defaults, and whether they accept **kwargs).
"""

from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import json
import pathlib
import re
import subprocess
import sys

import yaml

BACKEND = pathlib.Path(__file__).resolve().parents[1]
LIBRARY = BACKEND / "libraries" / "notebook_library"
sys.path[:0] = [str(LIBRARY), str(BACKEND / "libraries")]
import index_notebooks  # noqa: E402

# Results that aren't Pyleoclim objects (figures, dicts, plain Python).
NOT_OBJECTS = {"map", "stripes", "dashboard", "to_pandas", "to_csv", "to_json", "items", "keys", "values"}
# Methods of dicts, lists, strings, numpy and pandas, reached through results the tracker follows.
NOT_PYLEOCLIM = {"items", "keys", "values", "get", "update", "pop", "append", "extend", "index", "sort",
                 "split", "join", "replace", "format", "strip", "sum", "max", "min", "mean", "std", "median",
                 "count", "ceil", "floor", "round", "to_numpy", "tolist", "drop", "head", "tail", "reshape",
                 "astype", "flatten", "argmax", "argmin", "cumsum", "diff", "isnan", "any", "all", "unique",
                 "groupby", "iloc", "loc", "set_index", "reset_index", "dropna", "fillna", "rename", "merge"}
# Build folders hold copies of notebooks (Jupyter Book, Sphinx, JupyterLab).
BUILD_COPY = re.compile(r"/(_build|_sources|\.virtual_documents|\.ipynb_checkpoints)/")
IMPORTS_ONLY = re.compile(r"^\s*((import|from)\s.*)?$")
PLOTTING = {"plot", "scatter", "fill_between", "fill_betweenx", "bar", "barh", "hist", "loglog", "semilogx",
            "semilogy", "errorbar", "step", "stem", "imshow", "contour", "contourf", "pcolormesh", "stackplot"}
ARRAYS = {"time", "value", "frequency", "amplitude", "period", "scale"}
LIBRARIES = {"pyleoclim": "Pyleoclim", "pandas": "pandas", "xarray": "xarray", "pylipd": "PyLiPD",
             "pyleotups": "PyleoTUPS", "cartopy": "cartopy", "scipy": "scipy", "sklearn": "scikit-learn",
             "numpy": "numpy", "matplotlib": "matplotlib", "seaborn": "seaborn", "netCDF4": "netCDF4"}


def clean(code: str) -> str:
    """Notebook magics and shell lines aren't Python."""
    return "\n".join("" if line.lstrip().startswith(("%", "!", "?")) else line for line in code.splitlines())


def root_name(node):
    while isinstance(node, (ast.Attribute, ast.Call, ast.Subscript)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


class Tracker:
    """Follows which names hold Pyleoclim objects through one notebook, in order."""

    def __init__(self, api: dict):
        self.api = api
        self.aliases: set[str] = set()   # names bound to the pyleoclim module
        self.objects: set[str] = set()   # names holding Pyleoclim objects

    def imports(self, tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] == "pyleoclim":
                        self.aliases.add(a.asname or "pyleoclim")
            elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("pyleoclim"):
                for a in node.names:
                    self.objects.add(a.asname or a.name)

    def is_pyleo(self, node) -> bool:
        name = root_name(node)
        return name in self.aliases or name in self.objects

    def holds_object(self, value) -> bool:
        """A Pyleoclim call's result, or another name for an object, but not `fig, ax` or arrays."""
        if isinstance(value, ast.Name):
            return value.id in self.objects
        if isinstance(value, ast.Subscript):
            return self.holds_object(value.value) or (isinstance(value.value, ast.Attribute)
                                                     and value.value.attr not in ARRAYS and self.is_pyleo(value.value))
        if isinstance(value, ast.Call) and self.is_pyleo(value.func):
            name = value.func.attr if isinstance(value.func, ast.Attribute) else ""
            return "plot" not in name and name not in NOT_OBJECTS
        return False

    def assignments(self, tree):
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None and self.holds_object(node.value):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, ast.Tuple) for t in targets):  # mostly fig, ax from a plot
                    continue
                for t in targets:
                    for n in ast.walk(t):
                        if isinstance(n, ast.Name):
                            self.objects.add(n.id)
            elif isinstance(node, ast.For) and self.is_pyleo(node.iter):
                for n in ast.walk(node.target):
                    if isinstance(n, ast.Name):
                        self.objects.add(n.id)


def candidates(api: dict, name: str, on_module: bool) -> dict:
    found = dict(api["methods"].get(name, {}))
    if on_module:  # pyleo.utils.f(...), pyleo.Series.from_pandas(...), or a class: pyleo.Series(...)
        found.update(api["functions"].get(name, {}))
        found.update({k: v for k, v in api["methods"].get("__init__", {}).items() if k.split(".")[0] == name})
    return found


def module_name_exists(api: dict, name: str) -> bool:
    classes = {k.split(".")[0] for m in api["methods"].values() for k in m}
    modules = {part for f in api["functions"].values() for k in f for part in k.split(".")}
    return name in classes or name in api["functions"] or name in modules


def judge_call(call: ast.Call, tracker: Tracker, api: dict) -> dict | None:
    """What one call on a Pyleoclim object or function says about drift and defaults."""
    if not isinstance(call.func, ast.Attribute) or not tracker.is_pyleo(call.func.value):
        return None
    name = call.func.attr
    on_module = root_name(call.func.value) in tracker.aliases and isinstance(call.func.value, (ast.Name, ast.Attribute)) \
        and not any(isinstance(n, ast.Call) for n in ast.walk(call.func.value))
    found = candidates(api, name, on_module)
    result = {"call": name, "unknown": False, "bad_args": [], "args": []}
    if not found:
        if (on_module and module_name_exists(api, name)) or name in NOT_PYLEOCLIM:
            return None
        result["unknown"] = True
        return result
    for kw in call.keywords:
        if kw.arg is None:
            continue
        defaults = {c["params"][kw.arg] for c in found.values() if kw.arg in c["params"]}
        if not defaults:
            if not any(c["kwargs"] for c in found.values()):
                result["bad_args"].append(kw.arg)
            else:
                result["args"].append({"name": kw.arg, "value": ast.unparse(kw.value), "status": "passed on (**kwargs)"})
            continue
        value = ast.unparse(kw.value)
        if len(defaults) > 1:
            status = "default differs by class"
        else:
            default = next(iter(defaults))
            status = ("no default" if default is None
                      else "default" if _same(value, default) else f"non-default (default {default})")
        result["args"].append({"name": kw.arg, "value": value, "status": status})
    return result


def _same(value: str, default: str) -> bool:
    try:
        return ast.literal_eval(value) == ast.literal_eval(default)
    except Exception:
        return value.replace('"', "'") == default.replace('"', "'")


def dismantles(tree, tracker: Tracker) -> list[str]:
    """A matplotlib plotting call given arrays pulled out of a Pyleoclim object.

    Numerical use of the arrays (len, np.where, np.std…) is fine; only plotting them is flagged.
    """
    found = []
    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
        if tracker.is_pyleo(call.func) or not isinstance(call.func, ast.Attribute) \
                or call.func.attr not in PLOTTING:
            continue
        for arg in [*call.args, *(k.value for k in call.keywords)]:
            for n in ast.walk(arg):
                if isinstance(n, ast.Attribute) and n.attr in ARRAYS and root_name(n) in tracker.objects:
                    found.append(ast.unparse(call)[:120])
                    break
    return list(dict.fromkeys(found))


def fingerprints(code: str, tree) -> tuple[str, str]:
    exact = hashlib.md5(" ".join(code.split()).encode()).hexdigest()

    class Anon(ast.NodeTransformer):
        def visit_Name(self, node):
            return ast.copy_location(ast.Name(id="_", ctx=node.ctx), node)
    shape = hashlib.md5(ast.dump(Anon().visit(ast.parse(ast.unparse(tree)))).encode()).hexdigest()
    return exact, shape


def notebook_date(repos: pathlib.Path, entry: dict) -> str | None:
    clone = repos / entry["repository"]
    if not clone.exists():
        return None
    out = subprocess.run(["git", "-C", str(clone), "log", "-1", "--format=%cs", "--", entry["source_path"]],
                         capture_output=True, text=True)
    return out.stdout.strip() or None


def guide_methods(workflow: dict) -> dict[str, str]:
    methods = {}
    for step in workflow["steps"]:
        apis = step.get("core_api") or []
        for api in apis if isinstance(apis, list) else [apis]:
            methods[api.rsplit(".", 1)[-1]] = step["id"]
    return methods


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", required=True)
    parser.add_argument("--repos", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    api = json.loads(pathlib.Path(args.api).read_text())
    repos = pathlib.Path(args.repos)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    workflow = yaml.safe_load((BACKEND / "workflows" / "spectral_full.yml").read_text())
    steps_by_method = guide_methods(workflow)
    entries = json.loads((LIBRARY / "my_notebooks" / "_metadata" / "notebooks.json").read_text())

    rows = []
    for entry in entries:
        path = LIBRARY / "my_notebooks" / entry["destination_path"]
        if not path.exists() or BUILD_COPY.search(entry["destination_path"]):
            continue
        date = notebook_date(repos, entry)
        try:
            snippets = index_notebooks.extract_snippets(path)
        except Exception as exc:  # a notebook the indexer can't read
            rows.append({"notebook": entry["destination_path"], "date": date, "error": str(exc)[:200]})
            continue
        tracker = Tracker(api)
        notebook_libraries = set()
        parsed = []
        for snippet in sorted(snippets, key=lambda s: min(s.get("cell_indices") or [0])):
            code = clean(snippet.get("code") or "")
            try:
                tree = ast.parse(code)
            except SyntaxError:
                parsed.append((snippet, code, None))
                continue
            tracker.imports(tree)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                    notebook_libraries |= {LIBRARIES[n.split(".")[0]] for n in names if n.split(".")[0] in LIBRARIES}
            parsed.append((snippet, code, tree))
        for snippet, code, tree in parsed:
            row = {"notebook": entry["destination_path"], "source": entry["source_name"],
                   "repository": entry["repository"], "date": date, "cells": snippet.get("cell_indices"),
                   "code": code, "libraries": sorted(notebook_libraries),
                   "has_markdown": bool((snippet.get("markdown_context") or "").strip())}
            if tree is None:
                row["parses"] = False
                rows.append(row)
                continue
            tracker.assignments(tree)
            calls = [j for j in (judge_call(c, tracker, api) for c in ast.walk(tree) if isinstance(c, ast.Call)) if j]
            row.update(parses=True,
                       pyleoclim_calls=[c["call"] for c in calls],
                       unknown_calls=[c["call"] for c in calls if c["unknown"]],
                       bad_args=[f"{c['call']}({a}=)" for c in calls for a in c["bad_args"]],
                       arguments=[{**a, "call": c["call"]} for c in calls for a in c["args"]],
                       dismantles=dismantles(tree, tracker),
                       steps=sorted({steps_by_method[c["call"]] for c in calls if c["call"] in steps_by_method}),
                       uses_matplotlib=bool(re.search(r"\bplt\.|\bmatplotlib\b", code)))
            row["exact"], row["shape"] = fingerprints(code, tree)
            rows.append(row)

    # Whole notebooks with the same content are copies (e.g. docsrc/ and docs/): keep the source one.
    by_notebook = collections.defaultdict(list)
    for r in rows:
        by_notebook[r["notebook"]].append(r.get("exact") or r["code"])
    groups = collections.defaultdict(list)
    for notebook, content in by_notebook.items():
        groups[tuple(content)].append(notebook)
    copies = {}
    for same in groups.values():
        keep = min(same, key=lambda n: ("/docs/" in n, len(n), n))
        copies.update({n: keep for n in same if n != keep})
    for r in rows:
        r["copy_of"] = copies.get(r["notebook"])
        r["imports_only"] = bool(IMPORTS_ONLY.fullmatch(r["code"]) or all(
            IMPORTS_ONLY.match(line) for line in r["code"].splitlines()))
    kept = [r for r in rows if not r["copy_of"]]

    counted = [r for r in kept if r.get("exact") and not r["imports_only"]]
    exact = collections.Counter(r["exact"] for r in counted)
    shape = collections.Counter(r["shape"] for r in counted)
    for r in kept:
        r["duplicate"] = None if r not in counted else (
            "exact" if exact[r["exact"]] > 1 else "same shape" if shape[r["shape"]] > 1 else None)

    (out / "corpus_examples.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    (out / "corpus_report.md").write_text(summary(kept, api, entries, len(copies), steps_by_method))
    print(f"{len(rows)} examples from {len({r['notebook'] for r in rows})} notebooks -> {out}")


def summary(rows: list[dict], api: dict, entries: list[dict], copies: int, steps_by_method: dict) -> str:
    ok = [r for r in rows if r.get("parses")]
    lines = [f"# Corpus quality report", "",
             f"Compared against Pyleoclim {api['version']}. Automatic checks only; no model was used.", "",
             "## Totals", "",
             f"- Notebooks in the manifest: {len(entries)}",
             f"  - copies in build folders (`_build/`, `_sources/`, `.virtual_documents/`), set aside: "
             f"{sum(1 for e in entries if BUILD_COPY.search(e['destination_path']))}",
             f"  - other copies with identical content (e.g. `docsrc/` and `docs/`), set aside: {copies}",
             f"  - notebooks kept: {len({r['notebook'] for r in rows})}",
             f"- Examples the indexer makes from them: {len(rows)}, of which only imports: "
             f"{sum(1 for r in rows if r['imports_only'])}",
             f"- Don't parse as Python: {sum(1 for r in rows if r.get('parses') is False)}; notebooks the indexer couldn't read: {sum(1 for r in rows if 'error' in r)}",
             f"- Call Pyleoclim: {sum(1 for r in ok if r['pyleoclim_calls'])}",
             f"- API drift (a call or argument today's Pyleoclim lacks): {sum(1 for r in ok if r['unknown_calls'] or r['bad_args'])}",
             f"- Take a Pyleoclim object apart for another library's plot: {sum(1 for r in ok if r['dismantles'])}",
             f"- Mention matplotlib at all: {sum(1 for r in ok if r['uses_matplotlib'])}, of which in notebooks that never import Pyleoclim: "
             f"{sum(1 for r in ok if r['uses_matplotlib'] and 'Pyleoclim' not in r['libraries'])}",
             f"- Duplicates: {sum(1 for r in ok if r['duplicate'] == 'exact')} exact, {sum(1 for r in ok if r['duplicate'] == 'same shape')} same code with other names",
             f"- Could serve a spectral-guide step: {sum(1 for r in ok if r['steps'])}", ""]

    lines += ["## By source and age", "", "| source | notebooks | examples | median last change | oldest | with drift |", "|---|---|---|---|---|---|"]
    by_source = collections.defaultdict(list)
    for r in rows:
        by_source[r.get("source") or "?"].append(r)
    for source, group in sorted(by_source.items()):
        dates = sorted(d for d in {(r["notebook"], r.get("date")) for r in group} if d[1])
        dated = sorted(d for _, d in dates)
        lines.append(f"| {source} | {len({r['notebook'] for r in group})} | {len(group)} | "
                     f"{dated[len(dated)//2] if dated else '?'} | {dated[0] if dated else '?'} | "
                     f"{sum(1 for r in group if r.get('unknown_calls') or r.get('bad_args'))} |")

    lines += ["", "## Drift found most often", "", "| call or argument | examples |", "|---|---|"]
    drift = collections.Counter(x for r in ok for x in [*(f"{c}()" for c in r["unknown_calls"]), *r["bad_args"]])
    lines += [f"| `{k}` | {v} |" for k, v in drift.most_common(25)]

    lines += ["", "## Examples that could serve a guide step", "",
              "Non-default arguments are the deliberate choices worth an expert's look.", ""]
    for step in dict.fromkeys(steps_by_method.values()):
        own = {m for m, s in steps_by_method.items() if s == step}
        group = [r for r in ok if step in r["steps"]]
        if not group:
            continue
        lines += [f"### {step}: {', '.join(f'`{m}`' for m in sorted(own))} ({len(group)} examples)", "",
                  "| notebook | last change | non-default arguments to this step | problems |", "|---|---|---|---|"]
        for r in sorted(group, key=lambda r: r.get("date") or "", reverse=True):
            nondefault = list(dict.fromkeys(f"`{a['name']}={a['value']}`" for a in r["arguments"]
                                            if a["call"] in own and a["status"].startswith("non-default")))
            problems = [*(f"unknown `{c}()`" for c in r["unknown_calls"]), *(f"bad `{b}`" for b in r["bad_args"]),
                        *(["takes object apart"] if r["dismantles"] else []), *([r["duplicate"]] if r["duplicate"] else [])]
            lines.append(f"| {r['notebook'].split('/', 1)[-1]} (cells {r['cells']}) | {r.get('date') or '?'} | "
                         f"{', '.join(nondefault) or '—'} | {', '.join(problems) or '—'} |")
        lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
