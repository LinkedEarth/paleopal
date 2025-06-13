from __future__ import annotations

"""readthedocs_library.index_symbols

Build a Qdrant vector store where **each document corresponds to a single class or function**
extracted from Sphinx Read-the-Docs HTML pages.

The resulting index stores:
    text = description + narrative example text (no code)
    metadata = {
        symbol, kind, signature, params, code, source, library, symbol_type
    }

Example usage:
    python -m readthedocs_library.index_symbols docs/pylipd/docs --collection readthedocs_symbols
"""

import pathlib
import argparse
import logging
import sys
import uuid
from typing import List, Dict, Any

# Add parent directory to path for imports
current_dir = pathlib.Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))


# Local import that works both as package and as script
try:
    from .rtd_loader import RTDExtractor
except ImportError:  # pragma: no cover
    from rtd_loader import RTDExtractor  # type: ignore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rtd-symbol-index")


def _html_files_in(paths: List[pathlib.Path]):
    for root in paths:
        if root.is_dir():
            yield from root.rglob("*.html")
        elif root.suffix == ".html":
            yield root


def show_all_symbols(
    html_paths: List[pathlib.Path], 
) -> str:
    """
    Build Qdrant index from ReadTheDocs symbol extraction.
    
    Args:
        html_paths: List of paths to ReadTheDocs HTML directories or files        

    """
    # Collect all symbols from all files
    all_classes = []
    all_functions = []
    all_constants = []
    
    for html_path in _html_files_in(html_paths):
        try:
            html_text = html_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            logger.warning("Cannot read %s: %s", html_path, exc)
            continue

        extractor = RTDExtractor(html_text, html_path)
        result = extractor.extract()
        
        # Filter out problematic symbols
        for symbol in result.classes:
            if not _should_skip_symbol(symbol.name, symbol.signature, symbol.full_narrative):
                all_classes.append(symbol)
                
        for symbol in result.functions:
            if not _should_skip_symbol(symbol.name, symbol.signature, symbol.full_narrative):
                all_functions.append(symbol)
                
        for symbol in result.constants:
            if not _should_skip_symbol(symbol.name, symbol.signature, symbol.full_narrative):
                all_constants.append(symbol)

    # Sort each group alphabetically
    all_classes.sort(key=lambda x: x.name)
    all_constants.sort(key=lambda x: x.name)
    all_functions.sort(key=lambda x: x.name)
    
    # Print in order: classes, constants, functions
    for symbol in all_classes + all_constants + all_functions:
        print(symbol.signature)


def _should_skip_symbol(symbol_name: str, signature: str, narrative: str) -> bool:
    """Check if a symbol should be skipped based on various criteria."""
    # Skip synonyms - they are huge JSON strings without useful information
    if symbol_name.lower().endswith("synonyms"):
        return True
        
    # Skip malformed symbols that contain angle brackets or incomplete assignments
    if ("<" in symbol_name or ">" in symbol_name or 
        "= <" in signature or "= <" in narrative or
        narrative.strip().endswith("= <pylipd")):
        return True
        
    return False


# -----------------------------------------------------------------------------
# Helper: turn a metadata dict into an LLM-ready markdown snippet
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Show all ReadTheDocs symbols")
    parser.add_argument("paths", nargs="+", help="One or more paths to ReadTheDocs HTML directories or files")
    args = parser.parse_args()

    paths = [pathlib.Path(p) for p in args.paths]
    try:
        show_all_symbols(paths)
        print(f"✅ ReadTheDocs symbols shown successfully")
    except Exception as e:
        print(f"❌ Failed to show symbols: {e}")
        sys.exit(1) 