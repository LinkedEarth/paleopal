"""
Node handlers for the Code Generation agent.
Enhanced with comprehensive contextual search.
"""

import logging
import json
import re
from typing import Dict, Any, List
from langchain.schema import HumanMessage, SystemMessage

from .state import CodeAgentState, CodeAgentConfig
from agents.base_state import MAX_REFINEMENTS
from agents.base_langgraph_agent import get_config_value, get_message_value
from services.search_integration_service import search_service

logger = logging.getLogger(__name__)


def extract_analysis_request_node(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """Extract and process the analysis request from user input."""
    try:
        # Get the last message from the user
        messages = state.messages or []
        if not messages:
            raise ValueError("No messages found in state")

        # Extract the text using the helper function
        user_query = ""
        last_message = messages[-1]
        
        # Check if the last message is from a user
        role = get_message_value(last_message, 'role')
        if role == 'user':
            user_query = get_message_value(last_message, 'content', '')
        else:
            # Look for the last user message in the list
            for msg in reversed(messages):
                if get_message_value(msg, 'role') == 'user':
                    user_query = get_message_value(msg, 'content', '')
                    break
        
        if not user_query:
            raise ValueError("Empty user query after all extraction attempts")
        
        # Extract context information
        context = state.context or {}
        analysis_type = context.get("analysis_type", "general")
        output_format = context.get("output_format", "notebook")
        data_context = context.get("data_context", {})
        
        logger.info(f"Extracted analysis request: '{user_query[:100]}...'")
        
        return {
            "analysis_request": user_query,
            "user_query": user_query,  # For compatibility with base state
            "analysis_type": analysis_type,
            "output_format": output_format,
            "data_context": data_context,
        }
        
    except Exception as e:
        logger.error(f"Error extracting analysis request: {e}")
        return {"error_message": f"Failed to extract analysis request: {str(e)}"}


async def search_code_examples_node(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """Enhanced search for relevant code examples using comprehensive contextual search."""
    try:
        analysis_request = getattr(state, "analysis_request", "") or state.user_input or ""
        analysis_type = getattr(state, "analysis_type", "general")
        
        if not analysis_request:
            return {"error_message": "No analysis request to search examples for"}
        
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
        }
        
    except Exception as e:
        logger.error(f"Error searching code examples: {e}")
        return {"error_message": str(e)}


def detect_clarification_needs_code(
    llm,
    user_query: str,
    examples: list,
    data_context: dict
) -> Dict[str, Any]:
    """
    Detect if the code generation request needs clarification.
    
    Args:
        llm: LLM model to use
        user_query: Raw user query
        examples: Code examples found for the query
        data_context: Context about the data being analyzed
        
    Returns:
        Dict with clarification details if needed
    """
    try:
        # Check for potential ambiguities in code generation
        ambiguities = []
        
        # Case 1: Vague analysis request
        vague_terms = ['analyze', 'plot', 'show', 'look at', 'examine', 'study']
        if any(term in user_query.lower() for term in vague_terms) and len(user_query.split()) < 5:
            ambiguities.append({
                'type': 'vague_request',
                'description': 'The analysis request is quite general and could be interpreted in multiple ways'
            })
        
        # Case 2: Missing data context
        if not data_context and 'data' in user_query.lower():
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
            if any(keyword in user_query.lower() for keyword in keywords):
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

USER REQUEST: "{user_query}"

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
      "question": "What specific type of analysis would you like to perform?",
      "context": "Your request could involve multiple analysis types",
      "choices": ["time series analysis", "correlation analysis", "spectral analysis"]
    }}
  ]
}}
```

Only include the JSON object, nothing else."""

            try:
                response = llm._call([HumanMessage(content=prompt)])
                
                # Parse JSON response
                json_match = re.search(r"```json\s*(\{.*?\})\s*```", response, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(1))
                    questions = parsed.get("questions", [])
                    
                    if questions:
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
            return {"needs_clarification": False}
        
        # Check if clarification is enabled
        enable_clarification = get_config_value(config, 'enable_clarification', True)
        if not enable_clarification:
            logger.info("Clarification is disabled, skipping detection")
            return {"needs_clarification": False}
        
        # Skip clarification if we already have clarification responses
        if state.clarification_responses:
            logger.info("Clarification responses already provided, skipping detection")
            return {"needs_clarification": False}
        
        # Get clarification threshold from config
        clarification_threshold = get_config_value(config, 'clarification_threshold', 'conservative')
        user_query = analysis_request
        
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
                if re.search(pattern, user_query.lower()):
                    logger.info(f"Permissive threshold: skipping clarification for simple code pattern: {pattern}")
                    return {"needs_clarification": False}
        
        # Detect clarification needs using existing function
        clarification_result = detect_clarification_needs_code(
            llm=llm,
            user_query=analysis_request,
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
                "clarification_ambiguities": clarification_result.get("ambiguities", [])
            }
        else:
            logger.info(f"No clarification needed (threshold: {clarification_threshold})")
            return {"needs_clarification": False}
        
    except Exception as e:
        logger.error(f"Error in clarification detection: {e}")
        return {"needs_clarification": False}


def process_clarification_response(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """Process clarification responses from the user."""
    try:
        clarification_responses = state.clarification_responses or []
        
        if not clarification_responses:
            return {"error_message": "No clarification responses to process"}
        
        logger.info(f"Processing {len(clarification_responses)} clarification responses")
        
        # Extract relevant information from responses
        analysis_preferences = {}
        for response in clarification_responses:
            question = response.get("question", "")
            answer = response.get("response", "")
            
            # Parse common preferences
            if "analysis type" in question.lower():
                analysis_preferences["preferred_analysis"] = answer
            elif "data" in question.lower():
                analysis_preferences["data_info"] = answer
            elif "output" in question.lower():
                analysis_preferences["output_preference"] = answer
        
        # Update analysis request with clarification context
        original_request = state.analysis_request or ""
        enhanced_request = original_request
        
        if analysis_preferences:
            clarification_text = " ".join([f"{k}: {v}" for k, v in analysis_preferences.items()])
            enhanced_request = f"{original_request} (Clarifications: {clarification_text})"
        
        return {
            "analysis_request": enhanced_request,
            "clarification_processed": True,
            "analysis_preferences": analysis_preferences,
            "needs_clarification": False,
        }
        
    except Exception as e:
        logger.error(f"Error processing clarification response: {e}")
        return {"error_message": str(e)}


def should_refine_code(state: CodeAgentState) -> str:
    """Determine if code should be refined."""
    try:
        generated_code = state.generated_code or ""
        error_message = state.error_message or ""
        refinement_count = state.refinement_count or 0
        
        # Check if we have errors and haven't exceeded max refinements
        if error_message and refinement_count < MAX_REFINEMENTS:
            logger.info(f"Code has errors, attempting refinement {refinement_count + 1}")
            return "true"
        
        # Check if code is too short (might indicate incomplete generation)
        if generated_code and len(generated_code.strip()) < 50 and refinement_count < MAX_REFINEMENTS:
            logger.info("Generated code seems too short, attempting refinement")
            return "true"
        
        return "false"
        
    except Exception as e:
        logger.error(f"Error in should_refine_code: {e}")
        return "false"


def refine_code_node(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """Refine the generated code to address issues."""
    try:
        generated_code = state.generated_code or ""
        error_message = state.error_message or ""
        analysis_request = state.analysis_request or ""
        refinement_count = state.refinement_count or 0
        
        if refinement_count >= MAX_REFINEMENTS:
            logger.warning("Maximum refinements reached")
            return {"refinement_complete": True}
        
        # Get LLM from config
        llm = get_config_value(config, 'llm')
        if not llm:
            return {"error_message": "LLM not available for refinement"}
        
        # Create refinement prompt
        refinement_prompt = f"""
The following Python code was generated but has issues that need to be addressed:

ORIGINAL REQUEST: {analysis_request}

GENERATED CODE:
```python
{generated_code}
```

ISSUES DETECTED:
{error_message or "Code seems incomplete or too short"}

Please provide an improved version of the code that:
1. Addresses the identified issues
2. Maintains the original functionality
3. Follows best practices for paleoclimate data analysis
4. Uses appropriate libraries (PyLiPD, Pyleoclim, pandas, numpy)

Return your response as JSON with keys: code, description, improvements_made.
"""
        
        messages = [
            SystemMessage(content="You are an expert Python developer specializing in paleoclimate data analysis."),
            HumanMessage(content=refinement_prompt)
        ]
        
        raw_response = llm._call(messages)
        
        # Parse refinement response
        try:
            json_match = re.search(r"```json\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(1))
            else:
                parsed = json.loads(raw_response)
        except (json.JSONDecodeError, AttributeError):
            # Fallback: extract code block
            code_match = re.search(r"```python\s*(.*?)\s*```", raw_response, re.DOTALL)
            refined_code = code_match.group(1) if code_match else generated_code
            parsed = {
                "code": refined_code,
                "description": "Refined code",
                "improvements_made": ["General improvements applied"]
            }
        
        refined_code = parsed.get("code", generated_code)
        
        return {
            "generated_code": refined_code,
            "refinement_count": refinement_count + 1,
            "error_message": "",  # Clear previous error
            "refinement_description": parsed.get("description", "Code refined"),
            "improvements_made": parsed.get("improvements_made", [])
        }
        
    except Exception as e:
        logger.error(f"Error refining code: {e}")
        return {"error_message": str(e)}


def process_refinement_request(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """Process a user request to refine existing code."""
    try:
        # Extract refinement request from the latest message
        messages = state.messages or []
        refinement_request = ""
        
        for msg in reversed(messages):
            if get_message_value(msg, 'role') == 'user':
                refinement_request = get_message_value(msg, 'content', '')
                break
        
        if not refinement_request:
            return {"error_message": "No refinement request found"}
        
        # Get previous code from context
        context = state.context or {}
        previous_code = context.get("previous_code", "")
        
        if previous_code:
            # Create combined request that incorporates previous code context
            combined_request = f"""
Refine this existing code based on the user's request:

EXISTING CODE:
```python
{previous_code}
```

USER REFINEMENT REQUEST:
{refinement_request}

Please generate new Python code that builds upon the previous code while incorporating the user's refinement request.
"""
            
            logger.info(f"Processing refinement request: {refinement_request}")
            logger.info(f"Previous code context: {previous_code[:100]}...")
            
            return {
                "user_query": combined_request,
                "analysis_request": combined_request,
                "is_refinement": True
            }
        else:
            # No previous code context, treat as regular request
            logger.warning("No previous code found, treating refinement as new request")
            return {
                "user_query": refinement_request,
                "analysis_request": refinement_request
            }
            
    except Exception as e:
        logger.error(f"Error processing refinement request: {e}")
        return {"error_message": str(e)}


def generate_code_node(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """Enhanced code generation with comprehensive contextual information."""
    try:
        logger.info("=== ENHANCED GENERATE_CODE_NODE CALLED ===")
        
        analysis_request = state.analysis_request or ""
        analysis_type = state.analysis_type or "general"
        output_format = state.output_format or "notebook"
        data_context = state.data_context or {}
        examples = state.similar_code or []
        contextual_data = getattr(state, 'contextual_search_data', {})
        
        logger.info(f"analysis_request: '{analysis_request}'")
        logger.info(f"analysis_type: {analysis_type}")
        logger.info(f"output_format: {output_format}")
        logger.info(f"examples count: {len(examples)}")
        logger.info(f"contextual_data keys: {list(contextual_data.keys())}")
        
        if not analysis_request:
            logger.error("No analysis request provided")
            return {"error_message": "No analysis request provided for code generation"}
        
        # Format comprehensive context for LLM
        context_prompt = ""
        if contextual_data:
            context_prompt = search_service.format_code_context_for_llm(contextual_data)
        
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
        clarification_text = ""
        if state.clarification_processed and state.clarification_responses:
            clarification_text = "\nUSER CLARIFICATIONS:\n"
            for resp in state.clarification_responses:
                question = resp.get("question", "")
                response = resp.get("response", "")
                clarification_text += f"Question: {question}\nResponse: {response}\n\n"
        
        # Include previous agent output context if available
        prev_ctx_lines = []
        prev_ctx = state.context or {}
        if prev_ctx.get("prev_sparql_query"):
            prev_ctx_lines.append("PREVIOUS SPARQL QUERY:\n```sparql\n" + prev_ctx["prev_sparql_query"] + "\n```")
        if prev_ctx.get("prev_query_results"):
            sample_results = prev_ctx["prev_query_results"]
            try:
                import json as _json
                prev_ctx_lines.append("PREVIOUS SPARQL RESULTS (truncated):\n" + _json.dumps(sample_results[:3], indent=2) + ("\n..." if len(sample_results) > 3 else ""))
            except Exception:
                prev_ctx_lines.append("PREVIOUS SPARQL RESULTS present (unable to display)\n")
        if prev_ctx.get("prev_generated_code"):
            code_snip = prev_ctx["prev_generated_code"]
            prev_ctx_lines.append("PREVIOUS GENERATED CODE:\n```python\n" + (code_snip[:400] + ("\n..." if len(code_snip) > 400 else "")) + "\n```")
        if prev_ctx.get("prev_workflow_plan"):
            prev_ctx_lines.append("PREVIOUS WORKFLOW PLAN PROVIDED (refer to steps as needed).")
        if prev_ctx.get("prev_execution_results"):
            prev_ctx_lines.append(f"PREVIOUS EXECUTION RESULTS: {len(prev_ctx['prev_execution_results'])} items available for reference.")

        previous_context_section = "\n\n".join(prev_ctx_lines)

        user_prompt = (
            f"ANALYSIS REQUEST: {analysis_request}{clarification_text}\n\n"
            f"DATA CONTEXT: {data_context}\n"
            f"ANALYSIS TYPE: {analysis_type}\n"
            f"OUTPUT FORMAT: {output_format}\n\n"
            f"{previous_context_section}\n\n" if previous_context_section else "" +
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
            return {"error_message": "LLM not available"}
        
        logger.info("Calling LLM to generate enhanced code...")
        messages = [
            SystemMessage(content="You are an expert Python data-analysis assistant specializing in paleoclimate data. "
                                 "You have access to comprehensive context including code snippets, documentation, "
                                 "and previous code. Generate complete, executable code that integrates seamlessly "
                                 "with existing variables and follows established patterns. "
                                 "Use PyLiPD, Pyleoclim, pandas, numpy, and matplotlib as appropriate. "
                                 "Return your response as JSON with keys: code, description, libraries, outputs."),
            HumanMessage(content=user_prompt)
        ]
        
        raw_response = llm._call(messages)
        logger.info(f"LLM raw response length: {len(raw_response)}")
        logger.info(f"LLM raw response preview: {raw_response[:200]}...")
        
        # Parse response
        try:
            # Try to extract JSON from response
            json_match = re.search(r"```json\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
            if json_match:
                logger.info("Found JSON in code block")
                parsed = json.loads(json_match.group(1))
            else:
                logger.info("Trying to parse entire response as JSON")
                parsed = json.loads(raw_response)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"JSON parsing failed: {e}, using fallback")
            # Fallback: extract code block
            code_match = re.search(r"```python\s*(.*?)\s*```", raw_response, re.DOTALL)
            code_block = code_match.group(1) if code_match else raw_response
            parsed = {
                "code": code_block,
                "description": f"Generated code for: {analysis_request}",
                "libraries": ["pyleoclim", "pandas", "numpy"],
                "outputs": ["results"],
            }
        
        # Format code based on output format
        generated_code = parsed.get("code", "")
        logger.info(f"Generated code length: {len(generated_code)}")
        logger.info(f"Generated code preview: {generated_code[:200]}...")
        
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
            "context_used": context_summary
        }
        
        logger.info(f"Returning enhanced result with generated_code length: {len(result['generated_code'])}")
        return result
        
    except Exception as e:
        logger.error(f"Error generating code: {e}", exc_info=True)
        return {"error_message": str(e)}


def finalize_code_response_node(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """Finalize the code generation response."""
    try:
        generated_code = state.generated_code or ""
        analysis_description = state.analysis_description or ""
        refinement_count = state.refinement_count or 0
        has_error = bool(state.error_message)
        
        if not generated_code:
            return {"error_message": "No code was generated"}
        
        # Add final message if not already present
        messages = state.messages or []
        
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
            "needs_clarification": False,
            "final_status": final_status
        }
        
    except Exception as e:
        logger.error(f"Error finalizing code response: {e}")
        return {"error_message": str(e)} 