"""
Main FastAPI application for the PaleoPal backend.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

# Import routers
from routers import conversations, agents, messages, libraries, document_extraction

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="PaleoPal API",
    description="API for paleoclimate data analysis with multi-agent system",
    version="2.0.0",
    redirect_slashes=False  # Disable automatic redirects to prevent Docker proxy issues
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",  # React dev server
        "http://localhost:8888", "http://127.0.0.1:8888",  # JupyterLab default
        "http://localhost:8889", "http://127.0.0.1:8889",  # JupyterLab alternate
        "http://localhost:8890", "http://127.0.0.1:8890",  # JupyterLab alternate
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(conversations.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(libraries.router, prefix="/api")
app.include_router(document_extraction.router, prefix="/api")

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "PaleoPal API", 
        "version": "2.0.0",
        "description": "Multi-agent system for paleoclimate data analysis",
        "available_endpoints": {
            "agents": "/api/agents",
            "conversations": "/api/conversations",
            "libraries": "/api/libraries"
        }
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "PaleoPal API is running"}

@app.get("/health")
async def health_check_legacy():
    """Legacy health check endpoint for backward compatibility."""
    return {"status": "healthy", "message": "PaleoPal API is running"}

@app.get("/api/status")
async def get_system_status():
    """Comprehensive system status endpoint."""
    try:
        from libraries.qdrant_config import get_system_status
        from services.llm_providers import LLMProviderFactory
        
        # Get Qdrant status
        qdrant_status = get_system_status()
        
        # Check LLM providers
        llm_providers = {}
        provider_types = ["ollama", "openai", "anthropic", "google", "grok"]
        
        for provider_type in provider_types:
            try:
                provider = LLMProviderFactory.create_provider(provider_type)
                llm_providers[provider_type] = {
                    "available": provider.is_available(),
                    "status": "connected" if provider.is_available() else "unavailable"
                }
            except Exception as e:
                llm_providers[provider_type] = {
                    "available": False,
                    "status": "error",
                    "error": str(e)
                }
        
        return {
            "backend": {
                "status": "healthy",
                "message": "PaleoPal API is running"
            },
            "qdrant": {
                "status": qdrant_status.get("qdrant_server", "unknown"),
                "collections": len(qdrant_status.get("qdrant_collections", {})) if isinstance(qdrant_status.get("qdrant_collections"), dict) else 0,
                "total_documents": qdrant_status.get("total_documents", 0)
            },
            "llm_providers": llm_providers,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return {
            "backend": {"status": "healthy", "message": "PaleoPal API is running"},
            "qdrant": {"status": "error", "error": str(e)},
            "llm_providers": {"error": "Failed to check LLM providers"},
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 
