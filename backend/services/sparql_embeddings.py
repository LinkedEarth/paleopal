"""
SPARQL Query Embeddings Service

Manages vector embeddings for SPARQL queries to enable semantic search
for similar queries and query patterns.
"""

import logging
import json
import re
import warnings
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

# Use the singleton embedding manager
from services.embedding_manager import embedding_manager

# Import query parser
from utils.sparql_query_loader import SparqlQueryParser

# Global config values
from config import (
    CHROMA_DB_PATH,
    EMBEDDING_PROVIDER,
    QUERY_CORPUS_PATH,
)

# Suppress ChromaDB warnings
warnings.filterwarnings("ignore", message=".*ChromaDB.*")

logger = logging.getLogger(__name__)

class SparqlEmbeddingsService:
    """Service for managing embeddings of SPARQL queries and patterns."""
    
    def __init__(self, embedding_provider: str = None, db_path: Optional[str] = None):
        """Initialize the SPARQL embeddings service."""
        # Allow provider to be passed or default from config
        self.embedding_provider = embedding_provider or EMBEDDING_PROVIDER
        
        # Get embeddings from singleton manager
        self.embeddings = embedding_manager.get_embeddings(self.embedding_provider)
        
        # Setup paths
        if db_path is None:
            # Use a subdirectory for SPARQL embeddings to avoid conflicts
            db_path = os.path.join(CHROMA_DB_PATH, "sparql_queries")
        self.db_path = db_path
        self.vectorstore = None
        
        self.data_dir = Path(__file__).parent.parent / "data"
        self.queries_dir = self.data_dir / "sparql_queries"
        
        # Ensure directories exist
        os.makedirs(self.db_path, exist_ok=True)
        self.queries_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Using {self.embedding_provider} for SPARQL embeddings")
    
    def _connect_to_vector_db(self) -> Chroma:
        """
        Connect to the vector database (create if it doesn't exist).
        
        Returns:
            Vector database connection
        """
        if not self.vectorstore:
            try:
                self.vectorstore = Chroma(
                    persist_directory=self.db_path,
                    embedding_function=self.embeddings
                )
                
                # Log the number of documents in the database
                logger.info(f"Connected to SPARQL vector database with {self.vectorstore._collection.count()} documents")
                
            except Exception as e:
                logger.error(f"Error connecting to vector database: {str(e)}")
                raise
        
        return self.vectorstore
    
    def _create_documents_from_queries(self, queries: List[Dict[str, str]]) -> List[Document]:
        """
        Convert query dictionaries to Document objects for the vector database.
        
        Args:
            queries: List of query dictionaries
            
        Returns:
            List of Document objects
        """
        documents = []
        
        for query in queries:
            # Create a document that only includes name and description (not the SPARQL query)
            content = f"Name: {query['name']}\n\nDescription: {query['description']}"
            
            doc = Document(
                page_content=content,
                metadata={
                    "name": query["name"],
                    "file": query["file"],
                    "type": "sparql_query",
                    "sparql": query["sparql"]  # Store the SPARQL query in metadata
                }
            )
            documents.append(doc)
        
        return documents
    
    def initialize(self, corpus_path: Optional[str] = None) -> None:
        """
        Initialize the vector database with queries from the corpus.
        
        Args:
            corpus_path: Path to the query corpus directory
        """
        logger.info(f"Initializing sparql query embeddings using {self.embedding_provider}")
        
        # Use default corpus path if not provided
        if corpus_path is None:
            corpus_path = QUERY_CORPUS_PATH
        
        # Load queries
        parser = SparqlQueryParser(corpus_path)
        queries = parser.load_queries()
        
        if not queries:
            logger.warning("No queries found to embed")
            return
        
        logger.info(f"Loaded {len(queries)} queries")
        
        # Convert to documents
        documents = self._create_documents_from_queries(queries)
        
        # Create or connect to the vector database
        vectorstore = self._connect_to_vector_db()
        
        # If the database exists and has content, clear it first
        if vectorstore._collection.count() > 0:
            logger.info("Clearing existing vector database before adding new documents")
            vectorstore._collection.delete(where={"type": "sparql_query"})
        
        # Add documents to the database
        vectorstore.add_documents(documents)
        
        logger.info(f"Successfully embedded {len(documents)} queries into the vector database")
    
    def get_matches(self, query_text: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve similar queries from the vector database.
        
        Args:
            query_text: User query text
            limit: Number of results to return
            
        Returns:
            List of similar queries with their metadata and similarity scores
        """
        vectorstore = self._connect_to_vector_db()
        
        # Ensure the database has documents
        if vectorstore._collection.count() == 0:
            logger.warning("Vector database is empty. Please initialize it first.")
            return []
        
        # Retrieve similar documents
        results = vectorstore.similarity_search_with_relevance_scores(
            query_text, 
            k=limit
        )
        
        # Format results
        similar_queries = []
        for doc, score in results:
            # Extract query details from the document and metadata
            lines = doc.page_content.split("\n\n")
            name = lines[0].replace("Name: ", "")
            description = lines[1].replace("Description: ", "")
            
            # Get SPARQL query from metadata
            sparql = doc.metadata.get("sparql", "")
            
            similar_queries.append({
                "name": name,
                "description": description,
                "sparql": sparql,
                "similarity": score,
                "metadata": doc.metadata
            })
        
        return similar_queries
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the SPARQL queries collection."""
        try:
            vectorstore = self._connect_to_vector_db()
            
            if vectorstore._collection.count() == 0:
                return {}
            
            count = vectorstore._collection.count()
            
            # Get all documents to analyze metadata
            all_docs = vectorstore.get()
            
            files = set()
            query_types = set()
            
            if all_docs and 'metadatas' in all_docs:
                for metadata in all_docs['metadatas']:
                    if metadata.get('file'):
                        files.add(metadata['file'])
                    if metadata.get('type'):
                        query_types.add(metadata['type'])
            
            return {
                'total_queries': count,
                'files': sorted(list(files)),
                'files_count': len(files),
                'query_types': sorted(list(query_types))
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {}

# Global service instance
sparql_embeddings_service = SparqlEmbeddingsService() 