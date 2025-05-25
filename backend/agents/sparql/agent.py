"""
SPARQL query generation agent using LangGraph.
"""

import logging
from langgraph.graph import Graph, StateGraph, START, END
from typing import Dict, Any

from .state import SparqlAgentState, SparqlAgentConfig
from .handlers import (
    extract_user_query,
    process_refinement_request,
    get_similar_queries_node,
    get_entity_matches_node,
    detect_clarification_node,
    process_clarification_response,
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

def format_clarification_question(state: SparqlAgentState) -> str:
    """Format clarification questions with context for the user."""
    questions = state.clarification_questions or []
    
    if not questions:
        return "Could you please clarify your query?"
    
    # Check if we have multiple questions
    if len(questions) > 1:
        # Format multiple questions with numbering
        formatted_text = "I need some clarification before generating your SPARQL query:\n\n"
        for i, question in enumerate(questions):
            question_text = question.get("question", "") if isinstance(question, dict) else str(question)
            context = question.get("context", "") if isinstance(question, dict) else ""
            choices = question.get("choices", []) if isinstance(question, dict) else []
            
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
        question_text = question.get("question", "") if isinstance(question, dict) else str(question)
        context = question.get("context", "") if isinstance(question, dict) else ""
        choices = question.get("choices", []) if isinstance(question, dict) else []
        
        # Format the choices if available
        choices_text = ""
        if choices:
            choices_text = "\n\nOptions:\n" + "\n".join([f"- {choice}" for choice in choices])
        
        # Add context if available
        context_text = f"\n\n_Context: {context}_" if context else ""
        
        return f"{question_text}{choices_text}{context_text}"

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
            "content": format_clarification_question(state)
        }
        updated_messages = messages + [clarification_message]
        
        # Return the state updates
        result = {
            "messages": updated_messages,
            "needs_clarification": True,
            "clarification_questions": _get(state, "clarification_questions", [])
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
        workflow.add_node("extract_query", extract_user_query)
        workflow.add_node("process_refinement", process_refinement_request)
        workflow.add_node("get_similar_queries", get_similar_queries_node)
        workflow.add_node("get_entity_matches", get_entity_matches_node)
        workflow.add_node("detect_clarification", detect_clarification_node)
        workflow.add_node("generate_query", generate_query_node)
        workflow.add_node("process_clarification", process_clarification_response)
        workflow.add_node("execute_query", execute_query_node)
        workflow.add_node("refine_query", refine_query_node)
        workflow.add_node("human_clarification_needed", human_clarification_needed_node)
        
        # Enhanced conditional routing from start
        def route_initial_request(state):
            clarification_responses = _get(state, "clarification_responses")
            is_refinement = _get(state, "is_refinement")
            
            logger.info(f"=== WORKFLOW ROUTING ===")
            logger.info(f"clarification_responses: {bool(clarification_responses)}")
            logger.info(f"is_refinement: {is_refinement}")
            
            if clarification_responses:
                logger.info("Routing to: has_clarification")
                return "has_clarification"
            elif is_refinement:
                logger.info("Routing to: is_refinement")
                return "is_refinement" 
            else:
                logger.info("Routing to: new_query")
                return "new_query"
        
        workflow.add_conditional_edges(
            START,
            route_initial_request,
            {
                "has_clarification": "process_clarification",
                "is_refinement": "process_refinement",
                "new_query": "extract_query"
            }
        )
        
        # Refinement flow - after processing refinement, continue with query generation
        workflow.add_edge("process_refinement", "get_similar_queries")
        
        # Main flow for new queries
        workflow.add_edge("extract_query", "get_similar_queries")
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
        
        # After human responds, process the clarification and go back to generate_query
        workflow.add_edge("human_clarification_needed", END)
        workflow.add_edge("process_clarification", "generate_query")
        
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