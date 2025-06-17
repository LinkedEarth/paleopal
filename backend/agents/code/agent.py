"""
Code generation agent using LangGraph.
"""

import logging
from langgraph.graph import Graph, StateGraph, START, END
import json
import asyncio
from services.message_service import message_service

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

# Progress hook wrapper
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
            # Offload blocking work to default thread pool so event loop stays responsive
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

def create_agent() -> Graph:
    """Create a code generation agent using LangGraph."""
    try:
        # Create the graph with config
        workflow = StateGraph(CodeAgentState, config_schema=CodeAgentConfig)
        
        # Add nodes with progress hooks
        workflow.add_node("search_examples", add_hooks(search_code_examples_node, "search_examples"))
        workflow.add_node("detect_clarification", add_hooks(detect_clarification_node, "detect_clarification"))
        workflow.add_node("generate_code", add_hooks(generate_code_node, "generate_code"))
        workflow.add_node("execute_code", add_hooks(execute_code_node, "execute_code"))
        workflow.add_node("refine_code", add_hooks(refine_code_node, "refine_code"))
        
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