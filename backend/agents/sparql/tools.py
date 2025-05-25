"""
Tool definitions for the SPARQL generation agent.
"""

import logging
from typing import List, Dict, Any, Optional
from services.sparql_service import SPARQLService
from services.graphdb_embeddings import GraphDBEmbeddingService

logger = logging.getLogger(__name__)

def get_similar_queries(
    sparql_embedding_service: Any,
    user_query: str,
    limit: int = 2
) -> List[Dict[str, Any]]:
    """Get similar queries from the database."""
    try:
        similar_queries = sparql_embedding_service.get_matches(user_query, limit=limit)
        
        # Make sure similar_queries is a list and not empty
        if not similar_queries or not isinstance(similar_queries, list):
            logger.warning("No similar queries found or invalid result format")
            return []
        
        # Process and return valid similar queries
        processed_queries = []
        for q in similar_queries:
            # Check if the required keys exist
            if not isinstance(q, dict):
                continue
                
            # Extract the fields with proper fallbacks
            query_text = q.get("description", "") if isinstance(q, dict) else ""
            sparql_text = q.get("sparql", "") if isinstance(q, dict) else ""
            similarity = q.get("similarity", 0.0) if isinstance(q, dict) else 0.0
            
            # Only add if we have at least the query and sparql
            if query_text and sparql_text:
                processed_queries.append({
                    "query": query_text,
                    "sparql": sparql_text,
                    "similarity": similarity
                })
        
        return processed_queries
    except Exception as e:
        logger.error(f"Error getting similar queries: {e}")
        return []

def get_entity_matches(
    graphdb_embedding_service: GraphDBEmbeddingService,
    user_query: str,
    limit: int = 2
) -> List[Dict[str, Any]]:
    """Get entity matches for the user query."""
    try:
        matches = graphdb_embedding_service.get_matches(user_query, limit=limit)
        
        # Make sure matches is a list and not empty
        if not matches or not isinstance(matches, list):
            logger.warning("No entity matches found or invalid result format")
            return []
        
        # Process and return valid entity matches
        processed_matches = []
        for match in matches:
            # Check if we have a dictionary
            if not isinstance(match, dict):
                continue
                
            # Extract the fields with proper fallbacks
            uri = match.get("uri", "") if isinstance(match, dict) else ""
            # Use class_name for the entity type (was previously "type")
            entity_type = match.get("class_name", "") if isinstance(match, dict) else ""
            # Try both label and class_name as potential label sources
            label = match.get("label", match.get("class_name", "")) if isinstance(match, dict) else ""
            similarity = match.get("similarity", 0.0) if isinstance(match, dict) else 0.0
            
            # If uri is missing, we can't use this match
            if uri:
                # If no label is available, use the last part of the URI
                if not label and uri:
                    label = uri.split("/")[-1]
                    
                processed_matches.append({
                    "uri": uri,
                    "label": label,
                    "type": entity_type,
                    "similarity": similarity
                })
        
        return processed_matches
    except Exception as e:
        logger.error(f"Error getting entity matches: {e}")
        return []

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