"""
Multi-agent router for the paleoclimate analysis system.
"""

import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from agents.base_agent import AgentRequest, AgentResponse, AgentStatus
from services.agent_registry import agent_registry
from agents.sparql.sparql_generation_agent import SparqlGenerationAgent
from agents.code import CodeGenerationAgent
from agents.workflow.workflow_manager_agent import WorkflowManagerAgent

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/agents", tags=["agents"])

# Initialize agents on startup
def initialize_agents():
    """Initialize and register all available agents."""
    try:
        # Register SPARQL agent with default settings
        sparql_agent = SparqlGenerationAgent()
        agent_registry.register_agent(sparql_agent)
        
        # Register Code Generation agent
        code_agent = CodeGenerationAgent()
        agent_registry.register_agent(code_agent)
        
        # Register Workflow Manager agent
        workflow_agent = WorkflowManagerAgent()
        agent_registry.register_agent(workflow_agent)
        
        logger.info("All agents initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing agents: {e}")

def create_sparql_agent_with_config(enable_clarification: bool = True, clarification_threshold: str = "conservative"):
    """Create a SPARQL agent with specific clarification configuration."""
    return SparqlGenerationAgent(
        enable_clarification=enable_clarification,
        clarification_threshold=clarification_threshold
    )

# Initialize agents when module loads
initialize_agents()

@router.get("/")
async def list_agents():
    """List all available agents and their capabilities."""
    try:
        agents = agent_registry.list_agents()
        return {
            "agents": agents,
            "total_count": len(agents)
        }
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/capabilities")
async def get_capabilities():
    """Get all capabilities across all agents."""
    try:
        capabilities = agent_registry.get_capabilities()
        return {"capabilities": capabilities}
    except Exception as e:
        logger.error(f"Error getting capabilities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_agent_status():
    """Get status information for all agents."""
    try:
        status = agent_registry.get_agent_status()
        return {"agent_status": status}
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/request")
async def handle_agent_request(request: AgentRequest):
    """
    Route a request to the appropriate agent.
    
    This is the main entry point for multi-agent interactions.
    Supports clarification configuration for SPARQL agents via metadata.
    """
    try:
        logger.info(f"Handling agent request: {request.agent_type}.{request.capability}")
        
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
        
        # Route the request through the registry (default behavior)
        response = await agent_registry.route_request(request)
        
        return response
    except Exception as e:
        logger.error(f"Error handling agent request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{agent_type}")
async def get_agent_info(agent_type: str):
    """Get information about a specific agent."""
    try:
        agent = agent_registry.get_agent(agent_type)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_type}' not found")
        
        return agent.get_info()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{agent_type}/capabilities")
async def get_agent_capabilities(agent_type: str):
    """Get capabilities for a specific agent."""
    try:
        agent = agent_registry.get_agent(agent_type)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_type}' not found")
        
        return {
            "agent_type": agent_type,
            "capabilities": [
                {
                    "name": cap.name,
                    "description": cap.description,
                    "requires_conversation": cap.requires_conversation,
                    "input_schema": cap.input_schema,
                    "output_schema": cap.output_schema
                }
                for cap in agent.capabilities.values()
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent capabilities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{agent_type}/{capability}")
async def call_agent_capability(
    agent_type: str, 
    capability: str,
    request_data: Dict[str, Any]
):
    """
    Call a specific capability of an agent.
    
    This is a convenience endpoint for direct capability calls.
    Supports clarification configuration for SPARQL agents.
    """
    try:
        # Extract common fields
        user_input = request_data.get("user_input", "")
        conversation_id = request_data.get("conversation_id")
        context = request_data.get("context", {})
        notebook_context = request_data.get("notebook_context", {})
        metadata = request_data.get("metadata", {})
        
        # Create agent request
        agent_request = AgentRequest(
            agent_type=agent_type,
            capability=capability,
            conversation_id=conversation_id,
            user_input=user_input,
            context=context,
            notebook_context=notebook_context,
            metadata=metadata
        )
        
        # Check if this is a SPARQL agent request with clarification config
        if agent_type == "sparql":
            # Extract clarification configuration from metadata
            enable_clarification = metadata.get("enable_clarification", True)
            clarification_threshold = metadata.get("clarification_threshold", "conservative")
            
            # Create a SPARQL agent with the specified configuration
            if enable_clarification != True or clarification_threshold != "conservative":
                logger.info(f"Creating SPARQL agent with custom clarification config: enable={enable_clarification}, threshold={clarification_threshold}")
                sparql_agent = create_sparql_agent_with_config(enable_clarification, clarification_threshold)
                response = await sparql_agent.handle_request(agent_request)
                return response
        
        # Route the request through the registry (default behavior)
        response = await agent_registry.route_request(agent_request)
        
        return response
    except Exception as e:
        logger.error(f"Error calling agent capability: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/find/capability/{capability_name}")
async def find_agents_with_capability(capability_name: str):
    """Find all agents that support a specific capability."""
    try:
        agents = agent_registry.find_agents_with_capability(capability_name)
        return {
            "capability": capability_name,
            "agents": agents
        }
    except Exception as e:
        logger.error(f"Error finding agents with capability: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 