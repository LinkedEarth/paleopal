"""
Node handlers for the Workflow Manager agent.
Enhanced with comprehensive contextual search and LLM-based planning.
"""

import logging
import json
import uuid
import re
from typing import Dict, Any, List
from langchain.schema import HumanMessage, SystemMessage

from .state import WorkflowAgentState, WorkflowAgentConfig
from agents.base_langgraph_agent import get_config_value, get_message_value
from services.search_integration_service import search_service
from services.service_manager import service_manager

logger = logging.getLogger(__name__)


def extract_workflow_request_node(state: WorkflowAgentState, config: WorkflowAgentConfig) -> Dict[str, Any]:
    """Extract workflow request from messages."""
    try:
        logger.info("=== EXTRACT_WORKFLOW_REQUEST_NODE CALLED ===")
        
        messages = state.messages or []
        user_input = ""
        
        if messages:
            # Get the most recent message
            last_message = messages[-1]
            user_input = get_message_value(last_message, 'content', '')
        else:
            # Look for user_input if no messages
            user_input = state.user_input or ""
        
        if not user_input:
            logger.warning("No user input found in state")
            return {
                "error_message": "No workflow request found",
                "conversation_id": state.conversation_id
            }
        
        logger.info(f"Extracted workflow request: '{user_input[:100]}...'")
        
        return {
            "user_input": user_input,
            "conversation_id": state.conversation_id
        }
        
    except Exception as e:
        logger.error(f"Error extracting workflow request: {e}")
        return {
            "error_message": str(e),
            "conversation_id": state.conversation_id
        }


def search_workflow_context_node(state: WorkflowAgentState, config: WorkflowAgentConfig) -> Dict[str, Any]:
    """Search for contextual guidance for workflow planning."""
    try:
        user_input = state.user_input or ""
        
        if not user_input:
            logger.warning("No user input found for workflow context search")
            return {
                "error_message": "No user input to search context for",
                "conversation_id": state.conversation_id
            }
        
        logger.info(f"=== SEARCH_WORKFLOW_CONTEXT_NODE CALLED ===")
        logger.info(f"Searching for workflow context with query: '{user_input}'")

        # Get context from notebook workflows and literature methods - run synchronously
        import asyncio
        context = asyncio.run(search_service.get_context_for_planning(user_input))
        
        # Store the context for later use
        state.contextual_search_data = context
        
        workflows_count = len(context.get('workflows', []))
        methods_count = len(context.get('methods', []))
        
        logger.info(f"Search completed: {workflows_count} workflows, {methods_count} methods found")
        logger.info(f"Setting contextual_search_data in state: {bool(context)}")
        
        # Log some details about the found workflows
        if workflows_count > 0:
            for i, workflow in enumerate(context.get('workflows', [])[:2]):  # Log first 2
                logger.info(f"Workflow {i+1}: {workflow.get('title', 'No title')} (similarity: {workflow.get('similarity_score', 0):.3f})")
        
        # Log some details about the found methods  
        if methods_count > 0:
            for i, method in enumerate(context.get('methods', [])[:2]):  # Log first 2
                logger.info(f"Method {i+1}: {method.get('method_name', 'No name')} (similarity: {method.get('similarity_score', 0):.3f})")
        
        return {
            "contextual_search_data": context,
            "conversation_id": state.conversation_id
        }
        
    except Exception as e:
        logger.error(f"Error searching workflow context: {e}", exc_info=True)
        return {
            "error_message": str(e),
            "conversation_id": state.conversation_id
        }


def detect_clarification_needs_workflow(
    llm,
    user_input: str,
    context_data: dict
) -> Dict[str, Any]:
    """
    Detect if the workflow planning request needs clarification.
    
    Args:
        llm: LLM model to use
        user_input: Raw user input
        context_data: Context from search
        
    Returns:
        Dict with clarification details if needed
    """
    try:
        # Check for potential ambiguities in workflow planning
        ambiguities = []
        
        # Case 1: Vague analysis request
        vague_terms = ['analyze', 'study', 'investigate', 'examine', 'look at', 'research']
        if any(term in user_input.lower() for term in vague_terms) and len(user_input.split()) < 8:
            ambiguities.append({
                'type': 'vague_request',
                'description': 'The analysis request is quite general and could be interpreted in multiple ways'
            })
        
        # Case 2: Missing scope specification
        scope_indicators = ['dataset', 'region', 'time period', 'proxy', 'variable']
        if not any(indicator in user_input.lower() for indicator in scope_indicators):
            ambiguities.append({
                'type': 'missing_scope',
                'description': 'No specific scope mentioned (datasets, regions, time periods, etc.)'
            })
        
        # Case 3: Multiple possible analysis approaches
        analysis_keywords = {
            'comparative': ['compare', 'comparison', 'versus', 'vs', 'contrast'],
            'temporal': ['time', 'temporal', 'chronological', 'trend', 'evolution'],
            'spatial': ['spatial', 'geographic', 'regional', 'location', 'site'],
            'statistical': ['statistics', 'correlation', 'regression', 'significance'],
            'visualization': ['plot', 'chart', 'graph', 'visualize', 'display']
        }
        
        matching_types = []
        for analysis_type, keywords in analysis_keywords.items():
            if any(keyword in user_input.lower() for keyword in keywords):
                matching_types.append(analysis_type)
        
        if len(matching_types) > 2:
            ambiguities.append({
                'type': 'multiple_analysis_types',
                'matching_types': matching_types,
                'description': f'The request could involve multiple types of analysis: {", ".join(matching_types)}'
            })
        
        # If we found ambiguities, generate clarification questions
        if ambiguities:
            prompt = f"""Based on the user's workflow planning request, I need to generate clarification questions.

USER REQUEST: "{user_input}"

CONTEXT DATA: {context_data}

AMBIGUITIES DETECTED:
{chr(10).join([f"- {a['description']}" for a in ambiguities])}

Generate clarification questions to help create a more precise workflow plan. Each question should:
1. Be specific about the ambiguity
2. Offer clear choices when possible
3. Help determine the exact analysis approach and scope needed

Generate the questions in JSON format:
```json
{{
  "questions": [
    {{
      "id": "optional_unique_id",
      "question": "What specific aspect would you like to analyze?",
      "context": "Your request could involve multiple analysis approaches",
      "choices": ["temporal patterns", "spatial variations", "comparative analysis"]
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
                    parsed = json.loads(json_match.group(1))
                    questions = parsed.get("questions", [])
                    
                    if questions:
                        # Add unique IDs to questions if they don't have them
                        for i, question in enumerate(questions):
                            if 'id' not in question:
                                question['id'] = f"workflow_q{i+1}_{uuid.uuid4().hex[:8]}"
                        
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


def detect_clarification_node(state: WorkflowAgentState, config: WorkflowAgentConfig) -> Dict[str, Any]:
    """Detect if clarification is needed for workflow planning."""
    try:
        user_input = state.user_input or ""
        context_data = state.contextual_search_data or {}
        
        # Get LLM from config
        llm = get_config_value(config, 'llm')
        if not llm:
            logger.warning("No LLM available for clarification detection")
            return {
                "needs_clarification": False,
                "conversation_id": state.conversation_id
            }
        
        # Check if clarification is enabled
        enable_clarification = get_config_value(config, 'enable_clarification', True)
        if not enable_clarification:
            logger.info("Clarification is disabled, skipping detection")
            return {
                "needs_clarification": False,
                "conversation_id": state.conversation_id
            }
        
        # Skip clarification if we already have clarification responses
        if state.clarification_responses:
            logger.info("Clarification responses already provided, skipping detection")
            return {
                "needs_clarification": False,
                "conversation_id": state.conversation_id
            }
        
        # Detect clarification needs
        clarification_result = detect_clarification_needs_workflow(
            llm=llm,
            user_input=user_input,
            context_data=context_data
        )
        
        # Apply threshold filtering
        needs_clarification = clarification_result.get("needs_clarification", False)
        clarification_threshold = get_config_value(config, 'clarification_threshold', 'conservative')
        
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
                "conversation_id": state.conversation_id
            }
        else:
            logger.info(f"No clarification needed (threshold: {clarification_threshold})")
            return {
                "needs_clarification": False,
                "conversation_id": state.conversation_id
            }
        
    except Exception as e:
        logger.error(f"Error in clarification detection: {e}")
        return {
            "needs_clarification": False,
            "conversation_id": state.conversation_id
        }


def process_clarification_response(state: WorkflowAgentState, config: WorkflowAgentConfig) -> Dict[str, Any]:
    """Process clarification responses from the user."""
    try:
        clarification_responses = state.clarification_responses or []
        
        if not clarification_responses:
            return {
                "error_message": "No clarification responses to process",
                "conversation_id": state.conversation_id
            }
        
        logger.info(f"Processing {len(clarification_responses)} clarification responses")
        
        # Extract relevant information from responses
        analysis_preferences = {}
        for response in clarification_responses:
            question = response.get("question", "")
            answer = response.get("response", "")
            
            # Parse common preferences
            if "aspect" in question.lower() or "type" in question.lower():
                analysis_preferences["preferred_analysis"] = answer
            elif "scope" in question.lower() or "focus" in question.lower():
                analysis_preferences["analysis_scope"] = answer
            elif "data" in question.lower():
                analysis_preferences["data_preferences"] = answer
        
        # Update user input with clarification context
        original_request = state.user_input or ""
        enhanced_request = original_request
        
        if analysis_preferences:
            clarification_text = " ".join([f"{k}: {v}" for k, v in analysis_preferences.items()])
            enhanced_request = f"{original_request} (Clarifications: {clarification_text})"
        
        return {
            "user_input": enhanced_request,
            "clarification_processed": True,
            "analysis_preferences": analysis_preferences,
            "needs_clarification": False,
            "conversation_id": state.conversation_id
        }
        
    except Exception as e:
        logger.error(f"Error processing clarification response: {e}")
        return {
            "error_message": str(e),
            "conversation_id": state.conversation_id
        }


def generate_workflow_plan_node(state: WorkflowAgentState, config: WorkflowAgentConfig) -> Dict[str, Any]:
    """Generate a workflow plan using LLM and contextual search."""
    try:
        logger.info("=== GENERATE_WORKFLOW_PLAN_NODE CALLED ===")
        
        user_input = state.user_input or ""
        context_data = state.contextual_search_data or {}
        
        if not user_input:
            logger.error("No user input provided")
            return {
                "error_message": "No user input provided for workflow planning",
                "conversation_id": state.conversation_id
            }
        
        # Get LLM from config
        llm = get_config_value(config, 'llm')
        if not llm:
            logger.error("No LLM found in config")
            return {
                "error_message": "LLM not available",
                "conversation_id": state.conversation_id
            }
        
        # Format context for LLM
        context_text = ""
        if context_data:
            context_text = search_service.format_context_for_llm(context_data)
        
        # Include clarification context if available
        clarification_text = ""
        if state.clarification_processed and state.clarification_responses:
            clarification_text = "\nUSER CLARIFICATIONS:\n"
            for resp in state.clarification_responses:
                question = resp.get("question", "")
                response = resp.get("response", "")
                clarification_text += f"Question: {question}\nResponse: {response}\n\n"
        
        # Create planning prompt
        system_prompt = (
            "You are a workflow planning expert for paleoclimate data analysis. "
            "Generate detailed, executable workflow plans as structured JSON that break down complex analysis requests "
            "into ordered steps using appropriate agents and tools. "
            "Return your response as a structured JSON object."
        )
        
        user_prompt = f"""Create a detailed workflow plan for this paleoclimate analysis request.

REQUEST: {user_input}{clarification_text}

CONTEXTUAL GUIDANCE:
{context_text}

AVAILABLE AGENTS:
- sparql: Generate SPARQL queries to find and retrieve paleoclimate datasets
- code: Generate Python code for data analysis, visualization, and processing

INSTRUCTIONS:
1. Break down the request into logical, ordered steps
2. Assign each step to the most appropriate agent
3. Include clear descriptions and expected outputs
4. Consider data flow between steps
5. Generate the workflow as structured JSON

Return the workflow in this JSON format:
```json
{{
  "workflow_id": "auto-generated-uuid",
  "title": "Brief workflow title",
  "description": "Overall workflow description",
  "steps": [
    {{
      "id": "step_1",
      "name": "Find Datasets",
      "agent": "sparql",
      "description": "Find relevant paleoclimate datasets from coral d18O for last 10,000 years in ENSO-sensitive regions",
      "input": "Search query for paleoclimate datasets",
      "expected_output": "List of relevant datasets with metadata",
      "dependencies": []
    }},
    {{
      "id": "step_2", 
      "name": "Analyze Data",
      "agent": "code",
      "description": "Analyze the retrieved datasets for ENSO variability patterns and create visualizations",
      "input": "Dataset analysis request with specific focus on ENSO patterns",
      "expected_output": "Analysis results, statistical summaries, and visualizations",
      "dependencies": ["step_1"]
    }}
  ]
}}
```

IMPORTANT FORMAT RULES:
- Use only "sparql" or "code" as agent values
- Each step must have a unique id
- Dependencies should reference step ids
- Keep descriptions detailed and specific
- Input should be actionable text that can be sent to the agent
- Generate a complete JSON workflow following this exact structure

Only return the JSON object, nothing else."""
        
        # Generate workflow plan
        logger.info("Calling LLM to generate workflow plan...")
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        raw_response = llm._call(messages)
        logger.info(f"LLM raw response length: {len(raw_response)}")
        
        # Extract structured JSON from response
        structured_workflow = ""
        try:
            # Try to extract structured JSON from response
            structured_match = re.search(r"```json\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
            if structured_match:
                logger.info("Found structured JSON in code block")
                structured_workflow = structured_match.group(1).strip()
            else:
                # Try to find structured JSON without code blocks
                structured_match = re.search(r"(structured JSON.*?)(?=\n\n|\n```|\nNote:|\nThe|\Z)", raw_response, re.DOTALL)
                if structured_match:
                    logger.info("Found structured JSON without code blocks")
                    structured_workflow = structured_match.group(1).strip()
                else:
                    logger.warning("No structured JSON found, using fallback")
                    raise ValueError("No valid structured JSON found")
                    
        except Exception as e:
            logger.warning(f"Structured JSON parsing failed: {e}, using fallback")
            # Fallback: create a simple structured JSON workflow
            workflow_id = str(uuid.uuid4())
            structured_workflow = f"""{{
  "workflow_id": "{workflow_id}",
  "title": "Brief workflow title",
  "description": "Overall workflow description",
  "steps": [
    {{
      "id": "step_1",
      "name": "Find Datasets",
      "agent": "sparql",
      "description": "Find relevant paleoclimate datasets from coral d18O for last 10,000 years in ENSO-sensitive regions",
      "input": "Search query for paleoclimate datasets",
      "expected_output": "List of relevant datasets with metadata",
      "dependencies": []
    }},
    {{
      "id": "step_2", 
      "name": "Analyze Data",
      "agent": "code",
      "description": "Analyze the retrieved datasets for ENSO variability patterns and create visualizations",
      "input": "Dataset analysis request with specific focus on ENSO patterns",
      "expected_output": "Analysis results, statistical summaries, and visualizations",
      "dependencies": ["step_1"]
    }}
  ]
}}"""
        
        # Parse workflow details for metadata
        workflow_id = str(uuid.uuid4())
        
        # Count tasks and extract agent types from structured JSON
        task_count = len(re.findall(r'"id": "step_[0-9]+",', structured_workflow))
        sparql_tasks = len(re.findall(r'"agent": "sparql"', structured_workflow))
        code_tasks = len(re.findall(r'"agent": "code"', structured_workflow))
        
        agents_involved = []
        if sparql_tasks > 0:
            agents_involved.append("sparql")
        if code_tasks > 0:
            agents_involved.append("code")
        
        estimated_steps = task_count
        
        logger.info(f"Generated structured JSON workflow with {task_count} steps, involving agents: {agents_involved}")
        
        # Add success message
        messages = state.messages or []
        context_summary = f"Used {len(context_data.get('workflows', []))} workflow examples, " \
                         f"{len(context_data.get('methods', []))} literature methods"
        
        messages.append({
            "role": "assistant",
            "content": f"Generated structured JSON workflow with {estimated_steps} steps. {context_summary}."
        })
        
        # Store as generated_code (structured JSON) instead of workflow_plan
        return {
            "generated_code": structured_workflow,  # This is the key change - use generated_code
            "workflow_id": workflow_id,
            "estimated_steps": estimated_steps,
            "agents_involved": agents_involved,
            "messages": messages,
            "context_used": context_summary,
            "conversation_id": state.conversation_id
        }
        
    except Exception as e:
        logger.error(f"Error generating workflow plan: {e}", exc_info=True)
        return {
            "error_message": str(e),
            "conversation_id": state.conversation_id
        }


def finalize_workflow_response_node(state: WorkflowAgentState, config: WorkflowAgentConfig) -> Dict[str, Any]:
    """Finalize the workflow response."""
    try:
        logger.info("=== FINALIZE_WORKFLOW_RESPONSE_NODE CALLED ===")
        
        # Check if we have generated_code (structured JSON)
        if not state.generated_code:
            logger.error("No structured JSON workflow generated")
            return {
                "error_message": "No workflow was generated",
                "conversation_id": state.conversation_id
            }
        
        # Get workflow metadata
        workflow_id = state.workflow_id or str(uuid.uuid4())
        estimated_steps = state.estimated_steps or 0
        agents_involved = state.agents_involved or []
        context_used = state.context_used or "No context used"
        
        # Create final success message
        messages = state.messages or []
        final_message = (f"✅ **Structured JSON Workflow Generated Successfully**\n\n"
                        f"**Workflow ID:** `{workflow_id}`\n"
                        f"**Estimated Steps:** {estimated_steps}\n"
                        f"**Agents Involved:** {', '.join(agents_involved)}\n"
                        f"**Context:** {context_used}\n\n"
                        f"The workflow has been generated as structured JSON that can be "
                        f"executed by the system or imported into workflow management tools.")
        
        messages.append({
            "role": "assistant", 
            "content": final_message
        })
        
        logger.info(f"Finalized structured JSON workflow response for workflow {workflow_id}")
        
        return {
            "generated_code": state.generated_code,  # CRITICAL: Pass through the structured JSON
            "messages": messages,
            "conversation_id": state.conversation_id,
            # Keep workflow metadata
            "workflow_id": workflow_id,
            "estimated_steps": estimated_steps,
            "agents_involved": agents_involved,
            "context_used": context_used,
            "execution_results": [{"type": "workflow_generated", "status": "success", "format": "Structured JSON"}],
            "workflow_summary": {
                "workflow_id": workflow_id,
                "estimated_steps": estimated_steps,
                "agents_involved": agents_involved,
                "context_used": context_used,
                "format": "Structured JSON"
            }
        }
        
    except Exception as e:
        logger.error(f"Error finalizing workflow response: {e}", exc_info=True)
        return {
            "error_message": str(e),
            "conversation_id": state.conversation_id
        } 