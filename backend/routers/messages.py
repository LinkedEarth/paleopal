"""
Message router for the PaleoPal API.
"""

import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from schemas.message import Message, MessageCreate, MessageUpdate
from services.message_service import message_service
from services.service_manager import service_manager
from services.conversation_service import conversation_service
from websocket_manager import websocket_manager
from config import DEFAULT_LLM_PROVIDER

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages", tags=["messages"])

@router.post("/", response_model=Message)
@router.post("", response_model=Message)  # Handle both /messages/ and /messages
async def create_message(message_data: MessageCreate):
    """Create a new message in a conversation."""
    try:
        message = message_service.create_message(message_data)
        return message
    except Exception as e:
        logger.error(f"Error creating message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{message_id}", response_model=Message)
async def get_message(message_id: str):
    """Get a single message by ID."""
    message = message_service.get_message(message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message

@router.put("/{message_id}")
async def update_message(message_id: str, update_data: MessageUpdate):
    """Update a message with new results and metadata."""
    # Convert MessageUpdate to the format expected by update_message_results
    update_kwargs = {}
    
    if update_data.generated_code is not None:
        update_kwargs["generated_code"] = update_data.generated_code
    if update_data.execution_results is not None:
        update_kwargs["execution_results"] = update_data.execution_results
    if update_data.result_variable_names is not None:
        update_kwargs["result_variable_names"] = update_data.result_variable_names
    if update_data.agent_metadata is not None:
        update_kwargs["agent_metadata"] = update_data.agent_metadata
    if update_data.similar_results is not None:
        update_kwargs["similar_results"] = update_data.similar_results
    if update_data.entity_matches is not None:
        update_kwargs["entity_matches"] = update_data.entity_matches
    if update_data.needs_clarification is not None:
        update_kwargs["needs_clarification"] = update_data.needs_clarification
    if update_data.clarification_questions is not None:
        update_kwargs["clarification_questions"] = update_data.clarification_questions
    if update_data.clarification_responses is not None:
        update_kwargs["clarification_responses"] = update_data.clarification_responses
    if update_data.metadata is not None:
        update_kwargs["metadata"] = update_data.metadata
    
    message = message_service.update_message_results(message_id, **update_kwargs)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Return in the format expected by frontend
    return {
        "success": True,
        "message": message
    }

@router.delete("/{message_id}")
async def delete_message(message_id: str):
    """Delete a message and all its progress messages."""
    success = message_service.delete_message(message_id)
    if not success:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"success": True}

@router.get("/conversation/{conversation_id}", response_model=List[Message])
async def get_conversation_messages(
    conversation_id: str, 
    include_progress: bool = Query(False, description="Include progress messages")
):
    """Get all messages for a conversation."""
    messages = message_service.get_conversation_messages(conversation_id, include_progress)
    return messages

@router.get("/progress/{owner_message_id}", response_model=List[Message])
async def get_progress_messages(owner_message_id: str):
    """Get progress messages for a specific owner message."""
    messages = message_service.get_progress_messages(owner_message_id)
    return messages

@router.post("/progress", response_model=Message)
async def create_progress_message(
    owner_message_id: str,
    node_name: str,
    phase: str,
    content: str = "",
    metadata: Optional[dict] = None
):
    """Create a progress message linked to an owner message."""
    try:
        message = message_service.create_progress_message(
            owner_message_id, node_name, phase, content, metadata
        )
        return message
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating progress message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/conversation/{conversation_id}/from/{from_sequence}")
async def delete_messages_from_sequence(conversation_id: str, from_sequence: int):
    """Delete messages from a specific sequence number onwards."""
    deleted_count = message_service.delete_messages_from_sequence(conversation_id, from_sequence)
    return {"deleted_count": deleted_count} 

# New endpoints for editing and re-executing code/SPARQL
@router.post("/{message_id}/save-edits")
async def save_edits(message_id: str, request_data: dict):
    """
    Save edited code/SPARQL without executing it.
    
    Request body:
    {
        "generated_code": "edited Python code",  // for code agents
        "generated_sparql": "edited SPARQL query"  // for SPARQL agents
    }
    """
    try:
        # Get the message
        message = message_service.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Extract request data
        new_generated_code = request_data.get("generated_code")
        new_generated_sparql = request_data.get("generated_sparql")
        
        # Validate that we have something to save
        if not new_generated_code and not new_generated_sparql:
            raise HTTPException(status_code=400, detail="No code or SPARQL provided to save")
        
        # Prepare update data
        update_data = {}
        
        # Handle SPARQL agent editing
        if message.agent_type == "sparql" and new_generated_sparql:
            logger.info("Saving edited SPARQL query")
            # For SPARQL agents, update the agent_metadata with the new query
            existing_metadata = message.agent_metadata or {}
            existing_metadata["generated_sparql"] = new_generated_sparql
            update_data["agent_metadata"] = existing_metadata
            
        # Handle Code agent editing
        elif message.agent_type == "code" and new_generated_code:
            logger.info("Saving edited code")
            update_data["generated_code"] = new_generated_code
            
        else:
            raise HTTPException(status_code=400, detail="Invalid agent type or content for saving")
        
        # Update the message using the message service
        updated_message = message_service.update_message_results(
            message_id=message_id,
            **update_data
        )
        
        if not updated_message:
            raise HTTPException(status_code=500, detail="Failed to save edits")
        
        return {
            "success": True,
            "message": updated_message,
            "saved_content": new_generated_code or new_generated_sparql
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving edits: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{message_id}/edit-and-execute")
async def edit_and_execute_code(message_id: str, request_data: dict):
    """
    Edit and re-execute generated code/SPARQL by calling the appropriate agent nodes.
    
    Request body:
    {
        "generated_code": "edited Python code",  // for code agents
        "generated_sparql": "edited SPARQL query",  // for SPARQL agents
        "clear_variables": false  // optional, whether to clear previous variables
    }
    """
    try:
        # Get the message
        message = message_service.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Extract request data
        new_generated_code = request_data.get("generated_code")
        new_generated_sparql = request_data.get("generated_sparql")
        clear_variables = request_data.get("clear_variables", False)
        
        # Clear execution state if requested
        if clear_variables:
            execution_service = service_manager.get_execution_service()
            execution_service.clear_conversation_state(message.conversation_id)
            logger.info(f"Cleared execution state for conversation {message.conversation_id}")
            
            # Rebuild execution state from remaining messages
            # Get conversation with messages
            conversation = conversation_service.get_conversation(message.conversation_id, include_messages=True)

            # Determine messages to replay (exclude current message and progress msgs)
            remaining_messages = []
            if conversation and conversation.messages:
                remaining_messages = [
                    m for m in conversation.messages
                    if m.id != message_id and not m.is_node_progress
                ]

            # Restore state by re-executing remaining messages in order
            if remaining_messages:
                try:
                    execution_service.restore_conversation_state_from_messages(
                        message.conversation_id,
                        remaining_messages
                    )
                    logger.info(
                        f"Restored execution state with {len(remaining_messages)} prior messages after clearing"
                    )
                except Exception as e:
                    logger.warning(f"Failed to restore conversation state: {e}")
        
        # Initialize result variables
        execution_results = []
        result_variable_names = []
        agent_metadata = message.agent_metadata or {}
        
        # Handle SPARQL agent editing - call execute_query_node
        if message.agent_type == "sparql" and new_generated_sparql:
            logger.info("Calling SPARQL agent execute_query_node for edited query")
            
            # Import SPARQL agent components
            from agents.sparql.state import SparqlAgentState, SparqlAgentConfig
            from agents.sparql.handlers import execute_query_node
            
            # Create minimal state for the node
            state = SparqlAgentState(
                conversation_id=message.conversation_id,
                generated_code=new_generated_sparql,  # SPARQL query goes in generated_code
                metadata={"enable_execution": True},
                result_variable_names=message.result_variable_names or []
            )
            
            # Create config
            config = SparqlAgentConfig(
                llm=service_manager.get_llm_provider(DEFAULT_LLM_PROVIDER),
                sparql_service=service_manager.get_sparql_service()
            )
            
            # Check if async execution is requested
            async_execution = request_data.get('async_execution', True)  # Default to async
            
            # SPARQL execution - use synchronous execution for now
            # (async SPARQL execution not yet implemented in isolated executor)
            node_result = execute_query_node(state, config)
            
            # Extract results from node output
            if node_result.get("execution_results"):
                execution_results = node_result["execution_results"]
            if node_result.get("result_variable_names"):
                result_variable_names = node_result["result_variable_names"]
            if node_result.get("agent_metadata"):
                agent_metadata.update(node_result["agent_metadata"])
            
            # Use the Python code generated by the node
            new_generated_code = node_result.get("generated_code", "")
            
        # Handle Code agent editing - call execute_code_node
        elif message.agent_type == "code" and new_generated_code:
            logger.info("Calling Code agent execute_code_node for edited code")
            
            # Import Code agent components
            from agents.code.state import CodeAgentState, CodeAgentConfig
            from agents.code.handlers import execute_code_node
            
            # Create minimal state for the node
            state = CodeAgentState(
                conversation_id=message.conversation_id,
                generated_code=new_generated_code
            )
            
            # Create config
            config = CodeAgentConfig(
                llm=service_manager.get_llm_provider(DEFAULT_LLM_PROVIDER)
            )
            
            # Check if async execution is requested
            async_execution = request_data.get('async_execution', True)  # Default to async
            
            if async_execution:
                # Use async execution service
                
                def update_callback(execution_update):
                    """Callback to send WebSocket updates and update message on completion."""
                    try:
                        # Create a safe variable summary for WebSocket (avoid circular references)
                        variables_summary = {}
                        raw_variables = execution_update.get("variables", {})
                        for name, value in raw_variables.items():
                            try:
                                # Only include simple, serializable information
                                var_type = type(value).__name__
                                if isinstance(value, (str, int, float, bool, list, dict)):
                                    # For simple types, include the actual value
                                    variables_summary[name] = {"type": var_type, "value": value}
                                else:
                                    # For complex objects, just include type and basic info
                                    variables_summary[name] = {
                                        "type": var_type,
                                        "description": f"{var_type} object"
                                    }
                            except Exception:
                                # If anything fails, just include the name and type
                                variables_summary[name] = {
                                    "type": type(value).__name__ if hasattr(value, '__class__') else "unknown",
                                    "description": "Complex object"
                                }
                        
                        # Send execution status update via WebSocket
                        websocket_manager.send_to_conversation(
                            message.conversation_id,
                            {
                                "type": "execution_update",
                                "execution_id": execution_update.get("execution_id"),
                                "message_id": message_id,
                                "status": execution_update.get("status"),
                                "output": execution_update.get("output", ""),
                                "error": execution_update.get("error", ""),
                                "execution_time": execution_update.get("execution_time", 0),
                                "plots": execution_update.get("plots", []),
                                "variables": variables_summary,
                                "agent_type": "code"
                            }
                        )
                        
                        # Update message in database when execution completes (success or failure)
                        if execution_update.get("status") in ['completed', 'error', 'failed', 'cancelled']:
                            try:
                                # Format execution results for message update
                                result_entry = {
                                    "type": "execution_success" if execution_update.get("status") == "completed" else "execution_error",
                                    "output": execution_update.get("output", ""),
                                    "error": execution_update.get("error", ""),
                                    "execution_time": execution_update.get("execution_time", 0),
                                    "plots": execution_update.get("plots", []),
                                    "execution_id": execution_update.get("execution_id")
                                }
                                # Include variable_summary for successful executions
                                if execution_update.get("status") == "completed":
                                    # Get variable summary from the execution service
                                    execution_service = service_manager.get_execution_service()
                                    var_summary = execution_service.get_variable_summary(message.conversation_id)
                                    result_entry["variable_summary"] = var_summary
                                
                                execution_results = [result_entry]
                                
                                # Update the message with execution results
                                updated_message = message_service.update_message_results(
                                    message_id=message_id,
                                    generated_code=new_generated_code,
                                    execution_results=execution_results,
                                    result_variable_names=list(execution_update.get("variables", {}).keys()),
                                    agent_metadata={"execution_id": execution_update.get("execution_id")}
                                )
                                
                                if updated_message:
                                    logger.info(f"✅ Updated message {message_id} with async execution results")
                                    
                                    # Send message update via WebSocket
                                    websocket_manager.send_to_conversation(
                                        message.conversation_id,
                                        {
                                            "type": "message_updated",
                                            "message": updated_message.dict() if hasattr(updated_message, 'dict') else updated_message
                                        }
                                    )
                                else:
                                    logger.error(f"❌ Failed to update message {message_id} with async execution results")
                                    
                            except Exception as e:
                                logger.error(f"❌ Error updating message with async execution results: {e}")
                        
                    except Exception as e:
                        logger.error(f"Error in execution update callback: {e}")
                
                # Generate execution ID
                execution_id = str(uuid.uuid4())
                
                # Start async execution using the simplified interface
                execution_service = service_manager.get_execution_service()
                execution_id = execution_service.submit_execution(
                    code=new_generated_code,
                    conversation_id=message.conversation_id,
                    execution_id=execution_id,
                    update_callback=update_callback
                )
                
                logger.info(f"🚀 Started async code execution {execution_id} for message {message_id}")
                
                return {
                    "success": True,
                    "message": message,
                    "execution_id": execution_id,
                    "async": True,
                    "status": "started",
                    "agent_type": "code"
                }
            else:
                # Synchronous execution (fallback)
                node_result = execute_code_node(state, config)
            
            # Extract results from node output
            if node_result.get("execution_results"):
                execution_results = node_result["execution_results"]
                if node_result.get("result_variable_names"):
                    result_variable_names = node_result["result_variable_names"]
        
        else:
            raise HTTPException(status_code=400, detail="No valid code or SPARQL provided for editing")
        
        # Update the message with new results using update_message_results
        updated_message = message_service.update_message_results(
            message_id=message_id,
            generated_code=new_generated_code,
            execution_results=execution_results,
            result_variable_names=result_variable_names,
            agent_metadata=agent_metadata
        )
        
        if not updated_message:
            raise HTTPException(status_code=500, detail="Failed to update message")
        
        # Extract execution ID if available from the most recent execution result
        execution_id = None
        if execution_results:
            for result in reversed(execution_results):  # Check most recent first
                if isinstance(result, dict) and result.get("execution_id"):
                    execution_id = result["execution_id"]
                    break

        logger.info(f"🆔 Returning execution ID: {execution_id} for message {message_id}")
        
        return {
            "success": True,
            "message": updated_message,
            "variables_cleared": clear_variables,
            "old_variable_count": len(message.result_variable_names or []),
            "new_variable_count": len(result_variable_names),
            "execution_id": execution_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error editing and executing code: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{message_id}/index-as-learned")
async def index_as_learned(message_id: str, request_data: dict):
    """
    Index generated code/SPARQL as learned content.
    
    Request body:
    {
        "user_prompt": "original user prompt",
        "clarifications": ["clarification 1", "clarification 2"],  // optional
        "tags": ["tag1", "tag2"],  // optional
        "description": "custom description"  // optional
    }
    """
    try:
        # Get the message
        message = message_service.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Extract request data
        user_prompt = request_data.get("user_prompt", "")
        clarifications = request_data.get("clarifications", [])
        tags = request_data.get("tags", [])
        description = request_data.get("description", "")
        
        if not user_prompt:
            raise HTTPException(status_code=400, detail="user_prompt is required")
        
        # Import indexing services
        from libraries.qdrant_config import get_qdrant_manager
        import uuid
        from datetime import datetime
        
        qdrant_manager = get_qdrant_manager()
        indexed_items = []
        
        # Index SPARQL if available (SPARQL agent)
        if message.agent_type == "sparql" and message.agent_metadata and message.agent_metadata.get("generated_sparql"):
            sparql_query = message.agent_metadata["generated_sparql"]
            
            # Create context text for indexing
            context_parts = [user_prompt]
            if clarifications:
                context_parts.append("Clarifications: " + "; ".join(clarifications))
            if description:
                context_parts.append("Description: " + description)
            
            context_text = "\n\n".join(context_parts)
            
            # Create document for learned_sparql collection
            sparql_doc = {
                "id": str(uuid.uuid4()),
                "text": f"{context_text}\n\nSPARQL Query:\n{sparql_query}",
                "content": context_text,
                "sparql_query": sparql_query,
                "user_prompt": user_prompt,
                "clarifications": clarifications,
                "tags": tags,
                "description": description,
                "agent_type": "sparql",
                "original_message_id": message_id,
                "conversation_id": message.conversation_id,
                "result_count": message.agent_metadata.get("result_count", 0),
                "endpoint": message.agent_metadata.get("endpoint", ""),
                "indexed_at": datetime.utcnow().isoformat(),
                "query_type": "learned",
                "source": "user_interaction"
            }
            
            # Create learned_sparql collection if it doesn't exist
            collection_name = "learned_sparql"
            if not qdrant_manager.create_collection(collection_name, force_recreate=False):
                logger.warning(f"Collection {collection_name} may already exist")
            
            # Index the document
            indexed_count = qdrant_manager.index_documents(
                collection_name=collection_name,
                documents=[sparql_doc],
                text_field="text"
            )
            
            if indexed_count > 0:
                indexed_items.append({
                    "type": "sparql",
                    "collection": collection_name,
                    "query_length": len(sparql_query)
                })
        
        # Index Python code if available (Code agent only, not SPARQL agent)
        if message.generated_code and message.agent_type != "sparql":
            python_code = message.generated_code
            
            # Create context text for indexing
            context_parts = [user_prompt]
            if clarifications:
                context_parts.append("Clarifications: " + "; ".join(clarifications))
            if description:
                context_parts.append("Description: " + description)
            
            context_text = "\n\n".join(context_parts)
            
            # Create document for learned_code collection
            code_doc = {
                "id": str(uuid.uuid4()),
                "text": f"{context_text}\n\nPython Code:\n{python_code}",
                "content": context_text,
                "code": python_code,
                "user_prompt": user_prompt,
                "clarifications": clarifications,
                "tags": tags,
                "description": description,
                "agent_type": message.agent_type,
                "original_message_id": message_id,
                "conversation_id": message.conversation_id,
                "indexed_at": datetime.utcnow().isoformat(),
                "code_type": "learned",
                "source": "user_interaction"
            }
            
            # Add execution results summary if available
            if message.execution_results:
                successful_executions = [r for r in message.execution_results if isinstance(r, dict) and r.get("type") == "execution_success"]
                code_doc["execution_successful"] = len(successful_executions) > 0
                code_doc["variable_count"] = len(message.result_variable_names or [])
            
            # Classify code type
            code_lower = python_code.lower()
            if "import matplotlib" in code_lower or "plt." in code_lower:
                code_doc["library"] = "matplotlib"
                code_doc["code_category"] = "visualization"
            elif "import pandas" in code_lower or "pd." in code_lower:
                code_doc["library"] = "pandas"
                code_doc["code_category"] = "data_analysis"
            elif "sparqlwrapper" in code_lower or "sparql" in code_lower:
                code_doc["library"] = "sparql"
                code_doc["code_category"] = "data_retrieval"
            else:
                code_doc["library"] = "general"
                code_doc["code_category"] = "general"
            
            # Create learned_code collection if it doesn't exist
            collection_name = "learned_code"
            if not qdrant_manager.create_collection(collection_name, force_recreate=False):
                logger.warning(f"Collection {collection_name} may already exist")
            
            # Index the document
            indexed_count = qdrant_manager.index_documents(
                collection_name=collection_name,
                documents=[code_doc],
                text_field="text"
            )
            
            if indexed_count > 0:
                indexed_items.append({
                    "type": "code",
                    "collection": collection_name,
                    "code_length": len(python_code),
                    "library": code_doc["library"],
                    "category": code_doc["code_category"]
                })
        
        if not indexed_items:
            raise HTTPException(status_code=400, detail="No code or SPARQL found to index")
        
        return {
            "success": True,
            "indexed_items": indexed_items,
            "message_id": message_id,
            "user_prompt": user_prompt,
            "clarifications_count": len(clarifications),
            "tags_count": len(tags)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error indexing as learned: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 