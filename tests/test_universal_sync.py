import os
import unittest
import pandas as pd

from structured_data.sync_engine import UniversalDataSyncEngine
from structured_data.multi_table_manager import MultiTableWarehouseManager
from smart_data.engine import SmartDataLayerEngine

class TestUniversalSync(unittest.TestCase):
    def setUp(self):
        self.test_db = "data/test_universal.db"
        self.manager = MultiTableWarehouseManager(db_path=self.test_db)
        self.engine = SmartDataLayerEngine(warehouse_manager=self.manager)

    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass

    def test_completely_unexpected_medical_dataset(self):
        # Create completely random medical CSV (no products, no prices, no Kirana)
        med_csv = "data/test_patients.csv"
        df = pd.DataFrame([
            {"patient_id": f"PAT-{i:04d}", "patient_name": f"Patient {i}", "blood_type": "O-Positive" if i%2==0 else "A-Negative", "ward": f"Ward-{i%5 + 1}", "heart_rate": 65 + (i%25)}
            for i in range(1, 201)
        ])
        df.to_csv(med_csv, index=False)

        # Ingest and sync via UniversalDataSyncEngine
        status = self.engine.sync_files([med_csv])
        self.assertTrue(status["ready_to_answer"])
        self.assertEqual(status["status"], "ready_to_answer")
        self.assertGreater(status["total_rows"], 0)

        # Query dynamic data
        res = self.engine.process_query("Patient 42")
        self.assertIsNotNone(res["matched_item"])
        self.assertEqual(res["matched_item"]["patient_id"], "PAT-0042")
        self.assertIn("Ward", res["spoken_confirmation"])

        if os.path.exists(med_csv):
            os.remove(med_csv)

    def test_completely_unexpected_aviation_dataset(self):
        # Create completely random aviation CSV
        air_csv = "data/test_flights.csv"
        df = pd.DataFrame([
            {"flight_num": f"AI-{100 + i}", "aircraft_tail": f"VT-EX{i}", "origin": "BOM", "destination": "DEL", "altitude_ft": 32000 + i*10}
            for i in range(1, 101)
        ])
        df.to_csv(air_csv, index=False)

        # Sync
        status = self.engine.sync_files([air_csv])
        self.assertTrue(status["ready_to_answer"])

        # Query dynamic data
        res = self.engine.process_query("AI-105")
        self.assertIsNotNone(res["matched_item"])
        self.assertEqual(res["matched_item"]["aircraft_tail"], "VT-EX5")

        if os.path.exists(air_csv):
            os.remove(air_csv)

if __name__ == "__main__":
    unittest.main()
