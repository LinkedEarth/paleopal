from __future__ import annotations

"""readthedocs_library.rtd_loader

Utilities to extract class/function symbol documentation blocks (description + examples) from
Sphinx-generated Read-the-Docs HTML pages and organize them into structured data.

The RTDExtractor returns organized data with separate classes, functions, and constants,
each containing name, description, signature, example code, and full narrative.
"""

from bs4 import BeautifulSoup  # type: ignore
from pathlib import Path
from typing import List, Dict, Any, NamedTuple
import re

try:
    # Only import if langchain is available.  This allows import of this module for unit tests
    # without requiring the full langchain dependency tree.
    from langchain.docstore.document import Document  # type: ignore
except ImportError:  # pragma: no cover
    Document = Any  # type: ignore  # fallback placeholder for type hints


class RTDSymbol(NamedTuple):
    """Structured representation of a symbol extracted from RTD documentation."""
    name: str
    description: str
    signature: str
    example_code: str
    full_narrative: str
    kind: str  # 'class', 'function', or 'constant'


class RTDExtractorResult(NamedTuple):
    """Result of RTD extraction organized by symbol type."""
    classes: List[RTDSymbol]
    functions: List[RTDSymbol]
    constants: List[RTDSymbol]


class RTDExtractor:
    """Parse a single Sphinx HTML file and extract organized symbol data."""

    #: CSS class prefix for Pygments-highlighted blocks
    _HIGHLIGHT_PREFIX = "highlight"
    _EXCLUDE_CODE_CLASSES = {"highlight-text", "highlight-console", "highlight-output"}

    def __init__(self, html_text: str, source_path: str | Path):
        self.soup = BeautifulSoup(html_text, "html.parser")
        self.source_path = str(source_path)

    # ---------------------------------------------------------------------
    # public helpers
    # ---------------------------------------------------------------------
    def extract(self) -> RTDExtractorResult:
        """Return organized RTD symbols grouped by type."""
        classes = []
        functions = []
        constants = []

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
                
                raw = cb.get_text()
                code_blocks.append(raw.strip())
            code_concat = "\n\n".join(code_blocks).strip()

            # -----------------------------
            # Create detailed signature
            # -----------------------------
            detailed_signature = self._create_detailed_signature(symbol_id, kind, signature, narrative_text)
            
            # -----------------------------
            # Extract description
            # -----------------------------
            description = self._extract_description(narrative_text)

            # Create RTDSymbol
            rtd_symbol = RTDSymbol(
                name=symbol_id,
                description=description,
                signature=detailed_signature,
                example_code=code_concat,
                full_narrative=narrative_text,
                kind=kind
            )

            # Categorize by type
            if kind == "class":
                classes.append(rtd_symbol)
            elif kind == "function":
                functions.append(rtd_symbol)
            else:  # constant
                constants.append(rtd_symbol)

        # Sort each category alphabetically
        classes.sort(key=lambda x: x.name)
        functions.sort(key=lambda x: x.name)
        constants.sort(key=lambda x: x.name)

        return RTDExtractorResult(classes=classes, functions=functions, constants=constants)

    def extract_legacy(self) -> List["Document"]:
        """Legacy method for backward compatibility - returns LangChain Documents."""
        result = self.extract()
        documents = []
        
        for symbol in result.classes + result.functions + result.constants:
            # Build embedding text: identifier + signature + narrative
            embedding_text = f"{symbol.name}\n{symbol.signature}\n{symbol.description}"

            meta: Dict[str, Any] = {
                "symbol": symbol.name,
                "kind": symbol.kind,
                "signature": symbol.signature,
                "params": self._extract_param_names_from_narrative(symbol.full_narrative),
                "code": symbol.example_code,
                "narrative": symbol.full_narrative,
                "source": self.source_path,
            }
            documents.append(Document(page_content=embedding_text, metadata=meta))  # type: ignore[arg-type]

        return documents

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _create_detailed_signature(self, symbol_id: str, kind: str, signature: str, narrative: str) -> str:
        """Create detailed type signature from symbol information."""
        # Clean signature: drop '[source]' and any unicode icons
        cleaned_sig = re.sub(r"\[source\].*", "", signature).replace("\uf0c1", "").strip()
        
        # Determine if this is a constant (no parentheses in signature)
        has_parentheses = "(" in cleaned_sig
        
        if not has_parentheses:
            # This is a constant - no parentheses
            return f"{kind} {symbol_id}"
        else:
            # Extract detailed parameter information from narrative
            params_with_types = self._extract_typed_parameters(narrative, cleaned_sig)
            compact_sig = f"{symbol_id}({params_with_types})"
            
            # Build the signature based on type
            if kind == "class":
                # Classes don't need return types
                return f"{kind} {compact_sig}"
            else:
                # Functions may have return types
                returns_info = self._extract_return_type(narrative)
                result = f"{kind} {compact_sig}"
                if returns_info:
                    result += f" -> {returns_info}"
                return result

    def _extract_description(self, narrative: str) -> str:
        """Extract the main description from the narrative."""
        # Extract purpose (first sentence of description)
        desc_split_re = re.compile(r"(Parameters|Returns|Examples)\s*:\s*", re.IGNORECASE)
        m_desc = desc_split_re.search(narrative)
        description = narrative[:m_desc.start()] if m_desc else narrative
        
        # Get first sentence as purpose
        purpose = description.split('.')[0].strip() if description else ""
        if len(purpose) > 150:
            purpose = purpose[:150] + "..."
        
        return purpose

    def _extract_typed_parameters(self, narrative: str, signature: str) -> str:
        """Extract parameter names with types from the narrative Parameters section."""
        # First, extract parameter names from the signature as fallback
        params_match = re.search(r"\((.*)\)", signature)
        sig_params_str = params_match.group(1) if params_match else ""
        
        # Parse signature parameters to get names and defaults
        sig_params = {}
        if sig_params_str:
            # Split by comma, but be careful of nested parentheses/brackets
            param_parts = []
            current_part = ""
            paren_depth = 0
            bracket_depth = 0
            
            for char in sig_params_str:
                if char == '(' and bracket_depth == 0:
                    paren_depth += 1
                elif char == ')' and bracket_depth == 0:
                    paren_depth -= 1
                elif char == '[' and paren_depth == 0:
                    bracket_depth += 1
                elif char == ']' and paren_depth == 0:
                    bracket_depth -= 1
                elif char == ',' and paren_depth == 0 and bracket_depth == 0:
                    param_parts.append(current_part.strip())
                    current_part = ""
                    continue
                current_part += char
            
            if current_part.strip():
                param_parts.append(current_part.strip())
            
            for param in param_parts:
                if '=' in param:
                    name, default = param.split('=', 1)
                    sig_params[name.strip()] = default.strip()
                else:
                    sig_params[param.strip()] = None

        # Now extract type information from the Parameters section
        params_section_match = re.search(r"Parameters\s*:\s*(.*?)(?=Returns\s*:|Return type\s*:|Examples\s*:|$)", narrative, re.IGNORECASE | re.DOTALL)
        
        typed_params = []
        
        if params_section_match:
            params_text = params_section_match.group(1)
            
            # Look for parameter entries like "signal (array-like, shape (n_samples,)) – The input signal."
            param_pattern = r"(\w+)\s*\(([^)]+(?:\([^)]*\))?[^)]*)\)\s*[–-]"
            param_matches = re.findall(param_pattern, params_text)
            
            for param_name, param_type_desc in param_matches:
                # Clean up the type description
                type_desc = param_type_desc.strip()
                
                # Convert common type descriptions to Python type hints
                python_type = self._convert_to_python_type(type_desc)
                
                # Check if parameter has default value
                if param_name in sig_params and sig_params[param_name] is not None:
                    default_val = sig_params[param_name]
                    # If parameter is optional and default is None, wrap type in Optional
                    if "optional" in type_desc.lower() and default_val.lower() == "none" and not python_type.startswith("Optional"):
                        python_type = f"Optional[{python_type}]"
                    typed_params.append(f"{param_name}: {python_type} = {default_val}")
                else:
                    typed_params.append(f"{param_name}: {python_type}")
        
        # If we couldn't extract typed parameters, fall back to signature parameters
        if not typed_params and sig_params:
            for param_name, default_val in sig_params.items():
                if default_val is not None:
                    typed_params.append(f"{param_name} = {default_val}")
                else:
                    typed_params.append(param_name)
        
        return ", ".join(typed_params)

    def _extract_return_type(self, narrative: str) -> str:
        """Extract return type information from the Returns/Return type section."""
        # Look for "Returns:" section first (more descriptive)
        returns_match = re.search(r"Returns\s*:\s*(.*?)(?=Return type|Examples|$)", narrative, re.IGNORECASE | re.DOTALL)
        if returns_match:
            returns_text = returns_match.group(1).strip()
            
            # Try to extract type information from the returns description
            # Look for patterns like "A tuple of four arrays" or "array-like"
            returns_lower = returns_text.lower()
            if "tuple" in returns_lower:
                # Try to count how many items in the tuple
                if ("four arrays" in returns_lower or "tuple of four" in returns_lower or 
                    "a tuple of four" in returns_lower):
                    return "Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]"
                elif ("three arrays" in returns_lower or "tuple of three" in returns_lower or
                      "a tuple of three" in returns_lower):
                    return "Tuple[np.ndarray, np.ndarray, np.ndarray]"
                elif ("two arrays" in returns_lower or "tuple of two" in returns_lower or
                      "a tuple of two" in returns_lower):
                    return "Tuple[np.ndarray, np.ndarray]"
                else:
                    return "tuple"
            elif "array" in returns_lower:
                return "np.ndarray"
            elif "dict" in returns_lower:
                return "dict"
            elif "list" in returns_lower:
                return "list"
            
            # Extract first word/phrase as potential type
            first_line = returns_text.split('\n')[0].strip()
            type_match = re.match(r"([^–\-:]+)", first_line)
            if type_match:
                potential_type = type_match.group(1).strip()
                return self._convert_to_python_type(potential_type)
        
        # Fall back to "Return type:" section if Returns section didn't provide good info
        return_type_match = re.search(r"Return type\s*:\s*(.*?)(?=\n\n|\n[A-Z]|$)", narrative, re.IGNORECASE | re.DOTALL)
        if return_type_match:
            return_type = return_type_match.group(1).strip()
            return self._convert_to_python_type(return_type)
        
        return ""

    def _convert_to_python_type(self, type_desc: str) -> str:
        """Convert documentation type descriptions to Python type hints."""
        type_desc = type_desc.strip().lower()
        
        # Handle common patterns
        if "array-like" in type_desc:
            if "shape" in type_desc:
                return "Sequence[float]"
            return "ArrayLike"
        elif "int" in type_desc:
            return "int"
        elif "float" in type_desc:
            return "float"
        elif "str" in type_desc:
            return "str"
        elif "bool" in type_desc:
            return "bool"
        elif "dict" in type_desc:
            return "dict"
        elif "list" in type_desc:
            return "list"
        elif "tuple" in type_desc:
            return "tuple"
        
        # Return the original if we can't convert it
        return type_desc.title() if type_desc else "Any"

    @staticmethod
    def _infer_kind(dt_tag) -> str:
        classes = dt_tag.get("class", [])
        if any("class" in c for c in classes):
            return "class"
        if any("method" in c or "function" in c for c in classes):
            return "function"
        # fall back to heuristic based on signature text
        text = dt_tag.get_text(" ", strip=True)
        if text.startswith("class "):
            return "class"
        elif "(" in text:
            return "function"
        else:
            return "constant"

    def _extract_param_names_from_narrative(self, narrative: str) -> str:
        """Extract parameter names from narrative for legacy compatibility."""
        params_section_match = re.search(r"Parameters\s*:\s*(.*?)(?=Returns\s*:|Return type\s*:|Examples\s*:|$)", narrative, re.IGNORECASE | re.DOTALL)
        
        if params_section_match:
            params_text = params_section_match.group(1)
            param_pattern = r"(\w+)\s*\([^)]+\)\s*[–-]"
            param_matches = re.findall(param_pattern, params_text)
            return ", ".join(param_matches)
        
        return ""

    @staticmethod
    def _extract_param_names(dd_tag) -> List[str]:
        """Legacy method for backward compatibility."""
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


# Backward compatibility alias
SymbolExtractor = RTDExtractor 