"""
Code generation agent using LangGraph.
"""

import logging
from langgraph.graph import Graph, StateGraph, START, END
import json

from .state import CodeAgentState, CodeAgentConfig
from .handlers import (
    search_code_examples_node,
    detect_clarification_node,
    generate_code_node,
    execute_code_node,
    should_execute_code,
    should_refine_code,
    refine_code_node,
    finalize_code_response_node
)

logger = logging.getLogger(__name__)


def create_agent() -> Graph:
    """Create a code generation agent using LangGraph."""
    try:
        # Create the graph with config
        workflow = StateGraph(CodeAgentState, config_schema=CodeAgentConfig)
        
        # Add nodes (updated for LangGraph v2)
        # Each node function will receive both state and config
        workflow.add_node("search_examples", search_code_examples_node)
        workflow.add_node("detect_clarification", detect_clarification_node)
        workflow.add_node("generate_code", generate_code_node)
        workflow.add_node("execute_code", execute_code_node)
        workflow.add_node("refine_code", refine_code_node)
        
        # Direct start edge
        workflow.add_edge(START, "search_examples")
        
        # Main flow - user_input is used directly, so we start with searching examples  
        workflow.add_edge("search_examples", "detect_clarification")
        
        # Add conditional edge from detect_clarification based on needs_clarification
        workflow.add_conditional_edges(
            "detect_clarification",
            lambda state: "true" if state.needs_clarification else "false",
            {
                "true": "human_clarification_needed",
                "false": "generate_code"
            }
        )
        
        # Human clarification needed - this is a special node that signals the agent to ask the user
        workflow.add_node("human_clarification_needed", lambda state: {
            "messages": (state.messages or []) + [{
                "role": "assistant",
                "content": "I need some clarifications"
            }],
            "needs_clarification": True,
            "clarification_questions": state.clarification_questions,
            "conversation_id": state.conversation_id
        })
        
        # After human responds, process the clarification and go back to search_examples for context
        workflow.add_edge("human_clarification_needed", END)
        
        # Code generation, execution, and refinement flow
        workflow.add_conditional_edges(
            "generate_code",
            should_execute_code,
            {
                "true": "execute_code",
                "false": "finalize"  # Skip execution if code has issues
            }
        )
        
        # After execution, check if refinement is needed
        workflow.add_conditional_edges(
            "execute_code",
            should_refine_code,
            {
                "true": "refine_code",
                "false": "finalize"
            }
        )
        
        # After refinement, go back to generation
        workflow.add_edge("refine_code", "generate_code")
        
        # Add finalize node that returns the final state
        workflow.add_node("finalize", finalize_code_response_node)
        workflow.add_edge("finalize", END)
        
        # Compile the graph
        return workflow.compile()
        
    except Exception as e:
        logger.error(f"Error creating code generation agent: {e}")
        raise 