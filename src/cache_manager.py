# src/cache_manager.py
"""
LLM Text Queue GPU - Response Caching System
This module provides a comprehensive caching system for LLM responses using Redis as the backend.
It manages cache keys, serialization, TTL (time-to-live), cache statistics, and provides
both class-based and functional interfaces for caching operations. The system includes
cache hit/miss tracking, cache invalidation, and detailed statistics reporting.
"""

import hashlib
import json
import time
import logging
from typing import Optional, Dict, Any, Tuple
from redis_manager import get_redis_manager

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages caching of LLM responses with Redis backend.
    """

    def __init__(self, default_ttl: int = 3600, max_key_length: int = 250):
        """
        Initialize cache manager.

        Args:
            default_ttl: Default time-to-live for cache entries in seconds (1 hour)
            max_key_length: Maximum length for cache keys
        """
        self.default_ttl = default_ttl
        self.max_key_length = max_key_length
        self.redis_mgr = get_redis_manager()
        self.cache_prefix = "llm_cache:"
        self.hit_count = 0
        self.miss_count = 0

    def _generate_cache_key(self, prompt: str, provider: str, model: str) -> str:
        """
        Generate a consistent cache key for the given parameters.

        Args:
            prompt: The input prompt
            provider: The provider name (openrouter, gemini, etc.)
            model: The model name

        Returns:
            Cache key string
        """
        # Create a hash of the prompt to keep key length manageable
        prompt_hash = hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:16]

        # Combine components into key
        key_components = [self.cache_prefix, provider, model, prompt_hash]
        key = ":".join(key_components)

        # Ensure key doesn't exceed maximum length
        if len(key) > self.max_key_length:
            key = key[:self.max_key_length]

        return key

    def _serialize_response(self, response: str, metadata: Dict[str, Any]) -> str:
        """
        Serialize response data for storage.

        Args:
            response: The generated response text
            metadata: Additional metadata to store

        Returns:
            JSON serialized data
        """
        cache_data = {
            "response": response,
            "metadata": metadata,
            "cached_at": time.time(),
            "version": "1.0"
        }
        return json.dumps(cache_data)

    def _deserialize_response(self, cached_data: str) -> Tuple[str, Dict[str, Any]]:
        """
        Deserialize cached response data.

        Args:
            cached_data: JSON serialized cache data

        Returns:
            Tuple of (response_text, metadata)
        """
        try:
            data = json.loads(cached_data)
            response = data.get("response", "")
            metadata = data.get("metadata", {})
            metadata["cached_at"] = data.get("cached_at", 0)
            return response, metadata
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to deserialize cached data: {e}")
            return "", {}

    def get(self, prompt: str, provider: str, model: str) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Retrieve cached response for given parameters.

        Args:
            prompt: The input prompt
            provider: The provider name
            model: The model name

        Returns:
            Tuple of (response_text, metadata) or (None, {}) if not found
        """
        if not self.redis_mgr.is_connected:
            logger.debug("Redis not connected, skipping cache get")
            return None, {}

        cache_key = self._generate_cache_key(prompt, provider, model)

        try:
            cached_data = self.redis_mgr.client.get(cache_key)
            if cached_data:
                response, metadata = self._deserialize_response(cached_data)
                if response:
                    self.hit_count += 1
                    logger.debug(f"Cache hit for key: {cache_key}")
                    return response, metadata

            # Cache miss
            self.miss_count += 1
            logger.debug(f"Cache miss for key: {cache_key}")
            return None, {}

        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None, {}

    def set(self, prompt: str, provider: str, model: str, response: str,
            metadata: Optional[Dict[str, Any]] = None, ttl: Optional[int] = None) -> bool:
        """
        Cache a response for given parameters.

        Args:
            prompt: The input prompt
            provider: The provider name
            model: The model name
            response: The response text to cache
            metadata: Additional metadata to store
            ttl: Time-to-live in seconds (uses default if None)

        Returns:
            True if successfully cached, False otherwise
        """
        if not self.redis_mgr.is_connected:
            logger.debug("Redis not connected, skipping cache set")
            return False

        if not response or not response.strip():
            logger.debug("Empty response, not caching")
            return False

        cache_key = self._generate_cache_key(prompt, provider, model)
        cache_ttl = ttl if ttl is not None else self.default_ttl

        try:
            cache_data = self._serialize_response(response, metadata or {})
            result = self.redis_mgr.client.setex(cache_key, cache_ttl, cache_data)

            if result:
                logger.debug(f"Cached response for key: {cache_key}, TTL: {cache_ttl}s")
                return True
            else:
                logger.warning(f"Failed to cache response for key: {cache_key}")
                return False

        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            return False

    def delete(self, prompt: str, provider: str, model: str) -> bool:
        """
        Delete cached response for given parameters.

        Args:
            prompt: The input prompt
            provider: The provider name
            model: The model name

        Returns:
            True if successfully deleted, False otherwise
        """
        if not self.redis_mgr.is_connected:
            logger.debug("Redis not connected, skipping cache delete")
            return False

        cache_key = self._generate_cache_key(prompt, provider, model)

        try:
            result = self.redis_mgr.client.delete(cache_key)
            if result:
                logger.debug(f"Deleted cache entry: {cache_key}")
                return True
            else:
                logger.debug(f"Cache entry not found: {cache_key}")
                return False

        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            return False

    def clear_all(self) -> bool:
        """
        Clear all cached responses.

        Returns:
            True if successfully cleared, False otherwise
        """
        if not self.redis_mgr.is_connected:
            logger.debug("Redis not connected, skipping cache clear")
            return False

        try:
            # Use SCAN to find all cache keys with our prefix
            cache_keys = []
            cursor = 0
            while True:
                cursor, keys = self.redis_mgr.client.scan(cursor, match=f"{self.cache_prefix}*")
                cache_keys.extend(keys)
                if cursor == 0:
                    break

            if cache_keys:
                result = self.redis_mgr.client.delete(*cache_keys)
                logger.info(f"Cleared {result} cache entries")
                return bool(result)
            else:
                logger.info("No cache entries to clear")
                return True

        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        stats = {
            "hits": self.hit_count,
            "misses": self.miss_count,
            "hit_rate": 0.0,
            "total_requests": self.hit_count + self.miss_count,
            "redis_connected": self.redis_mgr.is_connected
        }

        if stats["total_requests"] > 0:
            stats["hit_rate"] = self.hit_count / stats["total_requests"]

        # Get additional Redis info if available
        if self.redis_mgr.is_connected:
            try:
                redis_info = self.redis_mgr.get_info()
                if redis_info:
                    stats.update({
                        "redis_used_memory": redis_info.get("used_memory_human", "N/A"),
                        "redis_connected_clients": redis_info.get("connected_clients", 0),
                        "redis_uptime_days": redis_info.get("uptime_in_days", 0)
                    })
            except Exception as e:
                logger.debug(f"Failed to get Redis info for stats: {e}")

        return stats

    def get_cache_info(self, prompt: str, provider: str, model: str) -> Dict[str, Any]:
        """
        Get information about a specific cache entry.

        Args:
            prompt: The input prompt
            provider: The provider name
            model: The model name

        Returns:
            Dictionary with cache entry information
        """
        cache_key = self._generate_cache_key(prompt, provider, model)
        info = {
            "cache_key": cache_key,
            "exists": False,
            "ttl": None,
            "size": 0
        }

        if not self.redis_mgr.is_connected:
            return info

        try:
            exists = self.redis_mgr.client.exists(cache_key)
            if exists:
                info["exists"] = True
                info["ttl"] = self.redis_mgr.client.ttl(cache_key)
                info["size"] = len(self.redis_mgr.client.get(cache_key) or b"")
        except Exception as e:
            logger.debug(f"Failed to get cache info: {e}")

        return info


# Global cache manager instance
cache_manager = CacheManager()


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance."""
    return cache_manager


def cache_response(prompt: str, provider: str, model: str, response: str,
                  metadata: Optional[Dict[str, Any]] = None, ttl: Optional[int] = None) -> bool:
    """
    Cache a response with default settings.

    Args:
        prompt: The input prompt
        provider: The provider name
        model: The model name
        response: The response text
        metadata: Additional metadata
        ttl: Time-to-live in seconds

    Returns:
        True if cached successfully, False otherwise
    """
    return cache_manager.set(prompt, provider, model, response, metadata, ttl)


def get_cached_response(prompt: str, provider: str, model: str) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Get a cached response.

    Args:
        prompt: The input prompt
        provider: The provider name
        model: The model name

    Returns:
        Tuple of (response_text, metadata) or (None, {}) if not cached
    """
    return cache_manager.get(prompt, provider, model)