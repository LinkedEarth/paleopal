"""
Main FastAPI application for the PaleoPal backend.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import textwrap
import httpx
from fastapi import Request, Response, HTTPException

# Import routers
from routers import conversations, agents, messages, libraries, document_extraction, jobs, ws as ws_router

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
app.include_router(jobs.router, prefix="/api")
app.include_router(ws_router.router)

# Serve generated plots
PLOTS_DIR = Path(__file__).resolve().parent / "data" / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/plots", StaticFiles(directory=str(PLOTS_DIR)), name="plots")

# -------------------
# Simple proxy endpoint for LiPDVerse GraphDB to avoid CORS
# Frontend lipdjs can send its SPARQL POST/GET requests to /api/proxy/lipdverse
# which will forward them to the public GraphDB endpoint and relay the response.
# -------------------

LIPDVERSE_ENDPOINT = "https://linkedearth.graphdb.mint.isi.edu/repositories/LiPDVerse-dynamic"

@app.api_route("/api/proxy/lipdverse", methods=["GET", "POST"])
async def proxy_lipdverse(request: Request):
    """Proxy GraphDB requests to bypass CORS restrictions for the front-end.

    The path accepts the same query params and body as the original GraphDB endpoint.
    The client should keep headers like `Accept` and `Content-Type` when necessary.
    """
    try:
        client_headers = dict(request.headers)
        # Remove host header to avoid conflicts
        client_headers.pop("host", None)

        method = request.method.upper()
        async with httpx.AsyncClient(timeout=60) as client:
            if method == "GET":
                resp = await client.get(LIPDVERSE_ENDPOINT, params=request.query_params, headers=client_headers)
            elif method == "POST":
                body = await request.body()
                resp = await client.post(
                    LIPDVERSE_ENDPOINT,
                    params=request.query_params,
                    headers=client_headers,
                    content=body,
                )
            else:
                raise HTTPException(status_code=405, detail="Method not allowed")

        return Response(content=resp.content, status_code=resp.status_code, headers={
            "content-type": resp.headers.get("content-type", "application/octet-stream"),
        })
    except Exception as e:
        logger.error(f"Proxy to LiPDVerse failed: {e}")
        raise HTTPException(status_code=500, detail="Proxy error")

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
