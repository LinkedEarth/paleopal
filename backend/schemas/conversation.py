from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

from schemas.message import Message

class Conversation(BaseModel):
    id: str = Field(..., description="Unique conversation ID")
    title: str = Field(..., description="Human-readable conversation title")
    
    # Agent and LLM settings
    llm_provider: str = Field(default="google", description="LLM provider for the conversation")
    selected_agent: str = Field(default="sparql", description="Currently selected agent")
    
    # Clarification settings
    enable_clarification: bool = Field(default=False, description="Whether clarification is enabled")
    clarification_threshold: str = Field(default="conservative", description="Clarification threshold")
    
    # Execution settings
    enable_execution: bool = Field(default=True, description="Whether code execution is enabled")
    
    # Current conversation state
    waiting_for_clarification: bool = Field(default=False, description="Whether waiting for user clarification")
    clarification_questions: Optional[List[Any]] = Field(None, description="Active clarification questions")
    clarification_answers: Optional[Dict[str, Any]] = Field(None, description="User's clarification answers")
    original_request: Optional[str] = Field(None, description="Original request before clarification")
    
    # Messages (loaded from separate table)
    messages: List[Message] = Field(default=[], description="Conversation messages (loaded separately)")
    
    # Timestamps
    created_at: str = Field(..., description="Creation timestamp (ISO)")
    updated_at: str = Field(..., description="Last update timestamp (ISO)")
    
    # Additional metadata
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional conversation metadata")

    class Config:
        extra = "allow"
        validate_by_name = True
        from_attributes = True

class ConversationCreate(BaseModel):
    """Schema for creating a new conversation."""
    id: Optional[str] = None  # Allow frontend to provide conversation ID
    title: str = "New Conversation"
    llm_provider: str = "google"
    selected_agent: str = "sparql"
    enable_clarification: bool = False
    clarification_threshold: str = "conservative"
    enable_execution: bool = True
    metadata: Optional[Dict[str, Any]] = None

class ConversationUpdate(BaseModel):
    """Schema for updating conversation metadata (not messages)."""
    title: Optional[str] = None
    llm_provider: Optional[str] = None
    selected_agent: Optional[str] = None
    enable_clarification: Optional[bool] = None
    clarification_threshold: Optional[str] = None
    enable_execution: Optional[bool] = None
    waiting_for_clarification: Optional[bool] = None
    clarification_questions: Optional[List[Any]] = None
    clarification_answers: Optional[Dict[str, Any]] = None
    original_request: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None 
