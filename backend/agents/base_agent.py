"""
Base agent interface for the multi-agent paleoclimate analysis system.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum

class AgentCapability(BaseModel):
    """Represents a capability that an agent can perform."""
    name: str = Field(..., description="Name of the capability")
    description: str = Field(..., description="Description of what this capability does")
    input_schema: Dict[str, Any] = Field(..., description="JSON schema for input validation")
    output_schema: Dict[str, Any] = Field(..., description="JSON schema for output validation")
    requires_conversation: bool = Field(False, description="Whether this capability needs conversation management")

class AgentStatus(str, Enum):
    """Status of an agent operation."""
    SUCCESS = "success"
    NEEDS_CLARIFICATION = "needs_clarification"
    ERROR = "error"
    PROCESSING = "processing"

class AgentRequest(BaseModel):
    """Standard request format for all agents."""
    agent_type: str = Field(..., description="Type of agent to handle this request")
    capability: str = Field(..., description="Specific capability being requested")
    conversation_id: Optional[str] = Field(None, description="ID for conversation tracking")
    user_input: str = Field(default="", description="User's input/request (can be empty for clarification submissions)")
    context: Dict[str, Any] = Field(default_factory=dict, description="Shared context from other agents")
    notebook_context: Dict[str, Any] = Field(default_factory=dict, description="Notebook variables and cell context")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

class AgentResponse(BaseModel):
    """Standard response format from all agents."""
    status: AgentStatus = Field(..., description="Status of the operation")
    result: Any = Field(None, description="The main result of the operation")
    message: str = Field(..., description="Human-readable message about the result")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for follow-up")
    clarification_questions: Optional[List[Dict[str, Any]]] = Field(None, description="Questions if clarification needed")
    context_updates: Dict[str, Any] = Field(default_factory=dict, description="Updates to shared context")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional response metadata")

class BaseAgent(ABC):
    """Abstract base class for all agents in the system."""
    
    def __init__(self, agent_type: str, name: str, description: str):
        self.agent_type = agent_type
        self.name = name
        self.description = description
        self._capabilities = {}
    
    @property
    def capabilities(self) -> Dict[str, AgentCapability]:
        """Get all capabilities this agent supports."""
        return self._capabilities
    
    def register_capability(self, capability: AgentCapability):
        """Register a new capability for this agent."""
        self._capabilities[capability.name] = capability
    
    @abstractmethod
    async def handle_request(self, request: AgentRequest) -> AgentResponse:
        """
        Handle an incoming request.
        
        Args:
            request: The agent request to process
            
        Returns:
            AgentResponse with the result
        """
        pass
    
    
    def validate_request(self, request: AgentRequest) -> bool:
        """
        Validate that this agent can handle the request.
        
        Args:
            request: The request to validate
            
        Returns:
            True if request is valid for this agent
        """
        if request.agent_type != self.agent_type:
            return False
        
        if request.capability not in self._capabilities:
            return False
        
        # TODO: Add input schema validation
        return True
    
    def get_info(self) -> Dict[str, Any]:
        """Get information about this agent."""
        return {
            "agent_type": self.agent_type,
            "name": self.name,
            "description": self.description,
            "capabilities": {
                name: {
                    "name": cap.name,
                    "description": cap.description,
                    "requires_conversation": cap.requires_conversation
                }
                for name, cap in self._capabilities.items()
            }
        }

class ConversationMixin:
    """Mixin to provide conversation management capabilities."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._conversation_states = {}
    
    def get_conversation_state(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation state from memory."""
        return self._conversation_states.get(conversation_id)
    
    def set_conversation_state(self, conversation_id: str, state: Dict[str, Any]) -> None:
        """Set conversation state in memory."""
        self._conversation_states[conversation_id] = state
    
    def clear_conversation(self, conversation_id: str) -> None:
        """Clear a conversation from memory."""
        if conversation_id in self._conversation_states:
            del self._conversation_states[conversation_id] 