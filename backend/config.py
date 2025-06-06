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