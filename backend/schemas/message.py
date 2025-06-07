from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class Message(BaseModel):
    """Represents a single chat message with rich metadata."""
    id: str = Field(..., description="Unique message ID")
    conversation_id: str = Field(..., description="ID of the parent conversation")
    sequence_number: int = Field(..., description="Message order within conversation")
    
    # Core message content
    role: str = Field(..., description="Role of the sender: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    
    # Message classification
    message_type: str = Field(default="chat", description="Type: 'chat', 'clarification', 'system', 'progress'")
    agent_type: Optional[str] = Field(None, description="Which agent generated this message (for assistant messages)")
    
    # Agent execution results (for assistant messages)
    query_generated: Optional[str] = Field(None, description="SPARQL query or Python code generated")
    query_results: Optional[List[Any]] = Field(None, description="Results from query execution")
    execution_info: Optional[Dict[str, Any]] = Field(None, description="Execution metadata (libraries, result_count, etc.)")
    similar_results: Optional[List[Any]] = Field(None, description="Similar queries/code found during search")
    entity_matches: Optional[List[Any]] = Field(None, description="Entity matches from search")
    
    # Workflow data (for workflow manager messages)
    workflow_plan: Optional[Dict[str, Any]] = Field(None, description="Workflow plan data")
    workflow_id: Optional[str] = Field(None, description="Associated workflow ID")
    execution_results: Optional[List[Any]] = Field(None, description="Workflow execution results")
    failed_steps: Optional[List[Any]] = Field(None, description="Failed workflow steps")
    
    # Clarification state
    needs_clarification: bool = Field(default=False, description="Whether this message needs clarification")
    clarification_questions: Optional[List[Any]] = Field(None, description="Clarification questions for this message")
    
    # UI display flags (derived from data above, but stored for performance)
    has_query_results: bool = Field(default=False, description="Whether message has query results")
    has_generated_code: bool = Field(default=False, description="Whether message has generated code")
    has_workflow_plan: bool = Field(default=False, description="Whether message has workflow plan")
    has_workflow_execution: bool = Field(default=False, description="Whether message has workflow execution results")
    has_error: bool = Field(default=False, description="Whether message represents an error")
    
    # Progress tracking
    is_node_progress: bool = Field(default=False, description="Whether this is a progress update message")
    owner_message_id: Optional[str] = Field(None, description="For progress messages, which user message triggered this")
    phase: Optional[str] = Field(None, description="Progress phase: 'start', 'complete'")
    node_name: Optional[str] = Field(None, description="Name of the processing node")
    
    # Timestamps
    created_at: str = Field(..., description="Creation timestamp (ISO)")
    updated_at: str = Field(..., description="Last update timestamp (ISO)")
    
    # Additional metadata (for extensibility)
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional message metadata")

    class Config:
        extra = "allow"
        validate_by_name = True
        from_attributes = True

class MessageCreate(BaseModel):
    """Schema for creating a new message."""
    conversation_id: str
    role: str
    content: str
    message_type: str = "chat"
    agent_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class MessageUpdate(BaseModel):
    """Schema for updating message results and metadata."""
    query_generated: Optional[str] = None
    query_results: Optional[List[Any]] = None
    execution_info: Optional[Dict[str, Any]] = None
    similar_results: Optional[List[Any]] = None
    entity_matches: Optional[List[Any]] = None
    workflow_plan: Optional[Dict[str, Any]] = None
    workflow_id: Optional[str] = None
    execution_results: Optional[List[Any]] = None
    failed_steps: Optional[List[Any]] = None
    needs_clarification: Optional[bool] = None
    clarification_questions: Optional[List[Any]] = None
    metadata: Optional[Dict[str, Any]] = None 