"""
Multi-agent router for the paleoclimate analysis system.
"""

import logging
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Dict, Any, List, AsyncGenerator
import json
import uuid
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor

from agents.base_agent import AgentRequest, AgentResponse, AgentStatus
# Import schemas (these are safe)
from schemas.conversation import ConversationCreate
from schemas.message import MessageCreate

# Import base classes and utils (these are safe)
from agents.base_agent import AgentRequest, AgentResponse, AgentStatus
from utils.agent_utils import (
    create_sparql_agent_with_config, 
    create_code_agent_with_config, 
    route_agent_request_with_custom_config,
    create_workflow_agent_with_config
)

# Delayed imports for services to avoid initialization in child processes
# These will be imported when needed

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/agents", tags=["agents"])

# Thread pool for non-blocking execution
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent_exec")

# Initialize agents on startup
def initialize_agents():
    """Initialize and register all available agents."""
    try:
        # Import services only when needed (in main process)
        from services.agent_registry import agent_registry
        from agents.sparql.sparql_generation_agent import SparqlGenerationAgent
        from agents.code import CodeGenerationAgent
        from agents.workflow.workflow_generation_agent import WorkflowGenerationAgent
        
        # Register SPARQL agent with default settings
        sparql_agent = SparqlGenerationAgent()
        agent_registry.register_agent(sparql_agent)
        
        # Register Code Generation agent
        code_agent = CodeGenerationAgent()
        agent_registry.register_agent(code_agent)
        
        # Register Workflow Generation agent
        workflow_agent = WorkflowGenerationAgent()
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
        
        # Check if this is a workflow agent request
        elif request.agent_type == "workflow_generation":
            # Always use the new LangGraph workflow agent for better progress tracking
            logger.info("Creating LangGraph workflow agent for streaming")
            agent = create_workflow_agent_with_config()
        
        # Fallback to registry agent
        if not agent:
            from services.agent_registry import agent_registry
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


@router.get("/executions")
async def get_active_executions():
    """Get all active executions across all agents."""
    try:
        # Import services when needed
        from services.service_manager import service_manager
        execution_service = service_manager.get_execution_service()
        
        # Get active executions from execution service
        active_executions = execution_service.get_active_executions()
        
        # Format for response
        execution_list = []
        for execution_id, execution in active_executions.items():
            execution_list.append({
                "execution_id": execution_id,
                "conversation_id": execution.conversation_id,
                "message_id": execution.message_id,
                "status": execution.status.value,
                "started_at": execution.started_at.isoformat(),
                "progress": execution.progress
            })
        
        return {
            "active_executions": execution_list,
            "total_count": len(execution_list)
        }
    except Exception as e:
        logger.error(f"Error getting active executions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/executions/{conversation_id}")
async def get_conversation_executions(conversation_id: str):
    """Get active executions for a specific conversation."""
    try:
        # Import services when needed
        from services.service_manager import service_manager
        execution_service = service_manager.get_execution_service()
        
        # Get active executions for conversation from execution service
        active_executions = execution_service.get_active_executions(conversation_id)
        
        # Format for response
        execution_list = []
        for execution_id, execution in active_executions.items():
            execution_list.append({
                "execution_id": execution_id,
                "conversation_id": execution.conversation_id,
                "message_id": execution.message_id,
                "status": execution.status.value,
                "started_at": execution.started_at.isoformat(),
                "progress": execution.progress
            })
        
        return {
            "conversation_id": conversation_id,
            "active_executions": execution_list,
            "total_count": len(execution_list)
        }
    except Exception as e:
        logger.error(f"Error getting conversation executions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(execution_id: str):
    """Cancel a specific execution by ID."""
    try:
        # Import services when needed
        from services.service_manager import service_manager
        execution_service = service_manager.get_execution_service()
        
        logger.info(f"🛑 API request to cancel execution: {execution_id}")
        
        # Use execution service for cancellation
        cancelled = execution_service.cancel_execution(execution_id)
        
        if cancelled:
            logger.info(f"✅ Successfully cancelled execution {execution_id}")
            return {"success": True, "message": f"Execution {execution_id} cancelled"}
        else:
            logger.warning(f"⚠️ Execution {execution_id} not found or could not be cancelled")
            return {"success": False, "message": f"Execution {execution_id} not found or already completed"}
            
    except Exception as e:
        logger.error(f"❌ Error cancelling execution {execution_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/executions/cancel-conversation/{conversation_id}")
async def cancel_conversation_executions(conversation_id: str):
    """Cancel all executions for a conversation."""
    try:
        # Import services when needed
        from services.service_manager import service_manager
        execution_service = service_manager.get_execution_service()
        
        logger.info(f"🛑 API request to cancel all executions for conversation: {conversation_id}")
        
        # Use execution service for conversation cancellation
        cancelled_count = execution_service.cancel_conversation_executions(conversation_id)
        
        logger.info(f"✅ Cancelled {cancelled_count} executions for conversation {conversation_id}")
        return {
            "success": True,
            "message": f"Cancelled {cancelled_count} executions for conversation {conversation_id}",
            "cancelled_count": cancelled_count
        }
        
    except Exception as e:
        logger.error(f"❌ Error cancelling conversation executions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/executions/{execution_id}")
async def get_execution_status(execution_id: str):
    """Get the status of a specific execution."""
    try:
        # Import services when needed
        from services.service_manager import service_manager
        execution_service = service_manager.get_execution_service()
        
        execution = execution_service.get_execution(execution_id)
        
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        
        return execution.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting execution status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_agent_stats():
    """Get agent execution statistics."""
    try:
        # Import services when needed
        from services.service_manager import service_manager
        execution_service = service_manager.get_execution_service()
        
        stats = execution_service.get_state_statistics()
        return stats
    except Exception as e:
        logger.error(f"Error getting agent stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
@router.get("")  # Handle both /agents/ and /agents
async def list_agents():
    """List all available agents and their capabilities."""
    try:
        # Import services when needed
        from services.agent_registry import agent_registry
        
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
        # Import services when needed
        from services.agent_registry import agent_registry
        
        capabilities = agent_registry.get_capabilities()
        return {"capabilities": capabilities}
    except Exception as e:
        logger.error(f"Error getting capabilities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_agent_status():
    """Get status information for all agents."""
    try:
        # Import services when needed
        from services.agent_registry import agent_registry
        
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

@router.post("/request/async")
async def handle_agent_request_async(request: AgentRequest, background_tasks: BackgroundTasks):
    """
    Route a request to the appropriate agent asynchronously.
    
    Returns immediately while the agent runs in the background.
    The UI can poll for messages to see progress and results.
    """
    try:
        # Validate conversation exists or create one if needed
        if not request.conversation_id:
            return {"error": "conversation_id is required for async requests"}
        
        # Add the agent execution as a background task
        background_tasks.add_task(execute_agent_async, request)
        
        return {
            "status": "accepted",
            "message": "Agent request queued for execution",
            "conversation_id": request.conversation_id,
            "poll_endpoint": f"/messages/conversation/{request.conversation_id}"
        }
        
    except Exception as e:
        logger.error(f"Error queueing async agent request: {e}", exc_info=True)
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

@router.post("/chat")
async def chat(request_data: Dict[str, Any]):
    """
    Plain chat endpoint without persistence. Accepts messages array and returns assistant reply.
    Body example:
    {
      "messages": [{"role":"user","content":"..."}],
      "llm_provider": "openai",
      "model": "gpt-4o"
    }
    """
    try:
        from services.service_manager import service_manager
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

        messages = request_data.get("messages", [])
        provider = request_data.get("llm_provider") or request_data.get("provider") or "openai"
        model = request_data.get("model")

        # Get LLM
        llm = service_manager.get_llm_provider(provider=provider, model=model)

        # Convert to LangChain messages
        lc_messages = []
        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            if not content:
                continue
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))

        # Fallback if empty
        if not lc_messages:
            raise HTTPException(status_code=400, detail="messages array is required")

        # Call model
        response_text = llm._call(lc_messages)
        return {"role": "assistant", "content": response_text}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /agents/chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{agent_type}")
async def get_agent_info(agent_type: str):
    """Get information about a specific agent."""
    try:
        # Import services when needed
        from services.agent_registry import agent_registry
        
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
        # Import services when needed
        from services.agent_registry import agent_registry
        
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
        # Import services when needed
        from services.agent_registry import agent_registry
        
        agents = agent_registry.find_agents_with_capability(capability_name)
        return {
            "capability": capability_name,
            "agents": agents
        }
    except Exception as e:
        logger.error(f"Error finding agents with capability: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def execute_agent_async(request: AgentRequest):
    """Execute agent request in the background."""
    try:
        logger.info(f"Starting async execution for {request.agent_type} agent")
        
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
        
        # Check if this is a workflow agent request
        elif request.agent_type == "workflow_generation":
            # Always use the new LangGraph workflow agent for better progress tracking
            logger.info("Creating LangGraph workflow agent for streaming")
            agent = create_workflow_agent_with_config()
        
        # Fallback to registry agent
        if not agent:
            from services.agent_registry import agent_registry
            agent = agent_registry.get_agent(request.agent_type)
        
        if not agent:
            logger.error(f"Agent type {request.agent_type} not found")
            return
        
        # Check if agent supports streaming for progress tracking
        if hasattr(agent, 'handle_request_streaming'):
            logger.info(f"Using streaming execution for progress tracking")
            # Execute with streaming but don't stream to client - just process progress internally
            user_message_id = None
            
            async for update in agent.handle_request_streaming(request):
                if update.get("type") == "complete":
                    # Handle AgentResponse object properly - use attribute access not dict access
                    response = update.get('response')
                    if response and hasattr(response, 'status'):
                        logger.info(f"Async streaming execution completed with status: {response.status}")
                    else:
                        logger.info(f"Async streaming execution completed")
                    break
                # Progress messages are automatically created by the streaming handler
                # We just need to process the stream without sending to client
                logger.debug(f"Progress update: {update.get('type')} - {update.get('node_name')}")
        else:
            # Fallback to regular execution without progress tracking
            logger.info(f"Using regular execution (no progress tracking)")
            response = await agent.handle_request(request)
            logger.info(f"Async execution completed for {request.agent_type} agent with status: {response.status}")
        
    except Exception as e:
        logger.error(f"Error in async agent execution: {e}", exc_info=True)
        # The agent should have created error messages in the database already
        # via the _create_response_from_state method 