"""
Local Embedding Providers for PaleoPal

This module provides local embedding implementations that don't require API calls,
including sentence-transformers, Ollama embeddings, and HuggingFace models.
"""

import logging
import os
import sys
from typing import List, Optional, Dict, Any
from pathlib import Path

# Add the parent directory to the path to import from backend
sys.path.append(str(Path(__file__).parent.parent))
from config import OLLAMA_BASE_URL, get_embedding_model_name

# Configure logging
logger = logging.getLogger(__name__)

# Import dependencies with fallbacks
try:
    from langchain_core.embeddings import Embeddings
    from langchain.schema.document import Document
except ImportError as e:
    logger.error(f"Error importing langchain: {e}")
    raise

# Sentence Transformers
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    logger.warning("sentence-transformers not available. Install with: pip install sentence-transformers")
    SENTENCE_TRANSFORMERS_AVAILABLE = False

# Ollama
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    logger.warning("ollama not available. Install with: pip install ollama")
    OLLAMA_AVAILABLE = False

# HuggingFace Transformers
try:
    from transformers import AutoTokenizer, AutoModel
    import torch
    HUGGINGFACE_AVAILABLE = True
except ImportError:
    logger.warning("transformers not available. Install with: pip install transformers torch")
    HUGGINGFACE_AVAILABLE = False


class SentenceTransformersEmbeddings(Embeddings):
    """Local embeddings using sentence-transformers library."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", cache_folder: Optional[str] = None):
        """
        Initialize sentence-transformers embeddings.
        
        Args:
            model_name: Name of the sentence-transformers model
            cache_folder: Optional cache folder for models
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("sentence-transformers is required. Install with: pip install sentence-transformers")
        
        self.model_name = model_name
        self.cache_folder = cache_folder
        
        try:
            logger.info(f"Loading sentence-transformers model: {model_name}")
            self.model = SentenceTransformer(model_name, cache_folder=cache_folder)
            logger.info(f"Successfully loaded model: {model_name}")
        except Exception as e:
            logger.error(f"Error loading sentence-transformers model {model_name}: {e}")
            raise
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        try:
            embeddings = self.model.encode(texts, convert_to_tensor=False, show_progress_bar=False)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Error embedding documents: {e}")
            raise
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        try:
            embedding = self.model.encode([text], convert_to_tensor=False, show_progress_bar=False)
            return embedding[0].tolist()
        except Exception as e:
            logger.error(f"Error embedding query: {e}")
            raise


class OllamaEmbeddings(Embeddings):
    """Local embeddings using Ollama."""
    
    def __init__(self, model_name: str = "nomic-embed-text", base_url: str = None):
        """
        Initialize Ollama embeddings.
        
        Args:
            model_name: Name of the Ollama embedding model
            base_url: Ollama server URL
        """
        if not OLLAMA_AVAILABLE:
            raise ImportError("ollama is required. Install with: pip install ollama")
        
        self.model_name = model_name
        self.base_url = base_url or OLLAMA_BASE_URL
        
        # Configure ollama client
        if self.base_url != "http://localhost:11434":
            ollama.Client.host = self.base_url
        
        try:
            # Test if the model is available
            logger.info(f"Testing Ollama model: {model_name}")
            test_embedding = ollama.embeddings(model=model_name, prompt="test")
            logger.info(f"Successfully connected to Ollama model: {model_name}")
        except Exception as e:
            logger.error(f"Error connecting to Ollama model {model_name}: {e}")
            logger.info(f"Make sure Ollama is running and the model {model_name} is available")
            raise
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        try:
            embeddings = []
            for text in texts:
                response = ollama.embeddings(model=self.model_name, prompt=text)
                embeddings.append(response['embedding'])
            return embeddings
        except Exception as e:
            logger.error(f"Error embedding documents with Ollama: {e}")
            raise
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        try:
            response = ollama.embeddings(model=self.model_name, prompt=text)
            return response['embedding']
        except Exception as e:
            logger.error(f"Error embedding query with Ollama: {e}")
            raise


class HuggingFaceEmbeddings(Embeddings):
    """Local embeddings using HuggingFace transformers."""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", device: str = None):
        """
        Initialize HuggingFace embeddings.
        
        Args:
            model_name: Name of the HuggingFace model
            device: Device to run on ('cpu', 'cuda', etc.)
        """
        if not HUGGINGFACE_AVAILABLE:
            raise ImportError("transformers and torch are required. Install with: pip install transformers torch")
        
        self.model_name = model_name
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        
        try:
            logger.info(f"Loading HuggingFace model: {model_name}")
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
            self.model.to(self.device)
            logger.info(f"Successfully loaded model: {model_name} on {self.device}")
        except Exception as e:
            logger.error(f"Error loading HuggingFace model {model_name}: {e}")
            raise
    
    def _mean_pooling(self, model_output, attention_mask):
        """Apply mean pooling to get sentence embeddings."""
        token_embeddings = model_output[0]
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        try:
            # Tokenize sentences
            encoded_input = self.tokenizer(texts, padding=True, truncation=True, return_tensors='pt')
            encoded_input = {k: v.to(self.device) for k, v in encoded_input.items()}
            
            # Compute token embeddings
            with torch.no_grad():
                model_output = self.model(**encoded_input)
            
            # Perform pooling
            sentence_embeddings = self._mean_pooling(model_output, encoded_input['attention_mask'])
            
            # Normalize embeddings
            sentence_embeddings = torch.nn.functional.normalize(sentence_embeddings, p=2, dim=1)
            
            return sentence_embeddings.cpu().numpy().tolist()
        except Exception as e:
            logger.error(f"Error embedding documents with HuggingFace: {e}")
            raise
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        return self.embed_documents([text])[0]


def create_local_embeddings(provider: str, model_name: str = None, **kwargs) -> Embeddings:
    """
    Factory function to create local embedding instances.
    
    Args:
        provider: Type of local embedding provider ('sentence-transformers', 'ollama', 'huggingface')
        model_name: Optional model name (uses default if not provided)
        **kwargs: Additional arguments for the embedding provider
        
    Returns:
        Embeddings: A configured local embedding instance
        
    Raises:
        ValueError: If the provider is not supported
        ImportError: If required dependencies are not installed
    """
    provider = provider.lower()
    
    # Get the default model name if not provided
    if not model_name:
        model_name = get_embedding_model_name(provider, "default")
    
    if provider == "sentence-transformers":
        return SentenceTransformersEmbeddings(model_name=model_name, **kwargs)
    
    elif provider == "ollama":
        return OllamaEmbeddings(model_name=model_name, **kwargs)
    
    elif provider == "huggingface":
        return HuggingFaceEmbeddings(model_name=model_name, **kwargs)
    
    else:
        raise ValueError(f"Unsupported local embedding provider: {provider}")


def get_available_local_providers() -> Dict[str, bool]:
    """
    Check which local embedding providers are available.
    
    Returns:
        Dict mapping provider names to availability status
    """
    return {
        "sentence-transformers": SENTENCE_TRANSFORMERS_AVAILABLE,
        "ollama": OLLAMA_AVAILABLE,
        "huggingface": HUGGINGFACE_AVAILABLE,
    }


def get_recommended_model(use_case: str = "general") -> Dict[str, str]:
    """
    Get recommended models for different use cases.
    
    Args:
        use_case: The use case ('general', 'scientific', 'multilingual', 'fast', 'quality')
        
    Returns:
        Dict with provider and model recommendations
    """
    recommendations = {
        "fast": {
            "provider": "sentence-transformers",
            "model": "all-MiniLM-L6-v2",
            "description": "Fastest option, good for development and testing"
        },
        "general": {
            "provider": "sentence-transformers", 
            "model": "all-MiniLM-L6-v2",
            "description": "Good balance of speed and quality"
        },
        "quality": {
            "provider": "sentence-transformers",
            "model": "all-mpnet-base-v2", 
            "description": "Higher quality embeddings, slower"
        },
        "scientific": {
            "provider": "sentence-transformers",
            "model": "allenai-specter",
            "description": "Optimized for scientific text"
        },
        "multilingual": {
            "provider": "sentence-transformers",
            "model": "paraphrase-multilingual-MiniLM-L12-v2",
            "description": "Supports multiple languages"
        },
        "ollama": {
            "provider": "ollama",
            "model": "nomic-embed-text",
            "description": "Local Ollama embedding model"
        }
    }
    
    return recommendations.get(use_case, recommendations["general"]) 