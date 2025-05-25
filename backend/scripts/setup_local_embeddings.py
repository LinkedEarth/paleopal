#!/usr/bin/env python3
"""
Setup and test local embedding providers for PaleoPal.

This script helps users install dependencies and test local embedding providers.
"""

import argparse
import logging
import sys
import subprocess
from pathlib import Path

# Add the parent directory to the path to import from backend
sys.path.append(str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def install_dependencies(provider: str = None):
    """Install dependencies for local embedding providers."""
    requirements_file = Path(__file__).parent.parent / "requirements-local-embeddings.txt"
    
    if not requirements_file.exists():
        logger.error(f"Requirements file not found: {requirements_file}")
        return False
    
    try:
        logger.info("Installing local embedding dependencies...")
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
        ], check=True)
        logger.info("✅ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error installing dependencies: {e}")
        return False

def test_provider(provider: str, model: str = None):
    """Test a specific embedding provider."""
    try:
        logger.info(f"Testing {provider} embedding provider...")
        
        if provider == "sentence-transformers":
            from services.local_embeddings import SentenceTransformersEmbeddings
            embeddings = SentenceTransformersEmbeddings(model or "all-MiniLM-L6-v2")
            
        elif provider == "ollama":
            from services.local_embeddings import OllamaEmbeddings
            embeddings = OllamaEmbeddings(model or "nomic-embed-text")
            
        elif provider == "huggingface":
            from services.local_embeddings import HuggingFaceEmbeddings
            embeddings = HuggingFaceEmbeddings(model or "sentence-transformers/all-MiniLM-L6-v2")
            
        else:
            logger.error(f"❌ Unsupported provider: {provider}")
            return False
        
        # Test embedding
        test_text = "paleoclimate temperature data from coral archives"
        embedding = embeddings.embed_query(test_text)
        
        logger.info(f"✅ {provider} is working!")
        logger.info(f"   Model: {model or 'default'}")
        logger.info(f"   Embedding dimension: {len(embedding)}")
        logger.info(f"   Test text: '{test_text}'")
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import error for {provider}: {e}")
        logger.info("   Try installing dependencies with: python setup_local_embeddings.py --install")
        return False
    except Exception as e:
        logger.error(f"❌ Error testing {provider}: {e}")
        return False

def check_availability():
    """Check which local embedding providers are available."""
    logger.info("Checking local embedding provider availability...")
    
    try:
        from services.local_embeddings import get_available_local_providers
        providers = get_available_local_providers()
        
        logger.info("\n📊 Provider Status:")
        for provider, available in providers.items():
            status = "✅ Available" if available else "❌ Not available"
            logger.info(f"   {provider}: {status}")
        
        return providers
    except ImportError:
        logger.error("❌ Local embeddings module not available")
        return {}

def get_recommendations():
    """Get embedding recommendations for different use cases."""
    try:
        from services.local_embeddings import get_recommended_model
        
        logger.info("\n💡 Recommendations:")
        use_cases = ["fast", "general", "quality", "scientific", "multilingual", "ollama"]
        
        for use_case in use_cases:
            rec = get_recommended_model(use_case)
            logger.info(f"   {use_case.capitalize()}: {rec['provider']} - {rec['model']}")
            logger.info(f"      {rec['description']}")
        
    except ImportError:
        logger.error("❌ Cannot get recommendations - local embeddings not available")

def main():
    parser = argparse.ArgumentParser(description="Setup and test local embedding providers")
    parser.add_argument("--install", action="store_true", help="Install dependencies")
    parser.add_argument("--test", type=str, help="Test a specific provider (sentence-transformers, ollama, huggingface)")
    parser.add_argument("--model", type=str, help="Specific model to test (optional)")
    parser.add_argument("--check", action="store_true", help="Check provider availability")
    parser.add_argument("--recommendations", action="store_true", help="Show recommendations")
    parser.add_argument("--all", action="store_true", help="Run all checks and tests")
    
    args = parser.parse_args()
    
    if args.install or args.all:
        install_dependencies()
    
    if args.check or args.all:
        check_availability()
    
    if args.recommendations or args.all:
        get_recommendations()
    
    if args.test:
        test_provider(args.test, args.model)
    
    if args.all:
        # Test all available providers
        logger.info("\n🧪 Testing all available providers...")
        providers = ["sentence-transformers", "ollama", "huggingface"]
        for provider in providers:
            test_provider(provider)
            print()  # Add spacing
    
    if not any([args.install, args.test, args.check, args.recommendations, args.all]):
        parser.print_help()

if __name__ == "__main__":
    main() 