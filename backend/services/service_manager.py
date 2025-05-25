"""
Service Manager for PaleoPal Backend

Centralized management of all services including LLM providers, 
embedding services, and database connections.
"""

import logging
from typing import Optional, Dict, Any
from langchain_core.language_models import BaseLanguageModel

# Import services
from services.sparql_embeddings import SparqlEmbeddingsService
from services.code_embeddings import CodeEmbeddingsService
from services.embedding_manager import embedding_manager
from services.sparql_service import SPARQLService
from services.graphdb_embeddings import GraphDBEmbeddingService

# Import LLM provider factory
from services.llm_providers import LLMProviderFactory

# Import config
from config import SPARQL_ENDPOINT_URL, EMBEDDING_PROVIDER

logger = logging.getLogger(__name__)


class ServiceManager:
    """Centralized service manager for all backend services."""
    
    def __init__(self):
        """Initialize the service manager."""
        self._sparql_embeddings: Optional[SparqlEmbeddingsService] = None
        self._code_embeddings: Optional[CodeEmbeddingsService] = None
        self._sparql_service: Optional[SPARQLService] = None
        self._graphdb_embeddings: Optional[GraphDBEmbeddingService] = None
        self._llm_cache: Dict[str, BaseLanguageModel] = {}
        
        # Preload default embeddings to improve first-request performance
        self._preload_embeddings()
        
        logger.info("ServiceManager initialized")
    
    def _preload_embeddings(self):
        """Preload default embedding models to improve performance."""
        try:
            logger.info("Preloading default embedding models...")
            embedding_manager.preload_default_embeddings()
            logger.info("Default embedding models preloaded successfully")
        except Exception as e:
            logger.warning(f"Failed to preload embedding models: {e}")
    
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
    
    def get_graphdb_embeddings(self, provider: str = None) -> GraphDBEmbeddingService:
        """
        Get or create GraphDB embeddings service.
        
        Args:
            provider: Optional embedding provider override
            
        Returns:
            GraphDBEmbeddingService: Initialized GraphDB embeddings service
        """
        if self._graphdb_embeddings is None or (provider and provider != getattr(self._graphdb_embeddings, 'provider', None)):
            logger.info(f"Creating GraphDB embedding service with provider: {provider or 'default'}")
            self._graphdb_embeddings = GraphDBEmbeddingService(provider=provider or EMBEDDING_PROVIDER)
            
            # Pre-connect to the vector database to cache the connection
            try:
                vectorstore = self._graphdb_embeddings._connect_to_vector_db()
                document_count = vectorstore._collection.count() if hasattr(vectorstore, "_collection") else 0
                logger.info(f"GraphDB embedding service ready with {document_count} documents")
            except Exception as e:
                logger.warning(f"Could not pre-connect to GraphDB vector database: {e}")
            
        return self._graphdb_embeddings
    
    def get_sparql_embeddings(self, provider: str = None) -> SparqlEmbeddingsService:
        """
        Get or create SPARQL embeddings service.
        
        Args:
            provider: Optional embedding provider override
            
        Returns:
            SparqlEmbeddingsService: Initialized SPARQL embeddings service
        """
        if self._sparql_embeddings is None or (provider and provider != self._sparql_embeddings.embedding_provider):
            logger.info(f"Creating SPARQL embedding service with provider: {provider or 'default'}")
            self._sparql_embeddings = SparqlEmbeddingsService(embedding_provider=provider)
            self._sparql_embeddings.initialize()
            
            # Get collection stats
            stats = self._sparql_embeddings.get_collection_stats()
            if stats:
                logger.info(f"SPARQL embedding service ready with {stats.get('total_queries', 0)} queries from {stats.get('files_count', 0)} files")
            
        return self._sparql_embeddings
    
    def get_code_embeddings(self, provider: str = None) -> CodeEmbeddingsService:
        """
        Get or create code embeddings service.
        
        Args:
            provider: Optional embedding provider override
            
        Returns:
            CodeEmbeddingsService: Initialized code embeddings service
        """
        if self._code_embeddings is None or (provider and provider != self._code_embeddings.embedding_provider):
            logger.info(f"Creating code embedding service with provider: {provider or 'default'}")
            self._code_embeddings = CodeEmbeddingsService(embedding_provider=provider)
            self._code_embeddings.initialize()
            
            # Get collection stats
            stats = self._code_embeddings.get_collection_stats()
            if stats:
                logger.info(f"Code embedding service ready with {stats.get('total_examples', 0)} examples from {stats.get('notebooks_count', 0)} notebooks")
            
        return self._code_embeddings
    
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
    
    def get_embedding_cache_info(self) -> Dict[str, str]:
        """Get information about cached embedding models."""
        return embedding_manager.get_cache_info()
    
    def clear_embedding_cache(self):
        """Clear embedding model cache."""
        embedding_manager.clear_cache()
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get status of all services."""
        return {
            "sparql_service_initialized": self._sparql_service is not None,
            "graphdb_embeddings_initialized": self._graphdb_embeddings is not None,
            "sparql_embeddings_initialized": self._sparql_embeddings is not None,
            "code_embeddings_initialized": self._code_embeddings is not None,
            "llm_providers_cached": list(self._llm_cache.keys()),
            "embedding_models_cached": list(embedding_manager.get_cache_info().keys()),
        }


# Global service manager instance
service_manager = ServiceManager() 