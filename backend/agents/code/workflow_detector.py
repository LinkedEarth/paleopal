"""
workflow_detector.py — what has this notebook already done, and what's left?

Compares the text of a notebook's code cells with the steps in a workflow YAML.
Plain Python on purpose: the same notebook always gets the same answer, and it
can be tested without calling a model. Understanding the user's request (which
series, which objective) is the model's job and arrives here as arguments.

The cell text is the truth for which steps happened. Facts about the data, such
as whether a series is evenly spaced, need the kernel and are not decided here:
a step whose requiredness depends on them is reported as `depends_on_method`.

Known limit: steps are collected across everything derived from a series, so a
step on one branch (`a = ts.interp()`) also counts for another (`b = ts.spectral()`).
"""

from __future__ import annotations

import ast
import pathlib
from dataclasses import dataclass, field

_DEFAULT_WORKFLOW = pathlib.Path(__file__).parents[2] / "workflows" / "spectral_full.yml"

# pyleoclim calls that produce a new series.
_SERIES_CONSTRUCTORS = {"load_dataset", "Series", "GeoSeries"}

# Steps that only exist once a spectrum does (`lr04.plot()` isn't plotting a PSD).
_PSD_API_MARKER = ".psds."
_SPECTRAL_STEP = "spectral_estimate"


def load_workflow(path=_DEFAULT_WORKFLOW) -> dict:
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class StepStatus:
    id: str
    requiredness: str
    # done | to_do | propose | optional | depends_on_method | not_needed
    status: str


@dataclass
class NotebookState:
    imports: set[str] = field(default_factory=set)
    series: list[str] = field(default_factory=list)
    target: str | None = None
    # The newest variable derived from the target, where the next step continues from.
    current: str | None = None
    steps: list[StepStatus] = field(default_factory=list)
    # whole_workflow | next_step | needs_data | unclear
    level: str = "unclear"
    # Things the reader can't interpret. PaleoPAL should ask, not guess.
    uncertain: list[str] = field(default_factory=list)


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _method_to_step(workflow: dict) -> dict[str, tuple[str, bool]]:
    """Map a method name to (step id, needs a spectrum first), from the YAML."""
    mapping = {}
    for step in workflow["steps"]:
        for api in _as_list(step.get("core_api")):
            mapping[api.rsplit(".", 1)[-1]] = (step["id"], _PSD_API_MARKER in api)
    return mapping


def _call_chain(call: ast.Call) -> tuple[str | None, list[str]]:
    """`ts.interp().spectral()` -> ('ts', ['interp', 'spectral']), in applied order."""
    methods: list[str] = []
    node = call
    while isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute):
            methods.insert(0, func.attr)
            node = func.value
        elif isinstance(func, ast.Name):
            methods.insert(0, func.id)
            return func.id, methods
        else:
            return None, methods
    while isinstance(node, ast.Attribute):
        node = node.value
    return (node.id if isinstance(node, ast.Name) else None), methods


def _parse_cell(cell: str) -> ast.Module:
    """Parse a cell, dropping notebook-only lines such as `%matplotlib inline`."""
    lines = [line for line in cell.splitlines()
             if not line.lstrip().startswith(("%", "!", "?"))]
    return ast.parse("\n".join(lines))


class _Reader:
    def __init__(self, workflow: dict):
        self.steps_by_method = _method_to_step(workflow)
        self.state = NotebookState()
        self.pyleoclim_names: set[str] = set()   # aliases and from-imported names
        self.lineage: dict[str, list[str]] = {}  # variable -> steps applied to it
        self.origin: dict[str, str] = {}         # variable -> series it came from
        self.done: dict[str, set[str]] = {}      # series -> steps run on anything from it
        self.latest: dict[str, str] = {}         # series -> newest variable derived from it

    def read_cell(self, number: int, cell: str) -> None:
        try:
            tree = _parse_cell(cell)
        except SyntaxError as exc:
            self.state.uncertain.append(f"cell {number}: can't parse it ({exc.msg})")
            return
        statements = [n for n in ast.walk(tree)
                      if isinstance(n, (ast.Import, ast.ImportFrom, ast.Assign, ast.Expr))]
        for node in sorted(statements, key=lambda n: n.lineno):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self._read_import(node)
            elif isinstance(node, ast.Assign):
                self._read_assign(number, node)
            elif isinstance(node.value, ast.Call):
                self._apply(node.value)

    def _read_import(self, node) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                self.state.imports.add(top)
                if top == "pyleoclim":
                    self.pyleoclim_names.add(alias.asname or top)
        elif node.module:
            top = node.module.split(".")[0]
            self.state.imports.add(top)
            if top == "pyleoclim":
                self.pyleoclim_names.update(a.asname or a.name for a in node.names)

    def _read_assign(self, number: int, node: ast.Assign) -> None:
        target = node.targets[0].id if (
            len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)) else None

        if isinstance(node.value, ast.Name) and node.value.id in self.lineage and target:
            self.lineage[target] = list(self.lineage[node.value.id])
            self.origin[target] = self.origin[node.value.id]
        elif isinstance(node.value, ast.Call):
            applied = self._apply(node.value, target)
            if applied is None and target and self._mentions_series(node.value):
                self.state.uncertain.append(
                    f"cell {number}: can't tell what `{target} = {ast.unparse(node.value)}` does"
                )

    def _mentions_series(self, call: ast.Call) -> bool:
        return any(isinstance(n, ast.Name) and n.id in self.lineage for n in ast.walk(call))

    def _apply(self, call: ast.Call, target: str | None = None) -> list[str] | None:
        """Record one call chain. Returns the steps applied, or None if not a known series."""
        root, methods = _call_chain(call)
        if root in self.lineage:
            steps = list(self.lineage[root])
            origin = self.origin[root]
        elif root in self.pyleoclim_names and methods and methods[0] in _SERIES_CONSTRUCTORS:
            if target is None:
                return None
            steps, origin = [], target
            self.state.series.append(target)
            self.done.setdefault(origin, set())
            methods = methods[1:]
        else:
            return None

        for method in methods:
            step_id, needs_spectrum = self.steps_by_method.get(method, (None, False))
            if step_id and (not needs_spectrum or _SPECTRAL_STEP in steps):
                steps.append(step_id)
        self.done[origin].update(steps)
        if target:
            self.lineage[target] = steps
            self.origin[target] = origin
            self.latest[origin] = target
        return steps


def _rules_to_propose(workflow: dict, objective: str) -> set[str]:
    """Rules behind steps worth offering, from disclosure rules on this objective."""
    return {rule["related"] for rule in workflow["rules"]
            if rule.get("kind") == "disclosure" and rule.get("related")
            and objective in rule.get("applies_to_objectives", [])}


def _status(step: dict, is_done: bool, objective: str, to_propose: set[str]) -> str:
    requiredness = step["requiredness"]
    if is_done:
        return "done"
    if step.get("rule") in to_propose:
        return "propose"
    if requiredness.startswith("available_not_default"):
        return "optional"
    if requiredness.startswith("determined_by"):
        return "depends_on_method"
    if requiredness.startswith("required_for"):
        return "to_do" if requiredness == f"required_for({objective})" else "not_needed"
    return "to_do"  # required, recommended


def detect(cells: list[str], workflow: dict, target: str | None = None,
           objective: str = "exploratory") -> NotebookState:
    """Read code cells, in order, and compare them with the workflow's steps.

    `target` is the series the user means. Without one, it's used only if the
    notebook has exactly one series. An unstated objective is exploratory.
    """
    reader = _Reader(workflow)
    for number, cell in enumerate(cells, start=1):
        reader.read_cell(number, cell)
    state = reader.state

    if target is not None and target in reader.origin:
        target = reader.origin[target]
    elif target is None and len(state.series) == 1:
        target = state.series[0]
    elif target is not None:
        state.uncertain.append(f"can't find a series called `{target}` in the cells")
        target = None
    state.target = target
    state.current = reader.latest.get(target, target)

    done = reader.done.get(target, set())
    to_propose = _rules_to_propose(workflow, objective)
    state.steps = [
        StepStatus(step["id"], step["requiredness"],
                   _status(step, step["id"] in done, objective, to_propose))
        for step in workflow["steps"]
    ]

    if not state.series:
        state.level = "needs_data"
    elif target is None:
        state.level = "unclear"
    else:
        state.level = "next_step" if done else "whole_workflow"
    return state
