"""
tests/test_storage_adapters.py
==============================
Unit tests for SMAR v2 Storage Adapters (SQLite, CSV, Excel) and AdapterRegistry.
"""

import os
import csv
import tempfile
import unittest
from structured_data.adapters import SQLiteStorageAdapter, FileStorageAdapter, AdapterRegistry
from structured_data.db import InventoryDatabaseManager


class TestStorageAdapters(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_db.db")
        self.db = InventoryDatabaseManager(db_path=self.db_path)
        self.sqlite_adapter = SQLiteStorageAdapter(db_manager=self.db)

        # Seed sample item into SQLite
        conn = self.db.get_connection()
        conn.execute("""
            INSERT INTO inventory_items (
                item_id, barcode, canonical_name, normalized_name, category, brand,
                unit_of_measure, created_at, quantity, unit_price, cost_price,
                reorder_level, is_active, updated_at
            ) VALUES (
                'INV-001', '8901030000001', 'Tata Salt 1kg Pack', 'tata salt 1kg pack',
                'Spices & Cooking Essentials', 'Tata', 'kg', '2026-09-01T00:00:00Z',
                120.0, 28.0, 20.0, 10, 1, '2026-09-01T00:00:00Z'
            );
        """)
        conn.commit()
        conn.close()

        # Create a sample CSV file
        self.csv_path = os.path.join(self.temp_dir, "sample.csv")
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["item_id", "product_name", "category", "brand", "quantity", "unit_price"])
            writer.writerow(["CSV-001", "Aashirvaad Atta 5kg", "Atta & Grains", "Aashirvaad", "50", "245.0"])
            writer.writerow(["CSV-002", "Fortune Sunflower Oil 1L", "Oils & Ghee", "Fortune", "80", "145.0"])

    def tearDown(self):
        self.sqlite_adapter.close()

    def test_sqlite_adapter_introspection(self):
        schema = self.sqlite_adapter.introspect_schema()
        self.assertEqual(schema["source_type"], "sqlite")
        self.assertTrue(any(t["table_name"] == "inventory_items" for t in schema["tables"]))
        inv_table = next(t for t in schema["tables"] if t["table_name"] == "inventory_items")
        col_names = [c["name"] for c in inv_table["columns"]]
        self.assertIn("item_id", col_names)
        self.assertIn("quantity", col_names)
        # Check volatility flag
        qty_col = next(c for c in inv_table["columns"] if c["name"] == "quantity")
        self.assertTrue(qty_col["is_volatile"])

    def test_sqlite_adapter_queries(self):
        # 1. Exact PK
        item = self.sqlite_adapter.get_item_by_id("INV-001")
        self.assertIsNotNone(item)
        self.assertEqual(item["canonical_name"], "Tata Salt 1kg Pack")

        # 2. Text Search
        search_res = self.sqlite_adapter.search_by_text("salt")
        self.assertEqual(len(search_res), 1)
        self.assertEqual(search_res[0]["item_id"], "INV-001")

    def test_csv_file_adapter(self):
        file_adapter = FileStorageAdapter(file_path=self.csv_path)
        self.assertEqual(file_adapter.get_source_type(), "csv")
        self.assertEqual(file_adapter.get_total_count(), 2)

        # Introspection
        schema = file_adapter.introspect_schema()
        self.assertEqual(len(schema["tables"]), 1)
        col_names = [c["name"] for c in schema["tables"][0]["columns"]]
        self.assertIn("item_id", col_names)
        self.assertIn("product_name", col_names)

        # Query
        item = file_adapter.get_item_by_id("CSV-001")
        self.assertIsNotNone(item)
        self.assertEqual(item["brand"], "Aashirvaad")

        # Search
        search_res = file_adapter.search_by_text("Fortune")
        self.assertEqual(len(search_res), 1)
        self.assertEqual(search_res[0]["item_id"], "CSV-002")

        file_adapter.close()

    def test_adapter_registry(self):
        registry = AdapterRegistry()
        registry.register("sqlite", self.sqlite_adapter, set_as_primary=True)
        csv_adapter = registry.load_file_adapter(self.csv_path, key="csv_source", set_as_primary=False)

        self.assertEqual(registry.get_primary().get_source_type(), "sqlite")
        self.assertEqual(len(registry.list_adapters()), 2)

        # Switch primary
        registry.set_primary("csv_source")
        self.assertEqual(registry.get_primary().get_source_type(), "csv")
        self.assertEqual(registry.get_primary().get_total_count(), 2)
        csv_adapter.close()


if __name__ == "__main__":
    unittest.main()
