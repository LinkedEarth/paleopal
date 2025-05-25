"""
Singleton Embedding Manager

Manages embedding models as singletons to avoid multiple initializations
and improve performance across all embedding services.
"""

import logging
import threading
from typing import Dict, Optional
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Local embedding helpers
try:
    from services.local_embeddings import create_local_embeddings, get_available_local_providers
    LOCAL_EMBEDDINGS_AVAILABLE = True
except ImportError:
    LOCAL_EMBEDDINGS_AVAILABLE = False

# Global config values
from config import (
    OPENAI_API_KEY,
    GOOGLE_API_KEY,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
)

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """Singleton manager for embedding models."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(EmbeddingManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._embeddings_cache: Dict[str, Embeddings] = {}
            self._initialized = True
            logger.info("EmbeddingManager singleton initialized")
    
    def get_embeddings(self, provider: str, model: str = None) -> Embeddings:
        """
        Get or create embedding model for the specified provider.
        
        Args:
            provider: Embedding provider ('openai', 'google', 'sentence-transformers', etc.)
            model: Optional model name (uses default if not specified)
            
        Returns:
            Embeddings: Cached or newly created embedding model
            
        Raises:
            ValueError: If provider is not supported or requirements not met
        """
        # Use default model if not specified
        if model is None:
            model = EMBEDDING_MODEL
        
        # Create cache key
        cache_key = f"{provider}:{model}"
        
        # Return cached instance if available
        if cache_key in self._embeddings_cache:
            logger.debug(f"Using cached embedding model: {cache_key}")
            return self._embeddings_cache[cache_key]
        
        # Create new embedding model
        logger.info(f"Creating new embedding model: {cache_key}")
        embeddings = self._create_embeddings(provider, model)
        
        # Cache the model
        self._embeddings_cache[cache_key] = embeddings
        logger.info(f"Cached embedding model: {cache_key}")
        
        return embeddings
    
    def _create_embeddings(self, provider: str, model: str) -> Embeddings:
        """
        Create a new embedding model instance.
        
        Args:
            provider: Embedding provider
            model: Model name
            
        Returns:
            Embeddings: New embedding model instance
            
        Raises:
            ValueError: If provider is not supported or requirements not met
        """
        if provider == "openai":
            if not OPENAI_API_KEY:
                raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY in environment.")
            logger.info(f"Creating OpenAI embeddings with model: {model}")
            return OpenAIEmbeddings(model=model)
            
        elif provider == "google":
            if not GOOGLE_API_KEY:
                raise ValueError("Google API key is required. Set GOOGLE_API_KEY in environment.")
            logger.info(f"Creating Google embeddings with model: {model}")
            return GoogleGenerativeAIEmbeddings(model=model)
        
        elif provider in ["sentence-transformers", "ollama", "huggingface"]:
            if not LOCAL_EMBEDDINGS_AVAILABLE:
                raise ValueError(f"Local embeddings not available. Please install required dependencies for {provider}")
            
            # Check if the specific provider is available
            available_providers = get_available_local_providers()
            if not available_providers.get(provider, False):
                raise ValueError(f"Local embedding provider '{provider}' is not available. Please install required dependencies.")
            
            logger.info(f"Creating {provider} embeddings with model: {model}")
            return create_local_embeddings(provider, model)
            
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}. Supported: openai, google, sentence-transformers, ollama, huggingface")
    
    def clear_cache(self):
        """Clear all cached embedding models."""
        logger.info("Clearing embedding model cache")
        self._embeddings_cache.clear()
    
    def get_cache_info(self) -> Dict[str, str]:
        """Get information about cached embedding models."""
        return {
            cache_key: str(type(embeddings).__name__)
            for cache_key, embeddings in self._embeddings_cache.items()
        }
    
    def preload_default_embeddings(self):
        """Preload the default embedding model to improve first-request performance."""
        try:
            default_provider = EMBEDDING_PROVIDER
            logger.info(f"Preloading default embedding model: {default_provider}")
            self.get_embeddings(default_provider)
            logger.info("Default embedding model preloaded successfully")
        except Exception as e:
            logger.warning(f"Failed to preload default embedding model: {e}")


# Global singleton instance
embedding_manager = EmbeddingManager() 