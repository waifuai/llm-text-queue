import os

# MODEL_PATH = os.getenv("MODEL_PATH", "distilgpt2") # No longer needed for Gemini
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
# MAX_NEW_TOKENS can be used to configure Gemini generation if needed, e.g.,
# generation_config = genai.types.GenerationConfig(max_output_tokens=MAX_NEW_TOKENS)
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", 150)) # Default increased for LLM
# GPU_SERVICE_URL = os.getenv("GPU_SERVICE_URL", "http://localhost:5001") # No longer needed