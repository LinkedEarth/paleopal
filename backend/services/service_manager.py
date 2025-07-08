"""
Service Manager for PaleoPal Backend

Centralized management of all services including LLM providers, 
embedding services, and database connections.
"""

import logging
from typing import Optional, Dict, Any
from langchain_core.language_models import BaseLanguageModel
import os

# Import services
from services.sparql_service import SPARQLService

# Import LLM provider factory
from services.llm_providers import LLMProviderFactory

# Import config
from config import SPARQL_ENDPOINT_URL

# Option to use isolated execution service
USE_ISOLATED_EXECUTION = os.getenv('USE_ISOLATED_EXECUTION', 'true').lower() == 'true'

logger = logging.getLogger(__name__)

if USE_ISOLATED_EXECUTION:
    logger.info("🔗 Configured to use isolated execution service")
else:
    logger.info("🔧 Configured to use local async execution service")


class ServiceManager:
    """Centralized service manager for all backend services."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Ensure only one instance of ServiceManager exists."""
        if cls._instance is None:
            cls._instance = super(ServiceManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the service manager (only once)."""
        if ServiceManager._initialized:
            return
        
        self._llm_cache = {}
        self._sparql_service = None
        self._execution_service = None
        
        ServiceManager._initialized = True
        logger.info("ServiceManager initialized")

    def get_execution_service(self):
        """Get the execution service (either isolated or local)."""
        if self._execution_service is None:
            if USE_ISOLATED_EXECUTION:
                from services.execution_client import execution_client
                self._execution_service = execution_client
            else:
                from services.async_execution_service import execution_service
                self._execution_service = execution_service
        return self._execution_service
    
    # Keep the old method name for backward compatibility
    def get_async_execution_service(self):
        """Get async execution service (legacy method name)."""
        return self.get_execution_service()
    
    def get_sparql_service(self, endpoint_url: str = None) -> SPARQLService:
        """
        Get or create SPARQL service.
        
        Args:
            endpoint_url: Optional SPARQL endpoint URL override
            
        Returns:
            SPARQLService: Initialized SPARQL service
        """
        if self._sparql_service is None:
            endpoint = endpoint_url or SPARQL_ENDPOINT_URL
            logger.info(f"Creating SPARQL service for endpoint: {endpoint}")
            self._sparql_service = SPARQLService(endpoint_url=endpoint)
            
        return self._sparql_service
    
    def get_llm_provider(self, provider: str, model: str = None) -> BaseLanguageModel:
        """
        Get or create LLM provider.
        
        Args:
            provider: LLM provider name ('openai', 'anthropic', 'google', 'xai', 'ollama')
            model: Optional model name
            
        Returns:
            BaseLanguageModel: Initialized LLM instance
        """
        cache_key = f"{provider}:{model or 'default'}"
        
        if cache_key not in self._llm_cache:
            logger.info(f"Creating LLM provider: {provider} with model: {model}")
            
            # Use the LLM provider factory
            llm = LLMProviderFactory.get_langchain_model(
                provider_type=provider,
                model_name=model
            )
            
            if llm is None:
                raise ValueError(f"Failed to create LLM provider: {provider}")
            
            self._llm_cache[cache_key] = llm
            
        return self._llm_cache[cache_key]

    def get_service_status(self) -> Dict[str, Any]:
        """Get status of all services."""
        return {
            "sparql_service_initialized": self._sparql_service is not None,
            "execution_service_initialized": self._execution_service is not None,
            "llm_providers_cached": list(self._llm_cache.keys()),
            "execution_service_type": "isolated" if USE_ISOLATED_EXECUTION else "local"
        }


# Global service manager instance
service_manager = ServiceManager() 