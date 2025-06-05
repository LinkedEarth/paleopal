"""
Tool definitions for the SPARQL generation agent.
Updated to use sparql_library and ontology_library.
"""

import logging
import sys
import pathlib
from typing import List, Dict, Any, Optional
from services.sparql_service import SPARQLService

logger = logging.getLogger(__name__)

def execute_sparql_query(
    sparql_service: SPARQLService,
    query: str,
    limit: int = 1000
) -> List[Dict[str, Any]]:
    """Execute a SPARQL query and return the results."""
    try:
        # Execute the query
        raw_results = sparql_service.execute_query(query, limit=limit)
        
        # Format the results using the service's formatter
        formatted_results = sparql_service.format_results(raw_results)
        
        # Convert each value to a string for consistent handling
        return [
            {str(k): str(v) if not isinstance(v, dict) else str(v.get("value", "")) 
             for k, v in row.items()}
            for row in formatted_results
        ]
    except Exception as e:
        logger.error(f"Error executing SPARQL query: {e}")
        raise 