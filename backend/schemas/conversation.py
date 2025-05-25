from typing import List, Optional, Any
from pydantic import BaseModel, Field

class Message(BaseModel):
    """Represents a single chat message."""
    role: str = Field(..., description="Role of the sender: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(None, description="ISO timestamp of the message")
    metadata: Optional[Any] = Field(None, description="Additional metadata such as query, results, etc.")

    class Config:
        # Allow arbitrary extra fields so UI-specific flags (e.g., hasQueryResults) are preserved
        extra = "allow"

class Conversation(BaseModel):
    """Represents a conversation consisting of multiple messages."""
    id: str = Field(..., description="Unique conversation ID")
    title: str = Field(..., description="Conversation title")
    messages: List[Message] = Field(default_factory=list, description="List of chat messages")
    state_id: Optional[str] = Field(None, alias="stateId", description="Backend state identifier for SPARQL agent")
    created_at: Optional[str] = Field(None, description="Creation timestamp (ISO)")
    updated_at: Optional[str] = Field(None, description="Last update timestamp (ISO)")

    class Config:
        extra = "allow"
        validate_by_name = True
        # Ensure aliases are used when exporting to JSON
        from_attributes = True 
