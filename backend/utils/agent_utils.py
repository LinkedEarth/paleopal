"""
Agent utility functions for routing and creating custom agents.
"""

import logging
from typing import Dict, Any, Optional

from agents.base_agent import AgentRequest, AgentResponse, AgentStatus
from services.agent_registry import agent_registry
from agents.sparql.sparql_generation_agent import SparqlGenerationAgent
from agents.code import CodeGenerationAgent
# Remove the import to avoid circular dependency - import locally when needed
# from agents.workflow import WorkflowLangGraphAgent

logger = logging.getLogger(__name__)


def create_sparql_agent_with_config(enable_clarification: bool = True, clarification_threshold: str = "conservative"):
    """Create a SPARQL agent with specific clarification configuration."""
    return SparqlGenerationAgent(
        enable_clarification=enable_clarification,
        clarification_threshold=clarification_threshold
    )


def create_code_agent_with_config(enable_clarification: bool = True, clarification_threshold: str = "conservative"):
    """Create a code generation agent with specific clarification configuration."""
    return CodeGenerationAgent(
        enable_clarification=enable_clarification,
        clarification_threshold=clarification_threshold
    )


def create_workflow_agent_with_config(enable_clarification: bool = True, clarification_threshold: str = "conservative"):
    """Create a workflow agent with specific clarification configuration."""
    # Import locally to avoid circular dependency
    from agents.workflow import WorkflowLangGraphAgent
    return WorkflowLangGraphAgent()


async def route_agent_request_with_custom_config(request: AgentRequest) -> AgentResponse:
    """
    Route a request to the appropriate agent, creating custom agents for clarification config.
    
    This function handles the logic for creating custom agents based on clarification
    settings in the request metadata, avoiding circular imports.
    """
    try:
        logger.info(f"Routing agent request: {request.agent_type}.{request.capability}")
        
        # Check if this is a SPARQL agent request with clarification config
        if request.agent_type == "sparql":
            # Extract clarification configuration from metadata
            enable_clarification = request.metadata.get("enable_clarification", True)
            clarification_threshold = request.metadata.get("clarification_threshold", "conservative")
            
            # Create a SPARQL agent with the specified configuration
            if enable_clarification != True or clarification_threshold != "conservative":
                logger.info(f"Creating SPARQL agent with custom clarification config: enable={enable_clarification}, threshold={clarification_threshold}")
                sparql_agent = create_sparql_agent_with_config(enable_clarification, clarification_threshold)
                response = await sparql_agent.handle_request(request)
                return response
        
        # Check if this is a code agent request with clarification config
        elif request.agent_type == "code":
            # Extract clarification configuration from metadata
            enable_clarification = request.metadata.get("enable_clarification", True)
            clarification_threshold = request.metadata.get("clarification_threshold", "conservative")
            
            # Create a code agent with the specified configuration
            if enable_clarification != True or clarification_threshold != "conservative":
                logger.info(f"Creating code agent with custom clarification config: enable={enable_clarification}, threshold={clarification_threshold}")
                code_agent = create_code_agent_with_config(enable_clarification, clarification_threshold)
                response = await code_agent.handle_request(request)
                return response
        
        # Check if this is a workflow agent request
        elif request.agent_type == "workflow_manager":
            # Always use the new LangGraph workflow agent for better progress tracking
            logger.info("Creating LangGraph workflow agent")
            workflow_agent = create_workflow_agent_with_config()
            response = await workflow_agent.handle_request(request)
            return response
        
        # Route the request through the registry (default behavior)
        response = await agent_registry.route_request(request)
        
        return response
    except Exception as e:
        logger.error(f"Error routing agent request: {e}", exc_info=True)
        return AgentResponse(
            status=AgentStatus.ERROR,
            message=f"Internal error: {str(e)}",
            result=None
        ) 