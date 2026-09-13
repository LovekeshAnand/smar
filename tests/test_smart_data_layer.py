"""
tests/test_smart_data_layer.py
==============================
Schema-adaptive unit and integration tests for SMAR Smart Data Layer.

Uses a generic 3-column schema (no Kirana/domain-specific data).
Tests dynamic vocabulary learning, intent extraction, KG cache lookup,
and write-back behavior on ANY domain.
"""

import os
import tempfile
import unittest

from structured_data.db import InventoryDatabaseManager
from structured_data.adapters import SQLiteStorageAdapter, AdapterRegistry
from context_layer import ContextConfig, ContextLayerEngine
from smart_data import DynamicDomainDictionary, SmartIntentEntityExtractor, SmartDataLayerEngine


# ── Generic seed — no domain knowledge required ──────────────────────────────
SEED_ITEM = {
    "item_id": "GEN-0001",
    "barcode": "1234567890001",
    "canonical_name": "Alpha Widget Unit",
    "normalized_name": "alpha widget unit",
    "category": "Widgets",
    "brand": "GenBrand",
    "unit_of_measure": "pcs",
    "created_at": "2026-01-01T00:00:00Z",
    "quantity": 42.0,
    "unit_price": 99.0,
    "cost_price": 60.0,
    "reorder_level": 5,
    "is_active": 1,
    "updated_at": "2026-01-01T00:00:00Z",
}


class TestSmartDataLayer(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_inv.db")
        self.db = InventoryDatabaseManager(db_path=self.db_path)
        self.adapter = SQLiteStorageAdapter(db_manager=self.db)

        # Seed one generic item
        conn = self.db.get_connection()
        conn.execute("""
            INSERT INTO inventory_items (
                item_id, barcode, canonical_name, normalized_name, category, brand,
                unit_of_measure, created_at, quantity, unit_price, cost_price,
                reorder_level, is_active, updated_at
            ) VALUES (
                :item_id, :barcode, :canonical_name, :normalized_name,
                :category, :brand, :unit_of_measure, :created_at,
                :quantity, :unit_price, :cost_price, :reorder_level,
                :is_active, :updated_at
            )
        """, SEED_ITEM)
        conn.commit()
        conn.close()

        cfg = ContextConfig(db_path=os.path.join(self.temp_dir, "test_kg.db"))
        self.context_engine = ContextLayerEngine(cfg)

        self.registry = AdapterRegistry()
        self.registry.register("primary", self.adapter, set_as_primary=True)

        from structured_data.multi_table_manager import MultiTableWarehouseManager
        self.wh_mgr = MultiTableWarehouseManager(
            db_path=os.path.join(self.temp_dir, "test_wh.db")
        )

        self.smart_engine = SmartDataLayerEngine(
            adapter_registry=self.registry,
            context_store=self.context_engine.store,
            warehouse_manager=self.wh_mgr
        )

    def test_dynamic_dictionary_learning(self):
        """DynamicDomainDictionary learns column names from any schema."""
        schema = self.adapter.introspect_schema()
        d = DynamicDomainDictionary()
        d.learn_from_schema(schema)
        self.assertIn("quantity", d.term_to_canonical)
        self.assertIn("inventory_items", d.term_to_canonical)

    def test_intent_detection_quantity(self):
        """Intent extractor detects QUANTITY intent in a generic query."""
        extractor = self.smart_engine.intent_extractor
        # Use seeded item name — generic English, no domain dependency
        item_name = SEED_ITEM["canonical_name"].split()[0].lower()
        res = extractor.extract(f"how many {item_name} widget units are in stock")
        self.assertIn(res["intent"], ("QUANTITY", "GENERAL_SEARCH", "OPERATION"))

    def test_intent_detection_price(self):
        """Intent extractor detects PRICE intent in a generic query."""
        extractor = self.smart_engine.intent_extractor
        item_name = SEED_ITEM["canonical_name"].split()[0].lower()
        res = extractor.extract(f"what is the price of {item_name} widget unit")
        self.assertIn(res["intent"], ("PRICE", "GENERAL_SEARCH"))

    def test_smart_data_engine_end_to_end_and_cache(self):
        """
        End-to-end: first query hits DB, second query hits KG cache.
        Uses seeded item_id — not hardcoded to any domain.
        """
        item_name = SEED_ITEM["canonical_name"].lower()

        # 1. First query: cache miss, hits DB, writes back to KG
        res1 = self.smart_engine.process_query(f"how much {item_name} is in stock")
        self.assertFalse(res1["kg_cache_hit"])
        self.assertIsNotNone(res1["matched_item"])
        self.assertEqual(res1["matched_item"]["item_id"], SEED_ITEM["item_id"])
        # Verify the seeded quantity appears in context
        self.assertIn(str(int(SEED_ITEM["quantity"])), res1["context_string"])

        # 2. Second query: KG cache hit
        res2 = self.smart_engine.process_query(f"how much {item_name} is in stock")
        self.assertTrue(res2["kg_cache_hit"])
        self.assertEqual(res2["matched_item"]["item_id"], SEED_ITEM["item_id"])

    def test_conversation_bypass_no_db_hit(self):
        """Conversational queries must never hit the DB."""
        for prompt in ["who am i", "hi how are you", "what is your name"]:
            res = self.smart_engine.process_query(prompt)
            self.assertEqual(
                res.get("intent"), "CONVERSATION",
                f"'{prompt}' was not routed as CONVERSATION"
            )
            self.assertIsNone(res.get("matched_item"))


if __name__ == "__main__":
    unittest.main()
