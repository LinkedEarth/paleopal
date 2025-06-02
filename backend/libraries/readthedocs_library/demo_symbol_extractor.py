from __future__ import annotations

"""readthedocs_library.demo_symbol_extractor

Quick CLI helper to inspect what `SymbolExtractor` pulls out of a Sphinx-generated
Read-the-Docs HTML file.  Run it on one or more *.html* pages and it will print a
summary of each symbol found plus a preview of the associated example code.

Example:
    python -m readthedocs_library.demo_symbol_extractor docs/pylipd/docs/pylipd.lipd.html
"""

import argparse
import pathlib
import textwrap
from typing import List

# Relative import works whether we run "python -m readthedocs_library.demo_symbol_extractor"
# or execute the file directly from its folder.
try:
    from .symbol_loader import SymbolExtractor
except ImportError:  # pragma: no cover
    from symbol_loader import SymbolExtractor  # type: ignore


def _print_symbol(doc, *, index: int):
    meta = doc.metadata or {}
    print(f"\n[{index}] {meta.get('symbol', '<unknown>')} – {meta.get('kind', '')}")
    print(f"Signature : {meta.get('signature', '')}")
    params = meta.get('params', '')
    if params:
        print(f"Params    : {params}")
    narrative_preview = textwrap.shorten(doc.page_content.replace("\n", " ").strip(), width=120)
    print(f"Narrative : {narrative_preview}")
    code = meta.get('code', '')
    if code:
        first_line = code.splitlines()[0] if code else ''
        print(f"Code      : {code.splitlines()}") #len(code.splitlines())} lines – preview → {first_line[:80]}")
    else:
        print("Code      : <none>")


def inspect_html(path: pathlib.Path):
    html_text = path.read_text(encoding="utf-8", errors="ignore")
    extractor = SymbolExtractor(html_text, path)
    docs: List = extractor.extract()

    print(f"=== {path} | {len(docs)} symbol(s) ===")
    for idx, d in enumerate(docs, 1):
        _print_symbol(d, index=idx)
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo the SymbolExtractor on one or more HTML files")
    parser.add_argument("html", nargs="+", help="Path(s) to Sphinx HTML file(s)")
    args = parser.parse_args()

    for p in map(pathlib.Path, args.html):
        inspect_html(p) 
