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
    conv = conversation_service.get(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv

@router.post("/", response_model=Conversation, response_model_by_alias=True)
def create_conversation(conv: Conversation):
    if conversation_service.get(conv.id):
        raise HTTPException(status_code=400, detail="Conversation with id already exists")
    conversation_service.upsert(conv)
    return conv

@router.put("/{conv_id}", response_model=Conversation, response_model_by_alias=True)
def update_conversation(conv_id: str, conv: Conversation):
    if conv_id != conv.id:
        raise HTTPException(status_code=400, detail="ID mismatch")
    conversation_service.upsert(conv)
    return conv

@router.delete("/{conv_id}")
def delete_conversation(conv_id: str):
    conversation_service.delete(conv_id)
    return {"status": "deleted"} 