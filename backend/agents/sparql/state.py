"""
State definition for the SPARQL generation agent.
Updated to use the unified BaseAgentState.
"""
from typing import Dict, Any, List, Optional
from pydantic import Field

from agents.base_state import BaseAgentState, BaseAgentConfig
from services.sparql_service import SPARQLService
from services.graphdb_embeddings import GraphDBEmbeddingService
from services.sparql_embeddings import SparqlEmbeddingsService


class SparqlAgentState(BaseAgentState):
    """State for the SPARQL generation agent, extending BaseAgentState."""
    
    # No additional fields needed - all functionality is now in BaseAgentState
    # - generated_code serves as generated_query
    # - execution_results serves as query_results  
    # - similar_code serves as similar_queries
    pass

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
    graphdb_embedding_service: GraphDBEmbeddingService = Field(
        ...,
        description="GraphDB embedding service for entity matching"
    )
    sparql_embedding_service: SparqlEmbeddingsService = Field(
        ...,
        description="SPARQL query embedding service for similarity search"
    )
    
    # Clarification behavior configuration
    enable_clarification: bool = Field(
        default=True,
        description="Whether to enable clarification detection"
    )
    clarification_threshold: str = Field(
        default="conservative",
        description="Clarification detection threshold: 'strict', 'conservative', or 'permissive'"
    )

    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True 