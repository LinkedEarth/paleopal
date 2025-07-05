"""
State definition for the SPARQL generation agent.
Updated to use the unified BaseAgentState and new libraries.
"""
from typing import Dict, Any, List, Optional
from pydantic import Field
import pathlib

from agents.base_state import BaseAgentState, BaseAgentConfig
from services.sparql_service import SPARQLService


class SparqlAgentState(BaseAgentState):
    """State for the SPARQL generation agent, extending BaseAgentState."""
    
    # No additional fields needed - all functionality is now in BaseAgentState
    # - generated_code serves as generated_query
    # - execution_results serves as query_results  
    # - similar_code serves as similar_queries
    pass

    execution_successful: bool = Field(
        default=False,
        description="Whether the last execution was successful"
    )
    current_message_id: Optional[str] = Field(
        default=None,
        description="Current message ID for variable origin tracking"
    )

    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True
        extra = "allow"


class SparqlAgentConfig(BaseAgentConfig):
    """Configuration for the SPARQL generation agent."""
    
    sparql_service: SPARQLService = Field(
        ...,
        description="SPARQL service for query execution"
    )

    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True 