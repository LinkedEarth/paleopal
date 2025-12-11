"""
Shared Qdrant configuration and utilities for all libraries.
Provides consistent connection, collection management, and embedding operations.
"""
from __future__ import annotations

import os
import logging
import uuid
from typing import List, Dict, Any, Optional, Union
import json
from pathlib import Path
import sys

# Add backend to path for config import
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import (
        Distance, VectorParams, PointStruct, CollectionInfo,
        Filter, FieldCondition, MatchValue, SearchRequest, ScrollRequest
    )
    from qdrant_client.http.exceptions import UnexpectedResponse
except ImportError as e:
    raise ImportError("qdrant-client is required: pip install qdrant-client") from e

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except ImportError as e:
    raise ImportError("sentence-transformers is required: pip install sentence-transformers") from e

logger = logging.getLogger(__name__)

# Default configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")

# Model cache directory - use environment variable or default to backend/models_cache
MODEL_CACHE_DIR = os.getenv(
    "MODEL_CACHE_DIR", 
    str(Path(__file__).parent.parent / "models_cache")
)
# Ensure cache directory exists
Path(MODEL_CACHE_DIR).mkdir(parents=True, exist_ok=True)

# Collection names for each library
COLLECTION_NAMES = {
    "sparql": "sparql_queries",
    "ontology": "ontology_entities", 
    "notebook_snippets": "notebook_snippets",
    "notebook_workflows": "notebook_workflows",
    "literature": "literature_methods",
    "readthedocs_docs": "readthedocs_docs",
    "readthedocs_code": "readthedocs_code",
    "readthedocs_symbols": "readthedocs_symbols"
}


class QdrantManager:
    """Centralized Qdrant connection and collection management."""
    
    def __init__(self, host: str = QDRANT_HOST, port: int = QDRANT_PORT, api_key: Optional[str] = QDRANT_API_KEY):
        self.host = host
        self.port = port
        self.api_key = api_key
        self._client = None
        self._model = None
    
    @property
    def client(self) -> QdrantClient:
        """Get or create Qdrant client."""
        if self._client is None:
            self._client = QdrantClient(
                host=self.host,
                port=self.port,
                api_key=self.api_key
            )
            logger.info(f"Connected to Qdrant at {self.host}:{self.port}")
        return self._client
    
    @property
    def model(self) -> SentenceTransformer:
        """Get or create embedding model."""
        if self._model is None:
            self._model = SentenceTransformer(
                EMBED_MODEL_NAME,
                cache_folder=MODEL_CACHE_DIR
            )
            logger.info(f"Loaded embedding model: {EMBED_MODEL_NAME} (cached in {MODEL_CACHE_DIR})")
        return self._model
    
    def ping(self) -> bool:
        """Test connection to Qdrant server."""
        try:
            collections = self.client.get_collections()
            logger.info(f"Qdrant server is running. Found {len(collections.collections)} collections.")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            return False
    
    def create_collection(
        self, 
        collection_name: str, 
        vector_size: int = 384,  # default for all-MiniLM-L6-v2
        distance: Distance = Distance.COSINE,
        force_recreate: bool = False
    ) -> bool:
        """Create a collection if it doesn't exist."""
        try:
            # Check if collection exists
            try:
                collection_info = self.client.get_collection(collection_name)
                if force_recreate:
                    logger.info(f"Deleting existing collection: {collection_name}")
                    self.client.delete_collection(collection_name)
                else:
                    logger.info(f"Collection {collection_name} already exists")
                    return True
            except UnexpectedResponse:
                # Collection doesn't exist, which is fine
                pass
            
            # Create collection
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=distance)
            )
            logger.info(f"Created collection: {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {e}")
            return False
    
    def index_documents(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]],
        text_field: str = "text",
        batch_size: int = 100
    ) -> int:
        """Index documents into a Qdrant collection."""
        if not documents:
            logger.warning("No documents to index")
            return 0
        
        # Ensure collection exists before indexing
        self.create_collection(collection_name)
        
        # Extract texts for embedding
        texts = [doc.get(text_field, "") for doc in documents]
        if not any(texts):
            logger.warning(f"No text found in field '{text_field}'")
            return 0
        
        # Create embeddings
        logger.info(f"Creating embeddings for {len(texts)} documents...")
        embeddings = self.model.encode(
            texts, 
            normalize_embeddings=True, 
            show_progress_bar=True,
            batch_size=32
        )
        
        # Prepare points for indexing
        points = []
        for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
            # Create a unique ID if not provided
            point_id = doc.get("id", str(uuid.uuid4()))
            
            # Prepare payload (metadata)
            payload = {k: v for k, v in doc.items() if k != "id"}
            
            points.append(PointStruct(
                id=point_id,
                vector=embedding.tolist(),
                payload=payload
            ))
        
        # Index in batches
        total_indexed = 0
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            try:
                self.client.upsert(
                    collection_name=collection_name,
                    points=batch
                )
                total_indexed += len(batch)
                logger.info(f"Indexed batch {i//batch_size + 1}: {len(batch)} documents")
            except Exception as e:
                logger.error(f"Failed to index batch {i//batch_size + 1}: {e}")
        
        logger.info(f"Successfully indexed {total_indexed} documents in {collection_name}")
        return total_indexed
    
    def search(
        self,
        collection_name: str,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        score_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Search documents in a collection."""
        try:
            # Create query embedding
            query_embedding = self.model.encode([query], normalize_embeddings=True)[0]
            
            # Prepare filters
            query_filter = None
            if filters:
                conditions = []
                for field, value in filters.items():
                    if isinstance(value, list):
                        # Multiple values - use OR logic
                        for v in value:
                            conditions.append(FieldCondition(key=field, match=MatchValue(value=v)))
                    else:
                        conditions.append(FieldCondition(key=field, match=MatchValue(value=value)))
                
                if conditions:
                    query_filter = Filter(must=conditions)
            
            # Perform search
            search_result = self.client.search(
                collection_name=collection_name,
                query_vector=query_embedding.tolist(),
                limit=limit,
                query_filter=query_filter,
                score_threshold=score_threshold,
                with_payload=True
            )
            
            # Format results
            results = []
            for hit in search_result:
                result = {
                    "id": hit.id,
                    "score": hit.score,
                    **hit.payload
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Search failed in {collection_name}: {e}")
            return []
    
    def get_collection_info(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a collection."""
        try:
            collection_info = self.client.get_collection(collection_name)
            return {
                "name": collection_name,
                "status": collection_info.status,
                "vectors_count": collection_info.vectors_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count,
                "points_count": collection_info.points_count
            }
        except Exception as e:
            logger.error(f"Failed to get collection info for {collection_name}: {e}")
            return None
    
    def list_collections(self) -> List[str]:
        """List all collections."""
        try:
            collections = self.client.get_collections()
            return [col.name for col in collections.collections]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []
    
    def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection."""
        try:
            self.client.delete_collection(collection_name)
            logger.info(f"Deleted collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection {collection_name}: {e}")
            return False


# Global instance
qdrant_manager = QdrantManager()


def get_qdrant_manager() -> QdrantManager:
    """Get the global Qdrant manager instance."""
    return qdrant_manager


# Utility functions for common operations
def ensure_collection(collection_name: str, vector_size: int = 384) -> bool:
    """Ensure a collection exists."""
    return qdrant_manager.create_collection(collection_name, vector_size)


def index_documents(collection_name: str, documents: List[Dict[str, Any]], text_field: str = "text") -> int:
    """Index documents into a collection."""
    return qdrant_manager.index_documents(collection_name, documents, text_field)


def search_documents(
    collection_name: str,
    query: str,
    limit: int = 10,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Search documents in a collection."""
    return qdrant_manager.search(collection_name, query, limit, filters)


# System status and monitoring functions
def get_system_status() -> Dict[str, Any]:
    """Get comprehensive status of the Qdrant-based system."""
    status = {
        "qdrant_server": "unknown",
        "qdrant_collections": "unknown",
        "embedding_model": "unknown",
        "architecture": "Unified Qdrant vector search"
    }
    
    try:
        manager = get_qdrant_manager()
        
        # Check server connection
        if manager.ping():
            status["qdrant_server"] = "connected"
            
            # Get collection info
            collections = manager.list_collections()
            collection_info = {}
            total_documents = 0
            
            for collection_name in collections:
                collection_data = manager.get_collection_info(collection_name)
                if collection_data:
                    count = collection_data.get("points_count", 0)
                    collection_info[collection_name] = f"{count} documents"
                    total_documents += count
            
            status["qdrant_collections"] = collection_info if collection_info else "no collections found"
            status["total_documents"] = total_documents
        else:
            status["qdrant_server"] = "connection failed"
            status["qdrant_collections"] = "unavailable"
        
        # Check embedding model
        try:
            model_info = f"{EMBED_MODEL_NAME} (loaded: {hasattr(manager, '_model') and manager._model is not None})"
            status["embedding_model"] = model_info
        except Exception as e:
            status["embedding_model"] = f"error: {str(e)}"
            
    except Exception as e:
        status["qdrant_server"] = f"error: {str(e)}"
        status["qdrant_collections"] = "unavailable"
    
    return status


def get_library_status() -> Dict[str, Any]:
    """Get status of all Qdrant-based libraries and their collections."""
    try:
        manager = get_qdrant_manager()
        collections = manager.list_collections()
        
        # Map collections to their libraries
        library_status = {
            "sparql_library": [],
            "ontology_library": [],
            "notebook_library": [],
            "literature_library": [],
            "readthedocs_library": []
        }
        
        total_collections = 0
        total_documents = 0
        
        for collection_name in collections:
            collection_info = manager.get_collection_info(collection_name)
            count = collection_info.get("points_count", 0) if collection_info else 0
            total_collections += 1
            total_documents += count
            
            collection_status = f"{collection_name}: {count}"
            
            if "sparql" in collection_name:
                library_status["sparql_library"].append(collection_status)
            elif "ontology" in collection_name:
                library_status["ontology_library"].append(collection_status)
            elif "notebook" in collection_name:
                library_status["notebook_library"].append(collection_status)
            elif "literature" in collection_name:
                library_status["literature_library"].append(collection_status)
            elif "readthedocs" in collection_name:
                library_status["readthedocs_library"].append(collection_status)
        
        # Add summary
        library_status["summary"] = {
            "total_libraries": 5,
            "total_collections": total_collections,
            "total_documents": total_documents,
            "expected_collections": list(COLLECTION_NAMES.values())
        }
        
        return library_status
        
    except Exception as e:
        return {"error": f"Failed to get library status: {str(e)}"}


def get_collection_health() -> Dict[str, Any]:
    """Get detailed health information for all collections."""
    try:
        manager = get_qdrant_manager()
        collections = manager.list_collections()
        
        health_info = {}
        
        for collection_name in collections:
            collection_info = manager.get_collection_info(collection_name)
            if collection_info:
                health_info[collection_name] = {
                    "status": collection_info.get("status", "unknown"),
                    "points_count": collection_info.get("points_count", 0),
                    "vectors_count": collection_info.get("vectors_count", 0),
                    "indexed_vectors_count": collection_info.get("indexed_vectors_count", 0),
                    "health": "healthy" if collection_info.get("points_count", 0) > 0 else "empty"
                }
            else:
                health_info[collection_name] = {"status": "error", "health": "unhealthy"}
        
        return health_info
        
    except Exception as e:
        return {"error": f"Failed to get collection health: {str(e)}"}


# Legacy compatibility function for external code that might still use db_tools
def get_db_status() -> Dict[str, Any]:
    """Legacy compatibility function - use get_system_status() instead."""
    return get_system_status()


if __name__ == "__main__":
    # Test Qdrant connection and provide status information
    import argparse
    
    parser = argparse.ArgumentParser(description="Qdrant system management and status")
    parser.add_argument("--host", default=QDRANT_HOST, help="Qdrant host")
    parser.add_argument("--port", type=int, default=QDRANT_PORT, help="Qdrant port")
    parser.add_argument("--setup-collections", action="store_true", help="Setup all collections")
    parser.add_argument("--status", action="store_true", help="Show system status")
    parser.add_argument("--libraries", action="store_true", help="Show library status")
    parser.add_argument("--health", action="store_true", help="Show collection health")
    args = parser.parse_args()
    
    manager = QdrantManager(host=args.host, port=args.port)
    
    if args.status:
        import json
        print("System Status:")
        print("=" * 50)
        status = get_system_status()
        print(json.dumps(status, indent=2))
        
    elif args.libraries:
        import json
        print("Library Status:")
        print("=" * 50)
        status = get_library_status()
        print(json.dumps(status, indent=2))
        
    elif args.health:
        import json
        print("Collection Health:")
        print("=" * 50)
        health = get_collection_health()
        print(json.dumps(health, indent=2))
        
    elif manager.ping():
        print("✅ Successfully connected to Qdrant server")
        
        if args.setup_collections:
            print("\nSetting up collections...")
            for lib_name, collection_name in COLLECTION_NAMES.items():
                if manager.create_collection(collection_name):
                    print(f"✅ {collection_name} (for {lib_name})")
                else:
                    print(f"❌ Failed to create {collection_name}")
        
        print(f"\nExisting collections: {manager.list_collections()}")
        print(f"\n💡 Use --status, --libraries, or --health for detailed information")
    else:
        print("❌ Failed to connect to Qdrant server")
        print("Make sure Qdrant is running with: docker run -p 6333:6333 qdrant/qdrant") 