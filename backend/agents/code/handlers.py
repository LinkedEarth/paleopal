"""
Node handlers for the Code Generation agent.
"""

import logging
import json
import re
from typing import Dict, Any
from langchain.schema import HumanMessage, SystemMessage

from .state import CodeAgentState, CodeAgentConfig
from agents.base_state import MAX_REFINEMENTS
from agents.base_langgraph_agent import get_config_value, get_message_value

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


def search_code_examples_node(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """Search for relevant code examples using embeddings."""
    try:
        analysis_request = getattr(state, "analysis_request", "") or state.user_input or ""
        analysis_type = getattr(state, "analysis_type", "general")
        
        if not analysis_request:
            return {"error_message": "No analysis request to search examples for"}
        
        # Search for relevant examples using config helper
        code_embedding_service = get_config_value(config, 'code_embedding_service')
        if not code_embedding_service:
            logger.error("No code embedding service found in config")
            return {"error_message": "Code embedding service not available"}
        
        search_query = f"{analysis_request} {analysis_type}"
        examples = code_embedding_service.search_examples(query=search_query, limit=3)
        
        logger.info(f"Found {len(examples)} relevant code examples")
        
        # Prepare metadata for used examples
        used_examples_meta = []
        for ex in examples:
            used_examples_meta.append({
                "name": ex.get("name", "Unknown"),
                "description": ex.get("description", ""),
                "categories": ex.get("categories", []),
                "relevance_score": ex.get("relevance_score", 0),
            })
        
        return {
            "similar_code": examples,  # Use generalized field
            "code_examples_used": used_examples_meta,
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
      "id": "q1",
      "question": "What specific type of analysis would you like to perform?",
      "choices": ["Time series analysis", "Spectral analysis", "Statistical summary", "Visualization"],
      "context": "This will help determine which Pyleoclim methods to use"
    }}
  ]
}}
```

Return ONLY the valid JSON without any additional text."""

            # Generate the clarification questions
            messages = [
                SystemMessage(content="You are a paleoclimate data analysis expert helping to generate clarification questions for code generation. Return only valid JSON."),
                HumanMessage(content=prompt)
            ]
            
            response = llm._call(messages).strip()
            
            # Extract JSON from the response
            json_pattern = re.compile(r'\{.*\}', re.DOTALL)
            match = json_pattern.search(response)
            
            questions = []
            if match:
                try:
                    json_str = match.group(0)
                    json_data = json.loads(json_str)
                    
                    if "questions" in json_data:
                        questions = json_data["questions"]
                except Exception as e:
                    logger.warning(f"Error parsing LLM output as JSON: {str(e)}")
            
            # Return the result
            if questions:
                return {
                    'needs_clarification': True,
                    'questions': questions,
                    'ambiguities': ambiguities
                }
        
        # No ambiguities or couldn't generate questions
        return {
            'needs_clarification': False,
            'questions': []
        }
    except Exception as e:
        logger.error(f"Error in detect_clarification_needs_code: {e}")
        return {
            'needs_clarification': False,
            'questions': []
        }


def detect_clarification_node(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """
    Analyze the request to identify if clarification is needed for code generation.
    """
    try:
        # Skip clarification for refinement requests
        if state.is_refinement:
            logger.info("Skipping clarification detection for refinement request")
            return {"needs_clarification": False}
            
        # Access the LLM from config using helper function
        llm = get_config_value(config, 'llm')
        if not llm:
            logger.error("No LLM found in config")
            return {"error_message": "LLM not available", "needs_clarification": False}
        
        # Skip if we've already processed a clarification for this query
        clarification_sequence = state.clarification_sequence or 0
        if clarification_sequence > 0:
            logger.info(f"Already processed clarification (sequence {clarification_sequence}), skipping clarification detection")
            return {"needs_clarification": False}
            
        # Skip if we already have clarification responses
        if state.clarification_responses:
            logger.info("Clarification responses already provided, skipping clarification detection")
            return {"needs_clarification": False}
        
        # Check if clarification is needed
        result = detect_clarification_needs_code(
            llm,
            state.user_query or "",
            state.similar_code or [],
            state.data_context or {}
        )
        
        # If clarification is needed, add the questions to the state
        if result.get("needs_clarification", False):
            logger.info("Clarification needed, adding questions to state")
            return {
                "needs_clarification": True,
                "clarification_questions": result.get("questions", [])
            }
        else:
            logger.info("No clarification needed")
            return {"needs_clarification": False}
    except Exception as e:
        logger.error(f"Error in detect_clarification_node: {e}", exc_info=True)
        return {"error_message": str(e), "needs_clarification": False}


def process_clarification_response(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """
    Process the user's response to clarification questions and update the state.
    """
    try:
        # Get the clarification response (assumed to be the last message)
        messages = state.messages or []
        if not messages or len(messages) < 2:
            logger.warning("Not enough messages to process clarification response")
            return {"clarification_processed": False}
        
        # Get the user's response (last message)
        last_message = messages[-1]
        
        # Extract the text using the helper function
        clarification_response = ""
        
        # Check if the last message is from a user and get content
        role = get_message_value(last_message, 'role')
        if role == 'user':
            clarification_response = get_message_value(last_message, 'content', '')
        
        # Fallback: try alternative extraction methods
        if not clarification_response and hasattr(last_message, "content"):
            clarification_response = str(last_message.content)
        
        if not clarification_response:
            logger.warning("No clarification response could be extracted")
            clarification_response = "Please continue with the best option"
        
        # Process the clarification response
        responses = state.clarification_responses or []
        questions = state.clarification_questions or []
        
        if questions:
            first_question = questions[0]
            responses.append({
                "question_id": first_question.get("id", "q1"),
                "response": clarification_response,
                "question": first_question.get("question", "")
            })
        
        return {
            "clarification_responses": responses,
            "clarification_processed": True,
            "needs_clarification": False,
            "clarification_sequence": state.clarification_sequence or 0 + 1
        }
    except Exception as e:
        logger.error(f"Error processing clarification response: {e}", exc_info=True)
        return {
            "error_message": str(e),
            "clarification_processed": True,
            "needs_clarification": False
        }


def should_refine_code(state: CodeAgentState) -> str:
    """Determine if the code should be refined.
    
    Returns:
        str: "true" if the code should be refined, "false" otherwise
    """
    # Check refinement count first to avoid infinite loops
    refinement_count = state.refinement_count or 0
    logger.info(f"=== SHOULD_REFINE_CODE CHECK ===")
    logger.info(f"refinement_count: {refinement_count}")
    logger.info(f"has_generated_code: {bool(state.generated_code)}")
    logger.info(f"has_error_message: {bool(state.error_message)}")
    logger.info(f"execution_results: {state.execution_results}")
    
    if refinement_count >= MAX_REFINEMENTS:
        logger.info(f"Maximum refinement attempts reached ({refinement_count}), stopping refinement")
        return "false"
    
    # Check if there's an explicit error message
    if state.error_message:
        logger.info(f"Error message found, triggering refinement (attempt {refinement_count + 1})")
        return "true"
    
    # Check if execution_results contains error indicators
    execution_results = state.execution_results or []
    if execution_results and isinstance(execution_results, list) and len(execution_results) > 0:
        first_result = execution_results[0]
        if isinstance(first_result, dict) and "error" in first_result:
            logger.info(f"Error in execution results, triggering refinement (attempt {refinement_count + 1})")
            return "true"
    
    # Check if we have no generated code - but be more careful about this
    if not state.generated_code:
        # Only trigger refinement if we haven't tried before
        if refinement_count == 0:
            logger.info(f"No generated code found, triggering refinement (attempt {refinement_count + 1})")
            return "true"
        else:
            # If we've already tried to refine and still no code, stop trying
            logger.info(f"No generated code found after {refinement_count} refinement attempts, stopping")
            return "false"
    
    # If we reach here, the code generation seems successful
    logger.info("Code generation appears successful, no refinement needed")
    return "false"


def refine_code_node(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """Refine the generated code based on errors or issues."""
    try:
        # Get the LLM from config using helper function
        llm = get_config_value(config, 'llm')
        if not llm:
            logger.error("No LLM found in config")
            return {"error_message": "LLM not available"}
        
        # Construct refinement prompt
        error_msg = state.error_message or ""
        results = state.execution_results or []
        current_code = state.generated_code or ""
        refinement_count = state.refinement_count or 0
        analysis_request = state.analysis_request or ""
        
        # Prepare error description for the LLM
        error_description = ""
        if error_msg:
            error_description = f"Error Message: {error_msg}\n\n"
        elif results and isinstance(results, list) and len(results) > 0:
            first_result = results[0]
            if isinstance(first_result, dict) and "error" in first_result:
                error_description = f"Code generation error: {first_result['error']}\n\n"
        
        logger.info(f"Refining code (attempt {refinement_count + 1}/{MAX_REFINEMENTS})")
        logger.info(f"Current code: {current_code[:200]}...")
        logger.info(f"Error: {error_description.strip()}")
        
        prompt = f"""The previous Python code generation had issues or errors.
Please refine the code to fix the problems.

Original Request: {analysis_request}

Current Code:
{current_code}

{error_description}

Please provide refined Python code that addresses these issues.
Focus on:
1. Correct Python syntax
2. Proper use of Pyleoclim and PyLiPD libraries
3. Clear variable names and structure
4. Error handling where appropriate

Return your response as JSON with keys: code, description, libraries, outputs."""

        # Generate refined code using LangChain message types
        messages = [
            SystemMessage(content="You are a Python code refinement expert specializing in paleoclimate data analysis. Generate only the refined code as JSON."),
            HumanMessage(content=prompt)
        ]
        
        raw_response = llm._call(messages).strip()
        
        # Parse response
        try:
            # Try to extract JSON from response
            json_match = re.search(r"```json\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(1))
            else:
                parsed = json.loads(raw_response)
        except (json.JSONDecodeError, AttributeError):
            # Fallback: extract code block
            code_match = re.search(r"```python\s*(.*?)\s*```", raw_response, re.DOTALL)
            code_block = code_match.group(1) if code_match else raw_response
            parsed = {
                "code": code_block,
                "description": f"Refined code for: {analysis_request}",
                "libraries": ["pyleoclim", "pandas", "numpy"],
                "outputs": ["results"],
            }
        
        refined_code = parsed.get("code", "")
        
        logger.info(f"Refined code: {refined_code[:200]}...")
        
        # Update state - clear error state and increment refinement count
        return {
            "generated_code": refined_code,
            "analysis_description": parsed.get("description", ""),
            "required_libraries": parsed.get("libraries", []),
            "expected_outputs": parsed.get("outputs", []),
            "error_message": None,  # Clear the error message
            "execution_results": None,  # Clear previous results
            "refinement_count": refinement_count + 1
        }
    except Exception as e:
        logger.error(f"Error refining code: {e}")
        return {
            "error_message": f"Error during refinement: {str(e)}",
            "refinement_count": state.refinement_count or 0 + 1
        }


def process_refinement_request(state: CodeAgentState, config: CodeAgentConfig) -> Dict[str, Any]:
    """Process a code refinement request by combining previous context with the new request."""
    try:
        # Get the refinement request
        refinement_request = state.refinement_request or ""
        previous_code = state.previous_query or ""  # previous_query stores previous code
        
        if not refinement_request:
            logger.warning("No refinement request found, treating as regular request")
            return {}
        
        # Build a comprehensive request context for refinement
        if previous_code:
            # Combine the original intent with the refinement request
            combined_request = f"""
Original code context: The user previously requested code that resulted in this Python code:
{previous_code}

Now the user wants to refine this code with the following request:
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
    """Generate Python code based on the request and examples."""
    try:
        logger.info("=== GENERATE_CODE_NODE CALLED ===")
        
        analysis_request = state.analysis_request or ""
        analysis_type = state.analysis_type or "general"
        output_format = state.output_format or "notebook"
        data_context = state.data_context or {}
        examples = state.similar_code or []  # Use generalized field
        
        logger.info(f"analysis_request: '{analysis_request}'")
        logger.info(f"analysis_type: {analysis_type}")
        logger.info(f"output_format: {output_format}")
        logger.info(f"examples count: {len(examples)}")
        
        if not analysis_request:
            logger.error("No analysis request provided")
            return {"error_message": "No analysis request provided for code generation"}
        
        # Build examples section for prompt
        examples_section = ""
        for idx, ex in enumerate(examples, 1):
            examples_section += (
                f"\n## Example {idx}: {ex.get('name', 'Unknown')}\n"
                f"Description: {ex.get('description', '')}\n"
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
        
        # Create prompts
        system_prompt = (
            "You are an expert Python data-analysis assistant specializing in paleoclimate data. "
            "Generate complete, executable code for the user request using PyLiPD and Pyleoclim libraries. "
            "Return your response as JSON with keys: code, description, libraries, outputs."
        )
        
        user_prompt = (
            f"Analysis Request: {analysis_request}{clarification_text}\n\n"
            f"Data Context: {data_context}\n"
            f"Analysis Type: {analysis_type}\n"
            f"Output Format: {output_format}\n\n"
            "Relevant Examples:" + examples_section + "\n\n"
            "Generate Python code that addresses the analysis request. "
            "Return JSON with keys: code, description, libraries, outputs."
        )
        
        # Generate code using LLM from config
        llm = get_config_value(config, 'llm')
        if not llm:
            logger.error("No LLM found in config")
            return {"error_message": "LLM not available"}
        
        logger.info("Calling LLM to generate code...")
        messages = [
            SystemMessage(content=system_prompt),
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
                "# Auto-generated by PaleoPal CodeGenerationAgent\n\n"
            )
            generated_code = header + generated_code
        
        # Add success message
        messages = state.messages or []
        messages.append({
            "role": "assistant",
            "content": f"Generated {output_format} code for {analysis_type} analysis."
        })
        
        result = {
            "generated_code": generated_code,
            "analysis_description": parsed.get("description", ""),
            "required_libraries": parsed.get("libraries", []),
            "expected_outputs": parsed.get("outputs", []),
            "messages": messages,
            "execution_results": [{"type": "code_generated", "status": "success"}],  # Use generalized field
        }
        
        logger.info(f"Returning result with generated_code length: {len(result['generated_code'])}")
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
            "needs_clarification": False,
            "final_status": final_status
        }
        
    except Exception as e:
        logger.error(f"Error finalizing code response: {e}")
        return {"error_message": str(e)} 