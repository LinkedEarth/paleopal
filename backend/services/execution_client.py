"""
Execution Client - Clean Implementation

Simple client for interacting with the execution service.
"""

import logging
from typing import Any, Dict, Optional, Callable

from .async_execution_service import (
    AsyncExecutionService,
    ExecutionRequest,
    ExecutionResult
)

logger = logging.getLogger(__name__)

class ExecutionClient:
    """Clean execution client implementation."""
    
    def __init__(self, execution_service_url: str = "http://localhost:8201"):
        self.execution_service = AsyncExecutionService(execution_service_url)
        logger.info("ExecutionClient initialized")
    
    async def execute_code(
        self,
        code: str,
        conversation_id: str,
        execution_id: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """Execute code and return result."""
        if execution_id is None:
            import uuid
            execution_id = str(uuid.uuid4())
        
        request = ExecutionRequest(
            code=code,
            conversation_id=conversation_id,
            execution_id=execution_id,
            timeout=timeout
        )
        
        return await self.execution_service.execute_code_async(request)
    
    def submit_execution(
        self,
        code: str,
        conversation_id: str,
        execution_id: str,
        update_callback: Optional[Callable] = None
    ) -> str:
        """
        Submit execution request for async execution (compatibility method).
        
        This method exists for backward compatibility with the message router.
        Returns the execution_id immediately while execution happens asynchronously.
        """
        import asyncio
        import threading
        
        logger.info(f"🚀 Submitting async execution {execution_id}")
        
        def run_async_execution():
            """Run the execution in a separate thread."""
            try:
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Execute the code
                request = ExecutionRequest(
                    code=code,
                    conversation_id=conversation_id,
                    execution_id=execution_id
                )
                
                result = loop.run_until_complete(
                    self.execution_service.execute_code_async(request)
                )
                
                # Call callback if provided
                if update_callback:
                    try:
                        execution_update = {
                            'type': 'execution_update',
                            'execution_id': execution_id,
                            'status': 'completed' if result.success else 'failed',
                            'success': result.success,
                            'output': result.output,
                            'error': result.error,
                            'execution_time': result.execution_time,
                            'plots': result.plots,
                            'variables': result.variables
                        }
                        update_callback(execution_update)
                    except Exception as cb_e:
                        logger.error(f"Error in execution callback: {cb_e}")
                
                logger.info(f"✅ Async execution {execution_id} completed: success={result.success}")
                
            except Exception as e:
                logger.error(f"❌ Async execution {execution_id} failed: {e}")
                
                # Call error callback if provided
                if update_callback:
                    try:
                        execution_update = {
                            'type': 'execution_update',
                            'execution_id': execution_id,
                            'status': 'failed',
                            'success': False,
                            'output': '',
                            'error': str(e),
                            'execution_time': 0.0,
                            'plots': [],
                            'variables': {}
                        }
                        update_callback(execution_update)
                    except Exception as cb_e:
                        logger.error(f"Error in error callback: {cb_e}")
            finally:
                loop.close()
        
        # Start execution in background thread
        thread = threading.Thread(target=run_async_execution, name=f"async_exec_{execution_id}")
        thread.daemon = True
        thread.start()
        
        return execution_id
    
    def get_variable_summary(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get variable summary for a conversation (compatibility method).
        
        This method exists for backward compatibility with the message router.
        """
        import asyncio
        
        try:
            # Create event loop if needed
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Get variables from the execution service
            variables = loop.run_until_complete(
                self.execution_service.get_conversation_variables(conversation_id)
            )
            
            return variables
        except Exception as e:
            logger.error(f"Failed to get variable summary for {conversation_id}: {e}")
            return {}
    
    async def get_variables(self, conversation_id: str) -> Dict[str, Any]:
        """Get conversation variables."""
        return await self.execution_service.get_conversation_variables(conversation_id)
    
    async def clear_state(self, conversation_id: str) -> bool:
        """Clear conversation state."""
        return await self.execution_service.clear_conversation_state(conversation_id)
    
    async def health_check(self) -> bool:
        """Check service health."""
        return await self.execution_service.health_check()

# Create default client instance
execution_client = ExecutionClient() 