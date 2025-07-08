#!/usr/bin/env python
"""
Server script to run the FastAPI application using uvicorn.
"""

import os
import logging
import uvicorn
from main import app

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Get host and port from environment variables or use defaults
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    
    logger.info(f"Starting PaleoPal API server on {host}:{port}")
    
    # Auto-reload is useful during development but can be problematic if non-code files
    # (e.g., generated plots, database files) trigger reload loops. We therefore
    # restrict the reload watcher to Python source directories only and explicitly
    # exclude "data" (where execution states & plots are stored) and "frontend".

    is_dev = os.environ.get("ENV", "development") == "development"
    # Allow disabling reload even in dev mode for performance testing
    disable_reload = os.environ.get("DISABLE_RELOAD", "false").lower() == "true"

    # Directories that contain backend Python source code
    # Note: We exclude the entire "backend" dir to avoid watching data files,
    # and instead watch specific subdirectories
    reload_dirs = [
        "routers",
        "services", 
        "agents",
        "schemas",
        "utils",
        "libraries"
    ]

    # Explicitly excluded paths (relative to project root)
    reload_excludes = [
        "backend/data",      # execution DB + plots
        "frontend",          # avoid triggering reload on frontend rebuilds
        "docs",
        "*.db",              # SQLite database files
        "*.png",             # Plot images
        "*.jpg",             # Images
        "*.jpeg",            # Images
        "*.log"              # Log files
    ]

    # Enable reload only if in dev mode AND reload is not explicitly disabled
    enable_reload = is_dev and not disable_reload
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=enable_reload,
        reload_dirs=reload_dirs if enable_reload else None,
        reload_excludes=reload_excludes if enable_reload else None,
        log_level="info"
    ) 
