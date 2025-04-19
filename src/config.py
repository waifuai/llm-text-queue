import os

# Read Gemini API key from ~/.api-gemini
try:
    with open(os.path.expanduser('~/.api-gemini'), 'r') as f:
        GEMINI_API_KEY = f.read().strip()
except FileNotFoundError:
    GEMINI_API_KEY = None # Or raise an error, depending on desired behavior

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
# MAX_NEW_TOKENS can be used to configure Gemini generation if needed, e.g.,
# generation_config = genai.types.GenerationConfig(max_output_tokens=MAX_NEW_TOKENS)
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", 150)) # Default increased for LLM
