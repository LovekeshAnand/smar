"""
tests/test_smart_data_layer.py
==============================
Unit and integration tests for SMAR v2 Smart Data Layer.
Tests dynamic vocabulary learning, intent extraction, KG cache lookup,
adapter queries, and write-back behavior.
"""

import os
import tempfile
import unittest

from structured_data.db import InventoryDatabaseManager
from structured_data.adapters import SQLiteStorageAdapter, AdapterRegistry
from context_layer import ContextConfig, ContextLayerEngine
from smart_data import DynamicDomainDictionary, SmartIntentEntityExtractor, SmartDataLayerEngine


class TestSmartDataLayer(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_inv.db")
        self.db = InventoryDatabaseManager(db_path=self.db_path)
        self.adapter = SQLiteStorageAdapter(db_manager=self.db)

        # Seed sample item
        conn = self.db.get_connection()
        conn.execute("""
            INSERT INTO inventory_items (
                item_id, barcode, canonical_name, normalized_name, category, brand,
                unit_of_measure, created_at, quantity, unit_price, cost_price,
                reorder_level, is_active, updated_at
            ) VALUES (
                'SKU-9901', '8901030099012', 'Tata Salt Vacuum Evaporated 1kg', 'tata salt vacuum evaporated 1kg',
                'Spices', 'Tata', 'kg', '2026-09-01T00:00:00Z',
                85.0, 28.0, 20.0, 10, 1, '2026-09-01T00:00:00Z'
            );
        """)
        conn.commit()
        conn.close()

        # Context store (KG)
        cfg = ContextConfig(db_path=os.path.join(self.temp_dir, "test_kg.db"))
        self.context_engine = ContextLayerEngine(cfg)

        # Registry
        self.registry = AdapterRegistry()
        self.registry.register("primary", self.adapter, set_as_primary=True)

        from structured_data.multi_table_manager import MultiTableWarehouseManager
        self.wh_mgr = MultiTableWarehouseManager(db_path=os.path.join(self.temp_dir, "test_wh.db"))

        # Smart Data Layer
        self.smart_engine = SmartDataLayerEngine(
            adapter_registry=self.registry,
            context_store=self.context_engine.store,
            warehouse_manager=self.wh_mgr
        )

    def test_dynamic_dictionary_learning(self):
        schema = self.adapter.introspect_schema()
        dict_store = DynamicDomainDictionary()
        dict_store.learn_from_schema(schema)

        # Verify it learned columns and sample values
        self.assertIn("quantity", dict_store.term_to_canonical)
        self.assertIn("inventory_items", dict_store.term_to_canonical)

    def test_intent_detection(self):
        extractor = self.smart_engine.intent_extractor
        res1 = extractor.extract("Tata salt kitna packet bacha hai?")
        self.assertEqual(res1["intent"], "QUANTITY")

        res2 = extractor.extract("Tata salt ka kya bhav hai?")
        self.assertEqual(res2["intent"], "PRICE")

    def test_smart_data_engine_end_to_end_and_cache(self):
        # 1. First query: Cache miss, hits DB, writes back to KG cache
        res1 = self.smart_engine.process_query("Tata salt kitna packet bacha hai?")
        self.assertFalse(res1["kg_cache_hit"])
        self.assertIsNotNone(res1["matched_item"])
        self.assertEqual(res1["matched_item"]["item_id"], "SKU-9901")
        self.assertIn("Stock: 85.0 kg", res1["context_string"])

        # 2. Second query: Cache hit from KG!
        res2 = self.smart_engine.process_query("Tata salt kitna packet bacha hai?")
        self.assertTrue(res2["kg_cache_hit"])
        self.assertEqual(res2["matched_item"]["item_id"], "SKU-9901")
        self.assertIn("Stock: 85.0 kg", res2["context_string"])


if __name__ == "__main__":
    unittest.main()
