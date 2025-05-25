"""
Database tools for initialization and validation.
"""

import logging
from typing import Dict, Any
from services.graphdb_embeddings import GraphDBEmbeddingService
from services.sparql_embeddings import SparqlEmbeddingsService

logger = logging.getLogger(__name__)

def initialize_database(
    graphdb_embedding_service: GraphDBEmbeddingService,
    sparql_embedding_service: SparqlEmbeddingsService
) -> bool:
    """Initialize the database with required data and services.
    
    Args:
        sparql_service: The SPARQL service instance
        graphdb_embedding_service: The graphdb embedding service instance
        sparql_embedding_service: The sparql embedding service instance
        
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    try:        
        # Initialize entity embeddings
        logger.info("Initializing entity embeddings...")
        graphdb_embedding_service.initialize()
        
        # Initialize query embeddings
        logger.info("Initializing query embeddings...")
        sparql_embedding_service.initialize()
            
        logger.info("Database initialization completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

def get_db_status() -> Dict[str, Any]:
    """Get status of all database connections and services."""
    
    status = {
        "sparql_embeddings": "unknown",
        "code_embeddings": "unknown",
        "conversation_state": "unknown"
    }
    
    # Check SPARQL embeddings
    try:
        from services.sparql_embeddings import sparql_embeddings_service
        vectorstore = sparql_embeddings_service._connect_to_vector_db()
        count = vectorstore._collection.count() if hasattr(vectorstore, "_collection") else 0
        status["sparql_embeddings"] = f"ready ({count} documents)"
    except Exception as e:
        status["sparql_embeddings"] = f"error: {str(e)}"
    
    # Check code embeddings
    try:
        from services.code_embeddings import code_embeddings_service
        vectorstore = code_embeddings_service._connect_to_vector_db()
        count = vectorstore._collection.count() if hasattr(vectorstore, "_collection") else 0
        status["code_embeddings"] = f"ready ({count} documents)"
    except Exception as e:
        status["code_embeddings"] = f"error: {str(e)}"
    
    # Check conversation state service
    try:
        from services.conversation_state_service import conversation_state_service
        count = len(conversation_state_service._conversations)
        status["conversation_state"] = f"ready ({count} conversations)"
    except Exception as e:
        status["conversation_state"] = f"error: {str(e)}"
    
    return status