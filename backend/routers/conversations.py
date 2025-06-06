from fastapi import APIRouter, HTTPException
from typing import List

from schemas.conversation import Conversation
from services.conversation_service import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])

@router.get("/", response_model=List[Conversation], response_model_by_alias=True)
def list_conversations():
    """Return list of conversations (metadata and messages)."""
    return conversation_service.list_conversations()

@router.get("/{conv_id}", response_model=Conversation, response_model_by_alias=True)
def get_conversation(conv_id: str):
    """Get a specific conversation by ID."""
    conv = conversation_service.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv

@router.post("/", response_model=Conversation, response_model_by_alias=True)
def create_conversation(conv: Conversation):
    """Create a new conversation."""
    if conversation_service.conversation_exists(conv.id):
        raise HTTPException(status_code=400, detail="Conversation with id already exists")
    return conversation_service.create_conversation(conv)

@router.put("/{conv_id}", response_model=Conversation, response_model_by_alias=True)
def update_conversation(conv_id: str, conv: Conversation):
    """Update an existing conversation."""
    if conv_id != conv.id:
        raise HTTPException(status_code=400, detail="ID mismatch")
    
    if not conversation_service.conversation_exists(conv_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conversation_service.update_conversation(conv)

@router.delete("/{conv_id}")
def delete_conversation(conv_id: str):
    """Delete a conversation."""
    if not conversation_service.delete_conversation(conv_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}

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