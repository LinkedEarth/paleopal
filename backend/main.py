"""
Main FastAPI application for the PaleoPal backend.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from routers import conversations, agents, messages, libraries, document_extraction

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="PaleoPal API",
    description="API for paleoclimate data analysis with multi-agent system",
    version="2.0.0"
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 
