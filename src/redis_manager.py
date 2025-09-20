# src/redis_manager.py
"""
LLM Text Queue GPU - Redis Connection Management
This module provides robust Redis connection management with connection pooling,
error handling, and automatic reconnection capabilities. It manages Redis clients,
RQ queues, connection health monitoring, and provides both class-based and functional
interfaces for Redis operations. The system includes comprehensive health checks,
graceful error recovery, and detailed logging for debugging and monitoring.
"""

import redis
import logging
from redis.connection import ConnectionPool
from redis.exceptions import ConnectionError, TimeoutError, RedisError
from typing import Optional, Dict, Any
from rq import Queue

from config import REDIS_URL

logger = logging.getLogger(__name__)


class RedisManager:
    """
    Manages Redis connections with connection pooling and error recovery.
    """

    def __init__(self, redis_url: str = REDIS_URL, max_connections: int = 10):
        self.redis_url = redis_url
        self.max_connections = max_connections
        self._connection_pool: Optional[ConnectionPool] = None
        self._redis_client: Optional[redis.Redis] = None
        self._queue: Optional[Queue] = None
        self._is_connected = False

    def connect(self) -> bool:
        """
        Establish Redis connection with connection pooling.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Create connection pool
            self._connection_pool = ConnectionPool.from_url(
                self.redis_url,
                max_connections=self.max_connections,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )

            # Create Redis client
            self._redis_client = redis.Redis(connection_pool=self._connection_pool)

            # Test connection
            self._redis_client.ping()
            self._is_connected = True

            # Create RQ queue
            self._queue = Queue(connection=self._redis_client, name='default')

            logger.info("Redis connection established successfully")
            logger.info(f"Connection pool size: {self.max_connections}")
            return True

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to Redis: {e}")
            self._is_connected = False
            return False

    def disconnect(self):
        """Close Redis connections gracefully."""
        try:
            if self._redis_client:
                self._redis_client.close()
                logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
        finally:
            self._is_connected = False
            self._redis_client = None
            self._queue = None

    def reconnect(self) -> bool:
        """
        Attempt to reconnect to Redis.

        Returns:
            bool: True if reconnection successful, False otherwise
        """
        logger.info("Attempting to reconnect to Redis...")
        self.disconnect()
        return self.connect()

    def ping(self) -> bool:
        """
        Test Redis connection.

        Returns:
            bool: True if ping successful, False otherwise
        """
        if not self._redis_client:
            return False

        try:
            self._redis_client.ping()
            return True
        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.warning(f"Redis ping failed: {e}")
            self._is_connected = False
            return False

    def get_info(self) -> Dict[str, Any]:
        """
        Get Redis server information.

        Returns:
            Dict containing Redis info, empty dict if error
        """
        if not self._redis_client:
            return {}

        try:
            return self._redis_client.info()
        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.error(f"Failed to get Redis info: {e}")
            return {}

    def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check.

        Returns:
            Dict with health status details
        """
        health = {
            "connected": self._is_connected,
            "ping": False,
            "queue_available": False,
            "info_available": False,
            "error": None
        }

        if not self._redis_client:
            health["error"] = "No Redis client available"
            return health

        # Test ping
        try:
            self._redis_client.ping()
            health["ping"] = True
        except Exception as e:
            health["error"] = f"Ping failed: {e}"
            return health

        # Check queue
        if self._queue:
            health["queue_available"] = True

        # Check info
        try:
            info = self._redis_client.info()
            health["info_available"] = bool(info)
        except Exception as e:
            logger.warning(f"Failed to get Redis info: {e}")

        return health

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._is_connected and self.ping()

    @property
    def client(self) -> Optional[redis.Redis]:
        """Get Redis client instance."""
        return self._redis_client

    @property
    def queue(self) -> Optional[Queue]:
        """Get RQ queue instance."""
        return self._queue

    @property
    def connection_pool(self) -> Optional[ConnectionPool]:
        """Get Redis connection pool."""
        return self._connection_pool


# Global Redis manager instance
redis_manager = RedisManager()


def get_redis_manager() -> RedisManager:
    """Get the global Redis manager instance."""
    return redis_manager


def initialize_redis() -> bool:
    """
    Initialize Redis connection with retry logic.

    Returns:
        bool: True if initialization successful, False otherwise
    """
    max_retries = 3
    for attempt in range(max_retries):
        if redis_manager.connect():
            logger.info("Redis initialized successfully")
            return True

        if attempt < max_retries - 1:
            logger.warning(f"Redis initialization attempt {attempt + 1} failed, retrying...")
        else:
            logger.error("Redis initialization failed after all retries")

    return False


def get_redis_client() -> Optional[redis.Redis]:
    """Get Redis client with automatic reconnection."""
    if not redis_manager.is_connected:
        logger.warning("Redis not connected, attempting reconnection...")
        if not redis_manager.reconnect():
            logger.error("Redis reconnection failed")
            return None
    return redis_manager.client


def get_queue() -> Optional[Queue]:
    """Get RQ queue with automatic reconnection."""
    if not redis_manager.is_connected:
        logger.warning("Redis not connected, attempting reconnection...")
        if not redis_manager.reconnect():
            logger.error("Redis reconnection failed")
            return None
    return redis_manager.queue