"""
Async Execution Service - Clean Implementation

Interfaces with the isolated execution service for safe code execution.
Simple, reliable design with proper error handling.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ExecutionRequest(BaseModel):
    code: str
    conversation_id: str
    execution_id: str
    timeout: Optional[int] = None
    callback_url: Optional[str] = None

class ExecutionResult(BaseModel):
    success: bool
    output: str = ""
    error: str = ""
    variables: Dict[str, Any] = {}
    execution_time: float = 0.0
    plots: List[str] = []
    execution_id: str
    status: str

class AsyncExecutionService:
    """Clean async execution service implementation."""
    
    def __init__(self, execution_service_url: str = "http://localhost:8201"):
        self.execution_service_url = execution_service_url
        self.default_timeout = 300  # 5 minutes
        logger.info(f"AsyncExecutionService initialized with URL: {execution_service_url}")
    
    async def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make HTTP request to isolated execution service."""
        url = f"{self.execution_service_url}{endpoint}"
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.default_timeout + 30)  # Extra buffer
            async with aiohttp.ClientSession(timeout=timeout) as session:
                if method.upper() == "POST":
                    async with session.post(url, json=data) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            raise Exception(f"HTTP {response.status}: {error_text}")
                elif method.upper() == "GET":
                    async with session.get(url) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            raise Exception(f"HTTP {response.status}: {error_text}")
                elif method.upper() == "DELETE":
                    async with session.delete(url) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            raise Exception(f"HTTP {response.status}: {error_text}")
        except asyncio.TimeoutError:
            raise Exception(f"Request to {url} timed out")
        except Exception as e:
            logger.error(f"Request to {url} failed: {e}")
            raise
    
    async def execute_code_async(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute code asynchronously using the isolated service."""
        start_time = time.time()
        
        try:
            logger.info(f"Starting async execution for {request.execution_id}")
            
            # Prepare request data
            request_data = {
                "code": request.code,
                "conversation_id": request.conversation_id,
                "execution_id": request.execution_id,
                "timeout": request.timeout or self.default_timeout
            }
            
            # Make request to isolated service
            response_data = await self._make_request("POST", "/execute", request_data)
            
            # Convert response to ExecutionResult
            result = ExecutionResult(
                success=response_data.get("success", False),
                output=response_data.get("output", ""),
                error=response_data.get("error", ""),
                variables=response_data.get("variables", {}),
                execution_time=response_data.get("execution_time", time.time() - start_time),
                plots=response_data.get("plots", []),
                execution_id=request.execution_id,
                status=response_data.get("status", "failed")
            )
            
            logger.info(f"Execution {request.execution_id} completed: success={result.success}")
            return result
            
        except Exception as e:
            logger.error(f"Async execution failed for {request.execution_id}: {e}")
            return ExecutionResult(
                success=False,
                error=f"Execution service error: {str(e)}",
                execution_time=time.time() - start_time,
                execution_id=request.execution_id,
                status="failed"
            )
    
    async def execute_code(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute code synchronously (alias for async method)."""
        return await self.execute_code_async(request)
    
    async def get_conversation_variables(self, conversation_id: str) -> Dict[str, Any]:
        """Get variables for a conversation."""
        try:
            response_data = await self._make_request("GET", f"/state/{conversation_id}")
            return response_data.get("variables", {})
        except Exception as e:
            logger.error(f"Failed to get variables for {conversation_id}: {e}")
            return {}
    
    async def clear_conversation_state(self, conversation_id: str) -> bool:
        """Clear conversation state."""
        try:
            await self._make_request("DELETE", f"/state/{conversation_id}")
            logger.info(f"Cleared conversation state for {conversation_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear state for {conversation_id}: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check if the execution service is healthy."""
        try:
            response_data = await self._make_request("GET", "/health")
            return response_data.get("status") == "healthy"
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def get_service_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        try:
            return await self._make_request("GET", "/stats")
        except Exception as e:
            logger.error(f"Failed to get service stats: {e}")
            return {"error": str(e)}
    
    def submit_execution(self, request: ExecutionRequest):
        """Submit execution request (compatibility method)."""
        # This method exists for backward compatibility
        # In the new implementation, we just return the async method
        # The caller should await the result
        return self.execute_code_async(request)

# Create service instance with environment variable support
import os
execution_service_url = os.getenv('EXECUTION_SERVICE_URL', 'http://localhost:8201')
execution_service = AsyncExecutionService(execution_service_url)

# Compatibility functions for existing code
async def execute_code_async(request: ExecutionRequest) -> ExecutionResult:
    return await execution_service.execute_code_async(request)

async def execute_code(request: ExecutionRequest) -> ExecutionResult:
    return await execution_service.execute_code(request)

async def get_conversation_variables(conversation_id: str) -> Dict[str, Any]:
    return await execution_service.get_conversation_variables(conversation_id)

async def clear_conversation_state(conversation_id: str) -> bool:
    return await execution_service.clear_conversation_state(conversation_id)

def submit_execution(request: ExecutionRequest):
    return execution_service.submit_execution(request) 