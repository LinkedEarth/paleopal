from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import logging

from schemas.message import Message, MessageCreate, MessageUpdate
from services.message_service import message_service

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

@router.put("/{message_id}", response_model=Message)
async def update_message(message_id: str, update_data: MessageUpdate):
    """Update a message with new results and metadata."""
    message = message_service.update_message(message_id, update_data)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return message

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
        
        # Clear variables if requested
        if clear_variables:
            from services.python_execution_service import python_execution_service
            # Save variables created by other messages by restoring their execution
            from services.conversation_service import conversation_service

            # Get conversation with messages
            conversation = conversation_service.get_conversation(message.conversation_id, include_messages=True)

            # Clear all variables first
            python_execution_service.clear_conversation_state(message.conversation_id)

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
                    python_execution_service.restore_conversation_state_from_messages(
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
            from services.service_manager import service_manager
            from config import DEFAULT_LLM_PROVIDER
            
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
            
            # Call the execute_query_node
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
            from services.service_manager import service_manager
            from config import DEFAULT_LLM_PROVIDER
            
            # Create minimal state for the node
            state = CodeAgentState(
                conversation_id=message.conversation_id,
                generated_code=new_generated_code
            )
            
            # Create config
            config = CodeAgentConfig(
                llm=service_manager.get_llm_provider(DEFAULT_LLM_PROVIDER)
            )
            
            # Call the execute_code_node
            node_result = execute_code_node(state, config)
            
            # Extract results from node output
            if node_result.get("execution_results"):
                execution_results = node_result["execution_results"]
            
            # Extract created variable names from execution results
            if execution_results:
                for result in execution_results:
                    if isinstance(result, dict) and result.get("type") == "execution_success":
                        var_summary = result.get("variable_summary", {})
                        result_variable_names.extend(var_summary.keys())
        
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
        
        return {
            "success": True,
            "message": updated_message,
            "variables_cleared": clear_variables,
            "old_variable_count": len(message.result_variable_names or []),
            "new_variable_count": len(result_variable_names)
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