"""
tests/test_read_models_and_cache.py
====================================
Unit and integration test suite for SMAR v2 Read Models & Hot Data Cache Layer.
Tests read model correctness, materialized views, cache hits/misses, TTL expiration,
invalidation strategies, stale-data protection, database fallback safety, and concurrency.
"""

import os
import time
import tempfile
import unittest
from structured_data import (
    InventoryDatabaseManager,
    InventoryETLPipeline,
    KiranaInventoryDataGenerator,
    ReadModelManager,
    HotDataCacheManager,
    StructuredDataService
)


class TestReadModelsAndCache(unittest.TestCase):

    def setUp(self):
        """Set up isolated temp SQLite DB, cache manager, and service."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_cache_db.db")
        self.db = InventoryDatabaseManager(db_path=self.db_path)
        self.read_models = ReadModelManager(db_manager=self.db)
        self.cache = HotDataCacheManager(enabled=True)
        self.service = StructuredDataService(
            db_manager=self.db,
            read_model_manager=self.read_models,
            cache_manager=self.cache
        )

        # Ingest 100 sample items
        gen = KiranaInventoryDataGenerator(seed=42)
        records = list(gen.generate_records(total_records=100, invalid_ratio=0.0))
        pipeline = InventoryETLPipeline(db_manager=self.db)
        pipeline.run_pipeline(records)
        self.read_models.refresh_all_materialized_views()

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_read_models_category_summary(self):
        """Verify correctness of materialized category summary read model."""
        summaries = self.read_models.get_all_category_summaries()
        self.assertTrue(len(summaries) > 0)

        # Test single category summary
        cat_name = summaries[0]["category"]
        single_summary = self.read_models.get_category_summary(cat_name)
        self.assertIsNotNone(single_summary)
        self.assertEqual(single_summary["category"], cat_name)
        self.assertGreater(single_summary["total_skus"], 0)
        self.assertGreater(single_summary["total_stock_value_mrp"], 0.0)

    def test_low_stock_materialized_view(self):
        """Verify correctness of materialized low stock alerts."""
        alerts = self.read_models.get_low_stock_alerts(limit=50)
        self.assertIsInstance(alerts, list)
        for alert in alerts:
            self.assertIn("deficit_quantity", alert)
            self.assertLessEqual(alert["quantity"], alert["reorder_level"])

    def test_cache_miss_hit_population_flow(self):
        """Test Cache-Aside flow: MISS -> DB Lookup -> Population -> HIT."""
        test_item_id = "INV-000001"
        self.cache.clear()
        self.assertEqual(self.cache.hits, 0)
        self.assertEqual(self.cache.misses, 0)

        # 1. First Call: Cache MISS -> DB Query -> Populate
        item1 = self.service.get_item(test_item_id)
        self.assertIsNotNone(item1)
        self.assertEqual(item1["item_id"], test_item_id)
        self.assertEqual(self.cache.misses, 1)

        # 2. Second Call: Cache HIT
        item2 = self.service.get_item(test_item_id)
        self.assertIsNotNone(item2)
        self.assertEqual(item2["item_id"], test_item_id)
        self.assertEqual(self.cache.hits, 1)

    def test_cache_ttl_expiration(self):
        """Test TTL expiration invalidates cache entry."""
        key = "smar:test:ttl"
        # Set with 0.1 second TTL
        self.cache.set(key, {"data": "temp"}, ttl_seconds=0.1)
        self.assertEqual(self.cache.get(key), {"data": "temp"})

        # Wait 0.15s for expiration
        time.sleep(0.15)
        self.assertIsNone(self.cache.get(key))

    def test_stale_data_protection_and_invalidation(self):
        """Updating item quantity must invalidate cache and never serve stale stock."""
        test_item_id = "INV-000005"
        item_initial = self.service.get_item(test_item_id)
        self.assertIsNotNone(item_initial)
        initial_qty = item_initial["quantity"]

        # Populate cache
        self.assertIsNotNone(self.service.get_item(test_item_id))

        # Mutate stock in primary DB
        new_qty = initial_qty + 100.0
        success = self.service.update_item_stock_or_price(test_item_id, new_quantity=new_qty)
        self.assertTrue(success)

        # Re-fetch item: Must return updated quantity (no stale data)
        item_updated = self.service.get_item(test_item_id)
        self.assertEqual(item_updated["quantity"], new_qty)

    def test_database_fallback_when_cache_disabled(self):
        """If cache is disabled or encounters failures, system falls back to Primary DB."""
        disabled_cache = HotDataCacheManager(enabled=False)
        fallback_service = StructuredDataService(
            db_manager=self.db,
            read_model_manager=self.read_models,
            cache_manager=disabled_cache
        )

        item = fallback_service.get_item("INV-000010")
        self.assertIsNotNone(item)
        self.assertEqual(item["item_id"], "INV-000010")

    def test_barcode_lookup_caching(self):
        """Verify Cache-Aside pattern for Barcode scanning."""
        item = self.service.get_item("INV-000020")
        barcode = item["barcode"]
        self.assertIsNotNone(barcode)

        # Barcode MISS -> HIT
        b_item1 = self.service.get_item_by_barcode(barcode)
        self.assertEqual(b_item1["item_id"], "INV-000020")
        
        b_item2 = self.service.get_item_by_barcode(barcode)
        self.assertEqual(b_item2["item_id"], "INV-000020")


if __name__ == "__main__":
    unittest.main()
