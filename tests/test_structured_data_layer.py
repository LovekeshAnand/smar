"""
tests/test_structured_data_layer.py
====================================
Comprehensive unit and integration test suite for SMAR v2 Structured Data Layer.
Tests validation rules, malformed rows, duplicate handling, ETL pipeline rerun idempotency,
database transactions, indexing strategies, and FTS search.
"""

import os
import tempfile
import unittest
from structured_data.models import InventoryItem, ValidationResult
from structured_data.db import InventoryDatabaseManager
from structured_data.generator import KiranaInventoryDataGenerator
from structured_data.etl import InventoryETLPipeline


class TestStructuredDataLayer(unittest.TestCase):

    def setUp(self):
        """Create a temporary database for isolated test runs."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_inventory.db")
        self.db = InventoryDatabaseManager(db_path=self.db_path)
        self.pipeline = InventoryETLPipeline(db_manager=self.db)

    def tearDown(self):
        """Cleanup temporary files."""
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_valid_item_model(self):
        """Test creating a valid InventoryItem instance."""
        item = InventoryItem(
            item_id="INV-000001",
            barcode="8901030000001",
            canonical_name="Tata Salt 1kg",
            normalized_name="tata salt 1kg",
            category="Spices & Cooking Essentials",
            brand="Tata",
            unit_of_measure="kg",
            quantity=150.0,
            unit_price=28.0,
            cost_price=20.0
        )
        self.assertEqual(item.item_id, "INV-000001")
        self.assertEqual(item.quantity, 150.0)
        self.assertEqual(item.unit_price, 28.0)
        self.assertEqual(item.cost_price, 20.0)

    def test_negative_quantity_prohibition(self):
        """Validation must reject negative stock quantity."""
        raw = {
            "item_id": "INV-000002",
            "canonical_name": "Invalid Item",
            "category": "Test",
            "quantity": -10.0,
            "unit_price": 50.0,
            "cost_price": 40.0
        }
        transformed = self.pipeline.transform_record(raw)
        val_res = self.pipeline.validate_record(transformed)
        self.assertFalse(val_res.is_valid)
        self.assertTrue(any("Stock quantity cannot be negative" in err or "quantity" in err for err in val_res.errors))

    def test_invalid_price_prohibition(self):
        """Validation must reject zero or negative selling prices."""
        raw = {
            "item_id": "INV-000003",
            "canonical_name": "Free Item",
            "category": "Test",
            "quantity": 10.0,
            "unit_price": 0.0,
            "cost_price": 40.0
        }
        transformed = self.pipeline.transform_record(raw)
        val_res = self.pipeline.validate_record(transformed)
        self.assertFalse(val_res.is_valid)
        self.assertTrue(any("unit_price" in err for err in val_res.errors))

    def test_missing_required_fields(self):
        """Validation must reject missing item_id or empty canonical_name."""
        raw = {
            "item_id": "  ",
            "canonical_name": "",
            "category": "Test",
            "quantity": 10.0,
            "unit_price": 50.0,
            "cost_price": 40.0
        }
        transformed = self.pipeline.transform_record(raw)
        val_res = self.pipeline.validate_record(transformed)
        self.assertFalse(val_res.is_valid)

    def test_bulk_etl_ingestion(self):
        """Verify bulk ingestion of synthetic dataset."""
        gen = KiranaInventoryDataGenerator(seed=123)
        records = list(gen.generate_records(total_records=500, invalid_ratio=0.02))
        
        result = self.pipeline.run_pipeline(records, chunk_size=100)
        self.assertEqual(result.total_rows, 500)
        self.assertGreater(result.valid_rows, 480)
        self.assertGreater(result.inserted_rows, 480)
        self.assertGreater(result.invalid_rows, 0)
        self.assertEqual(self.db.get_total_count(), result.inserted_rows)

    def test_exact_lookup_and_barcode_lookup(self):
        """Verify exact Primary Key lookup and Barcode index search."""
        gen = KiranaInventoryDataGenerator(seed=456)
        records = list(gen.generate_records(total_records=10, invalid_ratio=0.0))
        self.pipeline.run_pipeline(records)

        target = records[0]
        item_by_id = self.db.get_item_by_id(target["item_id"])
        self.assertIsNotNone(item_by_id)
        self.assertEqual(item_by_id["item_id"], target["item_id"])

        item_by_barcode = self.db.get_item_by_barcode(target["barcode"])
        self.assertIsNotNone(item_by_barcode)
        self.assertEqual(item_by_barcode["barcode"], target["barcode"])

    def test_etl_rerun_idempotency_and_upsert(self):
        """Rerunning ETL on the same records should update existing records without errors."""
        gen = KiranaInventoryDataGenerator(seed=789)
        initial_records = list(gen.generate_records(total_records=50, invalid_ratio=0.0))
        
        # First Run
        res1 = self.pipeline.run_pipeline(initial_records, duplicate_mode="UPSERT")
        count1 = self.db.get_total_count()
        self.assertEqual(count1, 50)

        # Modify price on first item
        updated_records = [dict(r) for r in initial_records]
        updated_records[0]["unit_price"] = 999.00

        # Second Run (Rerun ETL)
        res2 = self.pipeline.run_pipeline(updated_records, duplicate_mode="UPSERT")
        count2 = self.db.get_total_count()
        
        # Total count must remain 50 (no duplicate inserts)
        self.assertEqual(count2, 50)
        
        # Verify price was updated
        updated_item = self.db.get_item_by_id(initial_records[0]["item_id"])
        self.assertEqual(updated_item["unit_price"], 999.00)

    def test_fts5_full_text_search(self):
        """Verify SQLite FTS5 search index functionality."""
        gen = KiranaInventoryDataGenerator(seed=999)
        records = list(gen.generate_records(total_records=200, invalid_ratio=0.0))
        self.pipeline.run_pipeline(records)

        # Search for "atta" or "salt"
        matches = self.db.search_full_text("atta")
        self.assertTrue(len(matches) > 0)
        self.assertTrue("atta" in matches[0]["canonical_name"].lower() or "atta" in matches[0]["category"].lower())


if __name__ == "__main__":
    unittest.main()
