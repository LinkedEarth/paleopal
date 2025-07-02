"""
SPARQL query generation agent using LangGraph.
"""

import logging
from langgraph.graph import StateGraph, START, END
from typing import Dict, Any
import json
import asyncio
from services.message_service import message_service

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

def add_hooks(fn, label):
    async def _wrapped(state, config):
        # Get owner_message_id from config
        owner_id = None
        if isinstance(config, dict) and 'configurable' in config and 'owner_message_id' in config['configurable']:
            owner_id = config['configurable']['owner_message_id']
        
        if owner_id:
            try:
                message_service.create_progress_message(owner_id, label, 'start', f'Running {label}...')
            except Exception as e:
                logger.error(f"Failed to send START progress for {label}: {e}")

        if asyncio.iscoroutinefunction(fn):
            result = await fn(state, config)
        else:
            result = await asyncio.to_thread(fn, state, config)

        if owner_id:
            try:
                # Extract safe, serializable data from result
                def make_serializable(obj):
                    """Recursively make an object JSON serializable"""
                    if obj is None or isinstance(obj, (str, int, float, bool)):
                        return obj
                    elif isinstance(obj, (list, tuple)):
                        return [make_serializable(item) for item in obj]
                    elif isinstance(obj, dict):
                        return {key: make_serializable(value) for key, value in obj.items()}
                    else:
                        # For non-serializable objects (like HumanMessage), convert to string
                        obj_str = str(obj)
                        return obj_str[:200] + "..." if len(obj_str) > 200 else obj_str
                
                safe_output = make_serializable(result) if isinstance(result, dict) else {"result": make_serializable(result)}
                
                message_service.create_progress_message(owner_id, label, 'complete', f'Completed {label}', {
                    'node_output': safe_output
                })
            except Exception as e:
                logger.error(f"Failed to send COMPLETE progress for {label}: {e}")
        return result
    return _wrapped

def create_agent():
    """Create a SPARQL query generation agent."""
    try:
        # Create the graph with config
        workflow = StateGraph(SparqlAgentState, config_schema=SparqlAgentConfig)
        
        # Add nodes (updated for LangGraph v2)
        # Each node function will receive both state and config
        workflow.add_node("get_similar_queries", add_hooks(get_similar_queries_node, "get_similar_queries"))
        workflow.add_node("get_entity_matches", add_hooks(get_entity_matches_node, "get_entity_matches"))
        workflow.add_node("detect_clarification", add_hooks(detect_clarification_node, "detect_clarification"))
        workflow.add_node("generate_query", add_hooks(generate_query_node, "generate_query"))
        workflow.add_node("execute_query", add_hooks(execute_query_node, "execute_query"))
        workflow.add_node("refine_query", add_hooks(refine_query_node, "refine_query"))
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