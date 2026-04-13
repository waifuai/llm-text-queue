"""
LLM Text Queue GPU - Response Generation Service
This module provides the core text generation service using OpenRouter,
featuring prompt validation, sanitization, rate limiting, error handling, and health monitoring.
The service handles both direct generation requests and queue-based processing,
with comprehensive logging and request handling capabilities.
"""
# src/respond.py
# Core text generation service with OpenRouter provider.

import logging
import os
import re

from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import configuration
from config import MAX_NEW_TOKENS, MODEL_NAME, RESPOND_PORT

# Provider modules
from provider_openrouter import generate_with_openrouter

app = Flask(__name__)

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

def predict_response(prompt: str) -> str:
    """
    Generate a response for the given prompt using OpenRouter.

    Args:
        prompt: The input prompt for text generation

    Returns:
        The generated text response, or an error message if generation fails
    """
    logger.info(f"Processing prompt: {prompt[:100]}...")

    # Handle test prompts (used for testing)
    is_test_prompt = prompt.startswith("test prompt:")
    api_prompt = prompt[len("test prompt:"):] if is_test_prompt else prompt

    try:
        logger.info("Attempting OpenRouter generation")
        result_text = generate_with_openrouter(
            api_prompt,
            model_name=MODEL_NAME,
            max_new_tokens=MAX_NEW_TOKENS
        ) or ""

        if not result_text:
            logger.error("OpenRouter generation failed")
            return "Error: Unable to generate response."

        # For test prompts, return bare result
        if is_test_prompt:
            return result_text

        # Format normal response
        return f"Okay. I received \"{prompt}\".\n\n{result_text}"

    except Exception as e:
        logger.error(f"Unexpected error in predict_response: {e}", exc_info=True)
        return "Error: Internal server error during text generation."

def sanitize_prompt(prompt: str) -> str:
    """
    Sanitize the input prompt to prevent injection attacks and normalize whitespace.

    Args:
        prompt: The raw prompt string

    Returns:
        Sanitized prompt string
    """
    if not prompt:
        return ""

    # Remove excessive whitespace and normalize line endings
    prompt = re.sub(r'\r\n', '\n', prompt)  # Normalize line endings
    prompt = re.sub(r'\n{3,}', '\n\n', prompt)  # Max 2 consecutive newlines
    prompt = re.sub(r'[ \t]+', ' ', prompt)  # Multiple spaces/tabs to single space

    # Remove potentially dangerous control characters
    prompt = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', prompt)

    return prompt.strip()


def validate_generation_prompt(prompt: str) -> tuple[bool, str]:
    """
    Validate prompt for generation endpoint.

    Args:
        prompt: The prompt to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not prompt:
        return False, "Missing 'prompt' parameter"

    if not isinstance(prompt, str):
        return False, "Prompt must be a string"

    prompt = prompt.strip()
    if len(prompt) == 0:
        return False, "Prompt cannot be empty or only whitespace"

    if len(prompt) > 10000:  # Reasonable limit
        return False, "Prompt too long (max 10000 characters)"

    return True, ""


@app.route('/health')
def health_check():
    """
    Health check endpoint for the response service.

    Returns:
        JSON response with service status
    """
    return jsonify({
        "status": "healthy",
        "service": "response",
        "provider": "openrouter"
    }), 200


@app.route('/generate', methods=['POST'])
@limiter.limit("10 per minute")
def generate_text_endpoint():
    """
    Generate text based on the provided prompt.

    Expected JSON payload:
    {
        "prompt": "Your prompt here"
    }

    Returns:
        JSON response with generated text or error message
    """
    try:
        # Validate request format
        if not request.is_json:
            logger.warning("Received non-JSON request to /generate")
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json()
        if not data:
            logger.warning("Received empty JSON payload")
            return jsonify({"error": "Missing JSON payload"}), 400

        prompt = data.get('prompt')

        # Sanitize the prompt first
        prompt = sanitize_prompt(prompt)

        is_valid, error_msg = validate_generation_prompt(prompt)

        if not is_valid:
            logger.warning(f"Invalid prompt: {error_msg}")
            return jsonify({"error": error_msg}), 400

        # Generate response
        logger.info(f"Processing generation request for prompt: {prompt[:50]}...")
        response = predict_response(prompt)

        return jsonify({
            "response": response,
            "provider_used": PROVIDER
        }), 200

    except Exception as e:
        logger.error(f"Error in generate_text_endpoint: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    port = RESPOND_PORT or int(os.getenv('RESPOND_PORT', 5001))
    logger.info(f"Starting Response API service on port {port}")
    logger.info(f"Provider: {PROVIDER}, Model: {MODEL_NAME}")
    app.run(host='0.0.0.0', port=port)