#!/usr/bin/env python3
"""
Initialize Code Examples Embeddings

This script initializes the vector database of Jupyter notebook code examples
for semantic search and code generation.
"""

import sys
import logging
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """Initialize the code examples embeddings."""
    try:
        logger.info("Initializing code examples embeddings...")
        
        # Import and initialize the service
        from services.code_embeddings import code_embeddings_service
        
        # Initialize the service
        code_embeddings_service.initialize()
        
        # Clear existing collection and reload from all notebooks
        logger.info("Clearing existing collection and reloading all notebooks...")
        try:
            code_embeddings_service.client.delete_collection("code_examples")
            logger.info("Cleared existing collection")
        except Exception as e:
            logger.info(f"No existing collection to clear: {e}")
        
        # Recreate collection
        code_embeddings_service.collection = code_embeddings_service.client.create_collection(
            name="code_examples",
            embedding_function=code_embeddings_service.embedding_function,
            metadata={"description": "Jupyter notebook code examples for data analysis"}
        )
        
        # Load all notebooks from data/notebooks directory
        notebooks_dir = Path("data/notebooks")
        if notebooks_dir.exists():
            logger.info(f"Loading notebooks from {notebooks_dir}")
            code_embeddings_service.load_notebooks_from_directory(str(notebooks_dir))
        else:
            logger.warning(f"Notebooks directory {notebooks_dir} does not exist")
            # Create sample notebook as fallback
            code_embeddings_service._load_notebook_examples()
        
        # Get collection statistics
        stats = code_embeddings_service.get_collection_stats()
        
        logger.info("Code embeddings initialization completed!")
        logger.info(f"Total examples: {stats.get('total_examples', 0)}")
        logger.info(f"Notebooks: {stats.get('notebooks_count', 0)}")
        logger.info(f"Categories: {stats.get('categories', [])}")
        logger.info(f"Libraries: {stats.get('libraries', [])}")
        
        # Test search functionality
        logger.info("\nTesting search functionality...")
        
        test_queries = [
            "spectral analysis",
            "time series correlation", 
            "wavelet analysis",
            "plot timeseries",
            "filter data",
            "load from sparql",
            "create pyleoclim series"
        ]
        
        for query in test_queries:
            examples = code_embeddings_service.search_examples(query, limit=2)
            logger.info(f"Query: '{query}' -> Found {len(examples)} relevant examples")
            for example in examples:
                logger.info(f"  - {example['name']}: {example['description'][:60]}...")
        
        logger.info("\n✅ Code embeddings service is ready for use!")
        
        # Show instructions for adding notebooks
        logger.info("\n📝 To add more notebooks:")
        logger.info("1. Place your .ipynb files in backend/data/notebooks/")
        logger.info("2. Use tags 'example-metadata' for description cells and 'example-code' for code cells")
        logger.info("3. Or let the system auto-detect patterns in code cells")
        logger.info("4. Run code_embeddings_service.load_notebooks_from_directory('/path/to/notebooks')")
        
    except Exception as e:
        logger.error(f"Error initializing code embeddings: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 