import logging
from typing import Dict, Any, Optional, List
import pathlib

from agents.base_langgraph_agent import BaseLangGraphAgent
from agents.base_agent import AgentRequest, AgentResponse, AgentStatus, AgentCapability
from agents.sparql.state import SparqlAgentState, SparqlAgentConfig
from config import DEFAULT_LLM_PROVIDER
from services.service_manager import service_manager

# Import LangGraph workflow creator
from agents.sparql.agent import create_agent

logger = logging.getLogger(__name__)


class SparqlGenerationAgent(BaseLangGraphAgent):
    """SPARQL query generation agent using LangGraph."""
    
    def __init__(self, enable_clarification: bool = True, clarification_threshold: str = "conservative"):
        super().__init__(
            agent_type="sparql",
            name="SPARQL Generation Agent",
            description="Generates and executes SPARQL queries for paleoclimate data",
            state_class=SparqlAgentState
        )
        
        # Store clarification configuration for passing to config
        self.enable_clarification = enable_clarification
        self.clarification_threshold = clarification_threshold
        
        # Register capabilities
        self.register_capability(AgentCapability(
            name="generate_query",
            description="Generate and execute SPARQL queries",
            input_schema={
                "type": "object",
                "properties": {
                    "user_input": {"type": "string", "description": "Natural language query"},
                    "clarification_responses": {
                        "type": "array", 
                        "items": {"type": "object"},
                        "description": "Responses to clarification questions"
                    }
                },
                "required": ["user_input"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "generated_code": {"type": "string", "description": "Generated SPARQL query"},
                    "execution_results": {"type": "array", "description": "Query execution results"},
                    "clarification_questions": {"type": "array", "description": "Clarification questions if needed"}
                }
            },
            requires_conversation=True
        ))
    
    def _build_graph(self) -> None:
        """Build the LangGraph workflow."""
        self._graph = create_agent()
    
    def _create_agent_config(self, request: AgentRequest) -> SparqlAgentConfig:
        """Create SPARQL agent configuration from request."""
        # Get services from service manager
        llm = service_manager.get_llm_provider(request.metadata.get("llm_provider", DEFAULT_LLM_PROVIDER))
        sparql_service = service_manager.get_sparql_service()
        
        return SparqlAgentConfig(
            llm=llm,
            sparql_service=sparql_service,
            enable_clarification=self.enable_clarification,
            clarification_threshold=self.clarification_threshold
        )

    def _create_result_from_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Create SPARQL-specific result from state."""
        return {
            "sparql_query": state.get("generated_query", ""),
            "results": state.get("query_results", []),
            "needs_clarification": False,
        }

    def _create_execution_info_from_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Create SPARQL-specific execution info from state."""
        # Helper function to get values from either Pydantic model or dict
        def get_state_value(key, default=None):
            if isinstance(state, dict):
                return state.get(key, default)
            else:
                return getattr(state, key, default)
        
        execution_results = get_state_value('execution_results', [])
        return {
            "language": "sparql",
            "endpoint": "triplestore",
            "result_count": len(execution_results) if isinstance(execution_results, list) else 0,
            "libraries": ["sparql_library", "ontology_library"],
            "expected_outputs": ["SPARQL query results"]
        }
