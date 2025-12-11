"""
Main FastAPI application for the PaleoPal backend.
"""

import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Mark this as the main process before any service imports
import os
os.environ['PALEOPAL_MAIN_PROCESS'] = 'true'

# Disable tokenizer parallelism warnings from multiprocessing
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Import routers
from routers import conversations, agents, messages, libraries, document_extraction, jobs, ws as ws_router
from services.service_manager import service_manager
# Removed: from routers.sparql_proxy import router as sparql_proxy_router

# Import additional modules for plot proxy
import requests
from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse
import io

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
# Removed: app.include_router(sparql_proxy_router)

# Serve generated plots
# When using isolated execution service, plots are stored in the shared Docker volume
USE_ISOLATED_EXECUTION = os.getenv('USE_ISOLATED_EXECUTION', 'true').lower() == 'true'

if USE_ISOLATED_EXECUTION:
    # In development mode, we need to serve plots from a local directory
    # The isolated service will save plots to the Docker volume, but we'll create
    # a local directory for development and use a proxy approach if needed
    PLOTS_DIR = Path(__file__).resolve().parent / "data" / "plots"
    logger.info("🖼️ Using isolated execution service with local plots directory for development: backend/data/plots")
else:
    # Plots are stored locally in backend/data/plots
    PLOTS_DIR = Path(__file__).resolve().parent / "data" / "plots"
    logger.info("🖼️ Using local plots directory: backend/data/plots")

PLOTS_DIR.mkdir(parents=True, exist_ok=True)
# Remove StaticFiles mount - we'll handle plot serving through the custom endpoint
# app.mount("/plots", StaticFiles(directory=str(PLOTS_DIR)), name="plots")

# Add plot proxy endpoint for development with isolated execution
@app.get("/plots/{plot_filename}")
async def get_plot(plot_filename: str):
    """Serve plot files, with proxy support for isolated execution service."""
    local_plot_path = PLOTS_DIR / plot_filename
    
    # If plot exists locally, serve it directly
    if local_plot_path.exists():
        return FileResponse(local_plot_path)
    
    # If using isolated execution service and plot doesn't exist locally,
    # try to fetch it from the isolated service
    if USE_ISOLATED_EXECUTION:
        try:
            # Try to fetch the plot from the isolated service
            service_url = os.getenv('EXECUTION_SERVICE_URL', 'http://localhost:8001')
            response = requests.get(f"{service_url}/plots/{plot_filename}", timeout=10)
            
            if response.status_code == 200:
                # Save the plot locally for future requests
                local_plot_path.parent.mkdir(parents=True, exist_ok=True)
                with open(local_plot_path, 'wb') as f:
                    f.write(response.content)
                
                # Return the plot content
                return StreamingResponse(
                    io.BytesIO(response.content),
                    media_type="image/png",
                    headers={"Content-Disposition": f"inline; filename={plot_filename}"}
                )
        except Exception as e:
            logger.warning(f"Failed to fetch plot {plot_filename} from isolated service: {e}")
    
    # Plot not found
    raise HTTPException(status_code=404, detail="Plot not found")

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("🚀 Starting PaleoPal API services...")
    
    # Set up event loop for WebSocket manager
    try:
        import asyncio
        from websocket_manager import websocket_manager
        loop = asyncio.get_running_loop()
        websocket_manager.set_event_loop(loop)
        logger.info("✅ WebSocket manager event loop configured")
    except Exception as e:
        logger.error(f"❌ Failed to configure WebSocket manager event loop: {e}")
    
    # Initialize async execution service
    try:
        logger.info("✅ Async execution service initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize async execution service: {e}")

@app.on_event("shutdown") 
async def shutdown_event():
    """Cleanup services on shutdown."""
    logger.info("🛑 Shutting down PaleoPal API services...")
    
    # Shutdown execution service
    try:
        execution_service = service_manager.get_execution_service()
        if hasattr(execution_service, 'shutdown'):
            execution_service.shutdown()
        logger.info("✅ Execution service shutdown complete")
    except Exception as e:
        logger.error(f"❌ Error shutting down execution service: {e}")

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
