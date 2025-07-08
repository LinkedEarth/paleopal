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
from services.service_manager import service_manager

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

# -----------------------------------------------------------------------------
# Utility: filter the massive all_symbols.txt to only the classes that matter
# -----------------------------------------------------------------------------

def _filter_library_symbols(all_symbols: str, variable_context: str, max_lines: int = 1500) -> str:
    """Return a trimmed version of *all_symbols* that only contains the classes
    referenced in *variable_context* (plus their indented method lines).

    This keeps the prompt small and focused while still giving the LLM the exact
    signatures it is allowed to use.

    Args:
        all_symbols: The full text of backend/all_symbols.txt.
        variable_context: The string returned by _create_comprehensive_variable_context().
        max_lines: Hard cap to avoid producing giant prompts if something goes
                   wrong (default 1500, well under most model limits).

    Returns:
        Filtered symbol text.  If no matching classes are found, falls back to
        the first *max_lines* lines of *all_symbols* to avoid returning an empty
        constraint block.
    """
    if not all_symbols:
        return ""

    import re

    # Pull fully-qualified class names from the variable context – they appear
    # in parentheses after the variable name, e.g. "• gisp2 (pyleoclim.core.series.Series)"
    class_matches = re.findall(r"\(([^)]+)\)", variable_context)
    relevant_classes = set(class_matches)

    if not relevant_classes:
        # Nothing extracted – return a safe slice of the original to keep some guidance
        return "\n".join(all_symbols.splitlines()[:max_lines])

    filtered_lines: list[str] = []
    include_block = False  # whether we are inside a class block that should be kept

    for line in all_symbols.splitlines():
        stripped = line.lstrip()

        # Detect the start of a class signature – lines beginning with "c:"
        if stripped.startswith("c:"):
            # Example line: "c:pyleoclim.core.series.Series(self)"
            class_name_part = stripped[2:]  # drop the "c:"
            class_name = class_name_part.split("(")[0].strip()

            include_block = class_name in relevant_classes

            if include_block:
                filtered_lines.append(line)
        else:
            # Indented method line – keep it only if current class is included
            if include_block:
                filtered_lines.append(line)

        if len(filtered_lines) >= max_lines:
            break

    # Fallback again if, for some reason, nothing was captured
    if not filtered_lines:
        return "\n".join(all_symbols.splitlines()[:max_lines])

    return "\n".join(filtered_lines)



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
    execution_results = state.execution_results or []
    refinement_count = state.refinement_count or 0
        
    # Check if we've reached max refinements
    if refinement_count >= MAX_REFINEMENTS:
        logger.info("Maximum refinements reached, not refining further")
        return "false"
        
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
        
        # Check for execution errors
        for result in execution_results:
            if isinstance(result, dict) and result.get("type") == "execution_error":
                error_msg = result.get('error', 'Unknown execution error')
                
                execution_issue = (
                    f"**Execution Error**: The code failed to execute with the following error:\n"
                    f"```\n{error_msg}\n```\n"
                    f"Please analyze the error message and fix the code accordingly."
                )
                issues_detected.append(execution_issue)    
        
        issues_text = "\n\n".join(issues_detected)
        
        # Use 2-step approach for refinement: detect current + needed functions
        use_two_step = get_config_value(config, 'use_two_step_llm') or True
        
        if use_two_step:
            # Step 1: Detect functions already in use + ask what additional ones might be needed
            step1_result = _step1_refine_functions(state, config)
            logger.info(f"Refinement Step 1 result: {step1_result}")
            if "error_message" in step1_result:
                # Fallback to traditional approach
                logger.warning("Step 1 refinement failed, using traditional approach")
                use_two_step = False
            else:
                # Step 2: Get signatures for detected + requested functions
                library_symbols_full = load_library_symbols()
                symbol_index = _create_function_index(library_symbols_full)
                
                current_functions = step1_result.get("current_functions", [])
                additional_functions = step1_result.get("additional_functions", [])
                all_requested = list(set(current_functions + additional_functions))  # Remove duplicates
                
                if all_requested:
                    trimmed_library_symbols = _find_matching_signatures(all_requested, symbol_index)
                    logger.info(f"2-step refinement: Found signatures for {len(all_requested)} functions ({len(current_functions)} current + {len(additional_functions)} additional)")
                else:
                    # Fallback to compact list if no functions detected
                    logger.warning("No functions detected in step 1, falling back to compact approach")
                    trimmed_library_symbols = _create_compact_function_list(library_symbols_full)
                
                final_size = len(trimmed_library_symbols)
                logger.info(f"2-step refinement library symbols: {final_size} chars")
        
        if not use_two_step:
            # Traditional approach with optimization (fallback)
            library_symbols_full = load_library_symbols()
            
            # Apply optimization to reduce token count
            optimization_level = get_config_value(config, 'symbols_optimization_level') or "aggressive"
            optimized_symbols = _optimize_library_symbols(library_symbols_full, optimization_level)
            
            # Apply filtering based on variable context
            variable_context = _create_comprehensive_variable_context(state.conversation_id)
            trimmed_library_symbols = _filter_library_symbols(optimized_symbols, variable_context)
            
            symbols_count = len(trimmed_library_symbols.splitlines()) if trimmed_library_symbols else 0
            final_size = len(trimmed_library_symbols)
            
            logger.info(f"Traditional refinement: Loaded {symbols_count} relevant library function signatures ({final_size} chars)")
        
        # Get comprehensive variable context for refinement (with fallback)
        variable_context = _create_comprehensive_variable_context(state.conversation_id)
        if "No variables available" in variable_context:
            # Fallback to variable summary from previous execution results
            variable_context = _variable_context_from_results(execution_results)
        logger.info(f"Generated variable context length for refinement: {len(variable_context)} characters")
        
        # Create refinement prompt - simplified to return just code
        refinement_prompt = f"""
The following Python code was generated but has issues that need to be addressed:

{variable_context}

CODE:
```python
{generated_code}
```

ISSUES DETECTED:
{issues_text}

Please provide an improved version of the code that:
1. **FIRST AND MOST IMPORTANT**: Carefully analyze any execution errors and fix them precisely
2. Uses only valid PyLiPD/Pyleoclim/Ammonyte functions from the approved signatures
3. Maintains the original functionality
4. Uses appropriate libraries (PyLiPD, Pyleoclim, Ammonyte, pandas, numpy)
5. Uses existing variables from the current variable state when applicable
6. References variables by their exact names as shown in the variable state

Return ONLY the corrected Python code. Do not include any explanations, markdown, or formatting - just the executable Python code.
"""
        
        # Build system message with library constraints (same as generate_code_node)
        system_content = ("You are an expert Python developer specializing in paleoclimate data analysis and debugging. "
                         "Your primary task is to fix execution errors by carefully analyzing error messages and correcting the code. "
                         "You must only use valid PyLiPD/Pyleoclim/Ammonyte functions that exist in the approved signatures. "
                         "CRITICAL REQUIREMENT: Return ONLY executable Python code. Do not include any explanations, descriptions, or markdown formatting. "
                         "Pay special attention to parameter types - booleans should be True/False, not strings like 'True'/'False'.")
        
        if trimmed_library_symbols:
            system_content += (f"""
                               
                **CRITICAL CONSTRAINT - READ CAREFULLY**
                ### Approved pylipd / pyleoclim / ammonyte signatures
                The file `backend/all_symbols.txt` is already loaded into context.  
                Format:
                • Classes begin with `class` followed by the fully-qualified name and constructor signature
                • Methods are indented with 2 spaces under their class and show full signatures  
                • Standalone functions begin with `function` followed by their full signature
                • All signatures use full Python typing (Optional[str], Union[list, float], etc.)
                • Return types are shown after `->` (if no return type shown, returns None)
                
                Examples:
                ```
                class pyleoclim.core.series.Series(self, time: list, value: numpy.ndarray, ...)
                  plot(self, xlabel: str, ylabel: str) -> matplotlib.figure
                  spectral_analysis(self, method: str) -> pyleoclim.core.psds.PSD
                
                function pyleoclim.utils.plotting.plot_xy(x: list, y: list) -> matplotlib.figure
                ```
                
                Generate code **only** with symbols that appear in this list, 
                respecting parameter order and type hints exactly.
                               
                {trimmed_library_symbols}
                If you need functionality that is not in the approved signatures, use alternative approaches
                with pandas, numpy, matplotlib, or other standard libraries instead. 

                DO NOT make up PyLiPD/Pyleoclim/Ammonyte function names.
                """
            )
        
        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=refinement_prompt)
        ]

        logger.info(refinement_prompt)
        
        raw_response = llm._call(messages)
        
        # Clean up the response - remove any code block markers if present
        refined_code = raw_response.strip()
        
        # Remove markdown code block markers if present
        if refined_code.startswith("```python"):
            refined_code = refined_code[9:]  # Remove ```python
        if refined_code.startswith("```"):
            refined_code = refined_code[3:]   # Remove ```
        if refined_code.endswith("```"):
            refined_code = refined_code[:-3]  # Remove trailing ```
        
        refined_code = refined_code.strip()
        
        # Check if the refined code is actually different from the original
        if refined_code.strip() == generated_code.strip():
            logger.warning("Refined code is identical to original code - LLM may not have understood the error")
        else:
            logger.info(f"Code successfully refined - {len(refined_code)} chars vs {len(generated_code)} chars original")
        
        return {
            "generated_code": refined_code,
            "refinement_count": refinement_count + 1,
            "error_message": "",  # Clear previous error
            "conversation_id": state.conversation_id  # Preserve conversation_id
        }
        
    except Exception as e:
        logger.error(f"Error refining code: {e}")
        return {
            "error_message": str(e),
            "conversation_id": state.conversation_id  # Preserve conversation_id even in error case
        }

def _create_comprehensive_variable_context(conversation_id: str) -> str:
    """Create a comprehensive context of available variables in the conversation."""
    try:
        # Import the async execution service
        # Get execution service from service manager
        execution_service = service_manager.get_execution_service()
        state = execution_service.get_conversation_state(conversation_id)
        
        if not state:
            return "No variables available in the current conversation context."
        
        context_parts = []
        context_parts.append("=== CURRENT CONVERSATION VARIABLES ===")
        
        # Group variables by type for better organization
        data_vars = {}
        function_vars = {}
        module_vars = {}
        other_vars = {}
        
        for name, value in state.items():
            # Check if this is a metadata dictionary from isolated execution service
            if isinstance(value, dict) and 'type' in value and 'module' in value:
                # Handle isolated execution service format
                var_info = _format_variable_metadata(value)
                var_type = value.get('type', 'unknown')
            else:
                # Handle direct object format (local execution service)
                # Skip common modules that are always imported
                if hasattr(value, '__module__') and value.__module__ in ['builtins', 'numpy', 'pandas', 'matplotlib.pyplot', 'matplotlib']:
                    continue
                var_info = _get_smart_value_preview(value)
                var_type = type(value).__name__
            
            # Categorize variables
            if any(keyword in var_info.lower() for keyword in ['function', 'method']):
                function_vars[name] = (var_type, var_info)
            elif any(keyword in var_info.lower() for keyword in ['module']):
                module_vars[name] = (var_type, var_info)
            elif any(data_type in var_type for data_type in ['DataFrame', 'Series', 'ndarray', 'LiPD', 'EnsembleSeries']):
                data_vars[name] = (var_type, var_info)
            else:
                other_vars[name] = (var_type, var_info)
        
        # Add data variables first (most important)
        context_parts.append("\nVARIABLES:")        
        if data_vars:
            for name, (var_type, info) in data_vars.items():
                context_parts.append(f"  • {name} ({var_type}): {info}")
        
        # Add other variables
        if other_vars:
            for name, (var_type, info) in other_vars.items():
                context_parts.append(f"  • {name} ({var_type}): {info}")
        
        # Add functions (less important for most analyses)
        if function_vars:
            context_parts.append("\n⚙️ FUNCTIONS:")
            for name, (var_type, info) in function_vars.items():
                context_parts.append(f"  • {name} ({var_type}): {info}")
        
        # Add modules (least important, usually just imported libraries)
        if module_vars:
            context_parts.append("\n📚 MODULES:")
            for name, (var_type, info) in module_vars.items():
                context_parts.append(f"  • {name} ({var_type}): {info}")
        
        if not any([data_vars, other_vars, function_vars, module_vars]):
            context_parts.append("No user-defined variables found.")
        
        context_parts.append("\n" + "="*50)
        
        return "\n".join(context_parts)
        
    except Exception as e:
        logger.error(f"Error creating variable context: {e}")
        return f"Error accessing conversation variables: {str(e)}"

# -----------------------------------------------------------------------------
# Fallback: build variable context from execution_results
# -----------------------------------------------------------------------------

def _variable_context_from_results(execution_results: List[Dict[str, Any]]) -> str:
    """Create a variable context string from the latest execution_success result.

    This is used when the execution environment does not keep the variable state
    alive between `execute_code_node` and `refine_code_node` (e.g., isolated
    execution service).
    """
    if not execution_results:
        return "No variables available in the current conversation context."

    latest_success = None
    for res in reversed(execution_results):
        if isinstance(res, dict) and res.get("type") == "execution_success":
            latest_success = res
            break

    if not latest_success:
        return "No variables available in the current conversation context."

    var_summary: dict = latest_success.get("variable_summary", {}) or {}
    if not var_summary:
        return "No variables available in the current conversation context."

    parts = ["=== CURRENT CONVERSATION VARIABLES (from previous execution) ===", "", "VARIABLES:"]

    for name, meta in var_summary.items():
        if isinstance(meta, dict):
            type_name = meta.get("type", "unknown")
            desc = meta.get("description", "") or meta.get("value", "")
        else:
            type_name = type(meta).__name__
            desc = str(meta)

        if len(str(desc)) > 80:
            desc = str(desc)[:77] + "..."
        parts.append(f"  • {name} ({type_name}): `{desc}`")

    parts.append("\n" + "="*50)
    return "\n".join(parts)

def _format_variable_metadata(metadata: Dict[str, Any]) -> str:
    """Format variable metadata from isolated execution service into readable string."""
    try:
        var_type = metadata.get('type', 'unknown')
        description = metadata.get('description', '')
        value = metadata.get('value', '')
        
        # Handle different types
        if var_type in ['ndarray']:
            shape = metadata.get('shape', [])
            dtype = metadata.get('dtype', 'unknown')
            size = metadata.get('size', 0)
            return f"`NumPy array shape {tuple(shape)}, dtype={dtype}, {size} elements`"
        
        elif var_type in ['DataFrame']:
            shape = metadata.get('shape', [])
            columns = metadata.get('columns', [])
            if columns:
                col_preview = columns[:3] + (['...'] if len(columns) > 3 else [])
                return f"`DataFrame {tuple(shape)}, columns: {col_preview}`"
            else:
                return f"`DataFrame {tuple(shape)}`"
        
        elif var_type in ['Series']:
            length = metadata.get('length', 0)
            name = metadata.get('name', 'unnamed')
            return f"`Series length {length}, name: {name}`"
        
        elif var_type in ['LiPD', 'EnsembleSeries', 'Series'] and 'pyleoclim' in metadata.get('module', ''):
            # PyLeoClim objects
            data_points = metadata.get('data_points', 0)
            label = metadata.get('label', '')
            archive_type = metadata.get('archive_type', '')
            
            parts = [f"PyLeoClim {var_type}"]
            if label:
                parts.append(f"'{label}'")
            if data_points:
                parts.append(f"({data_points} data points)")
            if archive_type:
                parts.append(f"[{archive_type}]")
            
            return f"`{' '.join(parts)}`"
        
        elif var_type in ['float64', 'int64', 'float32', 'int32', 'float', 'int']:
            # Numeric values
            return f"`{value}`"
        
        elif var_type == 'str':
            # String values
            if len(str(value)) <= 50:
                return f"`'{value}'`"
            else:
                return f"`'{str(value)[:47]}...'` (length: {len(str(value))})"
        
        elif var_type == 'bool':
            return f"`{value}`"
        
        elif var_type in ['list', 'tuple']:
            length = metadata.get('length', 0)
            if length == 0:
                return f"`Empty {var_type}`"
            else:
                return f"`{var_type} with {length} elements`"
        
        elif var_type == 'dict':
            size = metadata.get('size', 0)
            keys = metadata.get('keys', [])
            if keys:
                key_preview = keys[:3] + (['...'] if len(keys) > 3 else [])
                return f"`Dict with {size} keys: {key_preview}`"
            else:
                return f"`Dict with {size} keys`"
        
        else:
            # Generic fallback
            if description:
                return f"`{description}`"
            elif value:
                return f"`{value}`"
            else:
                return f"`{var_type} object`"
                
    except Exception as e:
        logger.debug(f"Error formatting variable metadata: {e}")
        return f"`{metadata.get('type', 'unknown')} object`"

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
        
        # Get context for conversation history
        context = state.context or {}
        logger.info(f"Context keys: {list(context.keys())}")
        
        # Add conversation history to contextual data if available
        if context.get("conversation_history"):
            contextual_data["conversation_history"] = context["conversation_history"]
            logger.info(f"Added conversation history with {len(context['conversation_history'])} messages")
        
        # Build examples section for prompt
        examples_section = ""
        for idx, ex in enumerate(examples, 1):
            examples_section += (
                f"\n## Example {idx}: {ex.get('name', 'Unknown')}\n"
                f"Relevance: {ex.get('relevance_score', 0):.3f}\n"
                "```python\n" + ex.get("code", "") + "\n```\n"
            )
        
        # Include clarification context if available
        clarification_text = format_clarification_response_for_llm(state)
        
        # Choose between 2-step LLM approach or traditional approach
        use_two_step = get_config_value(config, 'use_two_step_llm') or True
        
        if use_two_step:
            # Step 1: Ask LLM what functions it plans to use
            step1_result = _step1_plan_functions(state, config)
            logger.info(f"Step 1 result: {step1_result}")
            if "error_message" in step1_result:
                return step1_result
            
            # Step 2: Get only the signatures it requested
            library_symbols_full = load_library_symbols()
            symbol_index = _create_function_index(library_symbols_full)
            requested_symbols = step1_result.get("requested_symbols", [])
            
            if requested_symbols:
                trimmed_library_symbols = _find_matching_signatures(requested_symbols, symbol_index)
                logger.info(f"2-step approach: LLM requested {len(requested_symbols)} symbols, found signatures for them")
            else:
                # Fallback to compact list if no symbols extracted
                logger.warning("No symbols extracted from step 1, falling back to compact approach")
                trimmed_library_symbols = _create_compact_function_list(library_symbols_full)
            
            final_size = len(trimmed_library_symbols)
            logger.info(f"2-step library symbols: {final_size} chars (vs {len(library_symbols_full)} original)")
        else:
            # Traditional approach with optimization
            library_symbols_full = load_library_symbols()
            
            # Apply optimization to reduce token count
            optimization_level = get_config_value(config, 'symbols_optimization_level') or "aggressive"
            optimized_symbols = _optimize_library_symbols(library_symbols_full, optimization_level)
            
            # Apply filtering based on variable context
            variable_context = _create_comprehensive_variable_context(state.conversation_id)
            trimmed_library_symbols = _filter_library_symbols(optimized_symbols, variable_context)
            
            symbols_count = len(trimmed_library_symbols.splitlines()) if trimmed_library_symbols else 0
            original_size = len(library_symbols_full)
            optimized_size = len(optimized_symbols)
            final_size = len(trimmed_library_symbols)
            
            logger.info(f"Traditional library symbols optimization: {original_size} -> {optimized_size} -> {final_size} chars ({optimization_level})")
            logger.info(f"Loaded {symbols_count} relevant library function signatures for code generation")
        
        # Get comprehensive variable context with IDs, types, and smart previews
        variable_context = _create_comprehensive_variable_context(state.conversation_id)
        logger.info(f"Generated variable context length: {len(variable_context)} characters")
        
        # Format comprehensive context (includes conversation history if available)
        context_prompt = search_service.format_code_context_for_llm(contextual_data)
        # logger.info(f"Context prompt: {context_prompt}")
        
        user_prompt = (
            f"ANALYSIS REQUEST: {analysis_request}{clarification_text}\n\n"
            # f"DATA CONTEXT: {data_context}\n"
            # f"ANALYSIS TYPE: {analysis_type}\n"
            # f"OUTPUT FORMAT: {output_format}\n\n"
            f"CONTEXT:\n{context_prompt}\n\n"
            f"RELEVANT EXAMPLES:\n{examples_section}\n\n"
            f"{variable_context}\n\n"
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
        
        if trimmed_library_symbols:
            system_content += (f"""
                **CRITICAL CONSTRAINT - READ CAREFULLY**
                ### Approved pylipd / pyleoclim / ammonyte signatures
                The file `backend/all_symbols.txt` is already loaded into context.  
                Format:
                • Classes begin with `class` followed by the fully-qualified name and constructor signature
                • Methods are indented with 2 spaces under their class and show full signatures  
                • Standalone functions begin with `function` followed by their full signature
                • All signatures use full Python typing (Optional[str], Union[list, float], etc.)
                • Return types are shown after `->` (if no return type shown, returns None)
                
                Examples:
                ```
                class pyleoclim.core.series.Series(self, time: list, value: numpy.ndarray, ...)
                  plot(self, xlabel: str, ylabel: str) -> matplotlib.figure
                  spectral_analysis(self, method: str) -> pyleoclim.core.psds.PSD
                
                function pyleoclim.utils.plotting.plot_xy(x: list, y: list) -> matplotlib.figure
                ```
                
                Generate code **only** with symbols that appear in this list, 
                respecting parameter order and type hints exactly.\n
                {trimmed_library_symbols}\n"""
                "**COMMON PATTERNS FOR DATA ACCESS**:\n"
                "- pyleo.utils.load_dataset(name) ✅ (loads built-in Pyleoclim datasets)\n"
                "- lipd_obj.get(dsnames) ✅ (gets dataset(s) from graph)\n"
                "- lipd_obj.get_datasets() ✅ (returns list of Dataset objects)\n"
                "- lipd_obj.get_lipd(dsname) ✅ (gets LiPD json for dataset)\n\n"
                "If you need functionality that is not in the approved signatures, use alternative approaches "
                "with pandas, numpy, matplotlib, or other standard libraries instead. DO NOT make up PyLiPD/Pyleoclim/Ammonyte function names."
            )
        
        logger.info(f"System prompt: {system_content}")
        # logger.info(f"User prompt: {user_prompt}")
        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=user_prompt)
        ]

        logger.info(f"LLM system message length: {len(system_content)}")
        logger.info(f"LLM user message length: {len(user_prompt)}")
        
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
        
        if not generated_code:
            return {
                "error_message": "No code was generated",
                "conversation_id": state.conversation_id  # Preserve conversation_id
            }
        
        # Add final message if not already present
        messages = state.messages or []
        
        # Handle different completion scenarios
        if refinement_count >= MAX_REFINEMENTS and has_error:
            message_content = "Code generation completed after maximum refinement attempts."
            final_status = "refinement_exhausted"
        elif generated_code and not has_error:
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
                "execution_results": [{"type": "execution_error", "error": "No conversation ID for execution state"}],
                "conversation_id": conversation_id
            }
        
        # Check if we're in async mode (when called from async wrapper)
        async_mode = getattr(state, '_async_mode', False)
        
        if async_mode:
            # In async mode, return the prepared code for the async wrapper to execute
            logger.info("Running in async mode - returning prepared code for async execution")
            
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
            
            return {
                "prepared_code": final_code,
                "conversation_id": conversation_id,
                "async_execution": True
            }
        
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
        
        # Execute the main generated code using execution service
        execution_service = service_manager.get_execution_service()
        
        # Create execution request and run it synchronously
        import asyncio
        import uuid
        
        execution_id = str(uuid.uuid4())
        
        # Check if we're already in an async context
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, need to run in thread pool
            import concurrent.futures
            import functools
            
            async def run_execution():
                return await execution_service.execute_code(
                    code=final_code,
                    conversation_id=conversation_id,
                    execution_id=execution_id
                )
            
            # Create a new thread to run the async execution
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(run_execution())
                )
                execution_result = future.result(timeout=300)  # 5 minute timeout
                
        except RuntimeError:
            # No running loop, we can run directly
            execution_result = asyncio.run(execution_service.execute_code(
                code=final_code,
                conversation_id=conversation_id,
                execution_id=execution_id
            ))
        
        logger.info(f"Execution completed. Success: {execution_result.success}")
        
        # Prepare execution results for state
        execution_results = []
        
        if execution_result.success:
            # Get variable summary for display (this is JSON-serializable)
            var_summary = execution_service.get_variable_summary(conversation_id)
            
            # Add successful execution result
            result_entry = {
                "type": "execution_success",
                "output": execution_result.output,
                "execution_time": execution_result.execution_time,
                "variable_summary": var_summary,
                "plots": execution_result.plots or []
            }
            
            # Include execution ID if available
            if execution_result.execution_id:
                result_entry["execution_id"] = execution_result.execution_id
            
            # Note: Don't include raw variables as they contain non-serializable objects
            
            execution_results.append(result_entry)
            
            logger.info(f"Execution successful. Output length: {len(execution_result.output)}")
            logger.info(f"Variables created: {list(execution_result.variables.keys())}")
            
        else:
            # Add error result
            error_entry = {
                "type": "execution_error",
                "error": execution_result.error,
                "output": execution_result.output,
                "execution_time": execution_result.execution_time,
                "plots": execution_result.plots or []
            }
            
            # Include execution ID if available
            if execution_result.execution_id:
                error_entry["execution_id"] = execution_result.execution_id
                
            execution_results.append(error_entry)
            
            logger.warning(f"Execution failed: {execution_result.error}")
        
        # Also extract execution details for frontend display
        result = {
            "execution_results": execution_results,
            "conversation_id": conversation_id,
            "generated_code": generated_code  # CRITICAL: Pass through the generated code
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
            "execution_results": [{"type": "execution_error", "error": f"Execution node error: {str(e)}"}],
            "execution_successful": False,
            "execution_error": f"Execution node error: {str(e)}",
            "execution_time": 0.0,
            "conversation_id": state.conversation_id
        } 

def _optimize_library_symbols(all_symbols: str, optimization_level: str = "aggressive") -> str:
    """
    Optimize the library symbols encoding to reduce token count while preserving information.
    
    Args:
        all_symbols: The full text of backend/all_symbols.txt
        optimization_level: "conservative", "moderate", or "aggressive"
    
    Returns:
        Optimized symbols text with dramatically reduced size
    """
    if not all_symbols:
        return ""
    
    if optimization_level == "conservative":
        return _optimize_conservative(all_symbols)
    elif optimization_level == "moderate": 
        return _optimize_moderate(all_symbols)
    elif optimization_level == "aggressive":
        return _optimize_aggressive(all_symbols)
    else:
        return all_symbols

def _optimize_conservative(all_symbols: str) -> str:
    """Conservative optimization: abbreviate common patterns but keep structure."""
    lines = all_symbols.split('\n')
    optimized = []
    
    # Create abbreviation mappings
    abbrevs = {
        'pyleoclim.utils.': 'py.',
        'pyleoclim.core.': 'pyc.',
        'pylipd.': 'lipd.',
        'Optional[': 'O[',
        'Union[': 'U[',
        'numpy.ndarray': 'ndarray',
        'matplotlib.': 'mpl.',
        'pandas.': 'pd.',
        'Dict[str, Any]': 'DictSA',
        'List[': 'L[',
        'Literal[': 'Lit[',
        ', kwargs: Any': '',  # Remove common kwargs
        ', args: Any': '',    # Remove common args
    }
    
    for line in lines:
        if line.strip().startswith('#'):
            continue  # Skip comments
            
        optimized_line = line
        for old, new in abbrevs.items():
            optimized_line = optimized_line.replace(old, new)
        optimized.append(optimized_line)
    
    return '\n'.join(optimized)

def _optimize_moderate(all_symbols: str) -> str:
    """Moderate optimization: use compact format with symbol tables."""
    lines = all_symbols.split('\n')
    
    # Create symbol tables for common patterns
    modules = {}
    types = {}
    mod_counter = 1
    type_counter = 1
    
    # First pass: identify common modules and types
    for line in lines:
        if line.strip().startswith('#'):
            continue
            
        # Extract module paths
        if line.startswith(('class ', 'function ')):
            parts = line.split('(')[0].split()
            if len(parts) >= 2:
                full_name = parts[1]
                if '.' in full_name:
                    module_path = '.'.join(full_name.split('.')[:-1])
                    if module_path not in modules:
                        modules[module_path] = f"M{mod_counter}"
                        mod_counter += 1
        
        # Extract common types
        common_types = [
            'Optional[Any]', 'Union[str, list]', 'Union[float, list]', 
            'numpy.ndarray', 'matplotlib.axes.Axes', 'Dict[str, Any]',
            'Optional[str]', 'Optional[float]', 'Optional[int]',
            'List[str]', 'List[float]', 'List[int]'
        ]
        for ctype in common_types:
            if ctype in line and ctype not in types:
                types[ctype] = f"T{type_counter}"
                type_counter += 1
    
    # Build header with symbol tables
    result = ["# Symbol Tables:"]
    for module, abbrev in sorted(modules.items()):
        result.append(f"# {abbrev}={module}")
    for dtype, abbrev in sorted(types.items()):
        result.append(f"# {abbrev}={dtype}")
    result.append("")
    
    # Second pass: apply optimizations
    for line in lines:
        if line.strip().startswith('#'):
            continue
            
        optimized_line = line
        
        # Replace modules
        for module, abbrev in modules.items():
            optimized_line = optimized_line.replace(module + '.', abbrev + '.')
        
        # Replace types
        for dtype, abbrev in types.items():
            optimized_line = optimized_line.replace(dtype, abbrev)
        
        # Additional cleanup
        optimized_line = optimized_line.replace('self, ', 'self,')
        optimized_line = optimized_line.replace(', kwargs: A', '')
        optimized_line = optimized_line.replace(', args: A', '')
        
        result.append(optimized_line)
    
    return '\n'.join(result)

def _optimize_aggressive(all_symbols: str) -> str:
    """Aggressive optimization: ultra-compact format."""
    lines = all_symbols.split('\n')
    result = []
    
    # Ultra-compact legend
    result.extend([
        "# COMPACT API LEGEND:",
        "# c:ClassName(params)->ret | f:funcName(params)->ret | m:methodName(params)->ret",
        "# Types: S=str, I=int, F=float, B=bool, L=list, D=dict, A=Any, O=Optional[A], U=Union",
        "# Modules: py=pyleoclim, lipd=pylipd, np=numpy, pd=pandas, mpl=matplotlib",
        ""
    ])
    
    current_class = None
    
    for line in lines:
        if line.strip().startswith('#'):
            continue
            
        if line.startswith('class '):
            # Extract class info
            parts = line.split('(', 1)
            class_name = parts[0].replace('class ', '')
            
            # Compress class name
            compressed_name = class_name
            compressed_name = compressed_name.replace('pyleoclim.', 'py.')
            compressed_name = compressed_name.replace('pylipd.', 'lipd.')
            
            # Compress parameters
            if len(parts) > 1:
                params = parts[1].rstrip(')')
                params = _compress_params(params)
                result.append(f"c:{compressed_name}({params})")
            else:
                result.append(f"c:{compressed_name}")
            
            current_class = compressed_name
            
        elif line.startswith('function '):
            # Extract function info
            parts = line.split('(', 1)
            func_name = parts[0].replace('function ', '')
            
            # Compress function name
            compressed_name = func_name
            compressed_name = compressed_name.replace('pyleoclim.', 'py.')
            compressed_name = compressed_name.replace('pylipd.', 'lipd.')
            
            # Compress parameters and return type
            if len(parts) > 1:
                rest = parts[1]
                if ' -> ' in rest:
                    params_part, ret_part = rest.split(' -> ', 1)
                    params = _compress_params(params_part.rstrip(')'))
                    ret_type = _compress_type(ret_part)
                    result.append(f"f:{compressed_name}({params})->{ret_type}")
                else:
                    params = _compress_params(rest.rstrip(')'))
                    result.append(f"f:{compressed_name}({params})")
            else:
                result.append(f"f:{compressed_name}")
                
        elif line.startswith('  ') and current_class:
            # Method of current class
            method_line = line.strip()
            if '(' in method_line:
                parts = method_line.split('(', 1)
                method_name = parts[0]
                
                rest = parts[1]
                if ' -> ' in rest:
                    params_part, ret_part = rest.split(' -> ', 1)
                    params = _compress_params(params_part.rstrip(')'))
                    ret_type = _compress_type(ret_part)
                    result.append(f"  m:{method_name}({params})->{ret_type}")
                else:
                    params = _compress_params(rest.rstrip(')'))
                    result.append(f"  m:{method_name}({params})")
            else:
                result.append(f"  m:{method_line}")
        else:
            # Reset class context for non-indented lines
            if not line.startswith('  '):
                current_class = None
    
    return '\n'.join(result)

def _compress_params(params_str: str) -> str:
    """Compress parameter list using type abbreviations."""
    if not params_str.strip():
        return ""
    
    # Type mappings for aggressive compression
    type_map = {
        'str': 'S',
        'int': 'I', 
        'float': 'F',
        'bool': 'B',
        'list': 'L',
        'dict': 'D',
        'Any': 'A',
        'numpy.ndarray': 'nda',
        'matplotlib.axes.Axes': 'ax',
        'pandas.DataFrame': 'df',
        'Optional[Any]': 'OA',
        'Optional[str]': 'OS',
        'Optional[int]': 'OI',
        'Optional[float]': 'OF',
        'Union[str, list]': 'U[S,L]',
        'Union[float, list]': 'U[F,L]',
        'Dict[str, Any]': 'D[S,A]',
        'List[str]': 'L[S]',
        'List[float]': 'L[F]',
        'Literal[': 'Lit[',
    }
    
    compressed = params_str
    
    # Apply type mappings
    for full_type, abbrev in type_map.items():
        compressed = compressed.replace(full_type, abbrev)
    
    # Clean up common patterns
    compressed = compressed.replace('self, ', '')
    compressed = compressed.replace('self,', '')
    compressed = compressed.replace(', kwargs: A', '')
    compressed = compressed.replace(', args: A', '')
    compressed = compressed.replace('  ', ' ')
    
    # Remove parameter names, keep only types for ultra-compression
    # This is aggressive - only keep the essential type information
    param_parts = []
    for param in compressed.split(','):
        param = param.strip()
        if ':' in param:
            param_type = param.split(':', 1)[1].strip()
            param_parts.append(param_type)
        elif param:  # Keep params without type annotations
            param_parts.append(param)
    
    return ','.join(param_parts)

def _compress_type(type_str: str) -> str:
    """Compress return type using abbreviations."""
    type_map = {
        'str': 'S',
        'int': 'I',
        'float': 'F', 
        'bool': 'B',
        'list': 'L',
        'dict': 'D',
        'Any': 'A',
        'numpy.ndarray': 'nda',
        'matplotlib.axes.Axes': 'ax',
        'pandas.DataFrame': 'df',
        'Optional[Any]': 'OA',
        'Union[str, list]': 'U[S,L]',
        'Dict[str, Any]': 'D[S,A]',
        'List[str]': 'L[S]',
        'tuple': 'tup',
        'collections.namedtuple': 'nt',
    }
    
    compressed = type_str.strip()
    for full_type, abbrev in type_map.items():
        compressed = compressed.replace(full_type, abbrev)
    
    return compressed 

def _create_function_index(all_symbols: str) -> Dict[str, str]:
    """
    Create an index mapping function/class names to their full signatures.
    
    Returns:
        Dict mapping simple names and full names to their signatures
    """
    index = {}
    lines = all_symbols.split('\n')
    current_class = None
    current_class_lines = []
    
    for line in lines:
        if line.strip().startswith('#') or not line.strip():
            continue
            
        if line.startswith('class '):
            # Save previous class if exists
            if current_class and current_class_lines:
                full_signature = '\n'.join(current_class_lines)
                index[current_class] = full_signature
                # Also index by simple class name
                simple_name = current_class.split('.')[-1]
                if simple_name not in index:
                    index[simple_name] = full_signature
            
            # Start new class
            current_class = line.split('(')[0].replace('class ', '')
            current_class_lines = [line]
            
        elif line.startswith('function '):
            # Standalone function
            func_name = line.split('(')[0].replace('function ', '')
            index[func_name] = line
            # Also index by simple function name
            simple_name = func_name.split('.')[-1]
            if simple_name not in index:
                index[simple_name] = line
                
        elif line.startswith('  ') and current_class:
            # Method of current class
            current_class_lines.append(line)
            
            # Also index the method by its full qualified name
            method_name = line.strip().split('(')[0]
            full_method_name = f"{current_class}.{method_name}"
            
            # For methods, we want the entire class definition including this method
            class_with_method = '\n'.join(current_class_lines)
            index[full_method_name] = class_with_method
            
            # Also index by ClassName.method format
            simple_class_name = current_class.split('.')[-1]
            simple_method_key = f"{simple_class_name}.{method_name}"
            if simple_method_key not in index:
                index[simple_method_key] = class_with_method
    
    # Don't forget the last class
    if current_class and current_class_lines:
        full_signature = '\n'.join(current_class_lines)
        index[current_class] = full_signature
        simple_name = current_class.split('.')[-1]
        if simple_name not in index:
            index[simple_name] = full_signature
    
    return index

def _create_compact_function_list(all_symbols: str) -> str:
    """
    Create a compact list of all available functions and classes without signatures.
    This is used in step 1 to let the LLM choose what it needs.
    """
    lines = all_symbols.split('\n')
    functions = []
    classes = []
    
    current_class = None
    class_methods = []
    
    for line in lines:
        if line.strip().startswith('#'):
            continue
            
        if line.startswith('class '):
            # Save previous class if exists
            if current_class and class_methods:
                class_entry = {
                    'name': current_class,
                    'methods': class_methods
                }
                classes.append(class_entry)
            
            # Start new class
            current_class = line.split('(')[0].replace('class ', '')
            class_methods = []
            
        elif line.startswith('function '):
            # Standalone function
            func_name = line.split('(')[0].replace('function ', '')
            functions.append(func_name)
                
        elif line.startswith('  ') and current_class:
            # Method of current class
            method_name = line.strip().split('(')[0]
            class_methods.append(method_name)
    
    # Don't forget the last class
    if current_class and class_methods:
        class_entry = {
            'name': current_class,
            'methods': class_methods
        }
        classes.append(class_entry)
    
    # Format as compact list
    result = ["# AVAILABLE PYLEOCLIM/PYLIPD/AMMONYTE API", ""]
    
    if classes:
        result.append("## CLASSES:")
        for cls in classes:
            result.append(f"• {cls['name']}")
            if cls['methods']:
                # Show first few methods as examples
                method_preview = cls['methods'][:3]
                if len(cls['methods']) > 3:
                    method_preview.append(f"... +{len(cls['methods'])-3} more")
                result.append(f"  Methods: {', '.join(method_preview)}")
        result.append("")
    
    if functions:
        result.append("## FUNCTIONS:")
        # Group functions by module for better organization
        func_by_module = {}
        for func in functions:
            if '.' in func:
                module = '.'.join(func.split('.')[:-1])
                if module not in func_by_module:
                    func_by_module[module] = []
                func_by_module[module].append(func.split('.')[-1])
            else:
                if 'other' not in func_by_module:
                    func_by_module['other'] = []
                func_by_module['other'].append(func)
        
        for module, funcs in sorted(func_by_module.items()):
            result.append(f"### {module}:")
            # Show functions in groups of 5 per line
            for i in range(0, len(funcs), 5):
                func_group = funcs[i:i+5]
                result.append(f"  {', '.join(func_group)}")
        result.append("")
    
    result.append("NOTE: This is just a list of available functions/classes.")
    result.append("Request specific ones you need and their full signatures will be provided.")
    
    return '\n'.join(result)

def _extract_functions_from_code(code: str) -> List[str]:
    """
    Extract PyLiPD/PyLeoClim/Ammonyte function calls from existing code.
    Returns a list of function names that are already being used.
    """
    functions_found = []
    
    # Pattern 1: Direct module calls like pyleoclim.utils.datasets.load_dataset()
    direct_pattern = r'((?:pyleoclim|pylipd|ammonyte)\.[\w\.]+)\s*\('
    direct_matches = re.findall(direct_pattern, code)
    functions_found.extend(direct_matches)
    
    # Pattern 2: Object method calls where we can infer the type
    # Look for variable assignments that use PyLiPD/PyLeoClim constructors
    constructor_pattern = r'(\w+)\s*=\s*((?:pyleoclim|pylipd|ammonyte)\.[\w\.]+)\s*\('
    constructor_matches = re.findall(constructor_pattern, code)
    
    # Now look for method calls on those variables
    for var_name, class_name in constructor_matches:
        # Find method calls on this variable
        method_pattern = fr'{re.escape(var_name)}\.(\w+)\s*\('
        method_matches = re.findall(method_pattern, code)
        for method in method_matches:
            # Reconstruct the full method name
            full_method = f"{class_name}.{method}"
            functions_found.append(full_method)
    
    # Pattern 3: Import statements to detect what's being imported
    import_pattern = r'from\s+((?:pyleoclim|pylipd|ammonyte)\.[\w\.]+)\s+import\s+([\w\s,]+)'
    import_matches = re.findall(import_pattern, code)
    for module, imports in import_matches:
        # Split the imports and add them with their full module path
        for imported_item in imports.split(','):
            item = imported_item.strip()
            if item and item != '*':
                functions_found.append(f"{module}.{item}")
    
    # Pattern 4: Direct imports like "import pyleoclim as pyleo"
    direct_import_pattern = r'import\s+((?:pyleoclim|pylipd|ammonyte)(?:\.\w+)*)\s*(?:as\s+(\w+))?'
    direct_import_matches = re.findall(direct_import_pattern, code)
    
    # Track alias mappings
    alias_mappings = {}
    for full_module, alias in direct_import_matches:
        if alias:
            alias_mappings[alias] = full_module
    
    # Pattern 5: Calls using aliases (e.g., pyleo.utils.datasets.load_dataset)
    for alias, full_module in alias_mappings.items():
        alias_pattern = fr'{re.escape(alias)}\.([^(]*)\s*\('
        alias_matches = re.findall(alias_pattern, code)
        for match in alias_matches:
            # Reconstruct with full module name
            functions_found.append(f"{full_module}.{match}")
    
    # Clean up and deduplicate
    cleaned_functions = []
    for func in functions_found:
        func = func.strip().strip('.,()[]')
        # Only keep valid-looking function names
        if (func and 
            len(func) > 5 and  # Minimum reasonable length
            '.' in func and   # Must have module structure
            func not in cleaned_functions and
            any(lib in func.lower() for lib in ['pyleoclim', 'pylipd', 'ammonyte'])):
            cleaned_functions.append(func)
    
    return cleaned_functions

def _extract_requested_symbols(llm_response: str) -> List[str]:
    """
    Extract the list of functions/classes the LLM wants to use from its response.
    """
    requested = []
    
    # Look for direct mentions of pyleoclim/pylipd functions first (most reliable)
    func_pattern = r'((?:pyleoclim|pylipd|ammonyte)\.[\w\.]+)'
    func_matches = re.findall(func_pattern, llm_response)
    requested.extend(func_matches)
    
    # Look for bullet points and lists with function names
    lines = llm_response.split('\n')
    for line in lines:
        line = line.strip()
        
        # Skip empty lines and non-list items
        if not line or not (line.startswith(('-', '•', '*')) or re.match(r'\d+\.', line)):
            continue
        
        # Extract potential function names from the line
        # Remove list markers and explanatory text in parentheses
        cleaned_line = re.sub(r'^[-•*]\s*', '', line)  # Remove bullet points
        cleaned_line = re.sub(r'^\d+\.\s*', '', cleaned_line)  # Remove numbering
        cleaned_line = re.sub(r'\s*\([^)]*\).*$', '', cleaned_line)  # Remove explanations in parentheses
        cleaned_line = cleaned_line.strip()
        
        # Look for pyleoclim/pylipd patterns in the cleaned line
        if any(lib in cleaned_line.lower() for lib in ['pyleoclim', 'pylipd', 'ammonyte']):
            # Extract the actual function/class name
            func_match = re.search(r'((?:pyleoclim|pylipd|ammonyte)\.[\w\.]+)', cleaned_line)
            if func_match:
                requested.append(func_match.group(1))
            else:
                # If no full path found, add the cleaned line as-is
                if cleaned_line and len(cleaned_line) > 3:
                    requested.append(cleaned_line)
    
    # Look for other common patterns
    patterns = [
        r'(?:I (?:need|want|will use|plan to use))[^:]*:?\s*([^\n]+)',
        r'(?:Functions|Classes) (?:needed|required):?\s*([^\n]+)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, llm_response, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            # Look for function names in the match
            func_in_match = re.findall(r'((?:pyleoclim|pylipd|ammonyte)\.[\w\.]+)', match)
            requested.extend(func_in_match)
    
    # Clean up and deduplicate
    cleaned = []
    for item in requested:
        item = item.strip().strip('.,()[]')
        # Only keep items that look like valid function/class names
        if (item and 
            len(item) > 3 and 
            item not in cleaned and
            ('.' in item or any(lib in item.lower() for lib in ['series', 'psd', 'lipd', 'plot']))):
            cleaned.append(item)
    
    return cleaned

def _find_matching_signatures(requested_symbols: List[str], symbol_index: Dict[str, str]) -> str:
    """
    Find the full signatures for the requested symbols.
    """
    found_signatures = []
    not_found = []
    added_signatures = set()  # Track what we've already added to avoid duplicates
    
    for symbol in requested_symbols:
        found = False
        
        # Try exact match first
        if symbol in symbol_index:
            sig = symbol_index[symbol]
            if sig not in added_signatures:
                found_signatures.append(sig)
                added_signatures.add(sig)
            found = True
        else:
            # Try partial matching with priority order
            matches = []
            
            # 1. Look for exact suffix matches (e.g., "plot" matches "SomeClass.plot")
            for key in symbol_index.keys():
                if key.lower().endswith('.' + symbol.lower()):
                    matches.append((key, 1))  # Priority 1 (highest)
            
            # 2. Look for substring matches in method names
            if not matches:
                symbol_parts = symbol.split('.')
                target_method = symbol_parts[-1] if len(symbol_parts) > 1 else symbol
                
                for key in symbol_index.keys():
                    key_parts = key.split('.')
                    if len(key_parts) > 1 and target_method.lower() == key_parts[-1].lower():
                        matches.append((key, 2))  # Priority 2
            
            # 3. Look for general substring matches
            if not matches:
                for key in symbol_index.keys():
                    if symbol.lower() in key.lower():
                        matches.append((key, 3))  # Priority 3 (lowest)
            
            if matches:
                # Sort by priority and take the best match
                matches.sort(key=lambda x: x[1])
                best_match = matches[0][0]
                sig = symbol_index[best_match]
                if sig not in added_signatures:
                    found_signatures.append(sig)
                    added_signatures.add(sig)
                found = True
        
        if not found:
            not_found.append(symbol)
    
    result = []
    if found_signatures:
        result.append("# REQUESTED FUNCTION/CLASS SIGNATURES:")
        # Remove duplicates while preserving order
        unique_signatures = []
        for sig in found_signatures:
            if sig not in unique_signatures:
                unique_signatures.append(sig)
        result.extend(unique_signatures)
        result.append("")
    
    if not_found:
        result.append(f"# NOTE: Could not find signatures for: {', '.join(not_found)}")
        result.append("")
    
    return '\n'.join(result)

def _step1_plan_functions(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """
    Step 1: Ask LLM what functions/classes it plans to use.
    """
    try:
        analysis_request = state.analysis_request or ""
        variable_context = _create_comprehensive_variable_context(state.conversation_id)
        
        # Create compact function list
        library_symbols_full = load_library_symbols()
        compact_list = _create_compact_function_list(library_symbols_full)
        
        # Get LLM from config
        llm = get_config_value(config, 'llm')
        if not llm:
            return {"error_message": "LLM not available"}
        
        planning_prompt = f"""
You are planning to generate Python code for a paleoclimate data analysis task.

ANALYSIS REQUEST: {analysis_request}

{variable_context}

AVAILABLE API:
{compact_list}

Please analyze the request and identify the key PyLiPD, PyLeoClim, or Ammonyte functions/classes you would likely need for this task.

Include functions for:
1. The core functionality you definitely need
2. 1-2 alternative approaches if the main approach doesn't work
3. Essential supporting functions (data loading, basic processing)

Think about the main workflow steps but focus on the most relevant functions rather than listing everything possible.

Respond with a focused list of 5-15 functions/classes. For example:
- pyleoclim.core.series.Series
- pyleoclim.utils.datasets.load_dataset
- pyleoclim.utils.plotting.plot_xy
- pylipd.lipd.LiPD.get_datasets

Focus only on the PyLiPD/PyLeoClim/Ammonyte functions. Don't list standard libraries like pandas, numpy, matplotlib.
"""

        system_content = (
            "You are an expert in paleoclimate data analysis. "
            "Analyze the user's request and identify the most relevant PyLiPD, PyLeoClim, or Ammonyte "
            "functions and classes needed to complete the task effectively. "
            "Include core functions plus a few alternatives, but avoid listing everything possible. "
            "Aim for a focused selection of 5-15 functions that cover the main workflow needs."
        )
        
        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=planning_prompt)
        ]
        
        logger.info(f"Step 1: Planning functions for request: {analysis_request[:100]}...")
        response = llm._call(messages)
        
        # Extract requested symbols
        requested_symbols = _extract_requested_symbols(response)
        logger.info(f"Step 1: LLM requested {len(requested_symbols)} symbols: {requested_symbols}")
        
        return {
            "requested_symbols": requested_symbols,
            "planning_response": response,
            "conversation_id": state.conversation_id
        }
        
    except Exception as e:
        logger.error(f"Error in step 1 planning: {e}", exc_info=True)
        return {
            "error_message": str(e),
            "conversation_id": state.conversation_id
        }

def _step1_refine_functions(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """
    Step 1 for refinement: Detect functions already in use + ask what additional ones might be needed.
    """
    try:
        generated_code = state.generated_code or ""
        execution_results = state.execution_results or []
        
        # Extract functions already being used in the current code
        current_functions = _extract_functions_from_code(generated_code)
        logger.info(f"Detected {len(current_functions)} functions already in use: {current_functions}")
        
        # Build issues description for LLM
        issues_detected = []
        
        # Check for execution errors
        for result in execution_results:
            if isinstance(result, dict) and result.get("type") == "execution_error":
                error_msg = result.get('error', 'Unknown execution error')
                issues_detected.append(f"**Execution Error**: {error_msg}")
        
        issues_text = "\n".join(issues_detected) if issues_detected else "General code improvements needed"
        
        # Create compact function list for alternatives
        library_symbols_full = load_library_symbols()
        compact_list = _create_compact_function_list(library_symbols_full)
        
        # Get LLM from config
        llm = get_config_value(config, 'llm')
        if not llm:
            return {"error_message": "LLM not available"}
        
        refine_planning_prompt = f"""
You are analyzing existing Python code that needs to be fixed or improved.

CURRENT CODE:
```python
{generated_code}
```

ISSUES TO FIX:
{issues_text}

AVAILABLE API:
{compact_list}

The code already uses these PyLiPD/PyLeoClim/Ammonyte functions:
{', '.join(current_functions) if current_functions else 'None detected'}

Please identify what ADDITIONAL PyLiPD, PyLeoClim, or Ammonyte functions you might need to fix the issues or improve the code.

Include additional functions for:
1. Alternative approaches to fix the errors
2. Missing functionality that could help
3. Better methods to achieve the same goals

Respond with a focused list of 3-10 additional functions/classes (beyond what's already in use):
- pyleoclim.core.series.Series.plot
- pyleoclim.utils.datasets.load_dataset
- etc.

Focus only on ADDITIONAL PyLiPD/PyLeoClim/Ammonyte functions. Don't list standard libraries.
"""

        system_content = (
            "You are an expert in debugging and improving paleoclimate data analysis code. "
            "Analyze the existing code and the issues, then identify additional PyLiPD, PyLeoClim, or Ammonyte "
            "functions that could help fix the problems or improve the implementation. "
            "Focus on functions that are different from what's already being used."
        )
        
        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=refine_planning_prompt)
        ]
        
        logger.info(f"Step 1 Refinement: Analyzing code for additional functions needed...")
        response = llm._call(messages)
        
        # Extract additional symbols
        additional_symbols = _extract_requested_symbols(response)
        logger.info(f"Step 1 Refinement: LLM suggested {len(additional_symbols)} additional symbols: {additional_symbols}")
        
        return {
            "current_functions": current_functions,
            "additional_functions": additional_symbols,
            "planning_response": response,
            "conversation_id": state.conversation_id
        }
        
    except Exception as e:
        logger.error(f"Error in step 1 refinement planning: {e}", exc_info=True)
        return {
            "error_message": str(e),
            "conversation_id": state.conversation_id
        }