"""
tests/test_structured_data_layer.py
====================================
Schema-adaptive unit and integration tests for SMAR Structured Data Layer.

Removes all Kirana/domain-specific references. Uses a GenericRecordGenerator
that creates random items with no domain knowledge.
Tests validation rules, ETL idempotency, FTS, and CRUD — all data-agnostic.
"""

import os
import uuid
import random
import string
import tempfile
import unittest
from structured_data.models import InventoryItem, ValidationResult
from structured_data.db import InventoryDatabaseManager
from structured_data.etl import InventoryETLPipeline


# ── Generic record generator — no Kirana, no domain dependency ───────────────

class GenericRecordGenerator:
    """
    Generates random inventory records with generic names.
    Completely domain-agnostic: no product names, brands, or categories assumed.
    """

    CATEGORIES = ["Type-A", "Type-B", "Type-C", "Type-D", "Type-E"]
    BRANDS = ["BrandX", "BrandY", "BrandZ"]
    UNITS = ["pcs", "kg", "litre", "box", "pack"]

    def __init__(self, seed=None):
        if seed is not None:
            random.seed(seed)

    def _random_name(self):
        prefix = random.choice(["Alpha", "Beta", "Gamma", "Delta", "Sigma"])
        suffix = "".join(random.choices(string.ascii_uppercase, k=3))
        return f"{prefix} Item {suffix}"

    def generate_records(self, total_records=100, invalid_ratio=0.0):
        invalid_count = int(total_records * invalid_ratio)
        for i in range(total_records):
            item_id = f"GEN-{str(uuid.uuid4())[:8].upper()}"
            barcode = str(random.randint(1000000000000, 9999999999999))
            name = self._random_name()
            is_invalid = (i < invalid_count)
            yield {
                "item_id": item_id,
                "barcode": barcode,
                "canonical_name": name,
                "normalized_name": name.lower(),
                "category": random.choice(self.CATEGORIES),
                "brand": random.choice(self.BRANDS),
                "unit_of_measure": random.choice(self.UNITS),
                "quantity": -1.0 if is_invalid else round(random.uniform(1, 500), 2),
                "unit_price": 0.0 if is_invalid else round(random.uniform(5, 5000), 2),
                "cost_price": round(random.uniform(1, 100), 2),
            }


class TestStructuredDataLayer(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_inventory.db")
        self.db = InventoryDatabaseManager(db_path=self.db_path)
        self.pipeline = InventoryETLPipeline(db_manager=self.db)
        self.gen = GenericRecordGenerator(seed=42)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_valid_item_model(self):
        """Create a valid InventoryItem with generic data."""
        item = InventoryItem(
            item_id="GEN-TEST-001",
            barcode="1000000000001",
            canonical_name="Generic Widget Alpha",
            normalized_name="generic widget alpha",
            category="Type-A",
            brand="BrandX",
            unit_of_measure="pcs",
            quantity=100.0,
            unit_price=50.0,
            cost_price=30.0,
        )
        self.assertEqual(item.item_id, "GEN-TEST-001")
        self.assertEqual(item.quantity, 100.0)
        self.assertEqual(item.unit_price, 50.0)

    def test_negative_quantity_rejected(self):
        """Validation must reject negative stock quantity."""
        raw = {
            "item_id": "GEN-TEST-002",
            "canonical_name": "Invalid Item",
            "category": "Type-A",
            "quantity": -10.0,
            "unit_price": 50.0,
            "cost_price": 40.0,
        }
        transformed = self.pipeline.transform_record(raw)
        val_res = self.pipeline.validate_record(transformed)
        self.assertFalse(val_res.is_valid)
        self.assertTrue(any("quantity" in e.lower() for e in val_res.errors))

    def test_zero_price_rejected(self):
        """Validation must reject zero or negative unit price."""
        raw = {
            "item_id": "GEN-TEST-003",
            "canonical_name": "Free Item",
            "category": "Type-A",
            "quantity": 10.0,
            "unit_price": 0.0,
            "cost_price": 40.0,
        }
        transformed = self.pipeline.transform_record(raw)
        val_res = self.pipeline.validate_record(transformed)
        self.assertFalse(val_res.is_valid)
        self.assertTrue(any("unit_price" in e for e in val_res.errors))

    def test_missing_required_fields_rejected(self):
        """Validation must reject blank item_id or empty canonical_name."""
        raw = {
            "item_id": "  ",
            "canonical_name": "",
            "category": "Type-A",
            "quantity": 10.0,
            "unit_price": 50.0,
            "cost_price": 40.0,
        }
        transformed = self.pipeline.transform_record(raw)
        val_res = self.pipeline.validate_record(transformed)
        self.assertFalse(val_res.is_valid)

    def test_bulk_etl_ingestion(self):
        """Bulk ingestion of generic records with a small invalid ratio."""
        records = list(self.gen.generate_records(total_records=200, invalid_ratio=0.02))
        result = self.pipeline.run_pipeline(records, chunk_size=50)
        self.assertEqual(result.total_rows, 200)
        # Valid records should be majority
        self.assertGreater(result.valid_rows, 180)
        self.assertGreater(result.inserted_rows, 180)
        self.assertGreater(result.invalid_rows, 0)
        self.assertEqual(self.db.get_total_count(), result.inserted_rows)

    def test_exact_lookup_and_barcode_lookup(self):
        """Primary key and barcode index lookups return the correct item."""
        records = list(self.gen.generate_records(total_records=10, invalid_ratio=0.0))
        self.pipeline.run_pipeline(records)

        target = records[0]
        item_by_id = self.db.get_item_by_id(target["item_id"])
        self.assertIsNotNone(item_by_id)
        self.assertEqual(item_by_id["item_id"], target["item_id"])

        item_by_barcode = self.db.get_item_by_barcode(target["barcode"])
        self.assertIsNotNone(item_by_barcode)
        self.assertEqual(item_by_barcode["barcode"], target["barcode"])

    def test_etl_rerun_idempotency_and_upsert(self):
        """Rerunning ETL on the same records updates without inserting duplicates."""
        records = list(self.gen.generate_records(total_records=50, invalid_ratio=0.0))

        res1 = self.pipeline.run_pipeline(records, duplicate_mode="UPSERT")
        self.assertEqual(self.db.get_total_count(), 50)

        # Modify first record's price
        updated = [dict(r) for r in records]
        updated[0]["unit_price"] = 9999.00

        res2 = self.pipeline.run_pipeline(updated, duplicate_mode="UPSERT")
        self.assertEqual(self.db.get_total_count(), 50)  # no duplicates

        # Verify price was updated
        item = self.db.get_item_by_id(records[0]["item_id"])
        self.assertEqual(item["unit_price"], 9999.00)

    def test_fts5_full_text_search(self):
        """FTS5 search finds seeded items by their dynamically generated name tokens."""
        # Generate records and find a name token we can search for
        records = list(self.gen.generate_records(total_records=100, invalid_ratio=0.0))
        self.pipeline.run_pipeline(records)

        # Use first word of first record name as search term (e.g., "Alpha", "Beta")
        first_name = records[0]["canonical_name"]
        search_token = first_name.split()[0]  # e.g. "Alpha"

        matches = self.db.search_full_text(search_token)
        self.assertGreater(len(matches), 0)
        # At least one result should contain the search token
        self.assertTrue(
            any(search_token.lower() in m.get("canonical_name", "").lower() for m in matches)
        )


if __name__ == "__main__":
    unittest.main()
