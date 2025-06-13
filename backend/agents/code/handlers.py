"""
Node handlers for the Code Generation agent.
Enhanced with comprehensive contextual search.
"""

import logging
import json
import re
import uuid
import pathlib
from typing import Dict, Any, List
from langchain.schema import HumanMessage, SystemMessage

from .state import CodeAgentState, CodeAgentConfig
from agents.base_state import MAX_REFINEMENTS
from agents.base_langgraph_agent import get_config_value, get_message_value, format_clarification_response_for_llm
from services.search_integration_service import search_service

logger = logging.getLogger(__name__)

def _fix_json_escapes(json_str: str) -> str:
    """
    Fix invalid escape sequences in JSON strings while preserving valid ones.
    
    This function handles common issues where LLMs generate JSON with unescaped backslashes
    in code strings, which breaks JSON parsing.
    """
    import re
    
    try:
        # First, try to handle common problematic patterns
        
        # 1. Fix unescaped backslashes in string values (but not in escape sequences)
        # This pattern matches backslashes that are NOT followed by valid JSON escape characters
        # Valid JSON escapes: \" \\ \/ \b \f \n \r \t \uXXXX
        invalid_escape_pattern = r'\\(?!["\\/bfnrtu])'
        fixed_json = re.sub(invalid_escape_pattern, r'\\\\', json_str)
        
        # 2. Handle cases where there might be unescaped quotes in string values
        # This is more complex and risky, so we'll be conservative
        
        # 3. Remove any trailing commas before closing braces/brackets (common LLM mistake)
        fixed_json = re.sub(r',(\s*[}\]])', r'\1', fixed_json)
        
        # 4. Fix missing commas between JSON properties (common in multi-line JSON)
        # This pattern looks for a quote followed by whitespace and another quote (missing comma)
        fixed_json = re.sub(r'"\s*\n\s*"', '",\n  "', fixed_json)
        
        # 5. Fix missing commas after closing braces/brackets
        fixed_json = re.sub(r'([}\]])\s*\n\s*"', r'\1,\n  "', fixed_json)
        
        # 6. Ensure proper spacing around colons and commas
        fixed_json = re.sub(r':\s*(["\d\[\{])', r': \1', fixed_json)
        
        return fixed_json
        
    except Exception as e:
        logger.warning(f"Error in _fix_json_escapes: {e}, returning original string")
        return json_str

def load_library_symbols() -> str:
    """Load the all_symbols.txt file containing PyLiPD and Pyleoclim function signatures."""
    try:
        # Look for all_symbols.txt in the backend directory
        backend_dir = pathlib.Path(__file__).parent.parent.parent
        symbols_file = backend_dir / "all_symbols.txt"
        
        if symbols_file.exists():
            with open(symbols_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            logger.info(f"Loaded {len(content.splitlines())} function signatures from all_symbols.txt")
            return content
        else:
            logger.warning(f"all_symbols.txt not found at {symbols_file}")
            return ""
    except Exception as e:
        logger.error(f"Error loading all_symbols.txt: {e}")
        return ""

def validate_pylipd_pyleoclim_usage(code: str, library_symbols: str) -> List[str]:
    """
    Validate that the generated code only uses approved PyLiPD/Pyleoclim functions.
    
    Returns a list of validation errors (empty if valid).
    """
    if not library_symbols:
        return []
    
    errors = []
    
    # Extract all approved function names from the symbols
    approved_functions = set()
    for line in library_symbols.split('\n'):
        if line.startswith('function ') or line.startswith('class '):
            # Extract function/class name
            # Format: "function pylipd.lipd.LiPD.get_dataset(...)" or "class pylipd.lipd.LiPD(...)"
            parts = line.split('(')[0].split()
            if len(parts) >= 2:
                full_name = parts[1]
                # Extract just the method name (last part after the last dot)
                method_name = full_name.split('.')[-1]
                approved_functions.add(method_name)
                # Also add the full qualified name
                approved_functions.add(full_name)
    
    # Common invalid patterns that LLMs often use
    invalid_patterns = [
        r'\.get_dataset\s*\(',
        r'\.load_dataset\s*\(',
        r'\.find_dataset\s*\(',
        r'\.select_dataset\s*\(',
        r'\.fetch_dataset\s*\(',
        r'\.retrieve_dataset\s*\(',
    ]
    
    # Check for invalid patterns
    for pattern in invalid_patterns:
        matches = re.finditer(pattern, code, re.IGNORECASE)
        for match in matches:
            errors.append(f"Invalid function call found: '{match.group()}' - this function does not exist in PyLiPD/Pyleoclim")
    
    # Check for pylipd/pyleoclim method calls that aren't in approved list
    pylipd_pattern = r'(pylipd|pyleoclim)\.[\w\.]+\.(\w+)\s*\('
    matches = re.finditer(pylipd_pattern, code)
    for match in matches:
        method_name = match.group(2)
        full_match = match.group(0)
        if method_name not in approved_functions:
            errors.append(f"Unapproved PyLiPD/Pyleoclim function: '{full_match}' - not found in approved signatures")
    
    # Check for object method calls (e.g., lipd_obj.method())
    obj_pattern = r'(\w+)\.(\w+)\s*\('
    matches = re.finditer(obj_pattern, code)
    for match in matches:
        obj_name = match.group(1)
        method_name = match.group(2)
        full_match = match.group(0)
        
        # Skip standard library and common objects
        if obj_name.lower() in ['pd', 'np', 'plt', 'df', 'fig', 'ax', 'os', 'sys', 'json', 'datetime']:
            continue
            
        # Check if this looks like a PyLiPD object call
        if ('lipd' in obj_name.lower() or 'series' in obj_name.lower()) and method_name not in approved_functions:
            # Check if it's one of the known invalid methods
            if method_name in ['get_dataset', 'load_dataset', 'find_dataset', 'select_dataset', 'fetch_dataset']:
                errors.append(f"Invalid PyLiPD method: '{full_match}' - use approved alternatives like .get(), .get_datasets(), or .get_lipd()")
    
    return errors

async def search_code_examples_node(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """Enhanced search for relevant code examples using comprehensive contextual search."""
    try:
        analysis_request = getattr(state, "analysis_request", "") or state.user_input or ""
        analysis_type = getattr(state, "analysis_type", "general")
        
        if not analysis_request:
            return {
                "error_message": "No analysis request to search examples for",
                "conversation_id": state.conversation_id  # Preserve conversation_id
            }
        
        search_query = f"{analysis_request} {analysis_type}"
        logger.info(f"Searching for code context with query: '{search_query}'")

        # Extract previous code from context for variable continuity
        previous_code = ""
        context = state.context or {}
        if "previous_cells" in context:
            # Extract code from previous cells
            previous_cells = context["previous_cells"]
            if isinstance(previous_cells, list):
                code_parts = []
                for cell in previous_cells:
                    if isinstance(cell, dict) and cell.get("cell_type") == "code":
                        code_parts.append(cell.get("source", ""))
                previous_code = "\n\n".join(code_parts)
            elif isinstance(previous_cells, str):
                previous_code = previous_cells

        # Get comprehensive context for code generation using await
        context_data = await search_service.get_context_for_code_generation(
            user_query=search_query,
            previous_code=previous_code
        )
        
        # Store the context for later use in code generation
        state.contextual_search_data = context_data
        
        # Combine all examples from different sources
        examples: List[Dict[str, Any]] = []

        # 1) Add snippets from notebook library (high weight)
        snippets = context_data.get("snippets", [])
        for snippet in snippets:
            examples.append({
                "name": f"Notebook Snippet: {snippet.get('notebook', 'Unknown')}",
                "description": f"Code snippet with similarity {snippet.get('similarity_score', 0):.3f}",
                "categories": ["notebook_snippet"],
                "relevance_score": snippet.get("similarity_score", 0),
                "code": snippet.get("code", ""),
                "imports": snippet.get("imports", []),
                "source_type": "notebook_library"
            })

        # 2) Add code examples from readthedocs library
        code_examples = context_data.get("code_examples", [])
        for example in code_examples:
            examples.append({
                "name": f"API Example: {example.get('symbol', 'Unknown')}",
                "description": f"API usage example with similarity {example.get('similarity_score', 0):.3f}",
                "categories": ["api_example"],
                "relevance_score": example.get("similarity_score", 0),
                "code": example.get("code", ""),
                "source_type": "readthedocs_library"
            })

        # Sort examples by relevance score (descending)
        examples.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        logger.info(f"Total examples collected: {len(examples)} (snippets: {len(snippets)}, code_examples: {len(code_examples)})")

        # Prepare metadata for used examples
        used_examples_meta = []
        for ex in examples:
            used_examples_meta.append({
                "name": ex.get("name", "Unknown"),
                "description": ex.get("description", ""),
                "categories": ex.get("categories", []),
                "relevance_score": ex.get("relevance_score", 0),
                "source_type": ex.get("source_type", "unknown")
            })
        
        return {
            "similar_code": examples,  # Use generalized field
            "code_examples_used": used_examples_meta,
            "contextual_search_data": context_data,  # Store for code generation
            "conversation_id": state.conversation_id  # Preserve conversation_id
        }
        
    except Exception as e:
        logger.error(f"Error searching code examples: {e}")
        return {
            "error_message": str(e),
            "conversation_id": state.conversation_id  # Preserve conversation_id even in error case
        }

def detect_clarification_needs_code(
    llm,
    user_input: str,
    examples: list,
    data_context: dict
) -> Dict[str, Any]:
    """
    Detect if the code generation request needs clarification.
    
    Args:
        llm: LLM model to use
        user_input: Raw user input
        examples: Code examples found for the input
        data_context: Context about the data being analyzed
        
    Returns:
        Dict with clarification details if needed
    """
    try:
        # Check for potential ambiguities in code generation
        ambiguities = []
        
        # Case 1: Vague analysis request
        vague_terms = ['analyze', 'plot', 'show', 'look at', 'examine', 'study']
        if any(term in user_input.lower() for term in vague_terms) and len(user_input.split()) < 5:
            ambiguities.append({
                'type': 'vague_request',
                'description': 'The analysis request is quite general and could be interpreted in multiple ways'
            })
        
        # Case 2: Missing data context
        if not data_context and 'data' in user_input.lower():
            ambiguities.append({
                'type': 'missing_data_context',
                'description': 'No information about the data structure or format is available'
            })
        
        # Case 3: Multiple analysis types possible
        analysis_keywords = {
            'time series': ['time series', 'temporal', 'chronological'],
            'spectral': ['spectral', 'frequency', 'periodogram', 'psd'],
            'correlation': ['correlation', 'relationship', 'compare'],
            'statistics': ['statistics', 'statistical', 'mean', 'std', 'distribution'],
            'visualization': ['plot', 'chart', 'graph', 'visualize', 'show']
        }
        
        matching_types = []
        for analysis_type, keywords in analysis_keywords.items():
            if any(keyword in user_input.lower() for keyword in keywords):
                matching_types.append(analysis_type)
        
        if len(matching_types) > 1:
            ambiguities.append({
                'type': 'multiple_analysis_types',
                'matching_types': matching_types,
                'description': f'The request could involve multiple types of analysis: {", ".join(matching_types)}'
            })
        
        # If we found ambiguities, generate clarification questions
        if ambiguities:
            prompt = f"""Based on the user's code generation request, I need to generate clarification questions.

USER REQUEST: "{user_input}"

DATA CONTEXT: {data_context}

AMBIGUITIES DETECTED:
{chr(10).join([f"- {a['description']}" for a in ambiguities])}

Generate clarification questions to help create more precise Python code. Each question should:
1. Be specific about the ambiguity
2. Offer clear choices when possible
3. Help determine the exact analysis approach needed

Generate the questions in JSON format:
```json
{{
  "questions": [
    {{
      "id": "optional_unique_id",
      "question": "What specific type of analysis would you like to perform?",
      "context": "Your request could involve multiple analysis types",
      "choices": ["time series analysis", "correlation analysis", "spectral analysis"]
    }}
  ]
}}
```

Note: The "id" field is optional - unique IDs will be generated automatically if not provided.

Only include the JSON object, nothing else."""

            try:
                response = llm._call([HumanMessage(content=prompt)])
                
                # Parse JSON response
                json_match = re.search(r"```json\s*(\{.*?\})\s*```", response, re.DOTALL)
                if json_match:
                    raw_json = json_match.group(1)
                    try:
                        parsed = json.loads(raw_json)
                    except json.JSONDecodeError as je:
                        # Minimal fix: escape single backslashes that are not part of valid escapes
                        logger.warning(f"Primary JSON parse failed ({je}), applying backslash-escape fix and retrying")
                        safe_raw_json = raw_json.replace("\\", "\\\\")
                        try:
                            parsed = json.loads(safe_raw_json)
                        except json.JSONDecodeError as je2:
                            logger.error(f"Secondary JSON parse failed ({je2}), falling back to regex code extraction")
                            raise
                    
                    questions = parsed.get("questions", [])
                    
                    if questions:
                        # Add unique IDs to questions if they don't have them
                        for i, question in enumerate(questions):
                            if 'id' not in question:
                                question['id'] = f"code_q{i+1}_{uuid.uuid4().hex[:8]}"
                        
                        return {
                            "needs_clarification": True,
                            "clarification_questions": questions,
                            "ambiguities": ambiguities
                        }
                        
            except Exception as e:
                logger.warning(f"Failed to generate clarification questions: {e}")
        
        # No clarification needed
        return {"needs_clarification": False}
        
    except Exception as e:
        logger.error(f"Error detecting clarification needs: {e}")
        return {"needs_clarification": False}

def detect_clarification_node(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """Detect if clarification is needed for code generation."""
    try:
        analysis_request = state.analysis_request or ""
        examples = state.similar_code or []
        data_context = state.data_context or {}
        
        # Get LLM from config
        llm = get_config_value(config, 'llm')
        if not llm:
            logger.warning("No LLM available for clarification detection")
            return {
                "needs_clarification": False,
                "conversation_id": state.conversation_id  # Preserve conversation_id
            }
        
        # Check if clarification is enabled
        enable_clarification = get_config_value(config, 'enable_clarification', True)
        if not enable_clarification:
            logger.info("Clarification is disabled, skipping detection")
            return {
                "needs_clarification": False,
                "conversation_id": state.conversation_id  # Preserve conversation_id
            }
        
        # Skip clarification if we already have clarification responses
        if state.clarification_responses:
            logger.info("Clarification responses already provided, skipping detection")
            return {
                "needs_clarification": False,
                "conversation_id": state.conversation_id  # Preserve conversation_id
            }
        
        # Get clarification threshold from config
        clarification_threshold = get_config_value(config, 'clarification_threshold', 'conservative')
        user_input = analysis_request
        
        # For permissive threshold, skip clarification for simple, clear requests
        if clarification_threshold == "permissive":
            simple_patterns = [
                r'\bload\s+.*data.*into.*pandas\b',     # "load data into pandas"
                r'\bplot\s+.*time\s+series\b',          # "plot time series"
                r'\bcalculate\s+.*statistics?\b',       # "calculate statistics"
                r'\bshow\s+.*first.*rows?\b',           # "show first few rows"
                r'\bdisplay\s+.*data.*types?\b'         # "display data types"
            ]
            
            for pattern in simple_patterns:
                if re.search(pattern, user_input.lower()):
                    logger.info(f"Permissive threshold: skipping clarification for simple code pattern: {pattern}")
                    return {
                        "needs_clarification": False,
                        "conversation_id": state.conversation_id  # Preserve conversation_id
                    }
        
        # Detect clarification needs using existing function
        clarification_result = detect_clarification_needs_code(
            llm=llm,
            user_input=analysis_request,
            examples=examples,
            data_context=data_context
        )
        
        # Apply threshold filtering to the result
        needs_clarification = clarification_result.get("needs_clarification", False)
        
        if needs_clarification and clarification_threshold == "strict":
            # In strict mode, only ask for clarification if there are multiple ambiguities
            questions = clarification_result.get("clarification_questions", [])
            ambiguities = clarification_result.get("ambiguities", [])
            if len(questions) < 2 or len(ambiguities) < 2:
                logger.info("Strict threshold: skipping clarification with fewer than 2 questions/ambiguities")
                needs_clarification = False
        
        # If clarification is needed, return the questions
        if needs_clarification:
            logger.info(f"Clarification needed (threshold: {clarification_threshold}), adding questions to state")
            return {
                "needs_clarification": True,
                "clarification_questions": clarification_result.get("clarification_questions", []),
                "clarification_ambiguities": clarification_result.get("ambiguities", []),
                "conversation_id": state.conversation_id  # Preserve conversation_id
            }
        else:
            logger.info(f"No clarification needed (threshold: {clarification_threshold})")
            return {
                "needs_clarification": False,
                "conversation_id": state.conversation_id  # Preserve conversation_id
            }
        
    except Exception as e:
        logger.error(f"Error in clarification detection: {e}")
        return {
            "needs_clarification": False,
            "conversation_id": state.conversation_id  # Preserve conversation_id even in error case
        }

def should_refine_code(state: CodeAgentState) -> str:
    """Determine if code should be refined based on various criteria including validation errors."""
    generated_code = state.generated_code or ""
    error_message = state.error_message or ""
    validation_errors = getattr(state, 'validation_errors', []) or []
    refinement_count = state.refinement_count or 0
        
    # Check if we've reached max refinements
    if refinement_count >= MAX_REFINEMENTS:
        logger.info("Maximum refinements reached, not refining further")
        return "false"
    
    # Check if there are validation errors
    if validation_errors:
        logger.info(f"Found {len(validation_errors)} validation errors, should refine")
        return "true"
        
    # Check if there's an explicit error message
    if error_message:
        logger.info("Error message present, should refine")
        return "true"
        
    # Check if code is too short (likely incomplete)
    if len(generated_code.strip()) < 50:
        logger.info("Generated code too short, should refine")
        return "true"
        
    logger.info("No refinement needed")
    return "false"

def refine_code_node(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """Refine the generated code to address issues including validation errors."""
    try:
        generated_code = state.generated_code or ""
        error_message = state.error_message or ""
        validation_errors = getattr(state, 'validation_errors', []) or []
        analysis_request = state.analysis_request or ""
        refinement_count = state.refinement_count or 0
        
        if refinement_count >= MAX_REFINEMENTS:
            logger.warning("Maximum refinements reached")
            return {
                "refinement_complete": True,
                "conversation_id": state.conversation_id  # Preserve conversation_id
            }
        
        # Get LLM from config
        llm = get_config_value(config, 'llm')
        if not llm:
            return {
                "error_message": "LLM not available for refinement",
                "conversation_id": state.conversation_id  # Preserve conversation_id
            }
        
        # Build issues description based on what problems we found
        issues_detected = []
        if validation_errors:
            validation_issue = (
                "**PyLiPD/Pyleoclim Validation Errors**: The code contains invalid function calls:\n"
                + "\n".join(f"• {error}" for error in validation_errors) +
                "\n\nPlease use only the approved PyLiPD/Pyleoclim functions from the provided signatures. "
                "Do not use functions like get_dataset(), load_dataset(), or find_dataset() as they do not exist. "
                "Use the correct alternatives like get(), get_datasets(), or get_lipd() instead."
            )
            issues_detected.append(validation_issue)
        
        if error_message:
            issues_detected.append(f"**General Error**: {error_message}")
        
        if not issues_detected and len(generated_code.strip()) < 50:
            issues_detected.append("**Code Length**: Code seems incomplete or too short")
        
        if not issues_detected:
            issues_detected.append("Code needs general improvement")
        
        issues_text = "\n\n".join(issues_detected)
        
        # Create refinement prompt
        refinement_prompt = f"""
The following Python code was generated but has issues that need to be addressed:

ORIGINAL REQUEST: {analysis_request}

GENERATED CODE:
```python
{generated_code}
```

ISSUES DETECTED:
{issues_text}

Please provide an improved version of the code that:
1. Addresses all the identified issues
2. Uses only valid PyLiPD/Pyleoclim functions from the approved signatures
3. Maintains the original functionality
4. Follows best practices for paleoclimate data analysis
5. Uses appropriate libraries (PyLiPD, Pyleoclim, pandas, numpy)

Return your response as JSON with keys: code, description, improvements_made.
"""
        
        messages = [
            SystemMessage(content="You are an expert Python developer specializing in paleoclimate data analysis. "
                                "You must only use valid PyLiPD/Pyleoclim functions that exist in the approved signatures."),
            HumanMessage(content=refinement_prompt)
        ]
        
        raw_response = llm._call(messages)
        
        # Parse response
        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError:
            # Fallback parsing
                code_match = re.search(r"```python\s*(.*?)\s*```", raw_response, re.DOTALL)
                refined_code = code_match.group(1) if code_match else generated_code
                parsed = {
                    "code": refined_code,
                "description": "Code refined to address issues",
                "improvements_made": ["Fixed validation errors", "General improvements"]
            }
        
        refined_code = parsed.get("code", generated_code)
        
        return {
            "generated_code": refined_code,
            "refinement_count": refinement_count + 1,
            "error_message": "",  # Clear previous error
            "validation_errors": [],  # Clear validation errors - they'll be re-checked
            "refinement_description": parsed.get("description", "Code refined"),
            "improvements_made": parsed.get("improvements_made", []),
            "conversation_id": state.conversation_id  # Preserve conversation_id
        }
        
    except Exception as e:
        logger.error(f"Error refining code: {e}")
        return {
            "error_message": str(e),
            "conversation_id": state.conversation_id  # Preserve conversation_id even in error case
        }

def generate_code_node(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """Enhanced code generation with comprehensive contextual information."""
    try:
        logger.info("=== ENHANCED GENERATE_CODE_NODE CALLED ===")
        
        analysis_request = state.analysis_request or state.user_input or ""
        analysis_type = state.analysis_type or "general"
        output_format = state.output_format or "notebook"
        data_context = state.data_context or {}
        examples = state.similar_code or []
        contextual_data = getattr(state, 'contextual_search_data', {})
        
        logger.info(f"analysis_request: '{analysis_request}'")
        logger.info(f"user_input fallback: '{state.user_input}'")
        logger.info(f"analysis_type: {analysis_type}")
        logger.info(f"output_format: {output_format}")
        logger.info(f"examples count: {len(examples)}")
        logger.info(f"contextual_data keys: {list(contextual_data.keys())}")
        
        if not analysis_request:
            logger.error("No analysis request or user input provided")
            return {
                "error_message": "No analysis request or user input provided for code generation",
                "conversation_id": state.conversation_id  # Preserve conversation_id
            }
        
        # Format comprehensive context for LLM
        context_prompt = ""
        if contextual_data:
            context_prompt = search_service.format_code_context_for_llm(contextual_data)
        
        # Add previous context if available (replaces refinement-specific logic)
        context = state.context or {}
        if context.get("has_previous_context"):
            logger.info("=== ADDING PREVIOUS CONTEXT TO CODE GENERATION ===")
            # Add previous context to contextual_data for proper formatting
            contextual_data["refinement_context"] = {
                "is_refinement": True,
                "previous_query": context.get("previous_query"),
                "previous_results": context.get("previous_results"),
                "refinement_request": analysis_request,
                "previous_agent_type": context.get("previous_agent_type")
            }
            
            # Update the context prompt to include previous context
            context_prompt = search_service.format_code_context_for_llm(contextual_data)
            
            logger.info(f"Previous query/code length: {len(context.get('previous_query', ''))}")
            logger.info(f"Previous results count: {len(context.get('previous_results', []))}")
            logger.info(f"Previous agent type: {context.get('previous_agent_type')}")
        
        # Build examples section for prompt
        examples_section = ""
        for idx, ex in enumerate(examples, 1):
            examples_section += (
                f"\n## Example {idx}: {ex.get('name', 'Unknown')}\n"
                f"Source: {ex.get('source_type', 'unknown')}\n"
                f"Description: {ex.get('description', '')}\n"
                f"Relevance: {ex.get('relevance_score', 0):.3f}\n"
                f"Categories: {', '.join(ex.get('categories', []))}\n"
                "```python\n" + ex.get("code", "") + "\n```\n"
            )
        
        # Include clarification context if available
        clarification_text = format_clarification_response_for_llm(state)
        
        # Load library function signatures
        library_symbols = load_library_symbols()
        symbols_count = len(library_symbols.splitlines()) if library_symbols else 0
        logger.info(f"Loaded {symbols_count} library function signatures for code generation")
        
        # The previous context is now handled through the unified refinement_context 
        
        user_prompt = (
            f"ANALYSIS REQUEST: {analysis_request}{clarification_text}\n\n"
            f"DATA CONTEXT: {data_context}\n"
            f"ANALYSIS TYPE: {analysis_type}\n"
            f"OUTPUT FORMAT: {output_format}\n\n"
            f"COMPREHENSIVE CONTEXT:\n{context_prompt}\n\n"
            f"ADDITIONAL EXAMPLES:\n{examples_section}\n\n"
            "INSTRUCTIONS:\n"
            "1. Use variables from previous code when applicable\n"
            "2. Follow patterns from the code snippets and examples\n"
            "3. Use correct API calls based on documentation\n"
            "4. Generate complete, executable code\n"
            "5. Include necessary imports\n"
            "6. Add helpful comments\n\n"
            "Return JSON with keys: code, description, libraries, outputs."
        )
        
        # Generate code using LLM from config
        llm = get_config_value(config, 'llm')
        if not llm:
            logger.error("No LLM found in config")
            return {
                "error_message": "LLM not available",
                "conversation_id": state.conversation_id  # Preserve conversation_id
            }
        
        logger.info("Calling LLM to generate enhanced code...")
        
        # Build system message with library constraints
        system_content = ("You are an expert Python data-analysis assistant specializing in paleoclimate data. "
                                 "You have access to comprehensive context including code snippets, documentation, "
                                 "and previous code. Generate complete, executable code that integrates seamlessly "
                                 "with existing variables and follows established patterns. "
                                 "Use PyLiPD, Pyleoclim, pandas, numpy, and matplotlib as appropriate. "
                         "Return your response as valid JSON with keys: code, description, libraries, outputs. "
                         "*IMPORTANT*: Try to use the code snippets and examples to generate the code as much as possible. "
                         "*CRITICAL*: When including code in JSON, properly escape all backslashes (use \\\\ for \\) "
                         "and quotes (use \\\" for \") to ensure valid JSON format.")
        
        if library_symbols:
            system_content += (
                "\n\n**CRITICAL CONSTRAINT - READ CAREFULLY**: When using PyLiPD or Pyleoclim libraries, you MUST ONLY use "
                "functions, classes, and constants from the following approved signatures. Do NOT invent, assume, or use any "
                "PyLiPD or Pyleoclim functions that are not explicitly listed below. If a function is not in this list, IT DOES NOT EXIST.\n\n"
                f"APPROVED PYLIPD/PYLEOCLIM SIGNATURES:\n{library_symbols}\n\n"
                "**EXAMPLES OF WHAT NOT TO DO**:\n"
                "- lipd_obj.get_dataset(name) ❌ (does not exist)\n"
                "- lipd_obj.load_dataset(name) ❌ (does not exist)\n"
                "- lipd_obj.find_dataset(name) ❌ (does not exist)\n\n"
                "**CORRECT ALTERNATIVES**:\n"
                "- lipd_obj.get(dsnames) ✅ (gets dataset(s) from graph)\n"
                "- lipd_obj.get_datasets() ✅ (returns list of Dataset objects)\n"
                "- lipd_obj.get_lipd(dsname) ✅ (gets LiPD json for dataset)\n\n"
                "If you need functionality that is not in the approved signatures, use alternative approaches "
                "with pandas, numpy, matplotlib, or other standard libraries instead. DO NOT make up PyLiPD/Pyleoclim function names."
            )

        logger.info(f"System content: {system_content}")
        logger.info(f"User prompt: {user_prompt}")
        
        messages = [
            # SystemMessage(content=system_content),
            HumanMessage(content=system_content + "\n\n" + user_prompt)
        ]
        
        raw_response = llm._call(messages)
        logger.info(f"LLM raw response length: {len(raw_response)}")
        logger.info(f"LLM raw response preview: {raw_response[:200]}...")
        
        # Log the full response for debugging if it's not too long
        if len(raw_response) < 2000:
            logger.debug(f"Full LLM response: {raw_response}")
        else:
            logger.debug(f"LLM response too long for full logging ({len(raw_response)} chars)")
        
        # Parse response
        try:
            # Try to extract JSON from response
            # First try to find complete JSON blocks
            json_match = re.search(r"```json\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
            if not json_match:
                # If no complete JSON block, try to find JSON-like content
                json_match = re.search(r"```json\s*(\{.*)", raw_response, re.DOTALL)
                if json_match:
                    # Try to complete the JSON if it seems truncated
                    json_content = json_match.group(1)
                    # Count braces to see if we need to close them
                    open_braces = json_content.count('{') - json_content.count('}')
                    if open_braces > 0:
                        json_content += '}' * open_braces
                        logger.info(f"Attempted to complete truncated JSON by adding {open_braces} closing braces")
                    json_match = type('Match', (), {'group': lambda self, n: json_content})()
            
            if json_match:
                logger.info("Found JSON in code block")
                raw_json = json_match.group(1)
                try:
                    parsed = json.loads(raw_json)
                except json.JSONDecodeError as je:
                    # Smart fix: only escape backslashes that are not part of valid escape sequences
                    logger.warning(f"Primary JSON parse failed ({je}), applying smart backslash-escape fix and retrying")
                    logger.debug(f"Original JSON snippet around error: {raw_json[max(0, je.pos-50):je.pos+50]}")
                    safe_raw_json = _fix_json_escapes(raw_json)
                    try:
                        parsed = json.loads(safe_raw_json)
                        logger.info("JSON parsing succeeded after escape fix")
                        # Validate the parsed JSON has expected structure
                        if not isinstance(parsed, dict):
                            logger.warning(f"Parsed JSON is not a dict: {type(parsed)}")
                        elif 'code' not in parsed:
                            logger.warning("Parsed JSON missing 'code' field")
                        else:
                            logger.debug(f"Parsed JSON has {len(parsed)} fields: {list(parsed.keys())}")
                    except json.JSONDecodeError as je2:
                        logger.error(f"Secondary JSON parse failed ({je2}), falling back to regex code extraction")
                        logger.debug(f"Fixed JSON snippet around error: {safe_raw_json[max(0, je2.pos-50):je2.pos+50]}")
                        # Log the problematic character and context
                        if je2.pos < len(safe_raw_json):
                            problem_char = safe_raw_json[je2.pos]
                            logger.debug(f"Problematic character at position {je2.pos}: '{problem_char}' (ord: {ord(problem_char)})")
                        raise
            else:
                logger.info("Trying to parse entire response as JSON")
                parsed = json.loads(raw_response)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"JSON parsing failed: {e}, using fallback")
            # Enhanced fallback: try to extract structured information
            
            # Try to extract code block
            code_match = re.search(r"```python\s*(.*?)\s*```", raw_response, re.DOTALL)
            code_block = code_match.group(1) if code_match else ""
            
            # If no code block found, try to extract from JSON-like structure
            if not code_block:
                # Look for "code": "..." pattern
                code_pattern = r'"code"\s*:\s*"([^"]*(?:\\.[^"]*)*)"'
                code_match = re.search(code_pattern, raw_response, re.DOTALL)
                if code_match:
                    code_block = code_match.group(1).replace('\\"', '"').replace('\\\\', '\\')
                else:
                    # Last resort: use the entire response
                    code_block = raw_response
            
            # Try to extract description
            desc_pattern = r'"description"\s*:\s*"([^"]*(?:\\.[^"]*)*)"'
            desc_match = re.search(desc_pattern, raw_response)
            description = desc_match.group(1).replace('\\"', '"') if desc_match else f"Generated code for: {analysis_request}"
            
            # Try to extract libraries
            lib_pattern = r'"libraries"\s*:\s*\[(.*?)\]'
            lib_match = re.search(lib_pattern, raw_response, re.DOTALL)
            libraries = ["pyleoclim", "pandas", "numpy"]  # default
            if lib_match:
                lib_content = lib_match.group(1)
                # Extract quoted strings
                lib_strings = re.findall(r'"([^"]*)"', lib_content)
                if lib_strings:
                    libraries = lib_strings
            
            parsed = {
                "code": code_block,
                "description": description,
                "libraries": libraries,
                "outputs": ["results"],
            }
            logger.info(f"Fallback parsing extracted {len(code_block)} chars of code")
        
        # Format code based on output format
        generated_code = parsed.get("code", "")
        logger.info(f"Generated code length: {len(generated_code)}")
        logger.info(f"Generated code preview: {generated_code[:200]}...")
        
        # Validate PyLiPD/Pyleoclim function usage
        validation_errors = []
        if library_symbols and generated_code:
            validation_errors = validate_pylipd_pyleoclim_usage(generated_code, library_symbols)
            if validation_errors:
                logger.warning(f"Generated code contains {len(validation_errors)} PyLiPD/Pyleoclim validation errors:")
                for error in validation_errors:
                    logger.warning(f"  - {error}")
                
                # Store validation errors in state for potential retry
                # Don't add to description yet - let the retry logic handle it
                logger.info("Validation errors detected - code may need regeneration")
            else:
                logger.info("✅ Generated code passed PyLiPD/Pyleoclim validation")
        
        if output_format == "notebook":
            header = (
                f"# {parsed.get('description', 'Analysis')}\n"
                "# Auto-generated by PaleoPal CodeGenerationAgent with contextual search\n\n"
            )
            generated_code = header + generated_code
        
        # Add success message
        messages = state.messages or []
        context_summary = f"Used {len(contextual_data.get('snippets', []))} code snippets, " \
                         f"{len(contextual_data.get('documentation', []))} docs, " \
                         f"{len(contextual_data.get('code_examples', []))} examples"
        
        messages.append({
            "role": "assistant",
            "content": f"Generated {output_format} code for {analysis_type} analysis. {context_summary}."
        })
        
        result = {
            "generated_code": generated_code,
            "analysis_description": parsed.get("description", ""),
            "required_libraries": parsed.get("libraries", []),
            "expected_outputs": parsed.get("outputs", []),
            "messages": messages,
            "execution_results": [{"type": "code_generated", "status": "success"}],
            "context_used": context_summary,
            "validation_errors": validation_errors,  # Add validation errors to state
            "conversation_id": state.conversation_id  # Preserve conversation_id
        }
        
        logger.info(f"Returning enhanced result with generated_code length: {len(result['generated_code'])}")
        return result
        
    except Exception as e:
        logger.error(f"Error generating code: {e}", exc_info=True)
        return {
            "error_message": str(e),
            "conversation_id": state.conversation_id  # Preserve conversation_id even in error case
        }

def finalize_code_response_node(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """Finalize the code generation response."""
    try:
        generated_code = state.generated_code or ""
        analysis_description = state.analysis_description or ""
        refinement_count = state.refinement_count or 0
        has_error = bool(state.error_message)
        validation_errors = getattr(state, 'validation_errors', []) or []
        
        if not generated_code:
            return {
                "error_message": "No code was generated",
                "conversation_id": state.conversation_id  # Preserve conversation_id
            }
        
        # Add final message if not already present
        messages = state.messages or []
        
        # Handle different completion scenarios
        if validation_errors and refinement_count >= MAX_REFINEMENTS:
            # Add validation warnings to the description since we couldn't fix them
            validation_warning = (
                f"\n\n⚠️ **VALIDATION WARNINGS**: The generated code contains PyLiPD/Pyleoclim function calls that may not work:\n"
                + "\n".join(f"• {error}" for error in validation_errors) +
                "\n\nPlease review and correct these function calls manually using the approved PyLiPD/Pyleoclim API."
            )
            analysis_description += validation_warning
            message_content = "Code generation completed with validation warnings after maximum attempts."
            final_status = "completed_with_warnings"
        elif refinement_count >= MAX_REFINEMENTS and has_error:
            message_content = "Code generation completed after maximum refinement attempts."
            final_status = "refinement_exhausted"
        elif generated_code and not has_error and not validation_errors:
            message_content = f"Code generation completed successfully. {analysis_description}"
            final_status = "success"
        else:
            message_content = "Code generation completed."
            final_status = "completed"
        
        if not messages or get_message_value(messages[-1], "role") != "assistant":
            messages.append({
                "role": "assistant",
                "content": message_content
            })
        
        # Ensure execution_results is populated (may already be set by generate_code_node)
        execution_results = state.execution_results or []
        if not execution_results:
            execution_results = [{"type": "code_generated", "status": "success"}]
        
        return {
            "messages": messages,
            "execution_results": execution_results,
            "generated_code": generated_code,
            "analysis_description": analysis_description,  # Include updated description with warnings
            "needs_clarification": False,
            "final_status": final_status,
            "conversation_id": state.conversation_id  # Preserve conversation_id
        }
        
    except Exception as e:
        logger.error(f"Error finalizing code response: {e}")
        return {
            "error_message": str(e),
            "conversation_id": state.conversation_id  # Preserve conversation_id even in error case
        } 