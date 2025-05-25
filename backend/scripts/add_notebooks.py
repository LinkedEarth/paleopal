#!/usr/bin/env python3
"""
Add Notebooks to Code Embeddings

Utility script to add Jupyter notebooks from external directories
to the code embeddings system for semantic search.
"""

import sys
import argparse
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
    """Add notebooks to the code embeddings system."""
    parser = argparse.ArgumentParser(description="Add Jupyter notebooks to code embeddings")
    parser.add_argument("notebook_path", help="Path to notebook file or directory containing notebooks")
    parser.add_argument("--recursive", "-r", action="store_true", help="Search subdirectories recursively")
    parser.add_argument("--copy", "-c", action="store_true", help="Copy notebooks to local data directory")
    parser.add_argument("--reinitialize", action="store_true", help="Reinitialize the entire embeddings collection")
    
    args = parser.parse_args()
    
    try:
        from services.code_embeddings import code_embeddings_service
        
        # Initialize the service if not already done
        if args.reinitialize:
            logger.info("Reinitializing code embeddings service...")
            # Clear existing collection
            if code_embeddings_service.collection:
                code_embeddings_service.collection.delete()
            
        code_embeddings_service.initialize()
        
        notebook_path = Path(args.notebook_path)
        
        if not notebook_path.exists():
            logger.error(f"Path does not exist: {notebook_path}")
            sys.exit(1)
        
        if notebook_path.is_file() and notebook_path.suffix == '.ipynb':
            # Single notebook file
            logger.info(f"Adding single notebook: {notebook_path}")
            
            if args.copy:
                # Copy to local directory
                dest_path = code_embeddings_service.notebooks_dir / notebook_path.name
                dest_path.write_text(notebook_path.read_text(encoding='utf-8'), encoding='utf-8')
                logger.info(f"Copied notebook to: {dest_path}")
                code_embeddings_service.add_notebook(str(dest_path))
            else:
                code_embeddings_service.add_notebook(str(notebook_path))
                
        elif notebook_path.is_dir():
            # Directory of notebooks
            logger.info(f"Adding notebooks from directory: {notebook_path}")
            
            if args.copy:
                # Copy notebooks to local directory
                pattern = "**/*.ipynb" if args.recursive else "*.ipynb"
                notebook_files = list(notebook_path.glob(pattern))
                
                for nb_file in notebook_files:
                    dest_path = code_embeddings_service.notebooks_dir / nb_file.name
                    dest_path.write_text(nb_file.read_text(encoding='utf-8'), encoding='utf-8')
                    logger.info(f"Copied: {nb_file.name}")
                
                # Load from local directory
                code_embeddings_service._load_notebook_examples()
            else:
                # Load directly from external directory
                code_embeddings_service.load_notebooks_from_directory(str(notebook_path))
        else:
            logger.error(f"Invalid path: {notebook_path}")
            sys.exit(1)
        
        # Show updated statistics
        stats = code_embeddings_service.get_collection_stats()
        logger.info(f"\n📊 Updated Collection Statistics:")
        logger.info(f"Total examples: {stats.get('total_examples', 0)}")
        logger.info(f"Notebooks: {stats.get('notebooks_count', 0)}")
        logger.info(f"Categories: {stats.get('categories', [])}")
        logger.info(f"Libraries: {stats.get('libraries', [])}")
        
        # Test search with a common query
        logger.info(f"\n🔍 Testing search functionality...")
        test_examples = code_embeddings_service.search_examples("spectral analysis", limit=3)
        logger.info(f"Found {len(test_examples)} examples for 'spectral analysis'")
        for example in test_examples:
            logger.info(f"  - {example['name']} (notebook: {example['notebook']})")
        
        logger.info(f"\n✅ Successfully added notebooks to code embeddings!")
        
    except Exception as e:
        logger.error(f"Error adding notebooks: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 