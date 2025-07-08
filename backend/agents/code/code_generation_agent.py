"""
Code Generation Agent - Produces Python code snippets / notebooks for data analysis tasks.
Updated to use LangGraph and unified state management with new libraries.
"""

import logging
import pathlib
from typing import Dict, Any, Optional

from agents.base_langgraph_agent import BaseLangGraphAgent
from agents.base_agent import AgentRequest, AgentResponse, AgentStatus, AgentCapability
from agents.code.state import CodeAgentState, CodeAgentConfig
from services.service_manager import service_manager

# Import LangGraph workflow creator
from agents.code.agent import create_agent

logger = logging.getLogger(__name__)


class CodeGenerationAgent(BaseLangGraphAgent):
    """Agent that generates Python code for paleoclimate analysis workflows using LangGraph."""

    def __init__(self, enable_clarification: bool = True, clarification_threshold: str = "conservative", 
                 symbols_optimization_level: str = "aggressive", use_two_step_llm: bool = True):
        super().__init__(
            agent_type="code",
            name="Code Generation Agent",
            description="Generates Python code (notebooks / scripts) for data-analysis tasks using PyLiPD / Pyleoclim",
            state_class=CodeAgentState
        )
        
        # Store configuration for passing to config
        self.enable_clarification = enable_clarification
        self.clarification_threshold = clarification_threshold
        self.symbols_optimization_level = symbols_optimization_level
        self.use_two_step_llm = use_two_step_llm
        
        self._register_capabilities()

    def _register_capabilities(self):
        """Register code generation capabilities."""
        generate_cap = AgentCapability(
            name="generate_code",
            description="Generate Python code (notebook/script) for the requested analysis",
            input_schema={
                "type": "object",
                "properties": {
                    "analysis_request": {"type": "string"},
                    "data_context": {"type": "object"},
                    "analysis_type": {
                        "type": "string",
                        "enum": [
                            "spectral",
                            "correlation",
                            "visualization",
                            "filtering",
                            "statistics",
                            "general",
                        ],
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["notebook", "script", "function"],
                        "default": "notebook",
                    },
                    "clarification_responses": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Responses to clarification questions"
                    }
                },
                "required": [],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "generated_code": {"type": "string"},
                    "analysis_description": {"type": "string"},
                    "code_examples_used": {"type": "array"},
                    "required_libraries": {"type": "array"},
                    "expected_outputs": {"type": "array"},
                    "needs_clarification": {"type": "boolean"},
                    "clarification_questions": {"type": "array"}
                },
            },
            requires_conversation=True,
        )
        self.register_capability(generate_cap)

    def _build_graph(self) -> None:
        """Build the Code Generation LangGraph workflow."""
        try:
            self._graph = create_agent()
        except Exception as e:
            logger.error("Failed to build code generation graph: %s", e)
            self._graph = None

    def _create_agent_config(self, request: AgentRequest) -> CodeAgentConfig:
        """Create code generation specific configuration from request."""
        llm_provider = request.metadata.get("llm_provider", "openai")
        llm_model = request.metadata.get("model")
        
        # Get LLM from service manager
        llm = service_manager.get_llm_provider(
            provider=llm_provider,
            model=llm_model
        )
        
        return CodeAgentConfig(
            llm=llm,
            enable_clarification=self.enable_clarification,
            clarification_threshold=self.clarification_threshold,
            symbols_optimization_level=self.symbols_optimization_level,
            use_two_step_llm=self.use_two_step_llm
        )

    def _create_result_from_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Create code generation specific result from state."""
        # Helper function to get values from either Pydantic model or dict
        def get_state_value(key, default=None):
            if isinstance(state, dict):
                return state.get(key, default)
            else:
                return getattr(state, key, default)
        
        execution_results = get_state_value("execution_results", [])
        
        # Extract execution information
        execution_successful = False
        execution_output = ""
        execution_error = ""
        execution_time = 0.0
        variable_state = {}
        
        if execution_results:
            for result in execution_results:
                if isinstance(result, dict):
                    if result.get("type") == "execution_success":
                        execution_successful = True
                        execution_output = result.get("output", "")
                        execution_time = result.get("execution_time", 0.0)
                        variable_state = result.get("variable_summary", {})
                    elif result.get("type") == "execution_error":
                        execution_error = result.get("error", "")
                        execution_time = result.get("execution_time", 0.0)
        
        # Extract created variable names for cross-agent sharing
        result_variable_names = []
        if execution_results:
            for result in execution_results:
                if isinstance(result, dict) and result.get("type") == "execution_success":
                    # Get variable names from variable_summary
                    var_summary = result.get("variable_summary", {})
                    for var_name in var_summary.keys():
                        result_variable_names.append(var_name)
        
        # Build agent metadata with code-specific data
        agent_metadata = {
            # "analysis_description": get_state_value("analysis_description", ""),
            # "code_examples_used": get_state_value("code_examples_used", []),
            "required_libraries": get_state_value("required_libraries", []),
            "expected_outputs": get_state_value("expected_outputs", []),
            "execution_successful": execution_successful,
            "execution_output": execution_output,
            "execution_error": execution_error,
            "execution_time": execution_time,
            "variable_state": variable_state,
        }
        
        return {
            "generated_code": get_state_value("generated_code", ""),
            "execution_results": execution_results,
            "result_variable_names": result_variable_names,
            "agent_metadata": agent_metadata,
            "needs_clarification": get_state_value("needs_clarification", False),
        }

    def _create_execution_info_from_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Create code generation specific execution info from state."""
        # Helper function to get values from either Pydantic model or dict
        def get_state_value(key, default=None):
            if isinstance(state, dict):
                return state.get(key, default)
            else:
                return getattr(state, key, default)
        
        required_libraries = get_state_value("required_libraries", [])
        expected_outputs = get_state_value("expected_outputs", [])
        execution_results = get_state_value('execution_results', [])
        
        return {
            "language": "python",
            "result_count": len(execution_results) if isinstance(execution_results, list) else 0,
            "libraries": ["notebook_library", "readthedocs_library"] + required_libraries,
            "expected_outputs": expected_outputs,
        } 