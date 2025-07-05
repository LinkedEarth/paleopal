"""
Python Execution Service

Provides secure Python code execution with variable state management
for the code generation agent. Supports PyLiPD, Pyleoclim, and common
data science libraries.

Now includes persistent state storage to survive server restarts.
"""

# Configure matplotlib FIRST to prevent GUI issues
try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
except ImportError:
    pass  # matplotlib not available

import logging
import io
import traceback
import pickle
import sqlite3
import uuid
from typing import Dict, Any, List, Optional, Set
from contextlib import redirect_stdout, redirect_stderr
import threading
import time
from pathlib import Path
from datetime import datetime

# For secure execution
import ast

logger = logging.getLogger(__name__)

# Database path for state persistence
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DATA_DIR.mkdir(exist_ok=True)
_STATE_DB_PATH = _DATA_DIR / "execution_states.db"

# Plots directory for storing generated plots
_PLOTS_DIR = _DATA_DIR / "plots"
_PLOTS_DIR.mkdir(exist_ok=True)

class ExecutionResult:
    """Result of code execution."""
    
    def __init__(
        self,
        success: bool,
        output: str = "",
        error: str = "",
        variables: Dict[str, Any] = None,
        execution_time: float = 0.0,
        plots: List[str] = None
    ):
        self.success = success
        self.output = output
        self.error = error
        self.variables = variables or {}
        self.execution_time = execution_time
        self.plots = plots or []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "variables": self._serialize_variables(),
            "execution_time": self.execution_time,
            "plots": self.plots
        }
    
    def _serialize_variables(self) -> Dict[str, Any]:
        """Serialize variables for storage."""
        serialized = {}
        for name, value in self.variables.items():
            try:
                # Try to get a string representation
                var_type = type(value).__name__
                var_str = str(value)
                
                # Truncate long outputs
                if len(var_str) > 1000:
                    var_str = var_str[:1000] + "..."
                
                serialized[name] = {
                    "type": var_type,
                    "value": var_str,
                    "module": getattr(type(value), "__module__", "builtins")
                }
            except Exception as e:
                serialized[name] = {
                    "type": type(value).__name__,
                    "value": f"<Error serializing: {e}>",
                    "module": "unknown"
                }
        
        return serialized


class PythonExecutionService:
    """Service for executing Python code with state management and persistence."""
    
    # Allowed imports for security
    ALLOWED_MODULES = {
        'numpy', 'np', 'pandas', 'pd', 'matplotlib', 'plt', 'seaborn', 'sns',
        'pylipd', 'pyleoclim', 'pyleo', 'datetime', 'os', 'sys', 'json', 'ast',
        'ammonyte', 'math', 'statistics', 'collections', 're', 'itertools', 'functools',
        'pathlib', 'warnings', 'SPARQLWrapper', 'JSON'
    }
    
    # Restricted builtins for security
    SAFE_BUILTINS = {
        'abs', 'all', 'any', 'bin', 'bool', 'chr', 'dict', 'dir', 'divmod',
        'enumerate', 'filter', 'float', 'format', 'frozenset', 'getattr',
        'hasattr', 'hash', 'hex', 'id', 'int', 'isinstance', 'issubclass',
        'iter', 'len', 'list', 'map', 'max', 'min', 'oct', 'ord', 'pow',
        'print', 'range', 'repr', 'reversed', 'round', 'set', 'setattr',
        'slice', 'sorted', 'str', 'sum', 'tuple', 'type', 'vars', 'zip'
    }
    
    def __init__(self):
        # Configure matplotlib FIRST to prevent GUI issues during state loading
        try:
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            import warnings
            warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')
        except ImportError:
            pass  # matplotlib not available
        
        self.conversation_states: Dict[str, Dict[str, Any]] = {}
        self.execution_timeout = 30  # seconds
        self._state_lock = threading.Lock()
        
        # Initialize state persistence database
        self._init_state_db()
        
        # Clean up any corrupted states first
        self._clean_corrupted_states()
        
        # Load existing states on startup
        self._load_all_states()
        
    def _init_state_db(self):
        """Initialize the execution state database."""
        try:
            with sqlite3.connect(_STATE_DB_PATH) as conn:
                # Check if variable_origins column exists, add it if not
                cursor = conn.execute("PRAGMA table_info(execution_states)")
                columns = [row[1] for row in cursor.fetchall()]
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS execution_states (
                        conversation_id TEXT PRIMARY KEY,
                        state_data BLOB NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        variable_count INTEGER DEFAULT 0,
                        state_size INTEGER DEFAULT 0,
                        variable_origins TEXT DEFAULT NULL
                    )
                """)
                
                # Add variable_origins column if it doesn't exist (migration)
                if 'variable_origins' not in columns:
                    logger.info("Adding variable_origins column to execution_states table")
                    conn.execute("ALTER TABLE execution_states ADD COLUMN variable_origins TEXT DEFAULT NULL")
                
                conn.commit()
                logger.debug("Execution states database initialized")
        except Exception as e:
            logger.error(f"Error initializing execution states database: {e}")
            raise
    
    def _save_state(self, conversation_id: str, state: Dict[str, Any]):
        """Save execution state to database, excluding non-picklable objects."""
        try:
            with self._state_lock:
                # Create a filtered state that excludes non-picklable objects
                picklable_state = {}
                module_imports = []
                
                for name, value in state.items():
                    try:
                        # Skip built-in modules and functions
                        if hasattr(value, '__module__') and value.__module__ in ['builtins', 'numpy', 'pandas', 'matplotlib.pyplot', 'matplotlib', 'warnings']:
                            # Track module imports for restoration
                            module_imports.append({
                                'name': name,
                                'module': value.__module__,
                                'type': type(value).__name__
                            })
                            continue
                        
                        # Test if the object can be pickled
                        pickle.dumps(value)
                        picklable_state[name] = value
                        
                    except (TypeError, AttributeError, pickle.PicklingError) as e:
                        # Track non-picklable objects for better debugging
                        logger.debug(f"Skipping non-picklable object '{name}' of type {type(value).__name__}: {str(e)[:100]}")
                        # Store metadata about non-picklable objects for restoration hints
                        if hasattr(value, '__class__') and hasattr(value.__class__, '__module__'):
                            module_imports.append({
                                'name': name,
                                'module': value.__class__.__module__,
                                'type': type(value).__name__,
                                'non_picklable': True
                            })
                        continue
                
                # Create the state package with both data and metadata
                state_package = {
                    'variables': picklable_state,
                    'module_imports': module_imports,
                    'version': '1.0'
                }
                
                # Serialize the state package
                state_data = pickle.dumps(state_package)
                state_size = len(state_data)
                variable_count = len(picklable_state)
                
                now_iso = datetime.utcnow().isoformat()
                
                with sqlite3.connect(_STATE_DB_PATH) as conn:
                    # Check if state exists
                    cursor = conn.execute(
                        "SELECT created_at FROM execution_states WHERE conversation_id = ?",
                        (conversation_id,)
                    )
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update existing state
                        conn.execute("""
                            UPDATE execution_states 
                            SET state_data = ?, updated_at = ?, variable_count = ?, state_size = ?
                            WHERE conversation_id = ?
                        """, (state_data, now_iso, variable_count, state_size, conversation_id))
                    else:
                        # Insert new state
                        conn.execute("""
                            INSERT INTO execution_states 
                            (conversation_id, state_data, created_at, updated_at, variable_count, state_size)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (conversation_id, state_data, now_iso, now_iso, variable_count, state_size))
                    
                    conn.commit()
                    
                logger.debug(f"Saved execution state for conversation {conversation_id} ({variable_count} variables, {state_size} bytes)")
                
        except Exception as e:
            logger.error(f"Error saving execution state for {conversation_id}: {e}")
    
    def _load_state(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Load execution state from database and restore module imports."""
        try:
            # Configure matplotlib before any unpickling to prevent GUI issues
            try:
                import matplotlib
                matplotlib.use('Agg')  # Ensure non-interactive backend
                import warnings
                warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')
            except ImportError:
                pass
            
            with sqlite3.connect(_STATE_DB_PATH) as conn:
                cursor = conn.execute(
                    "SELECT state_data FROM execution_states WHERE conversation_id = ?",
                    (conversation_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    # Deserialize state package using pickle
                    state_data = row[0]
                    try:
                        state_package = pickle.loads(state_data)
                    except Exception as pickle_error:
                        logger.warning(f"Failed to unpickle state for {conversation_id}: {pickle_error}")
                        # Return None to force creation of fresh state
                        return None
                    
                    # Handle both old format (direct state) and new format (state package)
                    if isinstance(state_package, dict) and 'variables' in state_package:
                        # New format with module imports
                        restored_state = state_package['variables'].copy()
                        
                        # Restore module imports
                        module_imports = state_package.get('module_imports', [])
                        for module_info in module_imports:
                            name = module_info['name']
                            module_name = module_info['module']
                            
                            try:
                                # Re-import the module
                                if module_name == 'numpy':
                                    import numpy as np
                                    if name in ['np', 'numpy']:
                                        restored_state[name] = np
                                elif module_name == 'pandas':
                                    import pandas as pd
                                    if name in ['pd', 'pandas']:
                                        restored_state[name] = pd
                                elif module_name == 'matplotlib.pyplot':
                                    import matplotlib
                                    matplotlib.use('Agg')  # Ensure non-interactive backend
                                    import matplotlib.pyplot as plt
                                    if name in ['plt', 'matplotlib']:
                                        restored_state[name] = plt
                                elif module_name == 'matplotlib':
                                    import matplotlib
                                    matplotlib.use('Agg')
                                    if name == 'matplotlib':
                                        restored_state[name] = matplotlib
                                elif module_name == 'warnings':
                                    import warnings
                                    if name == 'warnings':
                                        restored_state[name] = warnings
                                        
                                # Try to import PyLiPD and Pyleoclim if they were in the original state
                                if name == 'pylipd':
                                    try:
                                        import pylipd
                                        restored_state[name] = pylipd
                                    except ImportError:
                                        logger.warning("PyLiPD not available during state restoration")
                                elif name in ['pyleoclim', 'pyleo']:
                                    try:
                                        import pyleoclim as pyleo
                                        restored_state[name] = pyleo
                                    except ImportError:
                                        logger.warning("Pyleoclim not available during state restoration")
                                        
                            except ImportError as e:
                                logger.warning(f"Could not restore module import '{name}': {e}")
                        
                        logger.debug(f"Loaded execution state for conversation {conversation_id} with {len(restored_state)} variables")
                        return restored_state
                    else:
                        # Old format - direct state (fallback)
                        logger.debug(f"Loaded legacy execution state for conversation {conversation_id}")
                        return state_package
                    
        except Exception as e:
            logger.error(f"Error loading execution state for {conversation_id}: {e}")
            
        return None
    
    def _load_all_states(self):
        """Load all execution states on service startup."""
        try:
            with sqlite3.connect(_STATE_DB_PATH) as conn:
                cursor = conn.execute("SELECT conversation_id FROM execution_states")
                conversation_ids = [row[0] for row in cursor.fetchall()]
                
            loaded_count = 0
            failed_count = 0
            
            for conv_id in conversation_ids:
                try:
                    state = self._load_state(conv_id)
                    if state:
                        self.conversation_states[conv_id] = state
                        loaded_count += 1
                    else:
                        failed_count += 1
                        logger.debug(f"Failed to load state for conversation {conv_id}")
                except Exception as e:
                    failed_count += 1
                    logger.warning(f"Error loading state for conversation {conv_id}: {e}")
                    
            if loaded_count > 0:
                logger.info(f"Restored execution states for {loaded_count} conversations")
            if failed_count > 0:
                logger.info(f"Failed to restore {failed_count} conversation states (will create fresh states when needed)")
                
        except Exception as e:
            logger.error(f"Error loading execution states on startup: {e}")
    
    def get_conversation_state(self, conversation_id: str) -> Dict[str, Any]:
        """Get the variable state for a conversation."""
        if conversation_id not in self.conversation_states:
            # Try to load from database first
            loaded_state = self._load_state(conversation_id)
            if loaded_state:
                self.conversation_states[conversation_id] = loaded_state
            else:
                # Create new initial state
                self.conversation_states[conversation_id] = self._create_initial_state()
                # Save the initial state
                self._save_state(conversation_id, self.conversation_states[conversation_id])
                
        return self.conversation_states[conversation_id]
    
    def _create_initial_state(self) -> Dict[str, Any]:
        """Create initial execution state with common imports."""
        state = {}
        
        # Pre-import common libraries
        try:
            import numpy as np
            import pandas as pd
            
            # Configure matplotlib for non-interactive use to avoid GUI issues
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            import matplotlib.pyplot as plt
            import warnings
            
            # Configure matplotlib to suppress GUI warnings
            warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')
            
            state.update({
                'np': np,
                'numpy': np,
                'pd': pd,
                'pandas': pd,
                'plt': plt,
                'matplotlib': plt,
                'warnings': warnings,
                # Add plot tracking variables
                '_plot_counter': 0,
                '_generated_plots': []
            })
            
            # Try to import PyLiPD and Pyleoclim if available
            try:
                import pylipd
                state['pylipd'] = pylipd
            except ImportError:
                logger.warning("PyLiPD not available in execution environment")
            
            try:
                import pyleoclim as pyleo
                state['pyleoclim'] = pyleo
                state['pyleo'] = pyleo
            except ImportError:
                logger.warning("Pyleoclim not available in execution environment")
            
            # Try to import SPARQLWrapper for SPARQL agent
            try:
                import SPARQLWrapper
                from SPARQLWrapper import SPARQLWrapper as SPARQLWrapperClass, JSON
                state['SPARQLWrapper'] = SPARQLWrapperClass
                state['JSON'] = JSON
            except ImportError:
                logger.warning("SPARQLWrapper not available in execution environment")
                
        except ImportError as e:
            logger.error(f"Failed to import basic libraries: {e}")
        
        return state
    
    def _clean_corrupted_states(self):
        """Remove corrupted states from the database."""
        try:
            corrupted_conversations = []
            
            with sqlite3.connect(_STATE_DB_PATH) as conn:
                cursor = conn.execute("SELECT conversation_id, state_data FROM execution_states")
                
                for conv_id, state_data in cursor.fetchall():
                    try:
                        # Try to unpickle the state
                        pickle.loads(state_data)
                    except Exception:
                        corrupted_conversations.append(conv_id)
                
                # Remove corrupted states
                if corrupted_conversations:
                    for conv_id in corrupted_conversations:
                        conn.execute("DELETE FROM execution_states WHERE conversation_id = ?", (conv_id,))
                    conn.commit()
                    logger.info(f"Cleaned up {len(corrupted_conversations)} corrupted execution states")
                    
        except Exception as e:
            logger.error(f"Error cleaning corrupted states: {e}")
    
    def _save_current_plots(self, conversation_id: str, execution_globals: Dict[str, Any]) -> List[str]:
        """Save any current matplotlib plots to files and return their paths."""
        saved_plots = []
        
        try:
            import matplotlib.pyplot as plt
            
            # Get all current figure numbers
            fig_nums = plt.get_fignums()
            
            if fig_nums:
                for fig_num in fig_nums:
                    try:
                        fig = plt.figure(fig_num)
                        
                        # Generate unique filename
                        plot_id = str(uuid.uuid4())[:8]
                        timestamp = int(time.time())
                        filename = f"plot_{conversation_id}_{timestamp}_{plot_id}.png"
                        filepath = _PLOTS_DIR / filename
                        
                        # Save the plot
                        fig.savefig(filepath, dpi=150, bbox_inches='tight', 
                                   facecolor='white', edgecolor='none')
                        
                        saved_plots.append(filename)
                        logger.info(f"Saved plot to {filepath}")
                        
                        # Close the figure to free memory
                        plt.close(fig)
                        
                    except Exception as e:
                        logger.warning(f"Failed to save figure {fig_num}: {e}")
                        continue
                
                # Update plot tracking in globals
                if '_generated_plots' in execution_globals:
                    execution_globals['_generated_plots'].extend(saved_plots)
                else:
                    execution_globals['_generated_plots'] = saved_plots
                    
        except Exception as e:
            logger.warning(f"Error saving plots: {e}")
        
        return saved_plots
    
    def _get_image_files(self, working_dir: Path = None) -> Set[Path]:
        """Get set of existing image files in working directory."""
        if working_dir is None:
            working_dir = Path.cwd()
        
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.svg', '.pdf'}
        image_files = set()
        
        try:
            for file_path in working_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                    image_files.add(file_path)
        except Exception as e:
            logger.warning(f"Error scanning for image files: {e}")
        
        return image_files
    
    def _detect_and_move_saved_plots(self, conversation_id: str, existing_files: Set[Path], working_dir: Path = None) -> List[str]:
        """Detect new image files saved directly by code execution and move them to plots directory."""
        moved_plots = []
        
        try:
            # Default to current working directory if not specified
            if working_dir is None:
                working_dir = Path.cwd()
            
            # Get current image files
            current_files = self._get_image_files(working_dir)
            
            # Find new files (created during execution)
            new_files = current_files - existing_files
            
            for file_path in new_files:
                try:
                    # Generate unique filename in plots directory
                    plot_id = str(uuid.uuid4())[:8]
                    timestamp = int(time.time())
                    extension = file_path.suffix
                    
                    # Create new filename with conversation ID and timestamp
                    new_filename = f"plot_c_{conversation_id}_{timestamp}_{plot_id}{extension}"
                    new_filepath = _PLOTS_DIR / new_filename
                    
                    # Move the file to plots directory
                    import shutil
                    shutil.move(str(file_path), str(new_filepath))
                    
                    moved_plots.append(new_filename)
                    logger.info(f"Moved plot from {file_path} to {new_filepath}")
                    
                except Exception as e:
                    logger.warning(f"Failed to move plot file {file_path}: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Error detecting saved plots: {e}")
        
        return moved_plots
    
    def execute_code(
        self, 
        code: str, 
        conversation_id: str,
        timeout: Optional[int] = None,
        message_id: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute Python code in a conversation context.
        
        Args:
            code: Python code to execute
            conversation_id: Conversation ID for state management
            timeout: Execution timeout in seconds
            message_id: Message ID for variable origin tracking
            
        Returns:
            ExecutionResult with output, errors, and updated variables
        """
        start_time = time.time()
        timeout = timeout or self.execution_timeout
        
        # Set message context for variable origin tracking
        if message_id:
            self._current_message_id = message_id
        
        # Configure matplotlib BEFORE any code execution to prevent GUI issues
        try:
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            import warnings
            warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')
        except ImportError:
            pass  # matplotlib not available
        
        # Get conversation state
        state = self.get_conversation_state(conversation_id)
        
        # Prepare execution environment
        execution_globals = state.copy()
        execution_locals = {}
        
        # Take snapshot of existing image files before execution
        existing_image_files = self._get_image_files()
        
        # Capture output
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            # Validate code for security
            if not self._is_code_safe(code):
                return ExecutionResult(
                    success=False,
                    error="Code contains potentially unsafe operations",
                    execution_time=time.time() - start_time
                )
            
            # Execute with timeout
            result = self._execute_with_timeout(
                code, execution_globals, execution_locals, 
                stdout_capture, stderr_capture, timeout
            )
            
            execution_time = time.time() - start_time
            
            if result["success"]:
                # Save any generated plots from matplotlib figures
                saved_plots = self._save_current_plots(conversation_id, execution_globals)
                
                # Detect and move any plots saved directly to files (e.g., pyleo.savefig, plt.savefig)
                moved_plots = self._detect_and_move_saved_plots(conversation_id, existing_image_files)
                
                # Combine all plots
                all_plots = saved_plots + moved_plots
                
                # Update conversation state with new variables
                self._update_conversation_state(
                    conversation_id, execution_globals, execution_locals
                )
                
                return ExecutionResult(
                    success=True,
                    output=stdout_capture.getvalue(),
                    variables=self._extract_user_variables(execution_globals, execution_locals),
                    execution_time=execution_time,
                    plots=all_plots
                )
            else:
                return ExecutionResult(
                    success=False,
                    output=stdout_capture.getvalue(),
                    error=result["error"],
                    execution_time=execution_time
                )
                
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Execution failed: {str(e)}",
                execution_time=time.time() - start_time
            )
        finally:
            # Clear message context
            if hasattr(self, '_current_message_id'):
                delattr(self, '_current_message_id')
    
    def _is_code_safe(self, code: str) -> bool:
        """Check if code is safe to execute."""
        try:
            tree = ast.parse(code)
            
            # Check for dangerous operations
            for node in ast.walk(tree):
                # Block dangerous function calls (but only actual calls, not strings)
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        # Only block if it's an actual function call, not a string containing these words
                        if node.func.id in ['open', 'exec', 'eval', '__import__']:
                            return False
                    elif isinstance(node.func, ast.Attribute):
                        # Block dangerous method calls
                        if node.func.attr in ['system', 'popen', 'spawn']:
                            return False
                
                # Block subprocess imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in ['subprocess', 'os.system', 'commands']:
                            return False
                
                if isinstance(node, ast.ImportFrom):
                    if node.module in ['subprocess', 'commands']:
                        return False
                
                # Block direct access to dangerous builtins
                if isinstance(node, ast.Name):
                    if node.id in ['__builtins__', '__globals__', '__locals__']:
                        return False
            
            return True
            
        except SyntaxError:
            logger.warning(f"Syntax error in code safety check: {code[:100]}...")
            return False


    
    def _execute_with_timeout(
        self, 
        code: str, 
        globals_dict: Dict[str, Any], 
        locals_dict: Dict[str, Any],
        stdout_capture: io.StringIO,
        stderr_capture: io.StringIO,
        timeout: int
    ) -> Dict[str, Any]:
        """Execute code with timeout protection."""
        
        result = {"success": False, "error": ""}
        
        def target():
            try:
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    # Use the same dictionary for globals and locals to ensure imports are accessible
                    exec(code, globals_dict)
                result["success"] = True
            except Exception as e:
                result["error"] = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        
        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout)
        
        if thread.is_alive():
            result["error"] = f"Code execution timed out after {timeout} seconds"
            # Note: We can't actually kill the thread in Python, but we can ignore its result
        
        return result
    
    def _update_conversation_state(
        self, 
        conversation_id: str, 
        globals_dict: Dict[str, Any], 
        locals_dict: Dict[str, Any]
    ):
        """Update the conversation state with new variables and persist to database."""
        # Merge locals into globals for the conversation state
        current_state = self.conversation_states[conversation_id]
        
        # Track new variables for origin tracking
        new_variables = {}
        
        # Update with new variables from locals (user-defined variables)
        for name, value in locals_dict.items():
            if not name.startswith('_'):  # Skip private variables
                if name not in current_state:  # This is a new variable
                    new_variables[name] = value
                current_state[name] = value
        
        # Update with modified globals (including non-picklable objects)
        for name, value in globals_dict.items():
            # Include ALL user variables, not just those already in state
            if not name.startswith('_') and name not in self.SAFE_BUILTINS:
                if name not in current_state:  # This is a new variable
                    new_variables[name] = value
                current_state[name] = value
        
        # Persist the updated state to database
        self._save_state(conversation_id, current_state)
        
        # Update variable origins for new variables if we have a current message context
        if new_variables and hasattr(self, '_current_message_id'):
            self._update_variable_origins(conversation_id, self._current_message_id, new_variables)
    
    def _extract_user_variables(
        self, 
        globals_dict: Dict[str, Any], 
        locals_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract user-defined variables for display."""
        user_vars = {}
        
        # Get variables from locals (newly defined)
        for name, value in locals_dict.items():
            if not name.startswith('_'):  # Include ALL user variables, not just non-callable ones
                user_vars[name] = value
        
        # Also get important variables from globals that might have been modified
        for name, value in globals_dict.items():
            if (not name.startswith('_') and 
                name not in self.SAFE_BUILTINS and 
                name not in ['__builtins__', '__file__', '__name__'] and
                not hasattr(value, '__module__') or 
                (hasattr(value, '__module__') and value.__module__ not in ['builtins', 'numpy', 'pandas', 'matplotlib.pyplot'])):
                user_vars[name] = value
        
        return user_vars
    
    def get_variable_summary(self, conversation_id: str) -> Dict[str, Any]:
        """Get a summary of variables in the conversation."""
        state = self.get_conversation_state(conversation_id)
        
        summary = {}
        for name, value in state.items():
            if not name.startswith('_') and name not in self.SAFE_BUILTINS:
                try:
                    var_type = type(value).__name__
                    var_module = getattr(type(value), "__module__", "builtins")
                    
                    # Special handling for different types of objects
                    if callable(value) and hasattr(value, '__self__'):
                        # Method or bound function
                        var_str = f"<bound method of {type(value.__self__).__name__}>"
                    elif hasattr(value, '__class__') and hasattr(value.__class__, '__module__'):
                        # Complex object - show type and module
                        if hasattr(value, '__dict__'):
                            # Object with attributes
                            attr_count = len([k for k in dir(value) if not k.startswith('_')])
                            var_str = f"<{var_type} object with {attr_count} public attributes>"
                        else:
                            var_str = f"<{var_type} object>"
                    elif callable(value):
                        # Function
                        var_str = f"<function {getattr(value, '__name__', 'unknown')}>"
                    else:
                        # Regular value
                        var_str = str(value)
                    
                    # Truncate long outputs
                    if len(var_str) > 200:
                        var_str = var_str[:200] + "..."
                    
                    summary[name] = {
                        "type": var_type,
                        "value": var_str,
                        "module": var_module
                    }
                except Exception:
                    summary[name] = {
                        "type": type(value).__name__,
                        "value": f"<{type(value).__name__} object>",
                        "module": "unknown"
                    }
        
        return summary
    
    def clear_conversation_state(self, conversation_id: str):
        """Clear the state for a conversation from memory and database."""
        if conversation_id in self.conversation_states:
            del self.conversation_states[conversation_id]
        
        # Remove from database
        try:
            with sqlite3.connect(_STATE_DB_PATH) as conn:
                conn.execute("DELETE FROM execution_states WHERE conversation_id = ?", (conversation_id,))
                conn.commit()
                logger.debug(f"Cleared execution state for conversation {conversation_id}")
        except Exception as e:
            logger.error(f"Error clearing execution state for {conversation_id}: {e}")
    
    def reset_conversation_state(self, conversation_id: str):
        """Reset conversation state to initial state and persist."""
        initial_state = self._create_initial_state()
        self.conversation_states[conversation_id] = initial_state
        self._save_state(conversation_id, initial_state)
    
    def restore_conversation_state_from_messages(self, conversation_id: str, remaining_messages: List[Any]):
        """Rebuild conversation state by re-executing code from remaining messages in order."""
        try:
            # 1. Start fresh
            self.reset_conversation_state(conversation_id)
                
            # 2. Replay every remaining message in chronological order
            for message in remaining_messages:
                if getattr(message, "generated_code", None):
                    try:
                        self.execute_code(
                            code=message.generated_code,
                            conversation_id=conversation_id,
                            timeout=30,
                            message_id=message.id  # Pass message ID for origin tracking
                        )
                    except Exception as e:
                        logger.warning(f"Failed to re-execute code from message {message.id}: {e}")
                        # Continue replaying even if one snippet fails
                        continue
            logger.info(f"Successfully rebuilt execution state for conversation {conversation_id}. Variables: {len(self.get_conversation_state(conversation_id))}")
        except Exception as e:
            logger.error(f"Error rebuilding execution state for {conversation_id}: {e}")
            self.reset_conversation_state(conversation_id)

    def smart_rebuild_conversation_state(self, conversation_id: str, deleted_messages: List[Any], remaining_messages: List[Any]):
        """Smart rebuild that only removes variables from deleted messages and preserves the rest."""
        try:
            current_state = self.get_conversation_state(conversation_id)
            
            # Get variable origins from current state metadata (if we have it)
            variable_origins = self._get_variable_origins(conversation_id)
            
            # Find variables that were created by deleted messages
            variables_to_remove = set()
            deleted_message_ids = {msg.id for msg in deleted_messages}
            
            for var_name, origin_message_id in variable_origins.items():
                if origin_message_id in deleted_message_ids:
                    variables_to_remove.add(var_name)
            
            # If we don't have origin tracking, fall back to analyzing execution results
            if not variable_origins and deleted_messages:
                for deleted_msg in deleted_messages:
                    if hasattr(deleted_msg, 'execution_results') and deleted_msg.execution_results:
                        for result in deleted_msg.execution_results:
                            if hasattr(result, 'variable_summary') and result.variable_summary:
                                variables_to_remove.update(result.variable_summary.keys())
                            elif isinstance(result, dict) and result.get('variable_summary'):
                                variables_to_remove.update(result['variable_summary'].keys())
            
            # Remove only the affected variables
            if variables_to_remove:
                logger.info(f"Smart rebuild: removing {len(variables_to_remove)} variables: {list(variables_to_remove)}")
                for var_name in variables_to_remove:
                    if var_name in current_state:
                        del current_state[var_name]
                
                # Update variable origins tracking
                for var_name in variables_to_remove:
                    if var_name in variable_origins:
                        del variable_origins[var_name]
                
                self._save_variable_origins(conversation_id, variable_origins)
                self._save_state(conversation_id, current_state)
                
                logger.info(f"Smart rebuild completed. Preserved {len(current_state)} variables, removed {len(variables_to_remove)}")
            else:
                logger.info("Smart rebuild: no variables to remove, state preserved as-is")
                
        except Exception as e:
            logger.error(f"Smart rebuild failed for {conversation_id}: {e}. Falling back to full rebuild.")
            # Fall back to full rebuild if smart rebuild fails
            self.restore_conversation_state_from_messages(conversation_id, remaining_messages)

    def _get_variable_origins(self, conversation_id: str) -> Dict[str, str]:
        """Get mapping of variable names to the message IDs that created them."""
        try:
            with sqlite3.connect(_STATE_DB_PATH) as conn:
                cursor = conn.execute(
                    "SELECT variable_origins FROM execution_states WHERE conversation_id = ?",
                    (conversation_id,)
                )
                row = cursor.fetchone()
                if row and row[0]:
                    import json
                    return json.loads(row[0])
        except Exception as e:
            logger.debug(f"Could not load variable origins for {conversation_id}: {e}")
        return {}
    
    def _save_variable_origins(self, conversation_id: str, origins: Dict[str, str]):
        """Save mapping of variable names to message IDs that created them."""
        try:
            import json
            origins_json = json.dumps(origins)
            with sqlite3.connect(_STATE_DB_PATH) as conn:
                conn.execute("""
                    UPDATE execution_states 
                    SET variable_origins = ? 
                    WHERE conversation_id = ?
                """, (origins_json, conversation_id))
                conn.commit()
        except Exception as e:
            logger.debug(f"Could not save variable origins for {conversation_id}: {e}")

    def _update_variable_origins(self, conversation_id: str, message_id: str, new_variables: Dict[str, Any]):
        """Update variable origins tracking when new variables are created."""
        try:
            origins = self._get_variable_origins(conversation_id)
            
            # Add origins for new variables
            for var_name in new_variables.keys():
                if not var_name.startswith('_'):  # Skip private variables
                    origins[var_name] = message_id
            
            self._save_variable_origins(conversation_id, origins)
        except Exception as e:
            logger.debug(f"Could not update variable origins for {conversation_id}: {e}")
    
    def get_state_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored execution states."""
        try:
            with sqlite3.connect(_STATE_DB_PATH) as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_states,
                        SUM(variable_count) as total_variables,
                        SUM(state_size) as total_size,
                        AVG(variable_count) as avg_variables,
                        AVG(state_size) as avg_size
                    FROM execution_states
                """)
                row = cursor.fetchone()
                
                return {
                    "total_conversations": row[0] if row[0] else 0,
                    "total_variables": row[1] if row[1] else 0,
                    "total_size_bytes": row[2] if row[2] else 0,
                    "avg_variables_per_conversation": row[3] if row[3] else 0,
                    "avg_size_per_conversation": row[4] if row[4] else 0,
                    "in_memory_conversations": len(self.conversation_states)
                }
        except Exception as e:
            logger.error(f"Error getting state statistics: {e}")
            return {
                "error": str(e),
                "in_memory_conversations": len(self.conversation_states)
            }

    def remove_variables(self, conversation_id: str, var_names: List[str]):
        """Remove specific variables from a conversation state and persist."""
        if not var_names:
            return
        state = self.get_conversation_state(conversation_id)
        changed = False
        for name in var_names:
            if name in state:
                state.pop(name, None)
                changed = True
        if changed:
            self._save_state(conversation_id, state)


# Global service instance
python_execution_service = PythonExecutionService() 