"""
Shared dependencies for FastAPI endpoints.
"""

import logging
from fastapi import Depends, Request, HTTPException

from config import SPARQL_ENDPOINT_URL
from services.sparql_service import SPARQLService

logger = logging.getLogger(__name__)

def get_app(request: Request):
    """Get the FastAPI app instance from the request."""
    return request.app

def get_sparql_service(app=Depends(get_app)):
    """Get the SPARQL service singleton."""
    try:
        if not hasattr(app, "sparql_service"):
            logger.info(f"Initializing SPARQL service with endpoint: {SPARQL_ENDPOINT_URL}")
            app.sparql_service = SPARQLService(endpoint_url=SPARQL_ENDPOINT_URL)
        return app.sparql_service
    except Exception as e:
        logger.error(f"Error creating SPARQL service: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize SPARQL service: {str(e)}")

def get_graphdb_embedding_service(app=Depends(get_app)):
    """Get the graphdb embedding service singleton."""
    try:
        if not hasattr(app, "graphdb_embedding_service"):
            raise HTTPException(status_code=500, detail="Graphdb embedding service not initialized")
        return app.graphdb_embedding_service
    except Exception as e:
        logger.error(f"Error getting graphdb embedding service: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def get_sparql_embedding_service(app=Depends(get_app)):
    """Get the sparql embedding service singleton."""
    try:
        if not hasattr(app, "sparql_embedding_service"):
            raise HTTPException(status_code=500, detail="Sparql embedding service not initialized")
        return app.sparql_embedding_service
    except Exception as e:
        logger.error(f"Error getting sparql embedding service: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))