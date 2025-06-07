"""
Workflow Manager agent using LangGraph.
"""

import logging
from langgraph.graph import Graph, StateGraph, START, END
from typing import Dict, Any

from .state import WorkflowAgentState, WorkflowAgentConfig
from .handlers import (
    extract_workflow_request_node,
    search_workflow_context_node,
    detect_clarification_node,
    process_clarification_response,
    generate_workflow_plan_node,
    finalize_workflow_response_node
)

logger = logging.getLogger(__name__)

# Helper to access state attributes for both dict and Pydantic models
def _get(state, key, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    try:
        return getattr(state, key, default)
    except AttributeError:
        return default

def human_clarification_needed_node(state: WorkflowAgentState) -> Dict[str, Any]:
    """Node that handles when human clarification is needed."""
    try:
        logger.info("=== HUMAN CLARIFICATION NEEDED NODE CALLED ===")
        logger.info(f"State needs_clarification: {_get(state, 'needs_clarification')}")
        logger.info(f"State has clarification_questions: {bool(_get(state, 'clarification_questions'))}")
        
        # Get current messages and add the clarification message
        messages = _get(state, "messages") or []
        clarification_message = {
            "role": "assistant",
            "content": "I need some clarifications to create a better workflow plan",
        }
        updated_messages = messages + [clarification_message]
        
        # Return the state updates
        result = {
            "messages": updated_messages,
            "needs_clarification": True,
            "clarification_questions": _get(state, "clarification_questions", []),
            "conversation_id": _get(state, "conversation_id")
        }
        
        logger.info(f"Returning state update: needs_clarification=True, questions={len(result['clarification_questions'])}")
        return result
    except Exception as e:
        logger.error(f"Error in human_clarification_needed_node: {e}")
        return {
            "error_message": f"Error formatting clarification: {str(e)}",
            "needs_clarification": True
        }

def create_agent() -> Graph:
    """Create a workflow planning agent."""
    try:
        # Create the graph with config
        workflow = StateGraph(WorkflowAgentState, config_schema=WorkflowAgentConfig)
        
        # Add nodes
        workflow.add_node("extract_request", extract_workflow_request_node)
        workflow.add_node("search_context", search_workflow_context_node)
        workflow.add_node("detect_clarification", detect_clarification_node)
        workflow.add_node("process_clarification", process_clarification_response)
        workflow.add_node("generate_plan", generate_workflow_plan_node)
        workflow.add_node("human_clarification_needed", human_clarification_needed_node)
        workflow.add_node("finalize", finalize_workflow_response_node)
        
        # Enhanced conditional routing from start
        def route_initial_request(state):
            clarification_responses = _get(state, "clarification_responses")
            
            logger.info(f"=== WORKFLOW ROUTING ===")
            logger.info(f"clarification_responses: {bool(clarification_responses)}")
            
            if clarification_responses:
                logger.info("Routing to: has_clarification")
                return "has_clarification"
            else:
                logger.info("Routing to: new_request")
                return "new_request"
        
        workflow.add_conditional_edges(
            START,
            route_initial_request,
            {
                "has_clarification": "process_clarification",
                "new_request": "extract_request"
            }
        )
        
        # After processing clarification, continue with context search
        workflow.add_edge("process_clarification", "search_context")
        
        # Main flow
        workflow.add_edge("extract_request", "search_context")
        workflow.add_edge("search_context", "detect_clarification")
        
        # Add conditional edge from detect_clarification based on needs_clarification
        workflow.add_conditional_edges(
            "detect_clarification",
            lambda state: "true" if _get(state, "needs_clarification", False) else "false",
            {
                "true": "human_clarification_needed",
                "false": "generate_plan"
            }
        )
        
        # After human responds, process the clarification and continue
        workflow.add_edge("human_clarification_needed", END)
        
        # Generate plan and finalize
        workflow.add_edge("generate_plan", "finalize")
        workflow.add_edge("finalize", END)
        
        # Compile the graph
        return workflow.compile()
    except Exception as e:
        logger.error(f"Error creating workflow agent: {e}")
        raise 