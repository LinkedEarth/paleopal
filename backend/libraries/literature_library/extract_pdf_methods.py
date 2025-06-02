from __future__ import annotations

"""literature_library.extract_pdf_methods

Extract methods sections from PDF papers using LLM and save to individual JSON files.
Each method step is categorized and summarized as searchable statements for code library matching.
Skip papers that already have extracted methods files.
"""

import json
import logging
import os
import pathlib
import re
from typing import List, Dict, Any, Optional, Tuple

try:
    import fitz  # PyMuPDF
except ImportError as e:  # pragma: no cover
    raise ImportError("PyMuPDF is required: pip install pymupdf") from e

LOG = logging.getLogger("lit-extract-pdf-methods")
logging.basicConfig(level=logging.INFO)

# ----------------------------------------------------
# PDF section parsing and filtering
# ----------------------------------------------------

_HEADING_RE = re.compile(r"^\s*[A-Z][A-Za-z0-9\s\-&]{2,}$")

def extract_pdf_text_with_structure(pdf_path: pathlib.Path) -> List[Dict[str, str]]:
    """Extract text from PDF and attempt to identify sections."""
    try:
        doc = fitz.open(pdf_path)
        sections = []
        current_section = {"heading": "", "content": "", "page": 0}
        
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            lines = text.splitlines()
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if this might be a heading (heuristic approach for PDFs)
                if (_HEADING_RE.match(line) and 
                    len(line.split()) <= 8 and 
                    not line.endswith('.') and
                    len(line) > 3):
                    
                    # Save previous section if it has content
                    if current_section["content"].strip():
                        sections.append(current_section.copy())
                    
                    # Start new section
                    current_section = {
                        "heading": line,
                        "content": line + "\n",
                        "page": page_num + 1
                    }
                else:
                    # Add line to current section
                    current_section["content"] += line + "\n"
        
        # Add final section
        if current_section["content"].strip():
            sections.append(current_section)
        
        doc.close()
        return sections
        
    except Exception as e:
        LOG.error(f"Error extracting text from {pdf_path}: {e}")
        return []


def is_likely_methods_section(heading: str) -> Tuple[bool, float]:
    """
    Check if a section heading likely contains methods.
    Returns (is_likely, confidence_score)
    """
    heading_lower = heading.lower().strip()
    
    # High confidence methods indicators
    high_confidence_patterns = [
        r'\bmethods?\b',
        r'\bmethodology\b',
        r'\bexperimental\s+procedures?\b',
        r'\bexperimental\s+methods?\b',
        r'\bexperimental\s+design\b',
        r'\bmaterials?\s+and\s+methods?\b',
        r'\bprocedures?\b',
        r'\bexperimental\s+setup\b',
        r'\bdata\s+collection\b',
        r'\banalytical\s+methods?\b',
        r'\bstatistical\s+analysis\b',
        r'\bdata\s+analysis\b'
    ]
    
    # Medium confidence indicators
    medium_confidence_patterns = [
        r'\banalysis\b',
        r'\bapproach\b',
        r'\btechniques?\b',
        r'\bprotocol\b',
        r'\bworkflow\b',
        r'\bprocessing\b',
        r'\bimplementation\b',
        r'\bexperimental\b',
        r'\bmeasurements?\b'
    ]
    
    # Low confidence indicators
    low_confidence_patterns = [
        r'\bdata\b',
        r'\bmodel\b',
        r'\bstudy\b',
        r'\bsampling\b'
    ]
    
    # Exclude patterns (sections unlikely to contain methods)
    exclude_patterns = [
        r'\babstract\b',
        r'\bintroduction\b',
        r'\bresults?\b',
        r'\bdiscussion\b',
        r'\bconclusions?\b',
        r'\breferences?\b',
        r'\bbibliography\b',
        r'\backnowledg',
        r'\bappendix\b',
        r'\bsupplementary\b',
        r'\bfigures?\b',
        r'\btables?\b',
        r'\bliterature\s+review\b',
        r'\bbackground\b',
        r'\brelated\s+work\b'
    ]
    
    # Check exclusions first
    for pattern in exclude_patterns:
        if re.search(pattern, heading_lower):
            return False, 0.0
    
    # Check high confidence patterns
    for pattern in high_confidence_patterns:
        if re.search(pattern, heading_lower):
            return True, 0.9
    
    # Check medium confidence patterns
    for pattern in medium_confidence_patterns:
        if re.search(pattern, heading_lower):
            return True, 0.6
    
    # Check low confidence patterns
    for pattern in low_confidence_patterns:
        if re.search(pattern, heading_lower):
            return True, 0.3
    
    return False, 0.0


def filter_methods_sections(sections: List[Dict[str, str]], min_confidence: float = 0.3) -> List[Dict[str, str]]:
    """Filter sections that likely contain methods information."""
    methods_sections = []
    
    for section in sections:
        is_likely, confidence = is_likely_methods_section(section["heading"])
        if is_likely and confidence >= min_confidence:
            section["confidence"] = confidence
            methods_sections.append(section)
            LOG.info(f"Selected section '{section['heading']}' from page {section['page']} (confidence: {confidence:.2f})")
    
    return methods_sections


def combine_sections_smartly(sections: List[Dict[str, str]], max_chars: int = 12000) -> str:
    """Combine filtered sections intelligently, prioritizing by confidence and staying under char limit."""
    if not sections:
        return ""
    
    # Sort by confidence (highest first)
    sorted_sections = sorted(sections, key=lambda x: x.get("confidence", 0.0), reverse=True)
    
    combined_text = ""
    for section in sorted_sections:
        section_text = f"\n## {section['heading']} (Page {section['page']})\n{section['content']}\n"
        
        # Check if adding this section would exceed the limit
        if len(combined_text) + len(section_text) <= max_chars:
            combined_text += section_text
        else:
            # Try to fit partial content
            remaining_chars = max_chars - len(combined_text) - len(f"\n## {section['heading']} (Page {section['page']})\n")
            if remaining_chars > 200:  # Only add if we have reasonable space
                partial_content = section['content'][:remaining_chars] + "..."
                combined_text += f"\n## {section['heading']} (Page {section['page']})\n{partial_content}\n"
            break
    
    return combined_text.strip()


# ----------------------------------------------------
# LLM-based extraction (same as extract_methods.py)
# ----------------------------------------------------

def _call_openai(prompt: str, model: str = "gpt-4o", max_tokens: int = 20000) -> str:
    """Call OpenAI chat completion API compatible with both <1.0 and >=1.0 SDKs."""
    try:
        import openai  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise ImportError("openai package is required for --llm openai") from e

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY environment variable not set")

    messages = [
        {"role": "system", "content": "You are an expert scientific methods extractor and code workflow analyzer. You extract methods and structure them as implementable code steps."},
        {"role": "user", "content": prompt},
    ]

    # Detect SDK version
    if hasattr(openai, "OpenAI"):  # >=1.0.0
        client = openai.OpenAI()
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            # max_tokens=max_tokens,
            temperature=0,
        )
        return resp.choices[0].message.content.strip()  # type: ignore
    else:  # 0.x series
        resp = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            # max_tokens=max_tokens,
            temperature=0,
        )
        try:
            return resp.choices[0].message["content"].strip()  # type: ignore
        except Exception:
            # Some 0.x versions expose .choices[0].message.content
            return resp.choices[0].message.content.strip()  # type: ignore


def _call_grok(prompt: str, model: str = "grok-3-mini-beta", max_tokens: int = 20000) -> str:
    """Call Grok (xAI) API using OpenAI-compatible format."""
    try:
        import openai  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise ImportError("openai package is required for --llm grok") from e

    if not os.getenv("XAI_API_KEY"):
        raise RuntimeError("XAI_API_KEY environment variable not set")

    messages = [
        {"role": "system", "content": "You are an expert scientific methods extractor and code workflow analyzer. You extract methods and structure them as implementable code steps."},
        {"role": "user", "content": prompt},
    ]

    # Use OpenAI client with xAI base URL
    client = openai.OpenAI(
        api_key=os.getenv("XAI_API_KEY"),
        base_url="https://api.x.ai/v1"
    )
    
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        # max_tokens=max_tokens,
        temperature=0,
    )
    return resp.choices[0].message.content.strip()  # type: ignore


def _call_gemini(prompt: str, model: str = "gemini-2.5-flash-preview-04-17", max_tokens: int = 20000) -> str:
    """Call Google Gemini API."""
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise ImportError("google-generativeai package is required for --llm gemini (pip install google-generativeai)") from e

    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError("GOOGLE_API_KEY environment variable not set")

    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    
    # Configure the model
    generation_config = {
        "temperature": 0,
        "max_output_tokens": max_tokens,
    }
    
    model_instance = genai.GenerativeModel(
        model_name=model,
        generation_config=generation_config,
        system_instruction="You are an expert scientific methods extractor and code workflow analyzer. You extract methods and structure them as implementable code steps."
    )
    
    response = model_instance.generate_content(prompt)
    return response.text.strip()


def _call_claude(prompt: str, model: str = "claude-3-7-sonnet-20250219", max_tokens: int = 20000) -> str:
    """Call Anthropic Claude API."""
    try:
        import anthropic  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise ImportError("anthropic package is required for --llm claude (pip install anthropic)") from e

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=0,
        system="You are an expert scientific methods extractor and code workflow analyzer. You extract methods and structure them as implementable code steps.",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return response.content[0].text.strip()


def _call_ollama(prompt: str, model: str = "deepseek-r1") -> str:
    import requests

    req = {"model": model, "prompt": prompt, "stream": False}
    try:
        resp = requests.post("http://localhost:11434/api/generate", json=req, timeout=180)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
    except Exception as e:
        raise RuntimeError(f"Ollama request failed: {e}")


def extract_structured_methods(pdf_sections: List[Dict[str, str]], engine: str, max_chars: int = 12000) -> Optional[Dict[str, Any]]:
    """Extract methods section and structure as JSON with categorized steps."""
    valid_engines = ["openai", "grok", "gemini", "claude", "ollama"]
    if engine not in valid_engines:
        raise ValueError(f"Unsupported LLM engine: {engine}. Valid options: {valid_engines}")
    
    # Filter for likely methods sections
    methods_sections = filter_methods_sections(pdf_sections, min_confidence=0.3)
    
    if not methods_sections:
        LOG.warning("No potential methods sections found based on headings")
        return {"paper_title": "Unknown", "methods_found": False, "methods": []}
    
    # Combine selected sections intelligently
    combined_methods_text = combine_sections_smartly(methods_sections, max_chars)
    
    if not combined_methods_text.strip():
        LOG.warning("No methods content found after filtering")
        return {"paper_title": "Unknown", "methods_found": False, "methods": []}
    
    LOG.info(f"Sending {len(combined_methods_text)} characters to LLM from {len(methods_sections)} sections")
    
    prompt = f"""Extract and structure all experimental methods from the following sections of a scientific paper. There may be multiple distinct methods/procedures described.

For each distinct method/procedure, create a JSON entry with:
1. "method_name": A concise name for this method/procedure
2. "description": Full text description of what this method does and why it's used
3. "steps": Array of procedural steps for this method

For each step within a method, include:
1. "step_number": Sequential number within this method
2. "category": One of ["data_fetch", "data_analysis", "data_processing", "visualization", "modeling", "validation", "other"]
3. "description": Original step description
4. "searchable_summary": A concise statement describing what code would need to do (e.g., "download climate data from NOAA API", "perform linear regression analysis", "calculate correlation coefficients")
5. "inputs": What data/parameters this step requires
6. "outputs": What this step produces
7. "keywords": Relevant technical keywords for searching code libraries

Return ONLY a valid JSON object with this structure:
{{
  "paper_title": "inferred title or filename",
  "methods_found": true/false,
  "methods": [
    {{
      "method_name": "Ice Core Data Collection",
      "description": "Process for extracting and preparing ice core samples for isotope analysis...",
      "steps": [
        {{
          "step_number": 1,
          "category": "data_fetch",
          "description": "original step description",
          "searchable_summary": "brief implementable statement",
          "inputs": ["input1", "input2"],
          "outputs": ["output1", "output2"],
          "keywords": ["keyword1", "keyword2"]
        }}
      ]
    }},
    {{
      "method_name": "Statistical Analysis",
      "description": "Statistical procedures used to analyze the collected data...",
      "steps": [...]
    }}
  ]
}}

If no clear methods exist, return: {{"methods_found": false, "methods": []}}

Methods sections:
{combined_methods_text}"""
    
    try:
        if engine == "openai":
            response = _call_openai(prompt)
        elif engine == "grok":
            response = _call_grok(prompt)
        elif engine == "gemini":
            response = _call_gemini(prompt)
        elif engine == "claude":
            response = _call_claude(prompt)
        elif engine == "ollama":
            response = _call_ollama(prompt)
        
        # Try to parse JSON response
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response if it has extra text
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                LOG.error(f"Could not parse JSON from LLM response: {response[:200]}...")
                return None
                
    except Exception as e:
        LOG.error(f"LLM extraction failed: {e}")
        return None


# ----------------------------------------------------
# File handling and processing
# ----------------------------------------------------

def get_methods_file_path(pdf_path: pathlib.Path, output_dir: pathlib.Path = None) -> pathlib.Path:
    """Get the path where methods JSON should be saved for a given PDF file."""
    if output_dir is None:
        output_dir = pdf_path.parent / "extracted_methods"
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    return output_dir / f"{pdf_path.stem}_methods.json"


def validate_and_enhance_methods(methods_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and enhance the extracted methods data."""
    if not methods_data.get("methods_found", False):
        return methods_data
    
    # Ensure all methods have required fields
    enhanced_methods = []
    for i, method in enumerate(methods_data.get("methods", [])):
        enhanced_method = {
            "method_name": method.get("method_name", f"Method {i + 1}"),
            "description": method.get("description", ""),
            "steps": []
        }
        
        # Enhance steps within this method
        enhanced_steps = []
        for j, step in enumerate(method.get("steps", [])):
            enhanced_step = {
                "step_number": step.get("step_number", j + 1),
                "category": step.get("category", "other"),
                "description": step.get("description", ""),
                "searchable_summary": step.get("searchable_summary", ""),
                "inputs": step.get("inputs", []),
                "outputs": step.get("outputs", []),
                "keywords": step.get("keywords", [])
            }
            
            # Validate category
            valid_categories = ["data_fetch", "data_analysis", "data_processing", "visualization", "modeling", "validation", "other"]
            if enhanced_step["category"] not in valid_categories:
                enhanced_step["category"] = "other"
            
            enhanced_steps.append(enhanced_step)
        
        enhanced_method["steps"] = enhanced_steps
        enhanced_methods.append(enhanced_method)
    
    methods_data["methods"] = enhanced_methods
    return methods_data


def process_pdf_files(
    pdf_paths: List[pathlib.Path], 
    llm_engine: str = "openai",
    force_reprocess: bool = False,
    output_dir: pathlib.Path = None
) -> Dict[str, Any]:
    """
    Process PDF files and extract structured methods using LLM.
    
    Args:
        pdf_paths: List of PDF file paths
        llm_engine: LLM engine to use
        force_reprocess: If True, reprocess even if methods file exists
        output_dir: Directory to save method JSON files
    
    Returns:
        Dict with processing statistics
    """
    stats = {
        "total_files": len(pdf_paths),
        "processed": 0,
        "skipped_existing": 0,
        "failed": 0,
        "no_methods": 0,
        "total_steps": 0
    }
    
    # Set default output directory if not specified
    if output_dir is None and pdf_paths:
        output_dir = pdf_paths[0].parent / "extracted_methods"
    
    LOG.info(f"Saving method files to: {output_dir}")
    
    for pdf_path in pdf_paths:
        methods_path = get_methods_file_path(pdf_path, output_dir)
        
        # Skip if methods file already exists (unless force_reprocess)
        if methods_path.exists() and not force_reprocess:
            LOG.info(f"Skipping {pdf_path.name} - methods file already exists")
            stats["skipped_existing"] += 1
            continue
        
        LOG.info(f"Processing {pdf_path.name}")
        
        try:
            # Extract text and sections from PDF
            pdf_sections = extract_pdf_text_with_structure(pdf_path)
            
            if not pdf_sections:
                LOG.warning(f"Could not extract sections from {pdf_path.name}")
                stats["failed"] += 1
                continue
            
            LOG.info(f"Extracted {len(pdf_sections)} sections from PDF")
            
            # Extract structured methods using LLM
            methods_data = extract_structured_methods(pdf_sections, llm_engine)
            
            if methods_data is None:
                LOG.error(f"Failed to extract methods from {pdf_path.name}")
                stats["failed"] += 1
                continue
            
            # Enhance and validate the data
            methods_data = validate_and_enhance_methods(methods_data)
            
            # Add metadata
            methods_data["source_file"] = str(pdf_path)
            methods_data["extracted_at"] = str(pathlib.Path().cwd())
            
            if not methods_data.get("methods_found", False) or not methods_data.get("methods"):
                LOG.warning(f"No methods section found in {pdf_path.name}")
                stats["no_methods"] += 1
            else:
                # Count total steps across all methods
                total_steps = sum(len(method.get("steps", [])) for method in methods_data.get("methods", []))
                total_methods = len(methods_data.get("methods", []))
                stats["total_steps"] += total_steps
                stats["processed"] += 1
                LOG.info(f"Extracted {total_methods} methods with {total_steps} total steps from {pdf_path.name}")
            
            # Save structured methods as JSON
            with methods_path.open("w", encoding='utf-8') as f:
                json.dump(methods_data, f, indent=2, ensure_ascii=False)
            
            LOG.info(f"Saved methods to {methods_path.name}")
                
        except Exception as e:
            LOG.error(f"Error processing {pdf_path.name}: {e}")
            stats["failed"] += 1
            continue
    
    return stats


def create_methods_summary(output_dir: pathlib.Path) -> pathlib.Path:
    """Create a summary file listing all extracted methods files with statistics."""
    summary_path = output_dir / "methods_summary.jsonl"
    
    methods_files = list(output_dir.glob("*_methods.json"))
    
    with summary_path.open("w", encoding='utf-8') as f:
        for methods_file in methods_files:
            try:
                with methods_file.open(encoding='utf-8') as mf:
                    methods_data = json.load(mf)
                
                has_methods = methods_data.get("methods_found", False)
                methods_list = methods_data.get("methods", [])
                
                # Count total steps and categories across all methods
                total_steps = 0
                categories = {}
                methods_info = []
                
                for method in methods_list:
                    method_steps = method.get("steps", [])
                    total_steps += len(method_steps)
                    
                    for step in method_steps:
                        cat = step.get("category", "other")
                        categories[cat] = categories.get(cat, 0) + 1
                    
                    methods_info.append({
                        "name": method.get("method_name", "Unknown"),
                        "description": method.get("description", "")[:100] + "..." if len(method.get("description", "")) > 100 else method.get("description", ""),
                        "num_steps": len(method_steps)
                    })
                
                record = {
                    "source_file": methods_data.get("source_file", ""),
                    "methods_file": str(methods_file),
                    "has_methods": has_methods,
                    "num_methods": len(methods_list),
                    "total_steps": total_steps,
                    "categories": categories,
                    "methods_info": methods_info,
                    "paper_title": methods_data.get("paper_title", methods_file.stem.replace('_methods', ''))
                }
                f.write(json.dumps(record) + "\n")
                
            except Exception as e:
                LOG.warning(f"Error reading {methods_file}: {e}")
    
    LOG.info(f"Created methods summary: {summary_path}")
    return summary_path


def search_methods_by_keyword(output_dir: pathlib.Path, keyword: str) -> List[Dict[str, Any]]:
    """Search for method steps that match a keyword across all methods files."""
    results = []
    methods_files = list(output_dir.glob("*_methods.json"))
    
    for methods_file in methods_files:
        try:
            with methods_file.open(encoding='utf-8') as f:
                methods_data = json.load(f)
            
            for method in methods_data.get("methods", []):
                method_name = method.get("method_name", "Unknown Method")
                method_description = method.get("description", "")
                
                for step in method.get("steps", []):
                    # Search in searchable_summary, keywords, description, and method info
                    search_text = " ".join([
                        step.get("searchable_summary", ""),
                        " ".join(step.get("keywords", [])),
                        step.get("description", ""),
                        method_name,
                        method_description
                    ]).lower()
                    
                    if keyword.lower() in search_text:
                        results.append({
                            "source_file": methods_data.get("source_file", ""),
                            "paper_title": methods_data.get("paper_title", ""),
                            "method_name": method_name,
                            "method_description": method_description,
                            "step": step
                        })
                        
        except Exception as e:
            LOG.warning(f"Error searching {methods_file}: {e}")
    
    return results


if __name__ == "__main__":
    import argparse, sys
    
    parser = argparse.ArgumentParser(description="Extract structured methods from PDF papers using LLM")
    parser.add_argument("paths", nargs="+", help="PDF file(s) or folder(s) (recursively scanned for *.pdf)")
    parser.add_argument("--llm", choices=["openai", "grok", "gemini", "claude", "ollama"], default="openai", help="LLM engine to use")
    parser.add_argument("--force", action="store_true", help="Reprocess files even if methods file already exists")
    parser.add_argument("--summary", action="store_true", help="Create a summary file of all extracted methods")
    parser.add_argument("--search", type=str, help="Search for method steps containing this keyword")
    parser.add_argument("--output-dir", type=str, help="Directory to save method JSON files (default: {input_dir}/extracted_methods)")
    
    args = parser.parse_args()
    
    # Find all PDF files
    pdf_paths: List[pathlib.Path] = []
    for p in args.paths:
        path = pathlib.Path(p)
        if path.is_dir():
            pdf_paths.extend(list(path.rglob("*.pdf")))
        elif path.suffix.lower() == ".pdf":
            pdf_paths.append(path)
    
    if not pdf_paths:
        sys.exit("No PDF (*.pdf) files found.")
    
    # Set output directory
    output_dir = None
    if args.output_dir:
        output_dir = pathlib.Path(args.output_dir)
    elif pdf_paths:
        output_dir = pdf_paths[0].parent / "extracted_methods"
    
    # Handle search functionality
    if args.search:
        if output_dir:
            results = search_methods_by_keyword(output_dir, args.search)
            print(f"\nFound {len(results)} method steps matching '{args.search}':")
            for result in results:
                print(f"\nPaper: {result['paper_title']}")
                print(f"Method: {result['method_name']}")
                print(f"Method Description: {result['method_description'][:150]}...")
                print(f"Step {result['step']['step_number']}: {result['step']['searchable_summary']}")
                print(f"Category: {result['step']['category']}")
                print(f"Keywords: {', '.join(result['step']['keywords'])}")
        else:
            print("No output directory specified for search.")
        sys.exit(0)
    
    LOG.info(f"Found {len(pdf_paths)} PDF files")
    
    # Process files
    stats = process_pdf_files(pdf_paths, llm_engine=args.llm, force_reprocess=args.force, output_dir=output_dir)
    
    # Print statistics
    LOG.info("Processing complete!")
    LOG.info(f"Total files: {stats['total_files']}")
    LOG.info(f"Processed: {stats['processed']}")
    LOG.info(f"Skipped (existing): {stats['skipped_existing']}")
    LOG.info(f"No methods found: {stats['no_methods']}")
    LOG.info(f"Failed: {stats['failed']}")
    LOG.info(f"Total method steps extracted: {stats['total_steps']}")
    
    # Create summary if requested
    if args.summary and output_dir:
        create_methods_summary(output_dir) 