from __future__ import annotations

"""readthedocs_library.symbol_loader

Utilities to extract class/function symbol documentation blocks (description + examples) from
Sphinx-generated Read-the-Docs HTML pages and turn them into `langchain` `Document`s.

The resulting document **text** (page_content) contains *only* human-readable narrative –
description paragraphs, example headings, etc.  All example **code** blocks are stripped
from the text and placed in the `metadata["code"]` field so that they can be surfaced to the
LLM separately without polluting the embedding space.

This file purposefully has *no* external runtime dependencies beyond BeautifulSoup4 so that
it can be reused in indexing and unit tests without LangChain present.
"""

from bs4 import BeautifulSoup  # type: ignore
from pathlib import Path
from typing import List, Dict, Any
import re

try:
    # Only import if langchain is available.  This allows import of this module for unit tests
    # without requiring the full langchain dependency tree.
    from langchain.docstore.document import Document  # type: ignore
except ImportError:  # pragma: no cover
    Document = Any  # type: ignore  # fallback placeholder for type hints


class SymbolExtractor:
    """Parse a single Sphinx HTML file and yield LangChain `Document`s – one per symbol."""

    #: CSS class prefix for Pygments-highlighted blocks
    _HIGHLIGHT_PREFIX = "highlight"
    _EXCLUDE_CODE_CLASSES = {"highlight-text", "highlight-console", "highlight-output"}

    def __init__(self, html_text: str, source_path: str | Path):
        self.soup = BeautifulSoup(html_text, "html.parser")
        self.source_path = str(source_path)

    # ---------------------------------------------------------------------
    # public helpers
    # ---------------------------------------------------------------------
    def extract(self) -> List["Document"]:
        """Return a list of `Document` objects (one per class/function found)."""
        documents: List["Document"] = []

        for dl in self.soup.find_all("dl", class_=lambda c: c and "py" in c):
            # <dt> holds the signature; <dd> the narrative, parameters, examples, …
            dt = dl.find("dt")
            dd = dl.find("dd")
            if dt is None or dd is None:
                continue


            symbol_id = dt.get("id") or dt.get_text(" ", strip=True)
            kind = self._infer_kind(dt)
            signature = dt.get_text(" ", strip=True)

            # -----------------------------
            # grab narrative text (no code)
            # -----------------------------
            # Make a shallow copy of the <dd> block so we can remove code blocks
            narrative_html = BeautifulSoup(str(dd), "html.parser")
            for code_div in narrative_html.find_all("div", class_=["highlight-python", "highlight-pycon", "literal-block", "cell_input"]):
                code_div.decompose()
            narrative_text = narrative_html.get_text(" ", strip=True)

            # -----------------------------------------------------------------
            # build embedding text: identifier + signature + narrative
            # this keeps code out of the embedding while making sure look-ups
            # that mention the function/class name rank highly.
            # -----------------------------------------------------------------
            embedding_text = f"{symbol_id}\n{signature}\n{narrative_text}"

            # -----------------------------
            # collect example code blocks
            # -----------------------------
            def _nearest_dl(tag):
                parent = tag.parent
                while parent is not None and parent.name != "dl":
                    parent = parent.parent
                return parent

            code_blocks = []
            for cb in dd.find_all("div", class_=["highlight-python", "highlight-pycon", "literal-block", "cell_input"]):
                # Only include code blocks whose nearest <dl> ancestor is the *current* dl
                if _nearest_dl(cb) is not dl:
                    continue  # belongs to nested symbol; skip
                
                raw = cb.get_text() #"", strip=False)
                # # Collapse spurious newlines introduced by Pygments markup (newline after every span)
                # cleaned = re.sub(r"[ \t]*\n[ \t]*", " ", raw)  # newline within code line → space
                # cleaned = re.sub(r"(\s\s+)", " ", cleaned)  # collapse multiple spaces
                # # Reintroduce real line breaks: two or more consecutive spaces replaced earlier may hide them.
                # cleaned = re.sub(r"( ?\n ?){2,}", "\n", cleaned)
                code_blocks.append(raw.strip())
            code_concat = "\n\n".join(code_blocks).strip()

            # -----------------------------
            # parameter names (best-effort)
            # -----------------------------
            params = self._extract_param_names(dd)

            meta: Dict[str, Any] = {
                "symbol": symbol_id,
                "kind": kind,
                "signature": signature,
                "params": ", ".join(params),
                "code": code_concat,
                "narrative": narrative_text,
                "source": self.source_path,
            }
            documents.append(Document(page_content=embedding_text, metadata=meta))  # type: ignore[arg-type]

        return documents

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _infer_kind(dt_tag) -> str:
        classes = dt_tag.get("class", [])
        if any("class" in c for c in classes):
            return "class"
        if any("method" in c or "function" in c for c in classes):
            return "function"
        # fall back to heuristic based on signature text
        text = dt_tag.get_text(" ", strip=True)
        return "class" if text.startswith("class ") else "function"

    @staticmethod
    def _extract_param_names(dd_tag) -> List[str]:
        names: List[str] = []
        # Sphinx parameter lists often appear in a <dt> within a <dl class="field-list">
        for field_dl in dd_tag.find_all("dl", class_=lambda c: c and "field-list" in c):
            for dt in field_dl.find_all("dt"):
                field_name = dt.get_text(" ", strip=True)
                if field_name.lower().startswith("parameters"):
                    # parameters list is in the following <dd>
                    dd = dt.find_next_sibling("dd")
                    if dd is None:
                        continue
                    for li in dd.find_all("li"):
                        # "name (type) – description" → grab name
                        token = li.get_text(" ", strip=True)
                        param = token.split(" ", 1)[0]
                        param = param.rstrip(",:")
                        if param:
                            names.append(param)
        return names

    @classmethod
    def _is_code_div(cls, div_classes):
        """Return True if the list of CSS classes indicates a code example block."""
        if not div_classes:
            return False
        # treat literal-block and cell_input as code as well
        if any(c == "literal-block" or c == "cell_input" for c in div_classes):
            return True
        # treat highlight-python and highlight-pycon as code as well
        if any(c == "highlight-python" or c == "highlight-pycon" for c in div_classes):
            return True
        for c in div_classes:
            if not c.startswith(cls._HIGHLIGHT_PREFIX):
                continue
            if c in cls._EXCLUDE_CODE_CLASSES:
                return False
            return True
        return False 