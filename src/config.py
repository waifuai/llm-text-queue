"""
LLM Text Queue GPU - Configuration Management
This module manages all configuration settings for the LLM text queue system, including
API keys, model configuration, port settings, and Redis connection.
It uses OpenRouter as the sole provider, with environment-specific settings,
and includes comprehensive validation and logging of configuration parameters.
"""
import os
import sys
from typing import Optional, Dict, Any
import logging

# Set up basic logging for config module
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _read_text_file(path: str) -> Optional[str]:
    """
    Read a text file, expanding user path if needed.

    Args:
        path: File path to read

    Returns:
        File contents as string, or None if file doesn't exist or can't be read
    """
    try:
        expanded_path = os.path.expanduser(path)
        with open(expanded_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if content:
                logger.info(f"Successfully read config from: {expanded_path}")
                return content
            else:
                logger.warning(f"Config file is empty: {expanded_path}")
                return None
    except FileNotFoundError:
        logger.info(f"Config file not found: {expanded_path}")
        return None
    except PermissionError:
        logger.error(f"Permission denied reading config file: {expanded_path}")
        return None
    except Exception as e:
        logger.error(f"Error reading config file {expanded_path}: {e}")
        return None

# Provider selection (only openrouter supported after Gemini migration)
PROVIDER = "openrouter"

# Model resolution
# ~/.model-openrouter for OpenRouter model name
OPENROUTER_MODEL_FILE = "~/.model-openrouter"

# Default if file/env not provided
DEFAULT_OPENROUTER_MODEL = "openrouter/free"

# Allow overriding via env, then fall back to file, then default
MODEL_NAME = (
    os.getenv("OPENROUTER_MODEL_NAME")
    or _read_text_file(OPENROUTER_MODEL_FILE)
    or DEFAULT_OPENROUTER_MODEL
)

# Queue/limits
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
QUEUE_PORT = int(os.getenv("QUEUE_PORT", 5000))
RESPOND_PORT = int(os.getenv("RESPOND_PORT", 5001))
MAIN_PORT = int(os.getenv("PORT", 8000))
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", 150))  # Default increased for LLM

# Configuration validation
def validate_configuration() -> tuple[bool, list[str]]:
    """
    Validate the current configuration and return any issues found.

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []

    # Validate ports
    ports_to_check = [
        ("QUEUE_PORT", QUEUE_PORT, 1024, 65535),
        ("RESPOND_PORT", RESPOND_PORT, 1024, 65535),
        ("MAIN_PORT", MAIN_PORT, 1024, 65535)
    ]

    for port_name, port_value, min_port, max_port in ports_to_check:
        if not (min_port <= port_value <= max_port):
            issues.append(f"{port_name} ({port_value}) is not in valid range ({min_port}-{max_port})")

    # Check for port conflicts
    ports = [QUEUE_PORT, RESPOND_PORT, MAIN_PORT]
    if len(ports) != len(set(ports)):
        issues.append("Port conflicts detected: multiple services configured to use the same port")

    # Validate Redis URL
    if not REDIS_URL or not REDIS_URL.startswith("redis://"):
        issues.append("REDIS_URL must be a valid Redis URL starting with 'redis://'")

    # Validate tokens
    if MAX_NEW_TOKENS <= 0:
        issues.append("MAX_NEW_TOKENS must be a positive integer")
    elif MAX_NEW_TOKENS > 4000:
        issues.append("MAX_NEW_TOKENS is very high (>4000), this may cause issues")

    # Validate provider
    if PROVIDER != "openrouter":
        issues.append(f"PROVIDER must be 'openrouter', got: {PROVIDER}")

    # Check OpenRouter API key
    openrouter_key = os.getenv("OPENROUTER_API_KEY") or _read_text_file("~/.api-openrouter")
    if not openrouter_key:
        issues.append("No OpenRouter API key found. Set OPENROUTER_API_KEY or create ~/.api-openrouter file")

    return len(issues) == 0, issues


def get_configuration_summary() -> Dict[str, Any]:
    """
    Get a summary of the current configuration for logging/debugging.

    Returns:
        Dictionary containing configuration summary
    """
    return {
        "provider": PROVIDER,
        "model": MODEL_NAME,
        "redis_url": REDIS_URL,
        "ports": {
            "main": MAIN_PORT,
            "queue": QUEUE_PORT,
            "respond": RESPOND_PORT
        },
        "limits": {
            "max_new_tokens": MAX_NEW_TOKENS
        },
        "api_keys": {
            "openrouter_configured": bool(os.getenv("OPENROUTER_API_KEY") or _read_text_file("~/.api-openrouter"))
        }
    }


def log_configuration():
    """Log the current configuration (without sensitive data)."""
    summary = get_configuration_summary()

    logger.info("=== Configuration Summary ===")
    logger.info(f"Provider: {summary['provider']}")
    logger.info(f"Model: {summary['model']}")
    logger.info(f"Redis URL: {summary['redis_url']}")
    logger.info(f"Ports: {summary['ports']}")
    logger.info(f"Limits: {summary['limits']}")
    logger.info(f"API Keys Configured: {summary['api_keys']}")
    logger.info("==============================")


def get_environment_name() -> str:
    """Get the current environment name based on configuration."""
    env = os.getenv("FLASK_ENV", "production").lower()
    return "production" if env == "production" else "development"


def load_environment_config():
    """Load environment-specific configuration overrides."""
    env = get_environment_name()
    logger.info(f"Loading configuration for environment: {env}")

    # Environment-specific overrides
    if env == "development":
        # More permissive settings for development
        global MAX_NEW_TOKENS
        MAX_NEW_TOKENS = min(MAX_NEW_TOKENS, 1000)  # Limit for dev

    elif env == "production":
        # Stricter settings for production
        pass  # Use defaults

    logger.info(f"Environment-specific configuration loaded for: {env}")


# Load environment-specific configuration on module import
load_environment_config()
