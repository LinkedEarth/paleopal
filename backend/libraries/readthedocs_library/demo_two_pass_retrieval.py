from __future__ import annotations

"""readthedocs_library.demo_two_pass_retrieval

Demo the *two-pass* retrieval workflow:
    1. Natural-language query → symbol index (search_symbols)
    2. For each top symbol hit → fetch best matching code from the code index

Run:
    python -m readthedocs_library.demo_two_pass_retrieval "get LiPD timeseries"

You can tweak number of results with --sym-k / --code-k and toggle full code output.
"""

import argparse
import textwrap

try:
    from .search_symbols import search_symbols_hybrid, search_symbols
    from .search_code import search_code
except ImportError:  # pragma: no cover – allow running as flat script
    from search_symbols import search_symbols_hybrid, search_symbols  # type: ignore
    from search_code import search_code  # type: ignore


def _shorten(text: str, *, width: int = 100) -> str:
    return textwrap.shorten(text.replace("\n", " ").strip(), width=width)


def two_pass(query: str, *, sym_k: int = 5, code_k: int = 3, preview_chars: int = 120):
    try:
        symbols = search_symbols_hybrid(query, top_k_dense=sym_k, top_k_lex=3)
    except Exception:
        symbols = search_symbols(query, top_k=sym_k)
    if not symbols:
        print("No symbol hits found.")
        return

    print(f"Top {len(symbols)} symbols for query → {query!r}\n" + "=" * 80)

    for rank, sym in enumerate(symbols, 1):
        symbol_name = sym.get("symbol", "<unknown>")
        signature = sym.get("signature", "")
        score = sym.get("score", 0.0)
        print(f"[{rank}] {symbol_name}  (score {score:.3f})")
        print(f"Signature : {signature}")
        narrative = _shorten(sym.get("content", ""), width=120)
        print(f"Narrative : {narrative}")

        # Prefer the example code already present in metadata
        code_snippet = sym.get("code", "")

        # If not present, fall back to code index search using symbol name/signature
        if not code_snippet:
            search_term = f"{query}\n{symbol_name}\n{signature}"
            code_hits = search_code(search_term, top_k=code_k)
            if code_hits:
                code_snippet = code_hits[0].get("code", "")

        if code_snippet:
            preview = code_snippet if preview_chars == 0 else code_snippet[:preview_chars]
            if preview_chars and len(code_snippet) > preview_chars:
                preview += " …"
            print("Code preview:\n" + textwrap.indent(preview, "    "))
        else:
            print("Code preview: <none found>")
        print("-" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Two-pass retrieval demo: NL query → symbols → code")
    parser.add_argument("query", help="Natural-language query")
    parser.add_argument("--sym-k", type=int, default=5, help="Number of symbol hits")
    parser.add_argument("--code-k", type=int, default=3, help="Number of code hits per symbol if not embedded in metadata")
    parser.add_argument("--full", action="store_true", help="Show full code instead of preview")
    args = parser.parse_args()

    two_pass(args.query, sym_k=args.sym_k, code_k=args.code_k, preview_chars=0 if args.full else 120) 