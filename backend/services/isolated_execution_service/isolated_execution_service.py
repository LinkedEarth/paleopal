"""
Isolated Python Execution Service - Simple Direct Execution

A containerized service for safely executing Python code with state persistence.
Uses direct execution instead of script generation for simplicity and reliability.
"""

import logging
import os
import pickle
import sqlite3
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ExecutionStatus:
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ExecutionRequest(BaseModel):
    code: str
    conversation_id: str
    execution_id: str
    timeout: Optional[int] = None
    callback_url: Optional[str] = None

class ExecutionResponse(BaseModel):
    success: bool
    output: str = ""
    error: str = ""
    variables: Dict[str, Any] = {}
    execution_time: float = 0.0
    plots: List[str] = []
    execution_id: str
    status: str

class SimpleExecutionService:
    """Simple execution service with direct code execution."""
    
    def __init__(self):
        self.db_path = "/app/data/conversations.db"
        self.default_timeout = 300  # 5 minutes default
        self.lock = Lock()
        self._init_database()
        self._setup_environment()
        logger.info("SimpleExecutionService initialized")
    
    def _init_database(self):
        """Initialize SQLite database for conversation state."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_state (
                    conversation_id TEXT PRIMARY KEY,
                    state_data BLOB,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def _setup_environment(self):
        """Setup the execution environment."""
        # Configure matplotlib for headless operation
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            plt.ioff()  # Turn off interactive mode
        except ImportError:
            pass
        
        # Suppress warnings
        import warnings
        warnings.filterwarnings('ignore')
    
    @contextmanager
    def _get_db_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()
    
    def _load_conversation_state(self, conversation_id: str) -> Dict[str, Any]:
        """Load conversation state from database."""
        with self._get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT state_data FROM conversation_state WHERE conversation_id = ?",
                (conversation_id,)
            )
            row = cursor.fetchone()
            if row:
                try:
                    return pickle.loads(row[0])
                except Exception as e:
                    logger.warning(f"Failed to deserialize state for {conversation_id}: {e}")
            return {}
    
    def _save_conversation_state(self, conversation_id: str, state: Dict[str, Any]):
        """Save conversation state to database."""
        try:
            state_blob = pickle.dumps(state)
            with self._get_db_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO conversation_state (conversation_id, state_data, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (conversation_id, state_blob))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save state for {conversation_id}: {e}")
    
    def _create_variable_summary(self, name: str, value: Any) -> Dict[str, Any]:
        """Create a JSON-serializable summary of a variable."""
        try:
            # Create fully qualified type name
            type_obj = type(value)
            module_name = getattr(type_obj, '__module__', 'builtins')
            type_name = type_obj.__name__
            
            if module_name == 'builtins':
                fully_qualified_type = type_name
            else:
                fully_qualified_type = f"{module_name}.{type_name}"
            
            summary = {
                'type': fully_qualified_type,
                'module': module_name,
                'value': str(value)[:500]  # Truncate long values
            }
            
            # Add specific info for common types
            if hasattr(value, 'shape'):
                summary['shape'] = str(value.shape)
            if hasattr(value, 'dtype'):
                summary['dtype'] = str(value.dtype)
            if isinstance(value, (list, tuple, dict)):
                summary['length'] = len(value)
            
            return summary
        except Exception as e:
            return {
                'type': 'unknown', 
                'value': f'Error creating summary: {str(e)}'
            }
    
    def _capture_plots(self, conversation_id: str, execution_id: str) -> List[str]:
        """Capture any open matplotlib figures and save them as PNG files."""
        import matplotlib.pyplot as plt
        import time
        import os
        
        plots = []
        
        try:
            # Get all figure numbers
            fig_nums = plt.get_fignums()
            
            if not fig_nums:
                return plots
            
            # Create plots directory
            plots_dir = "/app/data/plots"
            os.makedirs(plots_dir, exist_ok=True)
            
            # Save each figure
            for i, fig_num in enumerate(fig_nums):
                fig = plt.figure(fig_num)
                
                # Generate filename with timestamp to avoid conflicts
                timestamp = int(time.time() * 1000)  # milliseconds
                filename = f"plot_{conversation_id}_{execution_id}_{i}_{timestamp}.png"
                filepath = os.path.join(plots_dir, filename)
                
                # Save the figure
                fig.savefig(filepath, format='png', dpi=150, bbox_inches='tight', 
                           facecolor='white', edgecolor='none')
                
                plots.append(filename)
                logger.info(f"Saved plot: {filename}")
                
            # Close all figures to prevent memory leaks
            plt.close('all')
            
        except Exception as e:
            logger.error(f"Error capturing plots: {e}")
            # Don't re-raise - plots are optional
        
        return plots
    
    def execute_code(self, request: ExecutionRequest) -> ExecutionResponse:
        """Execute code directly in the current process with proper isolation."""
        start_time = time.time()
        
        logger.info(f"Executing code for {request.execution_id}")
        
        try:
            # Load previous conversation state
            state = self._load_conversation_state(request.conversation_id)
            
            # Create execution namespace
            exec_globals = {
                '__name__': '__main__',
                '__doc__': None,
                '__package__': None,
            }
            
            # Add common imports
            try:
                import numpy as np
                exec_globals['np'] = np
            except ImportError:
                pass
            
            try:
                import pandas as pd
                exec_globals['pd'] = pd
            except ImportError:
                pass
            
            try:
                import matplotlib.pyplot as plt
                exec_globals['plt'] = plt
            except ImportError:
                pass
            
            try:
                import pyleoclim as pyleo
                exec_globals['pyleo'] = pyleo
            except ImportError:
                pass
            
            try:
                import pylipd
                exec_globals['pylipd'] = pylipd
            except ImportError:
                pass
            
            # Restore previous state
            for name, value in state.items():
                if not name.startswith('_') and not callable(value):
                    exec_globals[name] = value
            
            # Capture stdout
            output_buffer = StringIO()
            
            with redirect_stdout(output_buffer):
                # Execute the user's code
                exec(request.code, exec_globals)
            
            # Capture output
            output = output_buffer.getvalue()
            
            # Capture any matplotlib plots
            plots = self._capture_plots(request.conversation_id, request.execution_id)
            
            # Extract new variables
            new_state = {}
            variable_summaries = {}
            excluded_names = {
                'np', 'pd', 'plt', 'pyleo', 'pylipd', '__name__', '__doc__', '__package__'
            }
            
            for name, value in exec_globals.items():
                if (not name.startswith('_') and 
                    not callable(value) and 
                    name not in excluded_names):
                    
                    # Store actual value for state persistence
                    try:
                        pickle.dumps(value)  # Test if serializable
                        new_state[name] = value
                    except:
                        pass  # Skip non-serializable objects
                    
                    # Create summary for response
                    variable_summaries[name] = self._create_variable_summary(name, value)
            
            # Save updated state
            self._save_conversation_state(request.conversation_id, new_state)
            
            return ExecutionResponse(
                success=True,
                output=output,
                error="",
                variables=variable_summaries,
                execution_time=time.time() - start_time,
                plots=plots,
                execution_id=request.execution_id,
                status=ExecutionStatus.COMPLETED
            )
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            logger.error(f"Execution failed for {request.execution_id}: {error_msg}")
            
            # Still try to capture any plots that might have been created before the error
            try:
                plots = self._capture_plots(request.conversation_id, request.execution_id)
            except:
                plots = []
            
            return ExecutionResponse(
                success=False,
                output="",
                error=error_msg,
                variables={},
                execution_time=time.time() - start_time,
                plots=plots,
                execution_id=request.execution_id,
                status=ExecutionStatus.FAILED
            )
    
    def get_conversation_state(self, conversation_id: str) -> Dict[str, Any]:
        """Get conversation state."""
        state = self._load_conversation_state(conversation_id)
        
        # Convert to summaries for API response
        summaries = {}
        for name, value in state.items():
            summaries[name] = self._create_variable_summary(name, value)
        
        return summaries
    
    def clear_conversation_state(self, conversation_id: str):
        """Clear conversation state."""
        with self._get_db_connection() as conn:
            conn.execute("DELETE FROM conversation_state WHERE conversation_id = ?", (conversation_id,))
            conn.commit()

# Create service instance
execution_service = SimpleExecutionService()

# Create FastAPI app
app = FastAPI(title="Simple Python Execution Service", version="3.0.0")

@app.post("/execute", response_model=ExecutionResponse)
async def execute_code(request: ExecutionRequest):
    """Execute Python code."""
    return execution_service.execute_code(request)

@app.post("/execute/async")
async def execute_code_async(request: ExecutionRequest, background_tasks: BackgroundTasks):
    """Execute Python code asynchronously."""
    # For simplicity, just run synchronously in background
    def run_execution():
        result = execution_service.execute_code(request)
        # Could send callback here if needed
        logger.info(f"Async execution {request.execution_id} completed: {result.success}")
    
    background_tasks.add_task(run_execution)
    return {"status": "started", "execution_id": request.execution_id}

@app.get("/state/{conversation_id}")
async def get_conversation_state(conversation_id: str):
    """Get conversation state."""
    variables = execution_service.get_conversation_state(conversation_id)
    return {"conversation_id": conversation_id, "variables": variables}

@app.delete("/state/{conversation_id}")
async def clear_conversation_state(conversation_id: str):
    """Clear conversation state."""
    execution_service.clear_conversation_state(conversation_id)
    return {"success": True, "conversation_id": conversation_id}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "simple-execution", "version": "3.0.0"}

@app.get("/stats")
async def get_stats():
    """Get service statistics."""
    return {"service": "simple-execution", "version": "3.0.0"}

@app.get("/plots/{filename}")
async def serve_plot(filename: str):
    """Serve plot files."""
    import os
    from fastapi.responses import FileResponse
    from fastapi import HTTPException
    
    plots_dir = "/app/data/plots"
    filepath = os.path.join(plots_dir, filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Plot not found")
    
    if not filename.endswith('.png'):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    # Security check: ensure filename doesn't contain path traversal
    if '..' in filename or '/' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    return FileResponse(filepath, media_type="image/png")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001) 