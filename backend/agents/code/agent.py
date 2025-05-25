"""
Code generation agent using LangGraph.
"""

import logging
from langgraph.graph import Graph, StateGraph, START, END

from .state import CodeAgentState, CodeAgentConfig
from .handlers import (
    extract_analysis_request_node,
    process_refinement_request,
    search_code_examples_node,
    detect_clarification_node,
    process_clarification_response,
    generate_code_node,
    should_refine_code,
    refine_code_node,
    finalize_code_response_node
)

logger = logging.getLogger(__name__)


def format_clarification_question(state: CodeAgentState) -> str:
    """Format clarification questions with context for the user."""
    questions = state.clarification_questions or []
    
    if not questions:
        return "Could you please clarify your code generation request?"
    
    # Check if we have multiple questions
    if len(questions) > 1:
        # Format multiple questions with numbering
        formatted_text = "I need some clarification before generating your Python code:\n\n"
        for i, question in enumerate(questions):
            question_text = question.get("question", "")
            context = question.get("context", "")
            choices = question.get("choices", [])
            
            # Add question number
            formatted_text += f"**Question {i+1}:** {question_text}\n\n"
            
            # Format the choices if available
            if choices:
                formatted_text += "Options:\n" + "\n".join([f"- {choice}" for choice in choices])
                formatted_text += "\n\n"
            
            # Add context if available
            if context:
                formatted_text += f"_Context: {context}_\n\n"
            
            # Add a separator between questions
            if i < len(questions) - 1:
                formatted_text += "---\n\n"
        
        # If there are multiple questions, add guidance on how to answer
        formatted_text += "You can answer each question separately or provide all answers at once.\n"
        formatted_text += "For multiple answers, use the Next/Previous buttons to navigate between questions.\n"
        formatted_text += "When you've answered all questions, click 'Submit All Answers'."
        
        return formatted_text.strip()
    else:
        # Single question format (original behavior)
        question = questions[0]
        question_text = question.get("question", "")
        context = question.get("context", "")
        choices = question.get("choices", [])
        
        # Format the choices if available
        choices_text = ""
        if choices:
            choices_text = "\n\nOptions:\n" + "\n".join([f"- {choice}" for choice in choices])
        
        # Add context if available
        context_text = f"\n\n_Context: {context}_" if context else ""
        
        return f"{question_text}{choices_text}{context_text}"


def create_agent() -> Graph:
    """Create a code generation agent using LangGraph."""
    try:
        # Create the graph with config
        workflow = StateGraph(CodeAgentState, config_schema=CodeAgentConfig)
        
        # Add nodes (updated for LangGraph v2)
        # Each node function will receive both state and config
        workflow.add_node("extract_request", extract_analysis_request_node)
        workflow.add_node("process_refinement", process_refinement_request)
        workflow.add_node("search_examples", search_code_examples_node)
        workflow.add_node("detect_clarification", detect_clarification_node)
        workflow.add_node("generate_code", generate_code_node)
        workflow.add_node("process_clarification", process_clarification_response)
        workflow.add_node("refine_code", refine_code_node)
        
        # Enhanced conditional routing from start
        def route_initial_request(state):
            if state.clarification_responses:
                return "has_clarification"
            elif state.is_refinement:
                return "is_refinement" 
            else:
                return "new_request"
        
        workflow.add_conditional_edges(
            START,
            route_initial_request,
            {
                "has_clarification": "process_clarification",
                "is_refinement": "process_refinement",
                "new_request": "extract_request"
            }
        )
        
        # Refinement flow - after processing refinement, continue with code generation
        workflow.add_edge("process_refinement", "search_examples")
        
        # Main flow for new requests
        workflow.add_edge("extract_request", "search_examples")
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
                "content": format_clarification_question(state)
            }]
        })
        
        # After human responds, process the clarification and go back to generate_code
        workflow.add_edge("human_clarification_needed", END)
        workflow.add_edge("process_clarification", "generate_code")
        
        # Code generation and refinement flow
        workflow.add_conditional_edges(
            "generate_code",
            should_refine_code,
            {
                "true": "refine_code",
                "false": "finalize"
            }
        )
        workflow.add_edge("refine_code", "finalize")
        
        # Add finalize node that returns the final state
        workflow.add_node("finalize", finalize_code_response_node)
        workflow.add_edge("finalize", END)
        
        # Compile the graph
        return workflow.compile()
        
    except Exception as e:
        logger.error(f"Error creating code generation agent: {e}")
        raise 