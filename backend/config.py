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
MODEL_CACHE_DIR = BASE_DIR / "models_cache"

# Create model cache directory if it doesn't exist
MODEL_CACHE_DIR.mkdir(exist_ok=True)

# LLM settings
LLM_PROVIDERS = {
    "openai": {
        "model": os.getenv("OPENAI_MODEL", "gpt-5")
    },
    "anthropic": {
        "model": os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
    },
    "google": {
        "model": os.getenv("GOOGLE_MODEL", "gemini-2.5-pro")
    },
    "grok": {
        "model": os.getenv("GROK_MODEL", "grok-4")
    },
    "ollama": {
        "model": os.getenv("OLLAMA_MODEL", "deepseek-r1")
    }
}

DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "openai")  # openai, anthropic, google, grok, ollama
DEFAULT_LLM_MODEL = LLM_PROVIDERS[DEFAULT_LLM_PROVIDER]["model"]

# SPARQL endpoint settings
SPARQL_ENDPOINT_URL = os.getenv("SPARQL_ENDPOINT_URL", "http://localhost:7200/repositories/LiPDVerse-dynamic")
SPARQL_UPDATE_URL = os.getenv("SPARQL_UPDATE_URL", "http://localhost:7200/repositories/LiPDVerse-dynamic/statements")
SPARQL_USERNAME = os.getenv("SPARQL_USERNAME", "")
SPARQL_PASSWORD = os.getenv("SPARQL_PASSWORD", "")
SPARQL_TIMEOUT = int(os.getenv("SPARQL_TIMEOUT", "30"))

# Common SPARQL endpoints for different environments
SPARQL_ENDPOINTS = {
    "local": {
        "url": "http://localhost:7200/repositories/LiPDVerse-dynamic",
        "update_url": "http://localhost:7200/repositories/LiPDVerse-dynamic/statements",
        "description": "Local GraphDB instance"
    },
    "remote_lipd": {
        "url": "https://linkedearth.graphdb.mint.isi.edu/repositories/LiPDVerse-dynamic",
        "update_url": "https://linkedearth.graphdb.mint.isi.edu/repositories/LiPDVerse-dynamic/statements",
        "description": "Remote LiPDVerse repository"
    },
    "remote_lipd2": {
        "url": "https://linkedearth.graphdb.mint.isi.edu/repositories/LiPDVerse2",
        "update_url": "https://linkedearth.graphdb.mint.isi.edu/repositories/LiPDVerse2/statements",
        "description": "Remote LiPDVerse2 repository"
    }
}

# Ollama settings
OLLAMA_REASONING_MODELS = os.getenv("OLLAMA_REASONING_MODELS", "deepseek-r1,marco-o1,qwen2.5-coder,thinking-model").split(",")
OLLAMA_JSON_TEMPERATURE = float(os.getenv("OLLAMA_JSON_TEMPERATURE", "0.1"))  # Lower temp for JSON tasks
OLLAMA_JSON_TOP_P = float(os.getenv("OLLAMA_JSON_TOP_P", "0.9"))
OLLAMA_JSON_REPEAT_PENALTY = float(os.getenv("OLLAMA_JSON_REPEAT_PENALTY", "1.1")) 