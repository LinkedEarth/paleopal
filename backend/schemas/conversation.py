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
    """Represents a conversation consisting of multiple messages and UI state."""
    id: str = Field(..., description="Unique conversation ID")
    title: str = Field(..., description="Conversation title")
    messages: List[Message] = Field(default_factory=list, description="List of chat messages")
    state_id: Optional[str] = Field(None, alias="stateId", description="Backend state identifier for agent context")
    
    # Clarification handling
    waiting_for_clarification: Optional[bool] = Field(False, alias="waitingForClarification", description="Whether waiting for user clarification")
    clarification_questions: Optional[List[Any]] = Field(default_factory=list, alias="clarificationQuestions", description="List of clarification questions")
    clarification_answers: Optional[dict] = Field(default_factory=dict, alias="clarificationAnswers", description="User answers to clarification questions")
    original_request_context: Optional[Any] = Field(None, alias="originalRequestContext", description="Original request context for clarification")
    
    # Agent and LLM settings
    llm_provider: Optional[str] = Field("google", alias="llmProvider", description="Selected LLM provider")
    selected_agent: Optional[str] = Field("sparql", alias="selectedAgent", description="Currently selected agent")
    
    # UI state
    is_loading: Optional[bool] = Field(False, alias="isLoading", description="Whether request is in progress")
    error: Optional[str] = Field(None, description="Error message if any")
    
    # Clarification settings
    enable_clarification: Optional[bool] = Field(False, alias="enableClarification", description="Whether clarification is enabled")
    clarification_threshold: Optional[str] = Field("conservative", alias="clarificationThreshold", description="Clarification threshold setting")
    
    # Execution state
    execution_start_time: Optional[int] = Field(None, alias="executionStartTime", description="Timestamp when execution started")
    
    # Timestamps
    created_at: Optional[str] = Field(None, alias="createdAt", description="Creation timestamp (ISO)")
    updated_at: Optional[str] = Field(None, alias="updatedAt", description="Last update timestamp (ISO)")

    class Config:
        extra = "allow"
        validate_by_name = True
        # Ensure aliases are used when exporting to JSON
        from_attributes = True 
