from fastapi import APIRouter, HTTPException
from typing import List

from schemas.conversation import Conversation, ConversationCreate, ConversationUpdate
from services.conversation_service import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])

@router.get("/", response_model=List[Conversation])
@router.get("", response_model=List[Conversation])  # Handle both /conversations/ and /conversations
def list_conversations():
    """Return list of conversations (metadata only, messages loaded separately)."""
    return conversation_service.list_conversations(include_messages=False)

@router.get("/{conv_id}", response_model=Conversation)
def get_conversation(conv_id: str):
    """Get a specific conversation by ID with all messages."""
    conv = conversation_service.get_conversation(conv_id, include_messages=True)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv

@router.post("/", response_model=Conversation)
@router.post("", response_model=Conversation)  # Handle both /conversations/ and /conversations
def create_conversation(conv_data: ConversationCreate):
    """Create a new conversation."""
    return conversation_service.create_conversation(conv_data)

@router.put("/{conv_id}", response_model=Conversation)
def update_conversation(conv_id: str, update_data: ConversationUpdate):
    """Update conversation metadata (not messages)."""
    conv = conversation_service.update_conversation(conv_id, update_data)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv

@router.delete("/{conv_id}")
def delete_conversation(conv_id: str):
    """Delete a conversation and all its messages."""
    if not conversation_service.delete_conversation(conv_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}

# Legacy endpoints for backward compatibility
@router.delete("/{conv_id}/messages/{message_index}")
def delete_message(conv_id: str, message_index: int):
    """Delete a specific message from a conversation by index (legacy endpoint)."""
    if not conversation_service.conversation_exists(conv_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if not conversation_service.delete_message(conv_id, message_index):
        raise HTTPException(status_code=400, detail="Invalid message index or message not found")
    
    return {"status": "message_deleted", "message_index": message_index}

@router.delete("/{conv_id}/messages/from/{from_index}")
def delete_messages_from_index(conv_id: str, from_index: int):
    """Delete all messages from a specific index onwards (legacy endpoint)."""
    if not conversation_service.conversation_exists(conv_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if not conversation_service.delete_messages_from_index(conv_id, from_index):
        raise HTTPException(status_code=400, detail="Invalid from_index or no messages to delete")
    
    return {"status": "messages_deleted", "from_index": from_index}

@router.get("/debug/database-state")
def get_database_state():
    """Debug endpoint to examine database state."""
    return conversation_service.debug_database_state()

@router.get("/debug/execution-states")
def get_execution_state_statistics():
    """Debug endpoint to examine Python execution state statistics."""
    from services.python_execution_service import python_execution_service
    return python_execution_service.get_state_statistics()

@router.delete("/debug/execution-states/{conversation_id}")
def clear_execution_state(conversation_id: str):
    """Debug endpoint to clear execution state for a specific conversation."""
    from services.python_execution_service import python_execution_service
    python_execution_service.clear_conversation_state(conversation_id)
    return {"message": f"Cleared execution state for conversation {conversation_id}"}

@router.post("/debug/execution-states/{conversation_id}/reset")
def reset_execution_state(conversation_id: str):
    """Debug endpoint to reset execution state for a specific conversation."""
    from services.python_execution_service import python_execution_service
    python_execution_service.reset_conversation_state(conversation_id)
    return {"message": f"Reset execution state for conversation {conversation_id}"}

@router.get("/{conversation_id}/export/notebook")
def export_conversation_as_notebook(conversation_id: str):
    """Export a conversation as a Jupyter notebook."""
    from services.notebook_export_service import notebook_export_service
    from fastapi.responses import JSONResponse
    
    try:
        # Export conversation to notebook format
        notebook_data = notebook_export_service.export_conversation_to_notebook(conversation_id)
        filename = notebook_export_service.get_notebook_filename(conversation_id)
        
        # Return notebook data with filename
        return JSONResponse(
            content={
                "notebook": notebook_data,
                "filename": filename,
                "conversation_id": conversation_id
            },
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export notebook: {str(e)}")

@router.get("/stats/count")
def get_conversation_stats():
    """Get conversation statistics."""
    return {
        "total_conversations": conversation_service.get_conversation_count()
    } 