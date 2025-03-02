import os

MODEL_PATH = os.getenv("MODEL_PATH", "distilgpt2")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", 20))
GPU_SERVICE_URL = os.getenv("GPU_SERVICE_URL", "http://localhost:5001")