"""
Base state definitions for all agents using Pydantic models.
This provides a unified state structure that can be extended by specific agents.
"""

from typing import Annotated, Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
from langgraph.graph import add_messages
from langchain.chat_models.base import BaseChatModel

# Constants
MAX_REFINEMENTS = 1  # Maximum number of refinement attempts for any agent

class BaseAgentState(BaseModel):
    """Base state for all agents using Pydantic."""
    
    # Core conversation management
    messages: Annotated[List[Any], add_messages] = Field(
        default_factory=list,
        description="Conversation messages"
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Unique conversation identifier"
    )
    
    # User input and context
    user_input: str = Field(
        default="",
        description="Original user input/query from the request"
    )
    
    # Agent configuration
    agent_type: str = Field(
        default="",
        description="Type of agent handling this request"
    )
    capability: str = Field(
        default="",
        description="Specific capability being executed"
    )
    llm_provider: str = Field(
        default="openai",
        description="LLM provider to use"
    )
    
    # Request context
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Shared context from other agents"
    )
    notebook_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Notebook variables and cell context"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional request metadata"
    )
    
    # Clarification handling
    needs_clarification: bool = Field(
        default=False,
        description="Whether the request needs clarification"
    )
    clarification_questions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of clarification questions"
    )
    clarification_responses: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="User responses to clarification questions"
    )
    clarification_processed: bool = Field(
        default=False,
        description="Whether clarification has been processed"
    )
    
    # Generation results
    generated_code: str = Field(
        default="",
        description="Generated code (SPARQL, Python, etc.)"
    )
    execution_results: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="Results from code execution"
    )
    result_variable_names: Optional[List[str]] = Field(
        None,
        description="Names of variables created to store execution results (for cross-agent sharing)"
    )
    agent_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Agent-specific metadata (unified schema)"
    )
    
    # Error handling
    error_message: Optional[str] = Field(
        None,
        description="Error message if any"
    )
    
    # Processing flags
    refinement_count: int = Field(
        default=0,
        description="Number of refinements attempted"
    )
    
    # Similar examples/queries (useful for both SPARQL and code generation)
    similar_code: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Similar code/queries from database (SPARQL queries or Python code)"
    )
    entity_matches: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Entity matches from database (for SPARQL) or relevant concepts (for code)"
    )
    
    # Agent-specific extensions (can be overridden by subclasses)
    agent_specific_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Agent-specific state data"
    )

    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True
        extra = "allow"  # Allow additional fields for agent-specific data


class BaseAgentConfig(BaseModel):
    """Base configuration for all agents."""
    
    llm: BaseChatModel = Field(
        ...,
        description="Language model instance"
    )
    
    # Common services that most agents might need
    embedding_service: Optional[Any] = Field(
        None,
        description="Embedding service for semantic search"
    )
    
    # Clarification behavior configuration (common to all agents)
    enable_clarification: bool = Field(
        default=True,
        description="Whether to enable clarification detection"
    )
    clarification_threshold: str = Field(
        default="conservative",
        description="Clarification detection threshold: 'strict', 'conservative', or 'permissive'"
    )
    
    # Agent-specific config extensions
    agent_specific_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Agent-specific configuration"
    )

    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True
        extra = "allow"  # Allow additional fields for agent-specific config 