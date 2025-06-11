"""
SPARQL query generation agent using LangGraph.
"""

import logging
from langgraph.graph import Graph, StateGraph, START, END
from typing import Dict, Any
import json

from .state import SparqlAgentState, SparqlAgentConfig
from .handlers import (
    get_similar_queries_node,
    get_entity_matches_node,
    detect_clarification_node,
    generate_query_node,
    execute_query_node,
    should_refine_query,
    refine_query_node,
    finalize_query_node
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

def human_clarification_needed_node(state: SparqlAgentState) -> Dict[str, Any]:
    """Node that handles when human clarification is needed."""
    try:
        logger.info("=== HUMAN CLARIFICATION NEEDED NODE CALLED ===")
        logger.info(f"State needs_clarification: {_get(state, 'needs_clarification')}")
        logger.info(f"State has clarification_questions: {bool(_get(state, 'clarification_questions'))}")
        
        # Get current messages and add the clarification message
        messages = _get(state, "messages") or []
        clarification_message = {
            "role": "assistant",
            "content": "I need some clarifications",
        }
        updated_messages = messages + [clarification_message]
        
        # Return the state updates
        result = {
            "messages": updated_messages,
            "needs_clarification": True,
            "clarification_questions": _get(state, "clarification_questions", []),
            "conversation_id": _get(state, "conversation_id")  # Preserve conversation_id
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
    """Create a SPARQL query generation agent."""
    try:
        # Create the graph with config
        workflow = StateGraph(SparqlAgentState, config_schema=SparqlAgentConfig)
        
        # Add nodes (updated for LangGraph v2)
        # Each node function will receive both state and config
        workflow.add_node("get_similar_queries", get_similar_queries_node)
        workflow.add_node("get_entity_matches", get_entity_matches_node)
        workflow.add_node("detect_clarification", detect_clarification_node)
        workflow.add_node("generate_query", generate_query_node)
        workflow.add_node("execute_query", execute_query_node)
        workflow.add_node("refine_query", refine_query_node)
        workflow.add_node("human_clarification_needed", human_clarification_needed_node)
        
        # Simplified start routing: always begin with gathering context.
        def route_initial_request(_state):
            return "new_query"
        
        # Direct edge from START to get_similar_queries
        workflow.add_edge(START, "get_similar_queries")
        
        # Main flow - user_input is used directly, so we start with similar queries
        workflow.add_edge("get_similar_queries", "get_entity_matches")
        workflow.add_edge("get_entity_matches", "detect_clarification")
        
        # Add conditional edge from detect_clarification based on needs_clarification
        workflow.add_conditional_edges(
            "detect_clarification",
            lambda state: "true" if _get(state, "needs_clarification", False) else "false",
            {
                "true": "human_clarification_needed",
                "false": "generate_query"
            }
        )
        
        # After human responds, process the clarification and go back to get_similar_queries for context
        workflow.add_edge("human_clarification_needed", END)
        
        # Remaining flow
        workflow.add_edge("generate_query", "execute_query")
        
        # Define conditional edges with string keys for refinement
        workflow.add_conditional_edges(
            "execute_query",
            should_refine_query,
            {
                "true": "refine_query",
                "false": "finalize"
            }
        )
        workflow.add_edge("refine_query", "execute_query")
        
        # Add finalize node that returns the final state
        workflow.add_node("finalize", finalize_query_node)
        workflow.add_edge("finalize", END)
        
        # Compile the graph with the config
        return workflow.compile()
    except Exception as e:
        logger.error(f"Error creating agent: {e}")
        raise