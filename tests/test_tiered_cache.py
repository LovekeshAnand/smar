import unittest
import time
from structured_data.cache import TieredHotCache, InMemoryLRUCache

class TestTieredHotCache(unittest.TestCase):
    def test_in_memory_lru_basic(self):
        cache = InMemoryLRUCache(maxsize=3, default_ttl=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        self.assertEqual(cache.get("a"), 1)
        self.assertEqual(cache.get("b"), 2)
        self.assertEqual(cache.get("c"), 3)

        # Eviction test (a was accessed before b, so b is LRU if we touch a, then c, then insert d)
        cache.get("a")
        cache.set("d", 4)
        # b should be evicted because a was touched, c was inserted after b
        self.assertIsNone(cache.get("b"))
        self.assertEqual(cache.get("d"), 4)

    def test_in_memory_ttl(self):
        cache = InMemoryLRUCache(maxsize=10, default_ttl=1)
        cache.set("temp", "fast_expire", ttl_seconds=1)
        self.assertEqual(cache.get("temp"), "fast_expire")
        time.sleep(1.1)
        self.assertIsNone(cache.get("temp"))

    def test_tiered_cache_methods(self):
        hot = TieredHotCache(in_memory_maxsize=100)
        hot.set_entity("Tata Salt 1kg", {"item_id": 42, "name": "Tata Salt 1kg", "price": 28.0})
        cached = hot.get_entity("tata salt 1kg")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["item_id"], 42)

        hot.set_query("hash123", [{"id": 1, "name": "item1"}])
        res = hot.get_query("hash123")
        self.assertEqual(len(res), 1)

        hot.set_agg("total_sales", 1540200.50)
        self.assertEqual(hot.get_agg("total_sales"), 1540200.50)

        stats = hot.stats()
        self.assertIn("active_engine", stats)
        self.assertGreater(stats["hits"], 0)

if __name__ == "__main__":
    unittest.main()
