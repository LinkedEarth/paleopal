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