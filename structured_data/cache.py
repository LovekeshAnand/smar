"""
structured_data/cache.py
========================
Hot Data Cache Layer for SMAR v2.
Provides a high-performance Cache-Aside strategy with thread-safe LRU eviction,
data-classification based TTL policies (Static vs. Volatile inventory fields),
selective invalidation, and graceful fallback handling on cache unavailable scenarios.
"""

import time
import threading
import logging
from typing import Any, Optional, Dict, List
from collections import OrderedDict

logger = logging.getLogger("smar.structured_data.cache")


class CacheEntry:
    """Container for a cached item with absolute expiration timestamp."""
    def __init__(self, value: Any, ttl_seconds: float):
        self.value = value
        self.expires_at = time.time() + ttl_seconds

    def is_expired(self) -> bool:
        return time.time() >= self.expires_at


class HotDataCacheManager:
    """
    High-performance Hot Data Cache Engine.
    Implements Cache-Aside pattern, static vs. volatile field TTL policies,
    LRU capacity eviction, thread safety, and transparent error resilience.
    """

    # Data Classification TTL Policies (in seconds)
    TTL_STATIC_ITEM = 3600.0    # 1 Hour for static product identity (name, brand, category, UOM)
    TTL_VOLATILE_ITEM = 15.0    # 15 Seconds for volatile stock & pricing
    TTL_BARCODE_LOOKUP = 3600.0 # 1 Hour for EAN barcode -> item_id mapping
    TTL_CATEGORY_SUMMARY = 60.0 # 60 Seconds for category aggregated stats
    TTL_LOW_STOCK_LIST = 30.0   # 30 Seconds for reorder alert list

    def __init__(self, max_capacity: int = 10000, enabled: bool = True):
        self.max_capacity = max_capacity
        self.enabled = enabled
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        
        # Performance Tracking Counters
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _generate_key(self, prefix: str, identifier: str) -> str:
        """Standardized cache key builder format (smar:namespace:id)."""
        clean_id = str(identifier).strip().lower()
        return f"smar:{prefix}:{clean_id}"

    def get_key_static_item(self, item_id: str) -> str:
        return self._generate_key("item:static", item_id)

    def get_key_full_item(self, item_id: str) -> str:
        return self._generate_key("item:full", item_id)

    def get_key_barcode(self, barcode: str) -> str:
        return self._generate_key("barcode", barcode)

    def get_key_category_summary(self, category: str) -> str:
        return self._generate_key("category:summary", category)

    def get_key_low_stock(self) -> str:
        return "smar:low_stock:list"

    def get(self, key: str) -> Optional[Any]:
        """
        Cache Lookup (Hit vs Miss check).
        Returns value if valid Cache HIT, or None on Cache MISS / Expired.
        """
        if not self.enabled:
            return None

        try:
            with self._lock:
                if key not in self._cache:
                    self.misses += 1
                    return None

                entry = self._cache[key]
                if entry.is_expired():
                    # TTL Expired
                    del self._cache[key]
                    self.misses += 1
                    return None

                # Move to end for LRU policy
                self._cache.move_to_end(key)
                self.hits += 1
                return entry.value
        except Exception as e:
            logger.warning(f"Cache lookup failed gracefully for key '{key}': {e}")
            self.misses += 1
            return None

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        """Populate cache with value, TTL expiration, and LRU eviction."""
        if not self.enabled or value is None:
            return

        try:
            with self._lock:
                # Evict LRU items if capacity reached
                while len(self._cache) >= self.max_capacity:
                    oldest_key, _ = self._cache.popitem(last=False)
                    self.evictions += 1

                self._cache[key] = CacheEntry(value, ttl_seconds)
                self._cache.move_to_end(key)
        except Exception as e:
            logger.warning(f"Cache set failed gracefully for key '{key}': {e}")

    def invalidate(self, key: str) -> None:
        """Invalidate a specific key from cache."""
        if not self.enabled:
            return

        try:
            with self._lock:
                if key in self._cache:
                    del self._cache[key]
        except Exception as e:
            logger.warning(f"Cache invalidation failed gracefully for key '{key}': {e}")

    def invalidate_item(self, item_id: str, barcode: Optional[str] = None, category: Optional[str] = None) -> None:
        """Invalidate all cache entries associated with an inventory item."""
        self.invalidate(self.get_key_static_item(item_id))
        self.invalidate(self.get_key_full_item(item_id))
        if barcode:
            self.invalidate(self.get_key_barcode(barcode))
        if category:
            self.invalidate(self.get_key_category_summary(category))
        self.invalidate(self.get_key_low_stock())

    def clear(self) -> None:
        """Flush all cache entries."""
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0

    def get_stats(self) -> Dict[str, Any]:
        """Return cache health and hit/miss statistics."""
        with self._lock:
            total_reqs = self.hits + self.misses
            hit_ratio = (self.hits / total_reqs) * 100.0 if total_reqs > 0 else 0.0
            return {
                "enabled": self.enabled,
                "current_size": len(self._cache),
                "max_capacity": self.max_capacity,
                "hits": self.hits,
                "misses": self.misses,
                "hit_ratio_pct": round(hit_ratio, 2),
                "evictions": self.evictions
            }
