# src/respond.py
# Core text generation service with OpenRouter primary provider and Gemini fallback.

import logging
import os
import re
from typing import Optional

from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import configuration
from config import MAX_NEW_TOKENS, GEMINI_API_KEY, MODEL_NAME, PROVIDER, RESPOND_PORT

# Provider modules
from provider_openrouter import generate_with_openrouter

# Google GenAI SDK (fallback)
from google import genai

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

# Initialize Gemini client (fallback path)
gemini_client: Optional[genai.Client] = None
if not GEMINI_API_KEY:
    logger.info("Gemini API key not found in env or ~/.api-gemini; Gemini fallback disabled.")
else:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Google GenAI client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Google GenAI client: {e}")
        gemini_client = None

def _generate_with_gemini(prompt: str) -> str:
    """
    Generate text using Google's Gemini API.

    Args:
        prompt: The input prompt for generation

    Returns:
        Generated text or error message
    """
    if not gemini_client:
        logger.error("Gemini client not initialized")
        return "Error: AI model not configured."

    try:
        logger.info(f"Calling Gemini API with model: {MODEL_NAME}")
        response = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            generation_config={"max_output_tokens": MAX_NEW_TOKENS},
        )

        if not getattr(response, "candidates", None):
            logger.warning("Gemini API returned no candidates")
            return "AI response generation failed or was blocked."

        text = getattr(response, "text", "")
        if not text:
            logger.warning("Gemini API returned empty text")
            return "AI response generation failed or was blocked."

        logger.info("Successfully generated response with Gemini")
        return text.strip()

    except Exception as e:
        logger.error(f"Error during Gemini API call: {e}", exc_info=True)
        return "Error generating AI response."

def predict_response(prompt: str) -> str:
    """
    Generate a response for the given prompt using configured provider with fallback.

    Args:
        prompt: The input prompt for text generation

    Returns:
        The generated text response, or an error message if generation fails
    """
    logger.info(f"Processing prompt: {prompt[:100]}...")

    # Handle test prompts (used for testing)
    is_test_prompt = prompt.startswith("test prompt:")
    api_prompt = prompt[len("test prompt:"):] if is_test_prompt else prompt

    result_text = ""

    try:
        if PROVIDER == "openrouter":
            # Primary: OpenRouter
            logger.info("Attempting OpenRouter generation")
            result_text = generate_with_openrouter(
                api_prompt,
                model_name=MODEL_NAME,
                max_new_tokens=MAX_NEW_TOKENS
            ) or ""

            if not result_text:
                logger.warning("OpenRouter generation failed; attempting Gemini fallback")
                result_text = _generate_with_gemini(api_prompt)
        else:
            # Primary: Gemini
            logger.info("Attempting Gemini generation")
            result_text = _generate_with_gemini(api_prompt)

            if not result_text:
                logger.warning("Gemini generation failed; attempting OpenRouter fallback")
                result_text = generate_with_openrouter(
                    api_prompt,
                    model_name=MODEL_NAME,
                    max_new_tokens=MAX_NEW_TOKENS
                ) or ""

        if not result_text:
            logger.error("All generation providers failed")
            return "Error: Unable to generate response from any provider."

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
        "providers": {
            "openrouter": "configured" if PROVIDER == "openrouter" else "fallback",
            "gemini": "configured" if gemini_client else "disabled"
        }
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