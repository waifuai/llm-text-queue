# src/main.py
# Main application entry point that consolidates all services into a single Flask app.

import os
import sys
import logging
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import configuration
from config import (
    MAX_NEW_TOKENS, GEMINI_API_KEY, MODEL_NAME, PROVIDER,
    QUEUE_PORT, RESPOND_PORT, MAIN_PORT, REDIS_URL,
    validate_configuration, log_configuration
)
from redis_manager import get_redis_manager, initialize_redis
from cache_manager import get_cache_manager

# Import service modules
from api_queue import (
    check_services_health as queue_health_check,
    validate_prompt,
    sanitize_prompt,
    call_predict_response
)
from respond import predict_response, validate_generation_prompt
from provider_openrouter import generate_with_openrouter
from google import genai

# Redis connection management
redis_conn = None
redis_queue = None

# Initialize main Flask app
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
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Google GenAI client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Google GenAI client: {e}")
        gemini_client = None


@app.route('/')
def index():
    """Root endpoint with service information."""
    return jsonify({
        "service": "LLM Text Queue GPU",
        "version": "2.0",
        "endpoints": {
            "/health": "Service health check",
            "/generate": "Direct text generation (with caching)",
            "/queue/generate": "Queue-based text generation",
            "/metrics": "Service metrics",
            "/cache/stats": "Cache statistics",
            "/cache/clear": "Clear all cache entries",
            "/cache/info": "Cache entry information"
        },
        "features": {
            "caching": True,
            "rate_limiting": True,
            "queue_processing": True,
            "health_checks": True,
            "metrics": True
        }
    })


@app.route('/health')
def health_check():
    """Comprehensive health check for all services."""
    health_status = {
        "overall": True,
        "services": {
            "redis": False,
            "queue": False,
            "generation": False
        }
    }

    try:
        # Check Redis connection using new manager
        redis_mgr = get_redis_manager()
        redis_health = redis_mgr.health_check()

        health_status["services"]["redis"] = redis_health.get('connected', False)
        health_status["services"]["queue"] = redis_health.get('queue_available', False)

        if not health_status["services"]["redis"]:
            health_status["overall"] = False
            health_status["details"] = {"redis_error": redis_health.get('error')}

        # Check generation providers
        if PROVIDER == "openrouter":
            health_status["services"]["generation"] = True
        elif gemini_client:
            health_status["services"]["generation"] = True
        else:
            health_status["overall"] = False

    except Exception as e:
        logger.error(f"Health check error: {e}")
        health_status["overall"] = False

    status_code = 200 if health_status["overall"] else 503
    return jsonify(health_status), status_code


@app.route('/generate', methods=['POST'])
@limiter.limit("10 per minute")
def generate_text():
    """Direct text generation endpoint (bypasses queue for immediate response)."""
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON payload"}), 400

        prompt = data.get('prompt')
        if not prompt:
            return jsonify({"error": "Missing 'prompt' parameter"}), 400

        # Sanitize and validate prompt
        prompt = sanitize_prompt(prompt)
        is_valid, error_msg = validate_generation_prompt(prompt)

        if not is_valid:
            logger.warning(f"Invalid prompt: {error_msg}")
            return jsonify({"error": error_msg}), 400

        # Check cache first
        cache_mgr = get_cache_manager()
        cached_response, cache_metadata = cache_mgr.get(prompt, PROVIDER, MODEL_NAME)

        if cached_response:
            logger.info("Returning cached response")
            return jsonify({
                "response": cached_response,
                "provider_used": PROVIDER,
                "method": "cached",
                "cache_info": cache_metadata
            }), 200

        # Generate new response
        logger.info(f"Direct generation request: {prompt[:50]}...")
        response = predict_response(prompt)

        # Cache the response for future use
        if response and response.strip():
            cache_metadata = {
                "provider": PROVIDER,
                "model": MODEL_NAME,
                "method": "direct_generation"
            }
            cache_mgr.set(prompt, PROVIDER, MODEL_NAME, response, cache_metadata)

        return jsonify({
            "response": response,
            "provider_used": PROVIDER,
            "method": "direct"
        }), 200

    except Exception as e:
        logger.error(f"Error in direct generation: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/queue/generate', methods=['POST'])
@limiter.limit("10 per minute")
def queue_generate_text():
    """Queue-based text generation endpoint."""
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON payload"}), 400

        prompt = data.get('prompt')
        if not prompt:
            return jsonify({"error": "Missing 'prompt' parameter"}), 400

        # Sanitize and validate prompt
        prompt = sanitize_prompt(prompt)
        is_valid, error_msg = validate_prompt(prompt)

        if not is_valid:
            logger.warning(f"Invalid prompt: {error_msg}")
            return jsonify({"error": error_msg}), 400

        # Check if services are available
        redis_mgr = get_redis_manager()
        if not redis_mgr.is_connected or not redis_mgr.queue:
            logger.error("Redis/Queue not available")
            return jsonify({"error": "Service temporarily unavailable"}), 503

        # Enqueue the job
        logger.info(f"Queueing generation job for prompt: {prompt[:50]}...")
        job = redis_mgr.queue.enqueue_call(
            func=call_predict_response,
            args=(prompt,),
            result_ttl=3600,
            timeout=600
        )

        # Wait for result
        result = job.get_result(timeout=600)

        logger.info("Successfully generated response via queue")
        return jsonify({
            "response": result,
            "job_id": job.id,
            "method": "queued"
        }), 200


@app.route('/cache/stats')
def cache_stats():
    """Get cache statistics and performance metrics."""
    cache_mgr = get_cache_manager()
    stats = cache_mgr.get_stats()

    return jsonify({
        "cache_statistics": stats,
        "cache_configuration": {
            "default_ttl": cache_mgr.default_ttl,
            "max_key_length": cache_mgr.max_key_length
        }
    }), 200


@app.route('/cache/clear', methods=['POST'])
def clear_cache():
    """Clear all cached responses."""
    try:
        cache_mgr = get_cache_manager()
        success = cache_mgr.clear_all()

        if success:
            return jsonify({"message": "Cache cleared successfully"}), 200
        else:
            return jsonify({"error": "Failed to clear cache"}), 500

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/cache/info')
def cache_info():
    """Get information about cache entries."""
    try:
        prompt = request.args.get('prompt', '')
        provider = request.args.get('provider', PROVIDER)
        model = request.args.get('model', MODEL_NAME)

        if not prompt:
            return jsonify({"error": "Prompt parameter required"}), 400

        cache_mgr = get_cache_manager()
        info = cache_mgr.get_cache_info(prompt, provider, model)

        return jsonify({"cache_info": info}), 200

    except Exception as e:
        logger.error(f"Error getting cache info: {e}")
        return jsonify({"error": "Internal server error"}), 500

    except Exception as e:
        logger.error(f"Error in queue generation: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/metrics')
def metrics():
    """Basic metrics endpoint for monitoring."""
    try:
        # Get Redis info using new manager
        redis_mgr = get_redis_manager()
        redis_info = redis_mgr.get_info()

        # Queue info
        queue_info = {}
        if redis_mgr.queue:
            try:
                queue_info = {
                    "name": redis_mgr.queue.name,
                    "job_count": len(redis_mgr.queue.jobs) if hasattr(redis_mgr.queue, 'jobs') else 0
                }
            except Exception as e:
                logger.error(f"Error getting queue info: {e}")
                queue_info = {"error": str(e)}

        # Get cache statistics
        cache_mgr = get_cache_manager()
        cache_stats = cache_mgr.get_stats()

        return jsonify({
            "service": "LLM Text Queue GPU v2.0",
            "redis": redis_info,
            "queue": queue_info,
            "cache": cache_stats,
            "provider": PROVIDER,
            "model": MODEL_NAME
        }), 200

    except Exception as e:
        logger.error(f"Error in metrics endpoint: {e}")
        return jsonify({"error": "Internal server error"}), 500


def initialize_service():
    """Initialize the service with configuration validation."""
    logger.info("Initializing LLM Text Queue GPU service...")

    # Validate configuration
    is_valid, issues = validate_configuration()
    if not is_valid:
        logger.error("Configuration validation failed:")
        for issue in issues:
            logger.error(f"  - {issue}")
        logger.error("Please fix the configuration issues and restart the service.")
        sys.exit(1)

    # Log configuration
    log_configuration()

    # Initialize Redis with improved connection management
    if not initialize_redis():
        logger.error("Redis initialization failed")
        logger.error("Service may not function properly without Redis")
    else:
        redis_mgr = get_redis_manager()
        health = redis_mgr.health_check()
        if health.get('connected'):
            logger.info("Redis connection established with connection pooling")
            logger.info(f"Connection pool size: {redis_mgr.connection_pool.max_connections if redis_mgr.connection_pool else 'N/A'}")
        else:
            logger.error("Redis health check failed")

    logger.info("Service initialization completed successfully")


if __name__ == "__main__":
    # Initialize service with validation
    initialize_service()

    # Start the Flask application
    logger.info(f"Starting Flask application on port {MAIN_PORT}")
    try:
        app.run(host='0.0.0.0', port=MAIN_PORT)
    except KeyboardInterrupt:
        logger.info("Service shutdown requested by user")
    except Exception as e:
        logger.error(f"Failed to start Flask application: {e}")
        sys.exit(1)