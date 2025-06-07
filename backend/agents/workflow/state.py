"""
State definition for the Workflow Manager agent.
Uses the unified BaseAgentState and adds workflow-specific fields.
"""
from typing import Dict, Any, List, Optional
from pydantic import Field

from agents.base_state import BaseAgentState, BaseAgentConfig


class WorkflowAgentState(BaseAgentState):
    """State for workflow planning agent."""
    
    # Remove workflow_plan since we're using generated_code
    workflow_id: Optional[str] = None
    estimated_steps: Optional[int] = None
    agents_involved: List[str] = Field(default_factory=list)
    execution_results: List[Dict[str, Any]] = Field(default_factory=list)
    contextual_search_data: Optional[Dict[str, Any]] = None
    context_used: Optional[str] = None
    
    # Execution-related fields
    failed_steps: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Steps that failed during execution")
    current_step: Optional[int] = Field(default=None, description="Current step being executed")
    step_conversations: Optional[Dict[str, str]] = Field(default_factory=dict, description="Conversation IDs for each step")

    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True
        extra = "allow"


class WorkflowAgentConfig(BaseAgentConfig):
    """Configuration for the workflow manager agent."""
    
    # Workflow-specific configuration
    max_steps: int = Field(default=10, description="Maximum number of steps allowed in a workflow")
    execution_timeout: int = Field(default=300, description="Timeout for workflow execution in seconds")

    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True 