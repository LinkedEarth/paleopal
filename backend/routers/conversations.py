from fastapi import APIRouter, HTTPException
from typing import List

from schemas.conversation import Conversation, ConversationCreate, ConversationUpdate
from services.conversation_service import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])

@router.get("/", response_model=List[Conversation])
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

@router.get("/stats/count")
def get_conversation_stats():
    """Get conversation statistics."""
    return {
        "total_conversations": conversation_service.get_conversation_count()
    } 