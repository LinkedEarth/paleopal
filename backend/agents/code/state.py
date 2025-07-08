"""
State definition for the Code Generation agent.
Uses the unified BaseAgentState and new libraries.
"""
from typing import Dict, Any, List, Optional, Union
from pydantic import Field
import pathlib

from agents.base_state import BaseAgentState, BaseAgentConfig


class CodeAgentState(BaseAgentState):
    """State for the Code Generation agent, extending BaseAgentState."""
    
    # Code generation specific fields only (common fields are now in BaseAgentState)
    analysis_request: str = Field(
        default="",
        description="The analysis request from the user"
    )
    analysis_type: str = Field(
        default="general",
        description="Type of analysis requested"
    )
    output_format: str = Field(
        default="notebook",
        description="Desired output format (notebook, script, function)"
    )
    
    # Code-specific context and results
    data_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Context about the data being analyzed"
    )
    analysis_description: str = Field(
        default="",
        description="Description of the generated analysis"
    )
    required_libraries: List[str] = Field(
        default_factory=list,
        description="Required Python libraries"
    )
    expected_outputs: List[Union[str, Dict[str, Any]]] = Field(
        default_factory=list,
        description="Expected outputs from the code (string descriptions or structured objects)"
    )
    code_examples_used: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Metadata about code examples used"
    )
    validation_errors: List[str] = Field(
        default_factory=list,
        description="PyLiPD/Pyleoclim validation errors found in generated code"
    )
    
    # Execution-related fields
    execution_output: str = Field(
        default="",
        description="Output from code execution"
    )
    execution_error: str = Field(
        default="",
        description="Error from code execution"
    )
    execution_time: float = Field(
        default=0.0,
        description="Time taken for code execution in seconds"
    )
    variable_state: Dict[str, Any] = Field(
        default_factory=dict,
        description="Current variable state in the conversation"
    )
    execution_successful: bool = Field(
        default=False,
        description="Whether the last code execution was successful"
    )
    current_message_id: Optional[str] = Field(
        default=None,
        description="Current message ID for variable origin tracking"
    )

    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True
        extra = "allow"


class CodeAgentConfig(BaseAgentConfig):
    """Configuration for the Code Generation agent."""
    
    # Clarification settings
    enable_clarification: bool = Field(
        default=True,
        description="Whether to enable clarification requests"
    )
    clarification_threshold: str = Field(
        default="conservative",
        description="Threshold for clarification detection"
    )
    
    # Library symbols optimization
    symbols_optimization_level: str = Field(
        default="aggressive",
        description="Optimization level for library symbols: 'conservative', 'moderate', or 'aggressive'"
    )
    
    # Two-step LLM approach
    use_two_step_llm: bool = Field(
        default=True,
        description="Use 2-step LLM approach: first ask what functions to use, then provide only those signatures"
    )

    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True 