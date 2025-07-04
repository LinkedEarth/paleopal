"""
Node handlers for the Code Generation agent.
Enhanced with comprehensive contextual search.
"""

import logging
import json
import re
import uuid
import pathlib
from typing import Dict, Any, List, Optional
from langchain.schema import HumanMessage, SystemMessage
from datetime import datetime

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
    
    # Note: We used to have hardcoded invalid patterns, but this was incorrectly flagging valid functions
    # like load_dataset() which actually exists in pyleoclim.utils.datasets.load_dataset()
    # Now we rely only on the actual function signatures from all_symbols.txt
    
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
            # Only flag if the method name is truly not in approved functions (no hardcoded list)
            errors.append(f"Unrecognized PyLiPD method: '{full_match}' - method '{method_name}' not found in approved signatures")
    
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
            "similar_code": examples,  # Keep for internal state
            "similar_results": examples,  # Add for frontend display
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

def should_execute_code(state: CodeAgentState) -> str:
    """Determine if the generated code should be executed."""
    generated_code = state.generated_code or ""
    
    # Don't execute if no code was generated
    if not generated_code.strip():
        logger.info("No code to execute")
        return "false"
    
    # Check if execution is disabled
    enable_exec = True
    try:
        if isinstance(state, dict):
            enable_exec = state.get('metadata', {}).get('enable_execution', True)
        else:
            enable_exec = getattr(state, 'metadata', {}).get('enable_execution', True)
    except Exception:
        enable_exec = True
    
    if not enable_exec:
        logger.info("Execution disabled by frontend flag – skipping code execution")
        return "false"
    
    # Check validation errors - but allow execution if auto-execution is enabled
    validation_errors = getattr(state, 'validation_errors', []) or []
    if validation_errors:
        # If auto-execution is enabled, allow execution despite validation errors
        # This lets users see actual Python errors which can be more helpful
        if enable_exec:
            logger.info(f"Validation errors present but auto-execution is enabled - proceeding with execution")
            logger.info(f"Validation errors: {validation_errors}")
        else:
            logger.info("Validation errors present and auto-execution disabled, skipping execution")
            return "false"
    
    # Don't execute if there's already an error message
    if state.error_message:
        logger.info("Error message present, skipping execution")
        return "false"
    
    logger.info("Code ready for execution")
    return "true"

def should_refine_code(state: CodeAgentState) -> str:
    """Determine if code should be refined based on various criteria including execution errors."""
    generated_code = state.generated_code or ""
    error_message = state.error_message or ""
    validation_errors = getattr(state, 'validation_errors', []) or []
    execution_results = state.execution_results or []
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
    
    # Check for execution errors
    if execution_results:
        for result in execution_results:
            if isinstance(result, dict) and result.get("type") == "execution_error":
                logger.info("Execution error found, should refine")
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
        execution_results = state.execution_results or []
        
        if validation_errors:
            validation_issue = (
                "**PyLiPD/Pyleoclim Validation Errors**: The code contains function calls not found in the approved signatures:\n"
                + "\n".join(f"• {error}" for error in validation_errors) +
                "\n\nPlease use only the approved PyLiPD/Pyleoclim functions from the provided signatures. "
                "Check the function names and module paths to ensure they match the official API."
            )
            issues_detected.append(validation_issue)
        
        # Check for execution errors
        for result in execution_results:
            if isinstance(result, dict) and result.get("type") == "execution_error":
                execution_issue = (
                    f"**Execution Error**: The code failed to execute:\n"
                    f"• {result.get('error', 'Unknown execution error')}\n\n"
                    f"Please fix the code to resolve this execution error."
                )
                issues_detected.append(execution_issue)
        
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
6. **CRITICAL**: Contains ONLY executable Python code with proper # comment syntax
7. **CRITICAL**: All explanatory text must be Python comments starting with # character
8. **CRITICAL**: No markdown, prose, or unescaped text that would cause syntax errors

Return your response as JSON with keys: code, description, improvements_made.
"""
        
        messages = [
            SystemMessage(content="You are an expert Python developer specializing in paleoclimate data analysis. "
                                "You must only use valid PyLiPD/Pyleoclim functions that exist in the approved signatures. "
                                "CRITICAL REQUIREMENT: The 'code' field must contain ONLY executable Python code. "
                                "ALL explanatory text must use proper Python comment syntax starting with # character. "
                                "Never include markdown, prose, or unescaped text that would cause Python syntax errors."),
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

def _create_comprehensive_variable_context(conversation_id: str) -> str:
    """Create comprehensive variable context with IDs, types, and smart value previews."""
    try:
        from services.python_execution_service import python_execution_service
        
        # Get the current conversation state (all variables)
        state = python_execution_service.get_conversation_state(conversation_id)
        
        if not state:
            return ""
        
        # Filter out private variables and functions
        user_variables = {
            name: value for name, value in state.items() 
            if not name.startswith('_') and not callable(value)
        }
        
        if not user_variables:
            return ""
        
        variable_context = "**CURRENT VARIABLE STATE:**\n\n"
        
        # Check if we have string data that might need parsing
        has_string_data = any(
            isinstance(var_value, str) and (
                var_value.strip().startswith('[') or 
                var_value.strip().startswith('{') or
                'values' in str(var_value).lower()
            )
            for var_value in user_variables.values()
        )
        
        for var_name, var_value in user_variables.items():
            try:
                # Get variable ID (memory address as unique identifier)
                var_id = f"var_{id(var_value)}"
                
                # Get fully qualified type name
                var_type = type(var_value)
                fully_qualified_type = f"{var_type.__module__}.{var_type.__name__}" if var_type.__module__ != 'builtins' else var_type.__name__
                
                # Get smart value preview based on type
                value_preview = _get_smart_value_preview(var_value)
                
                # Add variable information to context
                variable_context += f"• **{var_name}** (ID: {var_id})\n"
                variable_context += f"  - Type: `{fully_qualified_type}`\n"
                variable_context += f"  - Value Preview: {value_preview}\n\n"
                
            except Exception as e:
                logger.warning(f"Error processing variable '{var_name}': {e}")
                # Fallback for problematic variables
                variable_context += f"• **{var_name}** (ID: unknown)\n"
                variable_context += f"  - Type: `{type(var_value).__name__}`\n"
                variable_context += f"  - Value Preview: <Error displaying value>\n\n"
        
        # Add safe parsing guidance if we detected string data
        if has_string_data:
            variable_context += "\n**SAFE STRING PARSING EXAMPLES:**\n"
            variable_context += "```python\n"
            variable_context += "import ast\n"
            variable_context += "import json\n"
            variable_context += "import numpy as np\n\n"
            variable_context += "# Safe way to convert string representations to data:\n"
            variable_context += "# For list/array strings like '[1, 2, 3]':\n"
            variable_context += "values = ast.literal_eval(string_data)  # Safe alternative to eval()\n"
            variable_context += "array_data = np.array(values)\n\n"
            variable_context += "# For JSON strings:\n"
            variable_context += "data = json.loads(json_string)\n\n"
            variable_context += "# Never use eval() - it's unsafe!\n"
            variable_context += "```\n\n"
        
        return variable_context
        
    except Exception as e:
        logger.warning(f"Error creating comprehensive variable context: {e}")
        return ""

def _get_smart_value_preview(value) -> str:
    """Get smart value preview based on variable type."""
    try:
        var_type = type(value).__name__
        
        # Handle pandas DataFrames
        if hasattr(value, 'head') and hasattr(value, 'shape'):
            try:
                shape_str = f"Shape: {value.shape}"
                if hasattr(value, 'columns'):
                    cols_str = f"Columns: {list(value.columns)[:5]}" + ("..." if len(value.columns) > 5 else "")
                    head_str = f"Head:\n{value.head().to_string()}"
                    return f"`{shape_str}, {cols_str}`\n```\n{head_str}\n```"
                else:
                    head_str = f"Head:\n{value.head().to_string()}"
                    return f"`{shape_str}`\n```\n{head_str}\n```"
            except Exception:
                return f"`DataFrame with shape {getattr(value, 'shape', 'unknown')}`"
        
        # Handle pandas Series
        elif hasattr(value, 'head') and hasattr(value, 'name'):
            try:
                shape_str = f"Length: {len(value)}"
                head_str = f"Head:\n{value.head().to_string()}"
                return f"`{shape_str}, Name: {value.name}`\n```\n{head_str}\n```"
            except Exception:
                return f"`Series with length {len(value) if hasattr(value, '__len__') else 'unknown'}`"
        
        # Handle numpy arrays
        elif hasattr(value, 'shape') and hasattr(value, 'dtype'):
            try:
                shape_str = f"Shape: {value.shape}, dtype: {value.dtype}"
                if value.size <= 20:  # Small arrays - show all values
                    return f"`{shape_str}`\n```\n{value}\n```"
                else:  # Large arrays - show first few values
                    preview = str(value.flat[:10]).replace('\n', ' ')
                    return f"`{shape_str}`\n```\n[{preview}...]\n```"
            except Exception:
                return f"`Array with shape {getattr(value, 'shape', 'unknown')}`"
        
        # Handle lists and tuples
        elif isinstance(value, (list, tuple)):
            length = len(value)
            if length == 0:
                return f"`Empty {var_type}`"
            elif length <= 5:
                return f"`{var_type} of length {length}: {value}`"
            else:
                preview = f"{value[:3]}...{value[-1:]}"
                return f"`{var_type} of length {length}: {preview}`"
        
        # Handle dictionaries
        elif isinstance(value, dict):
            length = len(value)
            if length == 0:
                return "`Empty dict`"
            elif length <= 3:
                return f"`Dict with {length} keys: {dict(list(value.items())[:3])}`"
            else:
                preview_keys = list(value.keys())[:3]
                return f"`Dict with {length} keys: {preview_keys}...`"
        
        # Handle strings
        elif isinstance(value, str):
            if len(value) <= 50:
                return f"`'{value}'`"
            else:
                return f"`'{value[:47]}...'` (length: {len(value)})"
        
        # Handle numbers
        elif isinstance(value, (int, float, complex)):
            return f"`{value}`"
        
        # Handle boolean
        elif isinstance(value, bool):
            return f"`{value}`"
        
        # Handle PyLiPD/Pyleoclim objects
        elif hasattr(value, '__class__') and ('pylipd' in str(type(value)).lower() or 'pyleoclim' in str(type(value)).lower()):
            try:
                # Try to get useful info about the object
                if hasattr(value, '__str__'):
                    str_repr = str(value)
                    if len(str_repr) <= 100:
                        return f"`{str_repr}`"
                    else:
                        return f"`{str_repr[:97]}...`"
                else:
                    return f"`{type(value).__name__} object`"
            except Exception:
                return f"`{type(value).__name__} object`"
        
        # Generic fallback
        else:
            str_repr = str(value)
            if len(str_repr) <= 100:
                return f"`{str_repr}`"
            else:
                return f"`{str_repr[:97]}...`"
                
    except Exception as e:
        logger.debug(f"Error getting smart preview for value: {e}")
        return "`<Error displaying value>`"

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
            # Add conversation history if available
            context = state.context or {}
            if context.get("conversation_history"):
                contextual_data["conversation_history"] = context["conversation_history"]
            
            context_prompt = search_service.format_code_context_for_llm(contextual_data)
        
        # Add previous context if available (replaces refinement-specific logic)
        context = state.context or {}
        previous_variable_info = ""
        
        # Check for previous context either from database (has_previous_context) or frontend (previous_result_variable/variables)
        has_database_context = context.get("has_previous_context")
        has_frontend_context = context.get("previous_result_variable") or context.get("previous_result_variables")
        
        if has_database_context or has_frontend_context:
            logger.info("=== ADDING PREVIOUS CONTEXT TO CODE GENERATION ===")
            
            # Add previous context to contextual_data for proper formatting (only if from database)
            if has_database_context:
                contextual_data["refinement_context"] = {
                    "is_refinement": True,
                    "previous_query": context.get("previous_query"),
                    "previous_results": context.get("previous_results"),
                    "refinement_request": analysis_request,
                    "previous_agent_type": context.get("previous_agent_type")
                }
                logger.info(f"Previous query/code length: {len(context.get('previous_query', ''))}")
                logger.info(f"Previous results count: {len(context.get('previous_results', []))}")
            
            # Add information about available variables (handle both single and multiple)
            previous_result_variables = context.get("previous_result_variables")
            previous_result_variable = context.get("previous_result_variable")
            
            if previous_result_variables and len(previous_result_variables) > 1:
                var_list = "', '".join(previous_result_variables)
                previous_variable_info = f"\n\n**IMPORTANT**: A previous {context.get('previous_agent_type', 'agent')} agent has created {len(previous_result_variables)} variables named '{var_list}' containing the execution results. You can use these variables directly in your code instead of creating new variables."
                logger.info(f"Multiple previous result variables available: {previous_result_variables}")
            elif previous_result_variable:
                previous_variable_info = f"\n\n**IMPORTANT**: A previous {context.get('previous_agent_type', 'agent')} agent has created a variable named '{previous_result_variable}' containing the query results. You can use this variable directly in your code instead of creating new variables."
                logger.info(f"Single previous result variable available: {previous_result_variable}")
            elif previous_result_variables and len(previous_result_variables) == 1:
                previous_variable_info = f"\n\n**IMPORTANT**: A previous {context.get('previous_agent_type', 'agent')} agent has created a variable named '{previous_result_variables[0]}' containing the query results. You can use this variable directly in your code instead of creating new variables."
                logger.info(f"Single previous result variable available: {previous_result_variables[0]}")
            
            # Update the context prompt to include previous context
            context_prompt = search_service.format_code_context_for_llm(contextual_data)
            
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
        
        # Get comprehensive variable context with IDs, types, and smart previews
        variable_context = _create_comprehensive_variable_context(state.conversation_id)
        logger.info(f"Generated variable context length: {len(variable_context)} characters")
        
        # The previous context is now handled through the unified refinement_context 
        
        user_prompt = (
            f"ANALYSIS REQUEST: {analysis_request}{clarification_text}\n\n"
            f"DATA CONTEXT: {data_context}\n"
            f"ANALYSIS TYPE: {analysis_type}\n"
            f"OUTPUT FORMAT: {output_format}\n\n"
            f"COMPREHENSIVE CONTEXT:\n{context_prompt}\n\n"
            f"ADDITIONAL EXAMPLES:\n{examples_section}\n\n"
            f"{variable_context}\n\n"
            f"{previous_variable_info}\n\n"
            "INSTRUCTIONS:\n"
            "1. Use existing variables from the current variable state when applicable\n"
            "2. Reference variables by their exact names as shown in the variable state\n"
            "3. Consider variable types and values when generating code\n"
            "4. Follow patterns from the code snippets and examples\n"
            "5. Use correct API calls based on documentation\n"
            "6. Generate complete, executable code\n"
            "7. Include necessary imports\n"
            "8. **CRITICAL**: ALL comments and explanatory text must use proper Python comment syntax starting with # character\n"
            "9. **CRITICAL**: Do NOT include any explanatory text or descriptions outside of Python comments\n"
            "10. **CRITICAL**: The 'code' field must contain ONLY valid Python code with # comments - no markdown, no prose\n"
            "11. **SECURITY**: Use ast.literal_eval() instead of eval() for safe string parsing\n"
            "12. When converting string representations to data, use json.loads() or ast.literal_eval()\n\n"
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
                         "and quotes (use \\\" for \") to ensure valid JSON format. "
                         "*ABSOLUTELY CRITICAL - CODE SYNTAX*: The 'code' field must contain ONLY executable Python code. "
                         "ALL explanatory text, descriptions, or comments MUST use proper Python comment syntax starting with # character. "
                         "Do NOT include any markdown, prose, or unescaped text that would cause Python syntax errors. "
                         "Examples: '# This loads the dataset' (CORRECT) vs 'This loads the dataset' (INCORRECT - causes syntax error). "
                         "*SECURITY*: Never use eval() for parsing strings - use ast.literal_eval() or json.loads() instead. "
                         "When converting string representations of lists/arrays to actual data structures, use safe parsing methods.")
        
        if library_symbols:
            system_content += (f"""
                **CRITICAL CONSTRAINT - READ CAREFULLY**
                ### Approved pylipd / pyleoclim signatures
                The file `backend/all_symbols.txt` is already loaded into context.  
                Format:
                • First line:  “p:” legend – symbol-kind prefixes (`c=class`, `f=function`).  
                • Second line: “t:” legend – 1-letter type codes (`S=str`, …, `C:custom`, `X=unknown`).  
                • A class line begins with `c:` followed by its fully-qualified name and constructor sig.  
                • All indented lines beneath that class are its public methods, written as
                    <2 spaces><methodName>(param:type,…)->ReturnTypeCode
                • A free function line begins with `f:`.  
                • `N` means the call returns `None`.  
                • `O` / `X` mean “any / unknown”.
                Generate code **only** with symbols that appear in this list, 
                respecting parameter order and type hints.\n
                {library_symbols}\n"""
                "**COMMON PATTERNS FOR DATA ACCESS**:\n"
                "- pyleo.utils.load_dataset(name) ✅ (loads built-in Pyleoclim datasets)\n"
                "- lipd_obj.get(dsnames) ✅ (gets dataset(s) from graph)\n"
                "- lipd_obj.get_datasets() ✅ (returns list of Dataset objects)\n"
                "- lipd_obj.get_lipd(dsname) ✅ (gets LiPD json for dataset)\n\n"
                "If you need functionality that is not in the approved signatures, use alternative approaches "
                "with pandas, numpy, matplotlib, or other standard libraries instead. DO NOT make up PyLiPD/Pyleoclim function names."
            )
        
        # logger.info(f"User prompt: {user_prompt}")
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
        
        # Validate PyLiPD/Pyleoclim function usage (DISABLED)
        validation_errors = []
        # TEMPORARILY DISABLED: Code validation causing issues
        # if library_symbols and generated_code:
        #     validation_errors = validate_pylipd_pyleoclim_usage(generated_code, library_symbols)
        #     if validation_errors:
        #         logger.warning(f"Generated code contains {len(validation_errors)} PyLiPD/Pyleoclim validation errors:")
        #         for error in validation_errors:
        #             logger.warning(f"  - {error}")
        #         
        #         # Store validation errors in state for potential retry
        #         # Don't add to description yet - let the retry logic handle it
        #         logger.info("Validation errors detected - code may need regeneration")
        #     else:
        #         logger.info("✅ Generated code passed PyLiPD/Pyleoclim validation")
        logger.info("Code validation temporarily disabled")
        
        if output_format == "notebook":
            # Check if this is a workflow step execution (contains step marker)
            is_workflow_step = analysis_request and "[WORKFLOW STEP" in analysis_request
            
            if not is_workflow_step:
                # Only add header for non-workflow requests to avoid duplication
                description = parsed.get('description', 'Analysis')
                # Ensure each line of description has proper comment syntax
                description_lines = description.split('\n')
                formatted_description = '\n'.join(f"# {line}" for line in description_lines)
                
                header = (
                    f"{formatted_description}\n"
                    "# Auto-generated by PaleoPal CodeGenerationAgent with contextual search\n\n"
                )
                generated_code = header + generated_code
            # For workflow steps, the step information is already included in the generated code
        
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

def execute_code_node(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """Execute the generated code and capture results."""
    try:
        logger.info("=== EXECUTE_CODE_NODE CALLED ===")
        
        generated_code = state.generated_code or ""
        conversation_id = state.conversation_id or ""
        
        if not generated_code:
            logger.warning("No generated code to execute")
            return {
                "execution_results": [{"type": "no_code", "message": "No code was generated to execute"}],
                "conversation_id": conversation_id
            }
        
        if not conversation_id:
            logger.warning("No conversation ID for state management")
            return {
                "execution_results": [{"type": "error", "message": "No conversation ID for execution state"}],
                "conversation_id": conversation_id
            }
        
        # Import the execution service
        from services.python_execution_service import python_execution_service
        
        # Check if we have a previous result variable to reference
        context = state.context or {}
        previous_result_variable = context.get("previous_result_variable")
        
        if previous_result_variable:
            logger.info(f"Previous agent created variable '{previous_result_variable}' - code can reference this variable")
        else:
            logger.info("No previous result variable found - code will execute in fresh context")
        
        logger.info(f"Executing code for conversation {conversation_id}")
        logger.info(f"Code to execute (first 200 chars): {generated_code[:200]}...")
        
        # Prepend matplotlib backend configuration to avoid GUI issues
        matplotlib_config = """
# Configure matplotlib for non-interactive use
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')
"""
        
        # Combine matplotlib config with the generated code
        final_code = matplotlib_config + "\n" + generated_code
        
        # Execute the main generated code
        execution_result = python_execution_service.execute_code(
            code=final_code,
            conversation_id=conversation_id,
            timeout=300
        )
        
        logger.info(f"Execution completed. Success: {execution_result.success}")
        
        # Prepare execution results for state
        execution_results = []
        
        if execution_result.success:
            # Get variable summary for display (this is JSON-serializable)
            var_summary = python_execution_service.get_variable_summary(conversation_id)
            
            # Add successful execution result
            result_entry = {
                "type": "execution_success",
                "output": execution_result.output,
                "execution_time": execution_result.execution_time,
                "variable_summary": var_summary,
                "plots": execution_result.plots or []
            }
            # Note: Don't include raw variables as they contain non-serializable objects
            
            execution_results.append(result_entry)
            
            logger.info(f"Execution successful. Output length: {len(execution_result.output)}")
            logger.info(f"Variables created: {list(execution_result.variables.keys())}")
            
        else:
            # Add error result
            execution_results.append({
                "type": "execution_error",
                "error": execution_result.error,
                "output": execution_result.output,
                "execution_time": execution_result.execution_time,
                "plots": execution_result.plots or []
            })
            
            logger.warning(f"Execution failed: {execution_result.error}")
        
        # Also extract execution details for frontend display
        result = {
            "execution_results": execution_results,
            "conversation_id": conversation_id
        }
        
        # Add execution details in the format expected by frontend
        if execution_results:
            latest_result = execution_results[-1]  # Get the most recent execution result
            if latest_result.get("type") == "execution_success":
                result.update({
                    "execution_successful": True,
                    "execution_output": latest_result.get("output", ""),
                    "execution_time": latest_result.get("execution_time", 0.0),
                    "variable_state": latest_result.get("variable_summary", {})
                })
            elif latest_result.get("type") == "execution_error":
                result.update({
                    "execution_successful": False,
                    "execution_error": latest_result.get("error", ""),
                    "execution_output": latest_result.get("output", ""),
                    "execution_time": latest_result.get("execution_time", 0.0)
                })
        
        return result
        
    except Exception as e:
        logger.error(f"Error in execute_code_node: {e}")
        return {
            "execution_results": [{"type": "error", "message": f"Execution node error: {str(e)}"}],
            "execution_successful": False,
            "execution_error": f"Execution node error: {str(e)}",
            "execution_time": 0.0,
            "conversation_id": state.conversation_id
        } 