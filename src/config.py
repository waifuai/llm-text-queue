import os
from typing import Optional

def _read_key_file(path: str) -> Optional[str]:
    try:
        with open(os.path.expanduser(path), 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None
    except Exception:
        return None

# Preferred environment variables for API key
# Order: GEMINI_API_KEY, GOOGLE_API_KEY, then fallback file ~/.api-gemini
GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
    or _read_key_file("~/.api-gemini")
)

# Centralized model name for the project
MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-pro")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", 150))  # Default increased for LLM
