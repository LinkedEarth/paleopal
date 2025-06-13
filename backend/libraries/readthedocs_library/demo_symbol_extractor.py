from __future__ import annotations

"""readthedocs_library.demo_symbol_extractor

Quick CLI helper to inspect what `RTDExtractor` pulls out of a Sphinx-generated
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
    from .rtd_loader import RTDExtractor
except ImportError:  # pragma: no cover
    from rtd_loader import RTDExtractor  # type: ignore


def _print_symbol(symbol, *, index: int):
    print(f"\n[{index}] {symbol.name} – {symbol.kind}")
    print(f"Signature : {symbol.signature}")
    narrative_preview = textwrap.shorten(symbol.description.replace("\n", " ").strip(), width=120)
    print(f"Description: {narrative_preview}")
    if symbol.example_code:
        code_lines = symbol.example_code.splitlines()
        first_line = code_lines[0] if code_lines else ''
        print(f"Code      : {len(code_lines)} lines – preview → {first_line[:80]}")
    else:
        print("Code      : <none>")


def inspect_html(path: pathlib.Path):
    html_text = path.read_text(encoding="utf-8", errors="ignore")
    extractor = RTDExtractor(html_text, path)
    result = extractor.extract()

    # Combine all symbols
    all_symbols = result.classes + result.functions + result.constants
    
    print(f"=== {path} | {len(all_symbols)} symbol(s) ===")
    print(f"Classes: {len(result.classes)}, Functions: {len(result.functions)}, Constants: {len(result.constants)}")
    
    for idx, symbol in enumerate(all_symbols, 1):
        _print_symbol(symbol, index=idx)
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo the RTDExtractor on one or more HTML files")
    parser.add_argument("html", nargs="+", help="Path(s) to Sphinx HTML file(s)")
    args = parser.parse_args()

    for p in map(pathlib.Path, args.html):
        inspect_html(p) 
