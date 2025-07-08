"""
Workflow Generation Agent using LangGraph.
Enhanced with comprehensive contextual search and LLM-based planning.
"""

import logging
import os
import sys

# Add the backend directory to Python path to enable imports
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from agents.base_langgraph_agent import BaseLangGraphAgent
from agents.base_agent import AgentRequest
from .state import WorkflowAgentState, WorkflowAgentConfig
from .agent import create_agent
from services.service_manager import service_manager

logger = logging.getLogger(__name__)


class WorkflowGenerationAgent(BaseLangGraphAgent):
    """LangGraph-based workflow generation agent."""
    
    def __init__(self):
        super().__init__(
            agent_type="workflow_generation",
            name="Workflow Generation Agent (LangGraph)",
            description="Plans multi-step paleoclimate analysis workflows using LLM and contextual search",
            state_class=WorkflowAgentState
        )
    
    def _build_graph(self) -> None:
        """Build the LangGraph workflow."""
        try:
            # Create the LangGraph workflow
            self._graph = create_agent()
            logger.info("Workflow LangGraph built successfully")
        except Exception as e:
            logger.error(f"Error building workflow graph: {e}")
            raise
    
    def _create_agent_config(self, request: AgentRequest) -> WorkflowAgentConfig:
        """Create agent configuration from request."""
        try:
            metadata = request.metadata or {}
            
            # Get LLM provider from metadata
            llm_provider = metadata.get("llm_provider", "google")
            llm = service_manager.get_llm_provider(llm_provider)
            
            # Get clarification settings
            enable_clarification = metadata.get("enable_clarification", True)
            clarification_threshold = metadata.get("clarification_threshold", "conservative")
            
            # Workflow-specific settings
            max_steps = metadata.get("max_steps", 10)
            execution_timeout = metadata.get("execution_timeout", 1800)  # 30 minutes default
            
            return WorkflowAgentConfig(
                llm=llm,
                llm_provider=llm_provider,
                enable_clarification=enable_clarification,
                clarification_threshold=clarification_threshold,
                max_steps=max_steps,
                execution_timeout=execution_timeout
            )
        except Exception as e:
            logger.error(f"Error creating workflow config: {e}")
            # Return minimal config as fallback
            return WorkflowAgentConfig(
                llm=service_manager.get_llm_provider("google"),
                llm_provider="google"
            ) 