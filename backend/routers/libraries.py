"""
Router for library management and dashboard functionality.
Provides endpoints for browsing Qdrant collections and their contents.
"""

import logging
import os
import sys
from typing import Dict, Any, List, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# Add libraries directory to path for imports
current_dir = Path(__file__).parent.parent
libraries_dir = current_dir / "libraries"
if str(libraries_dir) not in sys.path:
    sys.path.insert(0, str(libraries_dir))

try:
    from qdrant_config import get_qdrant_manager, COLLECTION_NAMES, get_library_status, get_system_status
    from sparql_library.search_queries import search_queries
    from ontology_library.search_ontology import search_entities
    from literature_library.search_methods import search_methods
    from readthedocs_library.search_docs import search_docs
    from readthedocs_library.search_code import search_code
    from readthedocs_library.search_symbols import search_symbols
    from notebook_library.search_snippets import search_snippets
    from notebook_library.search_workflows import search_workflows
except ImportError as e:
    logging.error(f"Failed to import library modules: {e}")
    # Define empty fallback functions
    def search_queries(*args, **kwargs): return []
    def search_entities(*args, **kwargs): return []
    def search_methods(*args, **kwargs): return []
    def search_docs(*args, **kwargs): return []
    def search_code(*args, **kwargs): return []
    def search_symbols(*args, **kwargs): return []
    def search_snippets(*args, **kwargs): return []
    def search_workflows(*args, **kwargs): return []
    def get_system_status(*args, **kwargs): return {"error": "Qdrant libraries not available"}
    def get_library_status(*args, **kwargs): return {"error": "Qdrant libraries not available"}
    def get_qdrant_manager(*args, **kwargs): raise Exception("Qdrant not available")
    COLLECTION_NAMES = {}

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/libraries", tags=["libraries"])

# Response models
class LibraryInfo(BaseModel):
    name: str
    type: str
    collections: List[str]
    total_documents: int
    description: str
    available_filters: Dict[str, List[str]]

class CollectionInfo(BaseModel):
    name: str
    library: str
    documents_count: int
    status: str
    sample_documents: List[Dict[str, Any]]

class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    filters: Optional[Dict[str, Any]] = None

class SearchResponse(BaseModel):
    collection: str
    library: str
    total_results: int
    results: List[Dict[str, Any]]

# Library configurations
LIBRARY_CONFIGS = {
    "sparql": {
        "name": "SPARQL Queries",
        "type": "query_library",
        "description": "Collection of SPARQL queries for paleoclimate data retrieval",
        "collections": ["sparql_queries"],
        "search_function": search_queries,
        "filters": {
            "query_type": ["SELECT", "CONSTRUCT", "ASK", "DESCRIBE"],
            "concepts": []  # Will be populated dynamically
        }
    },
    "ontology": {
        "name": "Ontology Entities",
        "type": "reference_library", 
        "description": "Paleoclimate ontology entities and their relationships",
        "collections": ["ontology_entities"],
        "search_function": search_entities,
        "filters": {
            "category": ["archive", "proxy", "variable", "method"],
            "entity_type": [],  # Will be populated dynamically
            "namespace": []
        }
    },
    "literature": {
        "name": "Literature Methods",
        "type": "methods_library",
        "description": "Extracted methods and procedures from paleoclimate literature",
        "collections": ["literature_methods"],
        "search_function": search_methods,
        "filters": {
            "category": ["data_analysis", "sample_preparation", "data_fetch"],
            "content_type": ["method_overview", "method_step"]
        }
    },
    "readthedocs": {
        "name": "ReadTheDocs Documentation",
        "type": "documentation_library",
        "description": "Documentation, code examples, and API references from scientific libraries",
        "collections": ["readthedocs_docs", "readthedocs_code", "readthedocs_symbols"],
        "search_function": search_docs,  # Default search function
        "filters": {
            "library": ["pyleoclim", "pylipd", "numpy", "pandas", "matplotlib"],
            "doc_type": ["code_example", "api_reference", "tutorial", "general"],
            "section": []
        }
    },
    "notebook": {
        "name": "Notebook Library", 
        "type": "workflow_library",
        "description": "Code snippets and workflows from Jupyter notebooks",
        "collections": ["notebook_snippets", "notebook_workflows"],
        "search_function": search_snippets,  # Default search function
        "filters": {
            "workflow_type": ["data_analysis", "visualization", "preprocessing", "modeling"],
            "complexity": ["simple", "medium", "complex"],
            "language": ["python", "r"]
        }
    }
}

@router.get("/")
async def get_libraries() -> Dict[str, Any]:
    """Get overview of all available libraries."""
    try:
        # Get system status from Qdrant
        system_status = get_system_status()
        library_status = get_library_status()
        
        libraries_info = {}
        total_documents = 0
        
        for lib_key, config in LIBRARY_CONFIGS.items():
            # Get document counts for this library's collections
            lib_collections = []
            lib_document_count = 0
            
            for collection_name in config["collections"]:
                if collection_name in system_status.get("qdrant_collections", {}):
                    collection_info = system_status["qdrant_collections"][collection_name]
                    # Extract document count from string like "1234 documents"
                    if isinstance(collection_info, str) and "documents" in collection_info:
                        count = int(collection_info.split()[0])
                        lib_document_count += count
                    lib_collections.append(collection_name)
            
            total_documents += lib_document_count
            
            libraries_info[lib_key] = LibraryInfo(
                name=config["name"],
                type=config["type"],
                collections=lib_collections,
                total_documents=lib_document_count,
                description=config["description"],
                available_filters=config["filters"]
            )
        
        return {
            "libraries": libraries_info,
            "system_status": {
                "total_libraries": len(LIBRARY_CONFIGS),
                "total_collections": len([c for config in LIBRARY_CONFIGS.values() for c in config["collections"]]),
                "total_documents": total_documents,
                "qdrant_status": system_status.get("qdrant_server", "unknown")
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting libraries overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{library_key}")
async def get_library_details(library_key: str) -> Dict[str, Any]:
    """Get detailed information about a specific library."""
    if library_key not in LIBRARY_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Library '{library_key}' not found")
    
    try:
        config = LIBRARY_CONFIGS[library_key]
        qdrant_manager = get_qdrant_manager()
        
        collections_info = []
        total_documents = 0
        
        for collection_name in config["collections"]:
            try:
                collection_info = qdrant_manager.get_collection_info(collection_name)
                if collection_info:
                    # Get sample documents
                    sample_results = qdrant_manager.search(
                        collection_name=collection_name,
                        query="",  # Empty query to get random samples
                        limit=3
                    )
                    
                    collection_data = CollectionInfo(
                        name=collection_name,
                        library=library_key,
                        documents_count=collection_info.get("points_count", 0),
                        status=collection_info.get("status", "unknown"),
                        sample_documents=sample_results
                    )
                    collections_info.append(collection_data)
                    total_documents += collection_data.documents_count
                    
            except Exception as e:
                logger.warning(f"Could not get info for collection {collection_name}: {e}")
        
        return {
            "library": LibraryInfo(
                name=config["name"],
                type=config["type"],
                collections=[c.name for c in collections_info],
                total_documents=total_documents,
                description=config["description"],
                available_filters=config["filters"]
            ),
            "collections": collections_info,
            "files": await _get_library_files(library_key)
        }
        
    except Exception as e:
        logger.error(f"Error getting library details for {library_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{library_key}/search")
async def search_library(library_key: str, search_request: SearchRequest) -> SearchResponse:
    """Search within a specific library."""
    if library_key not in LIBRARY_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Library '{library_key}' not found")
    
    try:
        config = LIBRARY_CONFIGS[library_key]
        search_function = config["search_function"]
        
        # Call the appropriate search function
        results = search_function(
            query=search_request.query,
            limit=search_request.limit,
            **(search_request.filters or {})
        )
        
        return SearchResponse(
            collection=config["collections"][0],  # Use primary collection
            library=library_key,
            total_results=len(results),
            results=results
        )
        
    except Exception as e:
        logger.error(f"Error searching library {library_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{library_key}/{collection_name}/search")
async def search_collection(
    library_key: str, 
    collection_name: str, 
    search_request: SearchRequest
) -> SearchResponse:
    """Search within a specific collection."""
    if library_key not in LIBRARY_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Library '{library_key}' not found")
    
    config = LIBRARY_CONFIGS[library_key]
    if collection_name not in config["collections"]:
        raise HTTPException(
            status_code=404, 
            detail=f"Collection '{collection_name}' not found in library '{library_key}'"
        )
    
    try:
        # Use specialized search functions for specific collections
        if collection_name == "readthedocs_code":
            results = search_code(
                query=search_request.query,
                limit=search_request.limit,
                collection_name=collection_name,
                **(search_request.filters or {})
            )
        elif collection_name == "readthedocs_symbols":
            results = search_symbols(
                query=search_request.query,
                limit=search_request.limit,
                collection_name=collection_name,
                **(search_request.filters or {})
            )
        elif collection_name == "notebook_workflows":
            results = search_workflows(
                query=search_request.query,
                limit=search_request.limit,
                collection_name=collection_name,
                **(search_request.filters or {})
            )
        else:
            # Use the library's default search function
            search_function = config["search_function"]
            results = search_function(
                query=search_request.query,
                limit=search_request.limit,
                collection_name=collection_name,
                **(search_request.filters or {})
            )
        
        return SearchResponse(
            collection=collection_name,
            library=library_key,
            total_results=len(results),
            results=results
        )
        
    except Exception as e:
        logger.error(f"Error searching collection {collection_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{library_key}/files")
async def get_library_files(library_key: str) -> Dict[str, Any]:
    """Get list of files indexed in a library."""
    if library_key not in LIBRARY_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Library '{library_key}' not found")
    
    try:
        files = await _get_library_files(library_key)
        return {"library": library_key, "files": files}
        
    except Exception as e:
        logger.error(f"Error getting files for library {library_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{library_key}/files/{file_path:path}")
async def get_file_content(library_key: str, file_path: str) -> Dict[str, Any]:
    """Get content of a specific file from a library."""
    if library_key not in LIBRARY_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Library '{library_key}' not found")
    
    try:
        # Map library key to directory
        library_base = libraries_dir / f"{library_key}_library"
        
        # Security check - ensure path is within library directory
        full_path = (library_base / file_path).resolve()
        if not str(full_path).startswith(str(library_base.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        # Read file content
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try to read as binary if UTF-8 fails
            with open(full_path, 'rb') as f:
                content = f.read()
                content = f"Binary file ({len(content)} bytes)"
        
        return {
            "library": library_key,
            "file_path": file_path,
            "content": content,
            "size": full_path.stat().st_size,
            "modified": full_path.stat().st_mtime
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _get_library_files(library_key: str) -> List[Dict[str, Any]]:
    """Helper function to get files for a library."""
    library_base = libraries_dir / f"{library_key}_library"
    
    if not library_base.exists():
        return []
    
    files = []
    try:
        # Get common data directories based on library type
        data_dirs = []
        if library_key == "literature":
            data_dirs = ["my_documents", "extracted_methods"]
        elif library_key == "notebook":
            data_dirs = ["my_notebooks"]
        elif library_key == "readthedocs":
            data_dirs = []  # ReadTheDocs processes external HTML
        elif library_key == "ontology":
            data_dirs = []  # Ontology uses RDF files
        elif library_key == "sparql":
            data_dirs = []  # SPARQL uses query files
        
        # Scan for files
        for data_dir in data_dirs:
            data_path = library_base / data_dir
            if data_path.exists():
                for file_path in data_path.rglob("*"):
                    if file_path.is_file() and not file_path.name.startswith('.'):
                        relative_path = file_path.relative_to(library_base)
                        files.append({
                            "path": str(relative_path),
                            "name": file_path.name,
                            "size": file_path.stat().st_size,
                            "modified": file_path.stat().st_mtime,
                            "extension": file_path.suffix
                        })
        
    except Exception as e:
        logger.warning(f"Error scanning files for {library_key}: {e}")
    
    return sorted(files, key=lambda x: x["modified"], reverse=True)

@router.get("/system/status")
async def get_system_status_endpoint() -> Dict[str, Any]:
    """Get comprehensive system status."""
    try:
        return get_system_status()
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{library_key}/documents")
async def get_library_documents(
    library_key: str, 
    collection: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """Get paginated documents from a library or specific collection."""
    if library_key not in LIBRARY_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Library '{library_key}' not found")
    
    try:
        config = LIBRARY_CONFIGS[library_key]
        qdrant_manager = get_qdrant_manager()
        
        # Determine which collection to query
        if collection:
            if collection not in config["collections"]:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Collection '{collection}' not found in library '{library_key}'"
                )
            collections_to_query = [collection]
        else:
            collections_to_query = config["collections"]
        
        all_documents = []
        total_count = 0
        
        for collection_name in collections_to_query:
            try:
                collection_info = qdrant_manager.get_collection_info(collection_name)
                if collection_info:
                    total_count += collection_info.get("points_count", 0)
                
                # Get documents using scroll for pagination
                from qdrant_client.http.models import ScrollRequest
                
                offset = (page - 1) * limit
                scroll_result = qdrant_manager.client.scroll(
                    collection_name=collection_name,
                    limit=limit if len(collections_to_query) == 1 else limit // len(collections_to_query),
                    offset=offset if len(collections_to_query) == 1 else 0,
                    with_payload=True
                )
                
                for point in scroll_result[0]:
                    document = {
                        "id": point.id,
                        "collection": collection_name,
                        "library": library_key,
                        **point.payload
                    }
                    all_documents.append(document)
                    
            except Exception as e:
                logger.warning(f"Could not get documents for collection {collection_name}: {e}")
        
        # Sort by creation time or ID if available
        all_documents.sort(key=lambda x: x.get("created_at", x.get("id", "")), reverse=True)
        
        # Apply pagination if querying multiple collections
        if len(collections_to_query) > 1:
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            all_documents = all_documents[start_idx:end_idx]
        
        return {
            "library": library_key,
            "collection": collection,
            "documents": all_documents,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "total_pages": (total_count + limit - 1) // limit,
                "has_next": page * limit < total_count,
                "has_prev": page > 1
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting documents for library {library_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{library_key}/documents/{document_id}")
async def get_document_details(library_key: str, document_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific document."""
    if library_key not in LIBRARY_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Library '{library_key}' not found")
    
    try:
        config = LIBRARY_CONFIGS[library_key]
        qdrant_manager = get_qdrant_manager()
        
        # Search across all collections in the library
        for collection_name in config["collections"]:
            try:
                # Try to retrieve the document by ID
                result = qdrant_manager.client.retrieve(
                    collection_name=collection_name,
                    ids=[document_id],
                    with_payload=True
                )
                
                if result:
                    point = result[0]
                    return {
                        "id": point.id,
                        "collection": collection_name,
                        "library": library_key,
                        "document": point.payload,
                        "source_info": {
                            "collection": collection_name,
                            "indexed_at": point.payload.get("indexed_at"),
                            "source_file": point.payload.get("source_file"),
                            "content_type": point.payload.get("content_type"),
                            "metadata": {k: v for k, v in point.payload.items() if k not in ["text", "content"]}
                        }
                    }
                    
            except Exception as e:
                logger.debug(f"Document {document_id} not found in {collection_name}: {e}")
                continue
        
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{library_key}/documents/{document_id}")
async def delete_document(library_key: str, document_id: str) -> Dict[str, Any]:
    """Delete a document from the library."""
    if library_key not in LIBRARY_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Library '{library_key}' not found")
    
    try:
        config = LIBRARY_CONFIGS[library_key]
        qdrant_manager = get_qdrant_manager()
        
        # Find and delete the document across all collections
        deleted = False
        for collection_name in config["collections"]:
            try:
                # Try to delete from this collection
                qdrant_manager.client.delete(
                    collection_name=collection_name,
                    points_selector=[document_id]
                )
                deleted = True
                logger.info(f"Deleted document {document_id} from {collection_name}")
                break
                
            except Exception as e:
                logger.debug(f"Document {document_id} not found in {collection_name}: {e}")
                continue
        
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
        
        return {"message": f"Document '{document_id}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class AddDocumentRequest(BaseModel):
    text: str
    metadata: Optional[Dict[str, Any]] = {}
    collection: Optional[str] = None

class BulkAddDocumentsRequest(BaseModel):
    documents: List[Dict[str, Any]]
    collection: Optional[str] = None

@router.post("/{library_key}/documents")
async def add_document(library_key: str, request: AddDocumentRequest) -> Dict[str, Any]:
    """Add a new document to the library."""
    if library_key not in LIBRARY_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Library '{library_key}' not found")
    
    try:
        config = LIBRARY_CONFIGS[library_key]
        qdrant_manager = get_qdrant_manager()
        
        # Determine target collection
        if request.collection:
            if request.collection not in config["collections"]:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Collection '{request.collection}' not found in library '{library_key}'"
                )
            collection_name = request.collection
        else:
            # Use primary collection (first one)
            collection_name = config["collections"][0]
        
        # Prepare document
        import uuid
        from datetime import datetime
        
        document_id = str(uuid.uuid4())
        document = {
            "id": document_id,
            "text": request.text,
            "indexed_at": datetime.now().isoformat(),
            "source": "user_added",
            "library": library_key,
            "collection": collection_name,
            **request.metadata
        }
        
        # Index the document
        indexed_count = qdrant_manager.index_documents(
            collection_name=collection_name,
            documents=[document],
            text_field="text"
        )
        
        if indexed_count > 0:
            return {
                "message": "Document added successfully",
                "document_id": document_id,
                "collection": collection_name,
                "library": library_key
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to index document")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{library_key}/documents/bulk")
async def add_documents_bulk(library_key: str, request: BulkAddDocumentsRequest) -> Dict[str, Any]:
    """Add multiple documents to the library at once."""
    if library_key not in LIBRARY_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Library '{library_key}' not found")
    
    if not request.documents:
        raise HTTPException(status_code=400, detail="No documents provided")
    
    try:
        config = LIBRARY_CONFIGS[library_key]
        qdrant_manager = get_qdrant_manager()
        
        # Determine target collection
        if request.collection:
            if request.collection not in config["collections"]:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Collection '{request.collection}' not found in library '{library_key}'"
                )
            collection_name = request.collection
        else:
            # Use primary collection (first one)
            collection_name = config["collections"][0]
        
        # Prepare documents
        import uuid
        from datetime import datetime
        
        prepared_documents = []
        for doc_data in request.documents:
            document_id = str(uuid.uuid4())
            
            # Extract text from various possible fields
            text = (doc_data.get("text") or 
                   doc_data.get("content") or 
                   doc_data.get("description") or 
                   doc_data.get("query") or 
                   doc_data.get("name") or "")
            
            if not text:
                logger.warning(f"Document has no extractable text content: {doc_data}")
                continue
            
            document = {
                "id": document_id,
                "text": text,
                "indexed_at": datetime.now().isoformat(),
                "source": "document_extraction",
                "library": library_key,
                "collection": collection_name,
                **doc_data  # Include all original fields as metadata
            }
            
            prepared_documents.append(document)
        
        if not prepared_documents:
            raise HTTPException(status_code=400, detail="No valid documents to index")
        
        # Index all documents at once
        indexed_count = qdrant_manager.index_documents(
            collection_name=collection_name,
            documents=prepared_documents,
            text_field="text"
        )
        
        return {
            "message": f"Successfully indexed {indexed_count} documents",
            "requested_documents": len(request.documents),
            "indexed_documents": indexed_count,
            "collection": collection_name,
            "library": library_key,
            "document_ids": [doc["id"] for doc in prepared_documents]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding bulk documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{library_key}/collections/{collection_name}/stats")
async def get_collection_stats(library_key: str, collection_name: str) -> Dict[str, Any]:
    """Get detailed statistics for a collection."""
    if library_key not in LIBRARY_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Library '{library_key}' not found")
    
    config = LIBRARY_CONFIGS[library_key]
    if collection_name not in config["collections"]:
        raise HTTPException(
            status_code=404, 
            detail=f"Collection '{collection_name}' not found in library '{library_key}'"
        )
    
    try:
        qdrant_manager = get_qdrant_manager()
        
        # Get collection info
        collection_info = qdrant_manager.get_collection_info(collection_name)
        if not collection_info:
            raise HTTPException(status_code=404, detail="Collection not found in Qdrant")
        
        # Get sample documents for content analysis
        sample_docs = qdrant_manager.search(
            collection_name=collection_name,
            query="",  # Empty query to get random samples
            limit=100
        )
        
        # Analyze document structure
        content_types = {}
        sources = {}
        categories = {}
        
        for doc in sample_docs:
            # Count content types
            content_type = doc.get("content_type", "unknown")
            content_types[content_type] = content_types.get(content_type, 0) + 1
            
            # Count sources
            source = doc.get("source", doc.get("source_file", "unknown"))
            sources[source] = sources.get(source, 0) + 1
            
            # Count categories
            category = doc.get("category", "unknown")
            categories[category] = categories.get(category, 0) + 1
        
        return {
            "collection": collection_name,
            "library": library_key,
            "stats": {
                "total_documents": collection_info.get("points_count", 0),
                "vector_count": collection_info.get("vectors_count", 0),
                "indexed_vectors": collection_info.get("indexed_vectors_count", 0),
                "status": collection_info.get("status", "unknown")
            },
            "content_analysis": {
                "content_types": content_types,
                "sources": dict(list(sources.items())[:10]),  # Top 10 sources
                "categories": categories
            },
            "sample_size": len(sample_docs)
        }
        
    except Exception as e:
        logger.error(f"Error getting collection stats: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 