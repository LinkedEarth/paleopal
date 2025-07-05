#!/usr/bin/env python3
"""
Generate backend/all_symbols.txt by introspecting pylipd and pyleoclim.
"""
import importlib
import inspect
import pkgutil
import sys
import re
from pathlib import Path
from typing import Any, get_origin, get_args

PACKAGES = ["pyleoclim", "pylipd", "ammonyte"]

# ---------------------------------------------------------------------------
# Compact representation helpers
# ---------------------------------------------------------------------------

# One-letter codes for common built-ins.  Anything custom will be encoded as
# C:<ShortName>.  Unknown / external becomes X.
TYPE_CODES = {
    "str": "S",
    "int": "I",
    "float": "F",
    "bool": "B",
    "list": "L",
    "tuple": "T",
    "dict": "D",
    "None": "N",
    "Any": "O",
    "object": "O",
}


def type_code(ann: Any) -> str:
    """Return compact code for *ann*.

    • Built-ins     → single letter (S,I,F,B,L,T,D,N,O)
    • Custom class  → C:ClassName (only if defined in target packages)
    • Generic       → recurse, e.g. L[C:ChronData]
    • Fallback      → X
    """
    if ann is inspect._empty:
        return "O"  # unspecified / any

    # Handle typing generics like list[ChronData]
    origin = get_origin(ann)
    if origin is not None:
        args = get_args(ann)
        encoded_origin = type_code(origin)
        encoded_args = ",".join(type_code(a) for a in args) if args else ""
        return f"{encoded_origin}[{encoded_args}]" if encoded_args else encoded_origin

    # Regular (non-generic) type
    name = getattr(ann, "__name__", str(ann).split(".")[-1])

    # Built-in?
    if name in TYPE_CODES:
        return TYPE_CODES[name]

    # Custom class from target packages?
    mod = getattr(ann, "__module__", "")
    if any(mod.startswith(pkg) for pkg in PACKAGES):
        return f"C:{name}"

    # Unknown / external
    return "X"


def fmt_sig(obj) -> str:
    """Return compact signature: (name:code,...) or (params)->R."""
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return "()"

    # Attempt to supplement with docstring-derived types
    doc_param_types, doc_return_type = parse_doc_types(obj)

    pieces = []
    for p in sig.parameters.values():
        if p.name == "self":
            pieces.append("self")
            continue

        annot_code = type_code(p.annotation)
        if annot_code == "O":  # unspecified
            annot_code = doc_param_types.get(p.name, "O")

        pieces.append(f"{p.name}:{annot_code}")

    ret = type_code(sig.return_annotation)
    if ret == "O":
        # Try docstring-derived return type first
        if doc_return_type:
            ret = doc_return_type
        else:
            # Assume None when completely unspecified
            ret = "N"

    rtn_part = "" if ret == "N" else f"->{ret}"
    return f"({','.join(pieces)}){rtn_part}"


def walk_package(pkg_name: str):
    """Yield (qualified_name, obj) for every symbol in pkg_name."""
    # print(f"Walking package {pkg_name}")
    try:
        pkg = importlib.import_module(pkg_name)
    except Exception as e:  # pragma: no cover
        print(f"❌  Could not import {pkg_name}: {e}", file=sys.stderr)
        return

    # Recursively import sub-modules so that their symbols appear.
    for mod_info in pkgutil.walk_packages(pkg.__path__, prefix=f"{pkg.__name__}."):
        if mod_info.name == "pylipd.usage":
            continue
        if "test" in mod_info.name:
            continue
        # print(f"Importing module {mod_info.name}")
        try:
            importlib.import_module(mod_info.name)
        except Exception:
            continue  # skip modules that fail to import

    # After importing everything, walk all loaded modules that belong to the package.
    for name, module in sys.modules.items():
        if name == pkg.__name__ or name.startswith(pkg.__name__ + "."):
            for attr_name, obj in inspect.getmembers(module):
                if attr_name.startswith("_"):
                    continue  # skip private symbols

                # Only keep objects actually *defined* inside the target package.
                obj_mod = getattr(obj, "__module__", "")
                if not obj_mod.startswith(pkg.__name__):
                    # e.g. pandas.DataFrame imported into pylipd namespace → skip
                    continue

                yield f"{name}.{attr_name}", obj


def main():
    lines = []

    INDENT = "  "  # two spaces for nested method lines

    for pkg in PACKAGES:
        for qname, obj in walk_package(pkg):
            if inspect.isclass(obj):
                # emit class line with compact signature of __init__
                lines.append(f"c:{qname}{fmt_sig(obj.__init__)}")

                # emit public methods, indented, without repeating class name
                for m_name, m_obj in inspect.getmembers(obj, inspect.isfunction):
                    if m_name.startswith("_"):
                        continue
                    lines.append(f"{INDENT}{m_name}{fmt_sig(m_obj)}")

            elif inspect.isfunction(obj):
                lines.append(f"f:{qname}{fmt_sig(obj)}")

    # ------------------------------------------------------------------
    # 1) Prepend one-line legend of type codes for the LLM
    # 2) Remove duplicates while preserving first-seen order
    # ------------------------------------------------------------------

    # Legend lines
    kind_legend = "p:c=class,f=function"  # prefix legend

    # Build type-code legend; exclude 'Any' and add C custom notation
    type_pairs = [f"{v}={k}" for k, v in TYPE_CODES.items() if k not in {"Any"}]
    type_pairs.append("C:custom")
    type_pairs.append("X=unknown")
    type_legend = "t:" + ",".join(type_pairs)

    seen = set()
    deduped = []
    for ln in lines:
        if ln not in seen:
            deduped.append(ln)
            seen.add(ln)

    output_lines = [kind_legend, type_legend] + deduped

    print("\n".join(output_lines))


# ---------------------------------------------------------------------------
# Docstring parsing helpers (very lightweight – handles NumPy-style)
# ---------------------------------------------------------------------------

PARAM_REGEX = re.compile(r"^\s*(?P<name>[A-Za-z0-9_]+)\s*:\s*(?P<type>[^,\n]+)")


def code_from_type_str(type_str: str) -> str:
    """Map a raw type string from a docstring to compact code."""
    type_str = type_str.strip()

    # Handle generics like list[ChronData]
    if type_str.lower().startswith("list"):
        inner = type_str[type_str.find("[") + 1 : type_str.rfind("]")] if "[" in type_str else "object"
        return f"L[{code_from_type_str(inner)}]"

    # Built-ins
    base = type_str.split()[0]  # drop description following the type
    if base in TYPE_CODES:
        return TYPE_CODES[base]

    # Custom class?
    for pkg in PACKAGES:
        if base.startswith(pkg.split(".")[-1]):  # simple contains check
            return f"C:{base.split('.')[-1]}"

    return "X"


def parse_doc_types(obj):
    """Return (param_types:dict, return_type_code or None) for *obj*."""
    doc = inspect.getdoc(obj) or ""
    param_types = {}
    return_code = None

    section = None
    for line in doc.splitlines():
        line = line.rstrip()
        # Detect section headers (Parameters, Returns, Yields)
        if line.strip().lower() in {"parameters", "args", "arguments"}:
            section = "params"
            continue
        if line.strip().lower() in {"returns", "yield", "yields"}:
            section = "returns"
            continue

        if section == "params":
            m = PARAM_REGEX.match(line)
            if m:
                param_types[m.group("name")] = code_from_type_str(m.group("type"))
        elif section == "returns":
            # First non-empty line after "Returns" that looks like a type string
            stripped = line.strip()
            if stripped:
                return_code = code_from_type_str(stripped.split()[0])
                section = None  # stop after first type
    return param_types, return_code


if __name__ == "__main__":
    main()