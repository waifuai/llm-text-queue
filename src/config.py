import os
from typing import Optional

def _read_text_file(path: str) -> Optional[str]:
    try:
        with open(os.path.expanduser(path), 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None
    except Exception:
        return None

# API key resolution for Gemini (unchanged behavior)
# Order: GEMINI_API_KEY, GOOGLE_API_KEY, then fallback file ~/.api-gemini
GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
    or _read_text_file("~/.api-gemini")
)

# Provider selection
# Default provider is openrouter (can be overridden by env PROVIDER)
PROVIDER = os.getenv("PROVIDER", "openrouter").strip().lower()

# Model resolution files
# ~/.model-openrouter for OpenRouter model name
# ~/.model-gemini for Gemini model name
OPENROUTER_MODEL_FILE = "~/.model-openrouter"
GEMINI_MODEL_FILE = "~/.model-gemini"

# Defaults if files/env not provided
DEFAULT_OPENROUTER_MODEL = "openrouter/horizon-beta"
DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"

# Allow overriding via env, then fall back to files, then defaults
OPENROUTER_MODEL_NAME = (
    os.getenv("OPENROUTER_MODEL_NAME")
    or _read_text_file(OPENROUTER_MODEL_FILE)
    or DEFAULT_OPENROUTER_MODEL
)

GEMINI_MODEL_NAME = (
    os.getenv("GEMINI_MODEL_NAME")
    or _read_text_file(GEMINI_MODEL_FILE)
    or DEFAULT_GEMINI_MODEL
)

# Centralized, provider-aware model name
MODEL_NAME = OPENROUTER_MODEL_NAME if PROVIDER == "openrouter" else GEMINI_MODEL_NAME

# Queue/limits
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", 150))  # Default increased for LLM
