"""
Multi-agent router for the paleoclimate analysis system.
"""

import logging
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List, AsyncGenerator
import json

from agents.base_agent import AgentRequest, AgentResponse, AgentStatus
from services.agent_registry import agent_registry
from agents.sparql.sparql_generation_agent import SparqlGenerationAgent
from agents.code import CodeGenerationAgent
from agents.workflow.workflow_manager_agent import WorkflowManagerAgent
from utils.agent_utils import (
    create_sparql_agent_with_config, 
    create_code_agent_with_config, 
    route_agent_request_with_custom_config
)

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
        raise

# Store for streaming connections
streaming_connections: Dict[str, Any] = {}

# Initialize agents when module loads
initialize_agents()

async def stream_agent_execution(request: AgentRequest) -> AsyncGenerator[str, None]:
    """
    Stream agent execution progress with intermediate node results.
    
    Yields:
        SSE-formatted messages with node execution updates
    """
    try:
        # Create a unique stream ID for this request
        stream_id = f"{request.agent_type}_{request.conversation_id or 'temp'}_{id(request)}"
        
        # Add to active connections
        streaming_connections[stream_id] = {
            "request": request,
            "active": True
        }
        
        # Send initial event
        yield f"data: {json.dumps({'type': 'start', 'message': f'Starting {request.agent_type} agent execution', 'request_id': stream_id})}\n\n"
        
        # Use the utility function to handle custom agent creation
        agent = None
        
        # Check if this is a SPARQL agent request with clarification config
        if request.agent_type == "sparql":
            enable_clarification = request.metadata.get("enable_clarification", True)
            clarification_threshold = request.metadata.get("clarification_threshold", "conservative")
            
            if enable_clarification != True or clarification_threshold != "conservative":
                agent = create_sparql_agent_with_config(enable_clarification, clarification_threshold)
        
        # Check if this is a code agent request with clarification config
        elif request.agent_type == "code":
            enable_clarification = request.metadata.get("enable_clarification", True)
            clarification_threshold = request.metadata.get("clarification_threshold", "conservative")
            
            if enable_clarification != True or clarification_threshold != "conservative":
                agent = create_code_agent_with_config(enable_clarification, clarification_threshold)
        
        # Fallback to registry agent
        if not agent:
            agent = agent_registry.get_agent(request.agent_type)
        
        if not agent:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Agent type {request.agent_type} not found'})}\n\n"
            return
        
        # Execute agent with streaming
        prev_complete_event = None
        prev_state_summary = {}
        
        if hasattr(agent, 'handle_request_streaming'):
            async for update in agent.handle_request_streaming(request):
                if stream_id not in streaming_connections or not streaming_connections[stream_id]["active"]:
                    logger.info(f"Streaming connection {stream_id} closed, stopping execution")
                    break

                if isinstance(update.get("response"), AgentResponse):
                    update["response"] = update["response"].model_dump()

                if prev_complete_event is not None:
                    yield f"data: {json.dumps(prev_complete_event)}\n\n"
                    prev_complete_event = None

                node_name = update.get('node_name')
                if node_name and node_name not in ("finalize", "finalize_response_node"):
                    start_event = {
                        'request_id': stream_id,
                        'agent_type': request.agent_type,
                        'type': 'node_start',
                        'node_name': node_name,
                        'state': prev_state_summary
                    }
                    yield f"data: {json.dumps(start_event)}\n\n"

                complete_event = {
                    'request_id': stream_id,
                    'agent_type': request.agent_type,
                    **update,
                    'state': update.get('current_state', {})
                }
                prev_complete_event = complete_event
                prev_state_summary = update.get('current_state', {})

            # END async for update

            # After the streaming generator is exhausted, make sure we flush the last pending
            # complete event (if any). Without this, the client never receives the final
            # 'complete' message when there are no further updates to trigger the flush,
            # leading to frontend errors such as "No final response received from streaming".
        
            # flush any remaining complete event (covers both streaming and non-streaming paths)
            if 'prev_complete_event' in locals() and prev_complete_event is not None:
                yield f"data: {json.dumps(prev_complete_event)}\n\n"
                prev_complete_event = None
        else:
            # Non-streaming agent fallback
            response = await agent.handle_request(request)
            yield f"data: {json.dumps({'type':'complete','response':response.model_dump()})}\n\n"
            return
        
    except Exception as e:
        logger.error(f"Error in streaming execution: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    finally:
        # Clean up connection
        if stream_id in streaming_connections:
            del streaming_connections[stream_id]

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
    Supports clarification configuration for SPARQL and code agents via metadata.
    """
    try:
        # Use the utility function to handle custom agent creation
        response = await route_agent_request_with_custom_config(request)
        return response
    except Exception as e:
        logger.error(f"Error handling agent request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/request/stream")
async def handle_agent_request_streaming(request: AgentRequest):
    """
    Route a request to the appropriate agent with streaming updates.
    
    Returns a Server-Sent Events (SSE) stream of intermediate execution progress.
    """
    try:
        return StreamingResponse(
            stream_agent_execution(request), 
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "Content-Encoding": "identity",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
    except Exception as e:
        logger.error(f"Error handling streaming agent request: {e}", exc_info=True)
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
    Supports clarification configuration for SPARQL and code agents.
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
        
        # Use the utility function to handle custom agent creation
        response = await route_agent_request_with_custom_config(agent_request)
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