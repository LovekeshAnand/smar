import os
import unittest
import pandas as pd
from structured_data.multi_table_manager import MultiTableWarehouseManager

class TestMultiTableWarehouse(unittest.TestCase):
    def setUp(self):
        self.test_db = "data/test_warehouse.db"
        self.manager = MultiTableWarehouseManager(db_path=self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass

    def test_dynamic_file_ingestion(self):
        # Create arbitrary test CSV with unknown structure
        csv_path = "data/test_unknown_data.csv"
        df = pd.DataFrame([
            {"asset_tag": f"AST-{i}", "equipment_name": f"Generator Model {i}", "department": "Operations", "cost": 1200.0 * i}
            for i in range(1, 101)
        ])
        df.to_csv(csv_path, index=False)

        # Ingest file
        res = self.manager.ingest_file(csv_path)
        self.assertEqual(res["rows_ingested"], 100)
        self.assertTrue(res["fts_enabled"])

        # Check table listing
        tables = self.manager.list_tables()
        tbl_names = [t["table_name"] for t in tables]
        self.assertIn("test_unknown_data", tbl_names)

        # Full-text search
        hits = self.manager.search_text("Generator Model 42", table_name="test_unknown_data")
        self.assertGreater(len(hits), 0)
        self.assertEqual(hits[0]["asset_tag"], "AST-42")

        # Cleanup CSV
        if os.path.exists(csv_path):
            os.remove(csv_path)

if __name__ == "__main__":
    unittest.main()
