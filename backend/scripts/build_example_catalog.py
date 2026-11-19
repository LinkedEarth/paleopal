#!/usr/bin/env python3
"""
build_example_catalog.py — one record per code cell of the notebook corpus, with facts read by Python.

    python scripts/build_example_catalog.py --out ~/Documents/PaleoPAL/example_catalog

No model is involved, and nothing is indexed: this writes `catalog.jsonl` (one record per code cell)
and `summary.md` for review. The facts:

- where the cell comes from (notebook, its GitHub link, tutorial or PaleoBook, section heading, the
  markdown just above it, its neighbours);
- the packages it uses, and its calls, each as `Type.method` when the receiver's type is known.
  Types are followed through the notebook with the return types recorded in references/*_api.json;
- the non-default arguments it sets (defaults from the same references);
- the guide steps it demonstrates (matched from the guides' `core_api`), and the steps already
  applied to that series before this cell (its lineage).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import urllib.request
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

import yaml

_BACKEND = Path(__file__).resolve().parents[1]
_LIBRARY = _BACKEND / "libraries" / "notebook_library" / "my_notebooks"
_REFERENCES = _BACKEND / "references"
_GUIDES = [_BACKEND / "workflows" / "spectral_full.yml", _BACKEND / "workflows" / "visualization.yml"]
_PACKAGES = ("pyleoclim", "pylipd", "pyleotups")
_KIND = {"pyleoclim_tutorials": "tutorial", "pylipd_tutorials": "tutorial",
         "pyleotups_tutorials": "tutorial", "paleobooks_gallery": "paleobook"}
_MARKDOWN_CHARS = 1200


# --- the packages' APIs -------------------------------------------------------------------------

class Api:
    """Classes, their methods (with defaults and return types) and functions, for every package."""

    def __init__(self, directory: Path = _REFERENCES):
        self.methods: dict[str, dict[str, dict]] = {}   # short class name -> method -> description
        self.bases: dict[str, list[str]] = {}
        self.functions: dict[str, dict] = {}            # full dotted path -> description
        self.classes: dict[str, str] = {}               # full dotted path -> short class name
        for package in _PACKAGES:
            path = directory / f"{package}_api.json"
            if not path.exists():
                continue
            reference = json.loads(path.read_text())
            for full, cls in reference["classes"].items():
                short = full.rsplit(".", 1)[-1]
                self.classes[full] = short
                self.methods.setdefault(short, {}).update(cls["methods"])
                self.bases[short] = [b.rsplit(".", 1)[-1] for b in cls["bases"]]
            self.functions.update(reference["functions"])
        self.short_functions = defaultdict(list)
        for full in self.functions:
            self.short_functions[full.rsplit(".", 1)[-1]].append(full)

    def method(self, type_: str, name: str) -> dict | None:
        return self.methods.get(type_, {}).get(name)

    def result_type(self, type_: str, name: str) -> str | None:
        """The type `type_.name()` returns. An inherited method keeps the receiver's type."""
        described = self.method(type_, name)
        if not described or not described.get("returns") or not described["returns"].get("type"):
            return None
        named = described["returns"]["type"]
        owner = described.get("defined_in", "").rsplit(".", 1)[-1]
        return type_ if named == owner and owner != type_ else named

    def function(self, dotted: str) -> dict | None:
        """A function by its full dotted name, or by its name within the same package, since packages
        re-export functions (`pyleo.utils.load_dataset` is defined in `pyleoclim.utils.datasets`)."""
        if dotted in self.functions:
            return self.functions[dotted]
        root = dotted.split(".")[0]
        matches = [f for f in self.short_functions.get(dotted.rsplit(".", 1)[-1], []) if f.split(".")[0] == root]
        return self.functions[matches[0]] if len(matches) == 1 else None

    def class_by_name(self, dotted: str) -> str | None:
        short = dotted.rsplit(".", 1)[-1]
        return short if short in self.methods else None


# --- the guides' steps --------------------------------------------------------------------------

def guide_steps() -> dict[str, list[str]]:
    """`Class.method` -> the guide steps that use it, e.g. "Series.detrend" -> ["spectral_analysis:detrend"]."""
    found: dict[str, list[str]] = defaultdict(list)
    for path in _GUIDES:
        guide = yaml.safe_load(path.read_text())
        for step in guide["steps"]:
            apis = []
            for key in ("core_api", "container_api"):
                value = step.get(key) or []
                apis += value if isinstance(value, list) else [value]
            for api in apis:
                found[".".join(api.rsplit(".", 2)[-2:])].append(f"{guide['workflow']['id']}:{step['id']}")
    return found


# --- reading one notebook -----------------------------------------------------------------------

def _literal(node):
    try:
        return repr(ast.literal_eval(node))
    except (ValueError, SyntaxError, TypeError):
        return None


class Reader:
    """Follows names, imports and types through one notebook, cell by cell."""

    def __init__(self, api: Api, steps: dict[str, list[str]]):
        self.api, self.steps = api, steps
        self.aliases: dict[str, str] = {}     # local name -> dotted module or object path
        self.types: dict[str, str] = {}       # variable -> short type name
        self.lineage: dict[str, list[str]] = {}

    def _dotted(self, node) -> str | None:
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if not isinstance(node, ast.Name):
            return None
        root = self.aliases.get(node.id)
        return ".".join([root or node.id, *reversed(parts)]) if root else None

    def _imports(self, tree) -> set[str]:
        used = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.aliases[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
                    used.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                for a in node.names:
                    self.aliases[a.asname or a.name] = f"{node.module}.{a.name}"
                used.add(node.module.split(".")[0])
        return used

    def evaluate(self, node, calls: list, lineage: list | None = None) -> tuple[str | None, list[str]]:
        """The type an expression produces and the guide steps along its chain; records each call."""
        if isinstance(node, ast.Name):
            return self.types.get(node.id), list(self.lineage.get(node.id, []))
        if not isinstance(node, ast.Call):
            return None, []
        func = node.func
        for arg in [*node.args, *(k.value for k in node.keywords)]:
            self.evaluate(arg, calls)
        if isinstance(func, ast.Attribute):
            receiver, chain = self.evaluate(func.value, calls)
            if receiver:
                described = self.api.method(receiver, func.attr)
                steps = self.steps.get(f"{receiver}.{func.attr}", [])
                calls.append(self._call(f"{receiver}.{func.attr}", node, described, steps, chain))
                return self.api.result_type(receiver, func.attr), chain + [s.split(":")[1] for s in steps]
        dotted = self._dotted(func)
        if dotted and dotted.split(".")[0] in _PACKAGES:
            owner = self.api.class_by_name(dotted.rsplit(".", 1)[0]) if "." in dotted else None
            if owner and self.api.method(owner, func.attr if isinstance(func, ast.Attribute) else ""):
                # A method called on the class itself, e.g. Series.from_pandas or PaleoUnit.from_synonym.
                name = func.attr
                steps = self.steps.get(f"{owner}.{name}", [])
                calls.append(self._call(f"{owner}.{name}", node, self.api.method(owner, name), steps, []))
                return self.api.result_type(owner, name), []
            cls = self.api.class_by_name(dotted)
            described = (self.api.method(cls, "__init__") if cls else self.api.function(dotted))
            calls.append(self._call(dotted, node, described, [], []))
            if cls:
                return cls, []
            returns = (described or {}).get("returns") or {}
            return returns.get("type"), []
        return None, []

    def _call(self, name: str, node: ast.Call, described: dict | None, steps: list[str], chain: list[str]) -> dict:
        defaults = {p["name"]: p["default"] for p in (described or {}).get("params", [])}
        chosen = {}
        for keyword in node.keywords:
            if keyword.arg is None:
                continue
            value = _literal(keyword.value)
            if keyword.arg not in defaults or value is None or value != defaults[keyword.arg]:
                chosen[keyword.arg] = value if value is not None else ast.unparse(keyword.value)[:80]
        return {"call": name, "known": described is not None, "steps": steps, "after": chain,
                "arguments": chosen}

    def read_cell(self, code: str) -> dict | None:
        try:
            tree = ast.parse(_without_magics(code))
        except SyntaxError:
            return None
        packages = self._imports(tree)
        calls: list[dict] = []
        for statement in tree.body:
            value = getattr(statement, "value", None)
            if isinstance(statement, (ast.Assign, ast.Expr, ast.AnnAssign)) and value is not None:
                kind, chain = self.evaluate(value, calls)
                targets = statement.targets if isinstance(statement, ast.Assign) else \
                    [statement.target] if isinstance(statement, ast.AnnAssign) else []
                for target in targets:
                    if isinstance(target, ast.Name):
                        if kind:
                            self.types[target.id], self.lineage[target.id] = kind, chain
                        else:
                            self.types.pop(target.id, None)
                            self.lineage.pop(target.id, None)
            else:
                for node in ast.walk(statement):
                    if isinstance(node, ast.Call):
                        self.evaluate(node, calls)
        packages |= {c["call"].split(".")[0] for c in calls if c["call"].split(".")[0] in _PACKAGES}
        if any(c["call"].split(".")[0] not in _PACKAGES for c in calls):
            packages.add("pyleoclim/pylipd/pyleotups objects")
        return {"packages": sorted(p for p in packages if p in _PACKAGES or not p.endswith("objects")),
                "calls": calls}


def _without_magics(code: str) -> str:
    """IPython lines (`%load_ext`, `!pip`, `%%time`) aren't Python; blank them so the rest parses."""
    return "\n".join("" if line.lstrip().startswith(("%", "!")) else line for line in code.splitlines())


# --- the rendered pages ----------------------------------------------------------------------
# The tutorials and some PaleoBooks are published as Jupyter Book pages, where every heading has
# an anchor. Linking there lands next to the example cell; GitHub's notebook view has no anchors.

def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


class _Sections(HTMLParser):
    """Each `<section id=...>`'s first heading text, read from the page itself."""

    def __init__(self):
        super().__init__()
        self.ids, self._pending, self._in_heading, self._text = {}, None, False, []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "section" and attrs.get("id"):
            self._pending = attrs["id"]
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._pending:
            self._in_heading, self._text = True, []

    def handle_endtag(self, tag):
        if self._in_heading and tag.startswith("h") and len(tag) == 2:
            self.ids.setdefault(_key("".join(self._text)), self._pending)
            self._in_heading, self._pending = False, None

    def handle_data(self, data):
        if self._in_heading:
            self._text.append(data)


def rendered_page(entry: dict) -> tuple[str | None, dict[str, str]]:
    """The notebook's published page, if it exists, and its heading-to-anchor map."""
    url = f"https://linked.earth/{entry['repository']}/{entry['source_path'].rsplit('.', 1)[0]}.html"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "paleopal-build"})
        with urllib.request.urlopen(request, timeout=30) as reply:
            html = reply.read().decode("utf-8", "replace")
    except Exception:
        return None, {}
    sections = _Sections()
    sections.feed(html)
    return url, sections.ids


def _heading_text(markdown_heading: str) -> str:
    """A markdown heading as the page shows it: no emphasis, code marks or link targets."""
    text = re.sub(r"<[^>]+>", "", markdown_heading)  # e.g. <a name='age'> … </a>
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return re.sub(r"[*_`]", "", text)


def _markdown(cell) -> str:
    return "".join(cell.get("source", "")) if isinstance(cell.get("source"), list) else cell.get("source", "")


def read_notebook(path: Path, entry: dict, api: Api, steps: dict,
                  page: tuple[str | None, dict[str, str]] = (None, {})) -> list[dict]:
    notebook = json.loads(path.read_text())
    page_url, anchors = page
    reader = Reader(api, steps)
    records, heading, markdown = [], None, []
    code_index = 0
    for number, cell in enumerate(notebook.get("cells", [])):
        text = _markdown(cell)
        if cell.get("cell_type") == "markdown":
            for line in text.splitlines():
                if line.lstrip().startswith("#"):
                    heading = line.lstrip("#").strip()
            markdown.append(text.strip())
            continue
        if cell.get("cell_type") != "code" or not text.strip():
            continue
        facts = reader.read_cell(text)
        if facts is None:
            markdown = []
            continue
        records.append({
            "id": f"{entry['destination_path']}#{number}",
            "notebook": entry["destination_path"], "url": entry.get("source_url"),
            "source": entry["source_name"], "kind": _KIND.get(entry["source_name"], "other"),
            "cell": number, "code_cell": code_index, "heading": heading,
            "markdown": "\n\n".join(m for m in markdown if m)[-_MARKDOWN_CHARS:],
            "code": text, **facts,
            "page_url": page_url,
            "section_url": (f"{page_url}#{anchors[_key(_heading_text(heading))]}"
                            if page_url and heading and _key(_heading_text(heading)) in anchors else page_url),
            "steps": sorted({s for c in facts["calls"] for s in c["steps"]}),
        })
        code_index += 1
        markdown = []
    for i, record in enumerate(records):
        record["previous"] = records[i - 1]["id"] if i else None
        record["next"] = records[i + 1]["id"] if i + 1 < len(records) else None
    return records


# --- the summary --------------------------------------------------------------------------------

def summarize(records: list[dict]) -> str:
    by_step, by_kind_step, unknown = Counter(), Counter(), Counter()
    packages = Counter()
    for r in records:
        packages.update(r["packages"])
        for step in r["steps"]:
            by_step[step] += 1
            by_kind_step[(step, r["kind"])] += 1
        for c in r["calls"]:
            if not c["known"] and "." in c["call"]:
                unknown[c["call"]] += 1
    lines = ["# Example catalog: summary", "",
             f"{len(records)} code cells from {len({r['notebook'] for r in records})} notebooks.", "",
             "## Cells using each package", ""]
    lines += [f"- {p}: {n}" for p, n in packages.most_common() if p in _PACKAGES]
    lines += ["", "## Cells demonstrating each guide step", "", "| step | cells | tutorials | PaleoBooks |",
              "|---|---|---|---|"]
    for step, n in sorted(by_step.items()):
        lines.append(f"| {step} | {n} | {by_kind_step[(step, 'tutorial')]} | {by_kind_step[(step, 'paleobook')]} |")
    with_lineage = Counter()
    for r in records:
        for c in r["calls"]:
            if any(s.endswith(":spectral_estimate") for s in c["steps"]):
                with_lineage[" → ".join(c["after"] + ["spectral"]) or "spectral"] += 1
    lines += ["", "## What came before each spectrum (lineage)", ""]
    lines += [f"- {k}: {n}" for k, n in with_lineage.most_common(15)]
    lines += ["", "## Calls on a known type that the references don't list (top 20)", ""]
    lines += [f"- `{k}`: {n}" for k, n in unknown.most_common(20)]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-pages", action="store_true", help="don't look up the published pages")
    args = parser.parse_args()
    api, steps = Api(), guide_steps()
    entries = json.loads((_LIBRARY / "_metadata" / "notebooks.json").read_text())
    records = []
    for entry in entries:
        path = _LIBRARY / entry["destination_path"]
        if path.exists():
            page = (None, {}) if args.no_pages else rendered_page(entry)
            records += read_notebook(path, entry, api, steps, page)
    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "catalog.jsonl", "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    (args.out / "summary.md").write_text(summarize(records))
    linked = sum(1 for r in records if r.get("section_url") and "#" in r["section_url"])
    print(f"Wrote {len(records)} cells to {args.out}; {linked} link to their section on a published page")


if __name__ == "__main__":
    main()
