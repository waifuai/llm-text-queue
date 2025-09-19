# src/api_queue.py
# Queue service that receives prompts, queues them using Redis, and forwards them to respond.py for processing.

import os
import subprocess
import requests
import logging
import redis
import re
from typing import Optional

from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from rq import Queue
from rq.exceptions import ConnectionError as RQConnectionError

# Import configuration
from config import RESPOND_PORT, REDIS_URL

# Service URL for the response service
GPU_SERVICE_URL = f"http://localhost:{RESPOND_PORT or 5001}"

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]  # Reasonable defaults
)

# Redis connection with error handling
try:
    conn = redis.from_url(REDIS_URL)
    q = Queue(connection=conn, name='default')
    logger.info("Redis connection established successfully")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    conn = None
    q = None


def call_predict_response(prompt: str) -> str:
    """
    Calls the response service to generate text for a given prompt.

    Args:
        prompt: The input prompt for text generation

    Returns:
        Generated text response or error message
    """
    try:
        logger.info(f"Calling response service with prompt: {prompt[:50]}...")
        response = requests.post(
            f"{GPU_SERVICE_URL}/generate",
            json={'prompt': prompt},
            timeout=30
        )
        response.raise_for_status()
        result = response.json().get('response', '')
        logger.info("Successfully received response from service")
        return result
    except requests.exceptions.Timeout:
        logger.error("Timeout calling response service")
        return "Error: Response service timeout"
    except requests.exceptions.ConnectionError:
        logger.error("Connection error calling response service")
        return "Error: Could not connect to response service"
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error calling response service: {e}")
        return f"Error: Response service returned {e.response.status_code}"
    except Exception as e:
        logger.error(f"Unexpected error calling response service: {e}")
        return "Error: Internal server error"


def test_worker() -> str:
    """
    Simple test function for worker health checks.

    Returns:
        Test confirmation string
    """
    return "worker_test_ok"


def check_services_health() -> dict:
    """
    Comprehensive health check for all services.

    Returns:
        Dict containing health status of each service
    """
    health_status = {
        "redis": False,
        "worker": False,
        "response_service": False,
        "overall": False
    }

    try:
        # Check Redis connection
        if conn:
            conn.ping()
            health_status["redis"] = True
            logger.info("Redis health check passed")
        else:
            logger.error("Redis connection not available")
            return health_status

        # Check worker by enqueueing a test job
        if q:
            job = q.enqueue_call(func=test_worker, result_ttl=5)
            job.get_status()
            job.delete()
            health_status["worker"] = True
            logger.info("Worker health check passed")
        else:
            logger.error("Queue not available")
            return health_status

        # Check response service
        try:
            response = requests.get(f"{GPU_SERVICE_URL}/health", timeout=5)
            response.raise_for_status()
            health_status["response_service"] = True
            logger.info("Response service health check passed")
        except Exception as e:
            logger.error(f"Response service health check failed: {e}")

    except redis.exceptions.ConnectionError as e:
        logger.error(f"Redis connection error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during health check: {e}")

    # Overall health is true only if all services are healthy
    health_status["overall"] = all([
        health_status["redis"],
        health_status["worker"],
        health_status["response_service"]
    ])

    return health_status


@app.route('/health')
def health_check():
    """
    Health check endpoint for all services.

    Returns:
        JSON response with detailed health status
    """
    health = check_services_health()

    if health["overall"]:
        return jsonify({
            "status": "healthy",
            "services": health
        }), 200
    else:
        return jsonify({
            "status": "unhealthy",
            "services": health
        }), 503


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


def validate_prompt(prompt: str) -> tuple[bool, str]:
    """
    Validate the input prompt.

    Args:
        prompt: The prompt to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not prompt:
        return False, "Prompt cannot be empty"

    if not isinstance(prompt, str):
        return False, "Prompt must be a string"

    prompt = prompt.strip()
    if len(prompt) == 0:
        return False, "Prompt cannot be only whitespace"

    if len(prompt) > 10000:  # Reasonable limit for LLM prompts
        return False, "Prompt too long (max 10000 characters)"

    return True, ""


@app.route('/generate', methods=['POST'])
@limiter.limit("10 per minute")  # Stricter limit for generation endpoint
def generate_text():
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

        is_valid, error_msg = validate_prompt(prompt)

        if not is_valid:
            logger.warning(f"Invalid prompt: {error_msg}")
            return jsonify({"error": error_msg}), 400

        # Check if services are available
        if not conn or not q:
            logger.error("Redis/Queue not available")
            return jsonify({"error": "Service temporarily unavailable"}), 503

        # Enqueue the job
        logger.info(f"Enqueueing generation job for prompt: {prompt[:50]}...")
        job = q.enqueue_call(
            func=call_predict_response,
            args=(prompt,),
            result_ttl=3600,  # 1 hour
            timeout=600  # 10 minutes
        )

        # Wait for result
        result = job.get_result(timeout=600)

        logger.info("Successfully generated response")
        return jsonify({
            "response": result,
            "job_id": job.id
        }), 200

    except Exception as e:
        logger.error(f"Error processing generation request: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    # Get port from environment or config
    port = int(os.getenv('QUEUE_PORT', 5000))

    logger.info(f"Starting Queue API service on port {port}")
    logger.info(f"Response service URL: {GPU_SERVICE_URL}")
    logger.info(f"Redis URL: {REDIS_URL}")

    # Perform initial health check
    health = check_services_health()
    if not health["overall"]:
        logger.warning("Some services are not healthy on startup. Check logs above.")

    app.run(host='0.0.0.0', port=port)