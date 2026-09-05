"""
SMAR v2 Tiered Hot Cache Layer
==============================
High-concurrency cache layer supporting Redis (Docker container `smar-redis-cache`)
with seamless, thread-safe In-Memory LRU fallback.

Ensures zero latency hit and non-blocking operation for the Voice AI loop.
"""

import json
import logging
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

logger = logging.getLogger("smar.cache")


class InMemoryLRUCache:
    """Thread-safe in-memory LRU cache with TTL expiration."""

    def __init__(self, maxsize: int = 10000, default_ttl: int = 300):
        self.maxsize = maxsize
        self.default_ttl = default_ttl
        self._cache: OrderedDict = OrderedDict()
        self._ttls: Dict[str, float] = {}
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                self.misses += 1
                return None

            # Check expiration
            expires_at = self._ttls.get(key)
            if expires_at and time.time() > expires_at:
                del self._cache[key]
                self._ttls.pop(key, None)
                self.misses += 1
                return None

            # Move to end (MRU)
            self._cache.move_to_end(key)
            self.hits += 1
            return self._cache[key]

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        with self._lock:
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
            expires_at = time.time() + ttl if ttl > 0 else None

            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value

            if expires_at:
                self._ttls[key] = expires_at
            else:
                self._ttls.pop(key, None)

            # Evict LRU if capacity exceeded
            while len(self._cache) > self.maxsize:
                evicted_key, _ = self._cache.popitem(last=False)
                self._ttls.pop(evicted_key, None)
            return True

    def delete(self, key: str) -> bool:
        with self._lock:
            existed = key in self._cache
            self._cache.pop(key, None)
            self._ttls.pop(key, None)
            return existed

    def clear(self) -> bool:
        with self._lock:
            self._cache.clear()
            self._ttls.clear()
            return True

    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            rate = (self.hits / total * 100.0) if total > 0 else 0.0
            return {
                "engine": "in_memory_lru",
                "total_keys": len(self._cache),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate_pct": round(rate, 2),
                "maxsize": self.maxsize,
            }


class TieredHotCache:
    """
    Tiered Hot Cache Layer.
    Attempts to connect to Redis on localhost:6379 (Docker container).
    If Redis is unavailable or disconnects, gracefully falls back to InMemoryLRUCache.
    """

    def __init__(
        self,
        redis_host: Optional[str] = None,
        redis_port: Optional[int] = None,
        in_memory_maxsize: int = 25000,
        default_ttl: int = 300,
    ):
        self.redis_host = redis_host or os.getenv("REDIS_HOST", "127.0.0.1")
        self.redis_port = redis_port or int(os.getenv("REDIS_PORT", 6379))
        self.default_ttl = default_ttl
        self.in_memory = InMemoryLRUCache(maxsize=in_memory_maxsize, default_ttl=default_ttl)
        self.redis_client = None
        self._use_redis = False
        self._last_redis_check = time.time()
        self._redis_retry_interval = 30.0  # Retry Redis every 30s if down
        self.hits = 0
        self.misses = 0

        self._init_redis()

    def _init_redis(self):
        try:
            import redis

            client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                socket_timeout=0.5,
                socket_connect_timeout=0.3,
                decode_responses=True,
            )
            client.ping()
            self.redis_client = client
            self._use_redis = True
            logger.info(f"Connected to Redis cache container at {self.redis_host}:{self.redis_port}")
        except Exception as e:
            self._use_redis = False
            self.redis_client = None
            logger.info(f"Redis not reachable ({e}). Operating in resilient In-Memory LRU Cache mode.")

    def _check_redis_health(self):
        """Periodically probe if Redis came online."""
        if self._use_redis:
            return
        now = time.time()
        if now - self._last_redis_check > self._redis_retry_interval:
            self._last_redis_check = now
            self._init_redis()

    @property
    def is_redis_active(self) -> bool:
        return self._use_redis and self.redis_client is not None

    def get(self, key: str) -> Optional[Any]:
        self._check_redis_health()
        if self.is_redis_active:
            try:
                val = self.redis_client.get(key)
                if val is not None:
                    self.hits += 1
                    try:
                        return json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        return val
                else:
                    self.misses += 1
                    return None
            except Exception as e:
                logger.warning(f"Redis read error ({e}), falling back to in-memory cache.")
                self._use_redis = False

        # Fallback to In-Memory
        val = self.in_memory.get(key)
        if val is not None:
            self.hits += 1
        else:
            self.misses += 1
        return val

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        self._check_redis_health()

        serialized = None
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            try:
                serialized = json.dumps(value)
            except Exception:
                serialized = str(value)
        else:
            serialized = value

        if self.is_redis_active:
            try:
                if ttl > 0:
                    self.redis_client.setex(key, ttl, serialized)
                else:
                    self.redis_client.set(key, serialized)
                return True
            except Exception as e:
                logger.warning(f"Redis write error ({e}), falling back to in-memory cache.")
                self._use_redis = False

        return self.in_memory.set(key, value, ttl_seconds=ttl)

    def delete(self, key: str) -> bool:
        if self.is_redis_active:
            try:
                self.redis_client.delete(key)
            except Exception:
                pass
        return self.in_memory.delete(key)

    def clear(self) -> bool:
        if self.is_redis_active:
            try:
                self.redis_client.flushdb()
            except Exception:
                pass
        return self.in_memory.clear()

    # Specialized cache methods for high performance
    def get_entity(self, term: str) -> Optional[Dict[str, Any]]:
        return self.get(f"entity:{term.lower().strip()}")

    def set_entity(self, term: str, record: Dict[str, Any], ttl: int = 3600) -> bool:
        return self.set(f"entity:{term.lower().strip()}", record, ttl_seconds=ttl)

    def get_query(self, query_hash: str) -> Optional[List[Dict[str, Any]]]:
        return self.get(f"query:{query_hash}")

    def set_query(self, query_hash: str, results: List[Dict[str, Any]], ttl: int = 300) -> bool:
        return self.set(f"query:{query_hash}", results, ttl_seconds=ttl)

    def get_schema(self, source: str) -> Optional[Dict[str, Any]]:
        return self.get(f"schema:{source}")

    def set_schema(self, source: str, schema_dict: Dict[str, Any], ttl: int = 1800) -> bool:
        return self.set(f"schema:{source}", schema_dict, ttl_seconds=ttl)

    def get_agg(self, metric_key: str) -> Optional[Any]:
        return self.get(f"agg:{metric_key}")

    def set_agg(self, metric_key: str, value: Any, ttl: int = 600) -> bool:
        return self.set(f"agg:{metric_key}", value, ttl_seconds=ttl)

    def stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        rate = (self.hits / total * 100.0) if total > 0 else 0.0
        active_engine = "redis" if self.is_redis_active else "in_memory_lru"

        redis_info = {}
        if self.is_redis_active:
            try:
                info = self.redis_client.info("memory")
                redis_info = {
                    "used_memory_human": info.get("used_memory_human", "N/A"),
                    "connected_clients": self.redis_client.info("clients").get("connected_clients", 1),
                }
            except Exception:
                pass

        return {
            "active_engine": active_engine,
            "is_redis": self.is_redis_active,
            "total_requests": total,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_pct": round(rate, 2),
            "in_memory_keys": self.in_memory.size(),
            "redis_details": redis_info,
        }


# Global singleton instance for easy import across modules
hot_cache = TieredHotCache()
