"""
LLM Text Queue GPU - RQ Worker Service
This module provides the RQ (Redis Queue) worker that processes text generation jobs
from the queue system. It uses the Redis manager for robust connection handling,
includes connection pooling, error recovery, and graceful shutdown capabilities.
The worker listens to the default queue and processes jobs with comprehensive
logging and monitoring for production reliability.
"""
import os
import logging
from rq import Worker
from rq.exceptions import ConnectionError as RQConnectionError
from redis_manager import get_redis_manager, initialize_redis

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Queue configuration
listen = ['default']

def create_worker():
    """
    Create and configure the RQ worker using Redis manager.

    Returns:
        Worker instance or None if connection fails
    """
    redis_mgr = get_redis_manager()

    if not redis_mgr.is_connected:
        logger.error("Cannot create worker: Redis not connected")
        return None

    try:
        from rq import Queue
        worker = Worker(list(map(Queue, listen)), connection=redis_mgr.client)
        logger.info("Worker created successfully with connection pooling")
        return worker
    except Exception as e:
        logger.error(f"Failed to create worker: {e}")
        return None

if __name__ == '__main__':
    logger.info("Starting RQ worker with improved connection management...")
    logger.info(f"Queues: {listen}")

    # Initialize Redis with connection pooling
    if not initialize_redis():
        logger.error("Redis initialization failed. Cannot start worker.")
        exit(1)

    worker = create_worker()
    if not worker:
        logger.error("Failed to create worker. Exiting.")
        exit(1)

    try:
        logger.info("Worker starting to process jobs with connection pooling...")
        worker.work()
    except KeyboardInterrupt:
        logger.info("Worker shutdown requested by user")
    except Exception as e:
        logger.error(f"Worker failed: {e}", exc_info=True)
        exit(1)
    finally:
        # Cleanup Redis connections
        redis_mgr = get_redis_manager()
        redis_mgr.disconnect()
        logger.info("Worker shutdown complete")
