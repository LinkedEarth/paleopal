import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", str(DATA_DIR / "chroma_db"))
QUERY_CORPUS_PATH = os.getenv("QUERY_CORPUS_PATH", str(BASE_DIR / "queries"))

# LLM settings
LLM_PROVIDERS = {
    "openai": {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o")
    },
    "anthropic": {
        "model": os.getenv("CLAUDE_MODEL", "claude-3-7-sonnet-20250219")
    },
    "google": {
        "model": os.getenv("GOOGLE_MODEL", "gemini-2.5-flash-preview-04-17")
    },
    "grok": {
        "model": os.getenv("GROK_MODEL", "grok-3-mini-beta")
    },
    "ollama": {
        "model": os.getenv("OLLAMA_MODEL", "deepseek-r1")
    }
}

DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "openai")  # openai, anthropic, google, grok, ollama
DEFAULT_LLM_MODEL = LLM_PROVIDERS[DEFAULT_LLM_PROVIDER]["model"]

# Embedding model settings
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")  # openai, google, sentence-transformers, ollama, huggingface
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")

# Local embedding model settings
LOCAL_EMBEDDING_MODELS = {
    "sentence-transformers": {
        "default": "all-MiniLM-L6-v2",  # Fast and lightweight
        "multilingual": "paraphrase-multilingual-MiniLM-L12-v2",  # Multilingual support
        "high-quality": "all-mpnet-base-v2",  # Higher quality, slower
        "scientific": "allenai-specter",  # Scientific text optimized
    },
    "ollama": {
        "default": "nomic-embed-text",  # Ollama's default embedding model
        "mxbai": "mxbai-embed-large",  # High-quality embedding model
    },
    "huggingface": {
        "default": "sentence-transformers/all-MiniLM-L6-v2",
        "scientific": "sentence-transformers/allenai-specter",
        "multilingual": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    }
}

# Get the specific model for the provider
def get_embedding_model_name(provider: str = None, model_type: str = "default") -> str:
    """Get the embedding model name for a specific provider and type."""
    provider = provider or EMBEDDING_PROVIDER
    
    if provider in LOCAL_EMBEDDING_MODELS:
        return LOCAL_EMBEDDING_MODELS[provider].get(model_type, LOCAL_EMBEDDING_MODELS[provider]["default"])
    else:
        return EMBEDDING_MODEL

# RAG settings
NUM_RESULTS = int(os.getenv("NUM_RESULTS", "5"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))

# SPARQL endpoint settings
SPARQL_ENDPOINT_URL = os.getenv("SPARQL_ENDPOINT_URL", "http://localhost:7200/repositories/LiPDVerse-dynamic")
SPARQL_UPDATE_URL = os.getenv("SPARQL_UPDATE_URL", "http://localhost:7200/repositories/LiPDVerse-dynamic/statements")
SPARQL_USERNAME = os.getenv("SPARQL_USERNAME", "")
SPARQL_PASSWORD = os.getenv("SPARQL_PASSWORD", "")

# Ollama settings
OLLAMA_REASONING_MODELS = os.getenv("OLLAMA_REASONING_MODELS", "deepseek-r1,marco-o1,qwen2.5-coder,thinking-model").split(",")
OLLAMA_JSON_TEMPERATURE = float(os.getenv("OLLAMA_JSON_TEMPERATURE", "0.1"))  # Lower temp for JSON tasks
OLLAMA_JSON_TOP_P = float(os.getenv("OLLAMA_JSON_TOP_P", "0.9"))
OLLAMA_JSON_REPEAT_PENALTY = float(os.getenv("OLLAMA_JSON_REPEAT_PENALTY", "1.1")) 