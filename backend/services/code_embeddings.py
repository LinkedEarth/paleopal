"""
Code Examples Embedding Service

Manages vector embeddings for Jupyter notebook code examples to enable
semantic search for relevant analysis patterns and code snippets.
Supports parsing of .ipynb files for Pyleoclim, PyLiPD, and general data analysis code.
"""

import logging
import json
import re
import warnings
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

# Use the singleton embedding manager
from services.embedding_manager import embedding_manager

# Global config values
from config import (
    CHROMA_DB_PATH,
    EMBEDDING_PROVIDER,
)

# Suppress ChromaDB warnings
warnings.filterwarnings("ignore", message=".*ChromaDB.*")

logger = logging.getLogger(__name__)

class CodeEmbeddingsService:
    """Service for managing embeddings of Jupyter notebook code examples."""
    
    def __init__(self, embedding_provider: str = None, db_path: Optional[str] = None):
        """Initialize the code examples embedding service."""
        # Allow provider to be passed or default from config
        self.embedding_provider = embedding_provider or EMBEDDING_PROVIDER
        
        # Get embeddings from singleton manager
        self.embeddings = embedding_manager.get_embeddings(self.embedding_provider)
        
        # Setup paths
        if db_path is None:
            # Use a subdirectory for code embeddings to avoid conflicts
            db_path = os.path.join(CHROMA_DB_PATH, "code_examples")
        self.db_path = db_path
        self.vectorstore = None
        
        self.data_dir = Path(__file__).parent.parent / "data"
        self.notebooks_dir = self.data_dir / "notebooks"
        
        # Ensure directories exist
        os.makedirs(self.db_path, exist_ok=True)
        self.notebooks_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Using {self.embedding_provider} for code embeddings")
    
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
                logger.info(f"Connected to code examples vector database with {self.vectorstore._collection.count()} documents")
                
            except Exception as e:
                logger.error(f"Error connecting to vector database: {str(e)}")
                raise
        
        return self.vectorstore
    
    def initialize(self):
        """Initialize the embedding service and load code examples."""
        try:
            logger.info(f"Initializing code embeddings using {self.embedding_provider}")
            
            # Connect to the vector database
            vectorstore = self._connect_to_vector_db()
            
            # Check if we already have examples loaded
            if vectorstore._collection.count() > 0:
                logger.info(f"Code examples collection ready with {vectorstore._collection.count()} documents")
                return
            
            # Load examples from notebooks if collection is empty
            self._load_notebook_examples()
            
            # Check collection size after loading
            count = vectorstore._collection.count()
            logger.info(f"Code examples collection ready with {count} documents")
            
        except Exception as e:
            logger.error(f"Error initializing code embeddings service: {e}")
            raise
    
    def _create_documents_from_examples(self, examples: List[Dict[str, Any]]) -> List[Document]:
        """
        Convert code examples to Document objects for the vector database.
        
        Args:
            examples: List of code example dictionaries
            
        Returns:
            List of Document objects
        """
        documents = []
        
        for example in examples:
            # Create a document with the description and code for embedding
            content = f"Name: {example['name']}\n\nDescription: {example['description']}\n\nCode:\n{example['code']}"
            
            doc = Document(
                page_content=content,
                metadata={
                    "name": example["name"],
                    "title": example.get("title", ""),
                    "description": example["description"],
                    "categories": ",".join(example["categories"]),
                    "libraries": ",".join(example["libraries"]),
                    "code": example["code"],
                    "notebook": example["notebook"],
                    "cell_index": str(example.get("cell_index", 0)),
                    "type": "code_example"
                }
            )
            documents.append(doc)
        
        return documents
    
    def _load_notebook_examples(self):
        """Load code examples from Jupyter notebooks."""
        logger.info("Loading code examples from Jupyter notebooks...")
        
        try:
            all_examples = []
            
            # Check for notebook files
            notebook_files = list(self.notebooks_dir.glob("**/*.ipynb"))

            for notebook_path in notebook_files:
                try:
                    examples = self._parse_notebook(notebook_path)
                    for example in examples:
                        example["source_notebook"] = notebook_path.name
                        all_examples.append(example)
                except Exception as e:
                    logger.error(f"Error loading examples from {notebook_path}: {e}")
            
            if all_examples:
                # Convert to documents
                documents = self._create_documents_from_examples(all_examples)
                
                # Add to vector database
                vectorstore = self._connect_to_vector_db()
                vectorstore.add_documents(documents)
                
                logger.info(f"Loaded {len(all_examples)} code examples from {len(notebook_files)} notebooks")
            else:
                logger.warning("No code examples found in notebooks")
            
        except Exception as e:
            logger.error(f"Error loading notebook examples: {e}")

    def _parse_notebook(self, notebook_path: Path) -> List[Dict[str, Any]]:
        """Parse a Jupyter notebook and extract code examples."""
        examples = []
        
        try:
            with open(notebook_path, 'r', encoding='utf-8') as f:
                notebook = json.load(f)
            
            current_example = None
            
            for i, cell in enumerate(notebook.get('cells', [])):
                cell_type = cell.get('cell_type', '')
                source = ''.join(cell.get('source', []))
                tags = cell.get('metadata', {}).get('tags', [])
                
                # Check if this is an example metadata cell
                if cell_type == 'markdown' and 'example-metadata' in tags:
                    current_example = self._parse_example_metadata(source, notebook_path.stem, i)
                
                # Check if this is an example code cell
                elif cell_type == 'code' and 'example-code' in tags and current_example:
                    current_example['code'] = source.strip()
                    current_example['cell_index'] = i
                    
                    # Create search text
                    current_example['search_text'] = f"{current_example['name']} {current_example['description']} {' '.join(current_example['categories'])} {current_example['code']}"
                    
                    examples.append(current_example)
                    current_example = None
                
                # Auto-detect code patterns if no tags
                elif cell_type == 'code' and not tags and source.strip():
                    # Auto-generate example from code cell
                    auto_example = self._auto_detect_example(source, notebook_path.stem, i)
                    if auto_example:
                        examples.append(auto_example)
            
        except Exception as e:
            logger.error(f"Error parsing notebook {notebook_path}: {e}")
        
        return examples
    
    def _parse_example_metadata(self, markdown_text: str, notebook_name: str, cell_index: int) -> Dict[str, Any]:
        """Parse example metadata from markdown cell."""
        lines = markdown_text.split('\n')
        
        # Extract title (usually the first header)
        title = ""
        for line in lines:
            if line.startswith('#'):
                title = line.lstrip('#').strip()
                break
        
        # Extract metadata
        description = ""
        categories = []
        libraries = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('**Description**:'):
                description = line.replace('**Description**:', '').strip()
            elif line.startswith('**Categories**:'):
                categories = [cat.strip() for cat in line.replace('**Categories**:', '').split(',')]
            elif line.startswith('**Libraries**:'):
                libraries = [lib.strip() for lib in line.replace('**Libraries**:', '').split(',')]
        
        # Generate name from title or create one
        name = re.sub(r'[^A-Za-z0-9]+', '_', title.upper()) if title else f"NOTEBOOK_{notebook_name}_{cell_index}"
        
        return {
            'name': name,
            'title': title,
            'description': description or title,
            'categories': categories,
            'libraries': libraries,
            'notebook': notebook_name,
            'cell_index': cell_index
        }
    
    def _auto_detect_example(self, code: str, notebook_name: str, cell_index: int) -> Optional[Dict[str, Any]]:
        """Auto-detect code patterns and create examples."""
        code_lower = code.lower()
        
        # Skip if too short or just imports
        if len(code.strip()) < 50 or code_lower.count('import') > len(code.split('\n')) / 2:
            return None
        
        # Detect libraries
        libraries = []
        if 'pyleoclim' in code_lower or 'pyleo' in code_lower:
            libraries.append('pyleoclim')
        if 'pylipd' in code_lower:
            libraries.append('pylipd')
        if 'pandas' in code_lower:
            libraries.append('pandas')
        if 'numpy' in code_lower:
            libraries.append('numpy')
        if 'matplotlib' in code_lower:
            libraries.append('matplotlib')
        
        # Detect categories based on code patterns
        categories = []
        if any(pattern in code_lower for pattern in ['spectral', 'psd', 'periodogram']):
            categories.append('spectral')
        if any(pattern in code_lower for pattern in ['correlation', 'corr']):
            categories.append('correlation')
        if any(pattern in code_lower for pattern in ['plot', 'figure', 'visualization']):
            categories.append('visualization')
        if any(pattern in code_lower for pattern in ['filter', 'smooth']):
            categories.append('filtering')
        if any(pattern in code_lower for pattern in ['wavelet', 'cwt']):
            categories.append('wavelet')
        if 'sparql' in code_lower:
            categories.append('sparql')
        
        if not categories:
            categories = ['general']
        
        # Generate description based on detected patterns
        description = f"Code example from {notebook_name}"
        if categories:
            description += f" involving {', '.join(categories)}"
        
        name = f"AUTO_{notebook_name}_{cell_index}_{categories[0].upper()}"
        
        return {
            'name': name,
            'title': f"Auto-detected: {categories[0].title()} Analysis",
            'description': description,
            'categories': categories,
            'libraries': libraries,
            'code': code.strip(),
            'notebook': notebook_name,
            'cell_index': cell_index,
            'search_text': f"{name} {description} {' '.join(categories)} {code}"
        }
    
    def search_examples(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant code examples based on query."""
        try:
            vectorstore = self._connect_to_vector_db()
            
            # Ensure the database has documents
            if vectorstore._collection.count() == 0:
                logger.warning("Vector database is empty. Please initialize it first.")
                return []
            
            # Retrieve similar documents
            results = vectorstore.similarity_search_with_relevance_scores(
                query, 
                k=limit
            )
            
            # Format results
            examples = []
            for doc, score in results:
                metadata = doc.metadata
                
                example = {
                    'name': metadata.get('name', ''),
                    'title': metadata.get('title', ''),
                    'description': metadata.get('description', ''),
                    'categories': metadata.get('categories', '').split(',') if metadata.get('categories') else [],
                    'libraries': metadata.get('libraries', '').split(',') if metadata.get('libraries') else [],
                    'code': metadata.get('code', ''),
                    'notebook': metadata.get('notebook', ''),
                    'cell_index': int(metadata.get('cell_index', 0)),
                    'relevance_score': score,
                    'search_text': doc.page_content
                }
                examples.append(example)
            
            logger.info(f"Found {len(examples)} relevant code examples for query: '{query}'")
            return examples
            
        except Exception as e:
            logger.error(f"Error searching examples: {e}")
            return []
    
    def get_examples_by_category(self, category: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get examples by category."""
        try:
            vectorstore = self._connect_to_vector_db()
            
            if vectorstore._collection.count() == 0:
                return []
            
            # Search using category as query
            results = vectorstore.similarity_search_with_relevance_scores(
                category,
                k=limit
            )
            
            examples = []
            for doc, score in results:
                metadata = doc.metadata
                categories = metadata.get('categories', '').split(',') if metadata.get('categories') else []
                
                # Filter to only include examples that actually contain the category
                if any(category.lower() in cat.lower() for cat in categories):
                    example = {
                        'name': metadata.get('name', ''),
                        'title': metadata.get('title', ''),
                        'description': metadata.get('description', ''),
                        'categories': categories,
                        'libraries': metadata.get('libraries', '').split(',') if metadata.get('libraries') else [],
                        'code': metadata.get('code', ''),
                        'notebook': metadata.get('notebook', ''),
                        'relevance_score': score
                    }
                    examples.append(example)
            
            return examples
            
        except Exception as e:
            logger.error(f"Error getting examples by category: {e}")
            return []
    
    def load_notebooks_from_directory(self, directory_path: str):
        """Load notebooks from a specific directory."""
        try:
            notebooks_path = Path(directory_path)
            if not notebooks_path.exists():
                logger.error(f"Directory does not exist: {directory_path}")
                return
            
            notebook_files = list(notebooks_path.glob("**/*.ipynb"))
            logger.info(f"Found {len(notebook_files)} notebooks in {directory_path}")
            
            all_examples = []
            for notebook_path in notebook_files:
                try:
                    examples = self._parse_notebook(notebook_path)
                    for example in examples:
                        example["source_notebook"] = notebook_path.name
                        all_examples.append(example)
                except Exception as e:
                    logger.error(f"Error processing {notebook_path}: {e}")
            
            if all_examples:
                # Convert to documents and add to vector database
                documents = self._create_documents_from_examples(all_examples)
                vectorstore = self._connect_to_vector_db()
                vectorstore.add_documents(documents)
                
                logger.info(f"Loaded {len(all_examples)} code examples from {len(notebook_files)} notebooks")
            
        except Exception as e:
            logger.error(f"Error loading notebooks from directory: {e}")
    
    def add_notebook(self, notebook_path: str):
        """Add a single notebook to the collection."""
        try:
            notebook_file = Path(notebook_path)
            if not notebook_file.exists():
                logger.error(f"Notebook file does not exist: {notebook_path}")
                return
            
            examples = self._parse_notebook(notebook_file)
            if examples:
                for example in examples:
                    example["source_notebook"] = notebook_file.name
                
                # Convert to documents and add to vector database
                documents = self._create_documents_from_examples(examples)
                vectorstore = self._connect_to_vector_db()
                vectorstore.add_documents(documents)
                
                logger.info(f"Added {len(examples)} examples from {notebook_file.name}")
            
        except Exception as e:
            logger.error(f"Error adding notebook: {e}")
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the code examples collection."""
        try:
            vectorstore = self._connect_to_vector_db()
            
            if vectorstore._collection.count() == 0:
                return {}
            
            count = vectorstore._collection.count()
            
            # Get all documents to analyze metadata
            all_docs = vectorstore.get()
            
            categories = set()
            libraries = set()
            notebooks = set()
            
            if all_docs and 'metadatas' in all_docs:
                for metadata in all_docs['metadatas']:
                    if metadata.get('categories'):
                        categories.update(metadata['categories'].split(','))
                    if metadata.get('libraries'):
                        libraries.update(metadata['libraries'].split(','))
                    if metadata.get('notebook'):
                        notebooks.add(metadata['notebook'])
            
            return {
                'total_examples': count,
                'categories': sorted(list(categories)),
                'libraries': sorted(list(libraries)),
                'notebooks': sorted(list(notebooks)),
                'notebooks_count': len(notebooks)
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {}

# Global service instance
code_embeddings_service = CodeEmbeddingsService() 