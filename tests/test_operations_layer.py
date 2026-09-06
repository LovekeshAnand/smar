"""
tests/test_operations_layer.py
==============================
Unit and integration tests for SMAR Operations Layer:
Mathematical Aggregations, Dynamic CRUD Mutations, Visual Chart Synthesis,
and Schema-Adaptive Operations Parsing.
"""

import os
import unittest
from structured_data.multi_table_manager import MultiTableWarehouseManager
from smart_data.operations import OperationsAnalyzer
from smart_data.visualizer import AdaptiveDataVisualizer
from smart_data.engine import SmartDataLayerEngine


class TestOperationsLayer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Use existing warehouse database
        cls.db_path = "data/warehouse.db"
        cls.manager = MultiTableWarehouseManager(db_path=cls.db_path)
        cls.analyzer = OperationsAnalyzer(warehouse_manager=cls.manager)
        cls.visualizer = AdaptiveDataVisualizer()
        cls.engine = SmartDataLayerEngine(warehouse_manager=cls.manager)

    def test_aggregation_sum(self):
        """Verify SUM aggregation calculates total salary across all employees."""
        res = self.manager.execute_aggregation("employees", agg_func="SUM", column="salary")
        self.assertEqual(res["operation"], "AGGREGATION")
        self.assertEqual(res["function"], "SUM")
        self.assertEqual(res["table"], "employees")
        self.assertGreater(res["value"], 0)
        self.assertEqual(res["total_rows_evaluated"], 1000)
        self.assertIn("SELECT SUM", res["sql"])
        self.assertLess(res["elapsed_ms"], 100.0)

    def test_aggregation_group_by(self):
        """Verify grouped aggregation returns breakdown per store."""
        res = self.manager.execute_aggregation("employees", agg_func="AVG", column="salary", group_by="store_id")
        self.assertEqual(res["operation"], "AGGREGATION")
        self.assertEqual(res["group_by"], "store_id")
        self.assertIn("breakdown", res)
        self.assertGreater(len(res["breakdown"]), 0)

    def test_tabular_query(self):
        """Verify tabular query retrieves structured rows and total count."""
        res = self.manager.query_tabular("employees", limit=5)
        self.assertEqual(res["operation"], "TABULAR")
        self.assertEqual(res["table"], "employees")
        self.assertEqual(res["displayed_count"], 5)
        self.assertEqual(res["total_count"], 1000)
        self.assertIn("salary", res["columns"])
        self.assertEqual(len(res["rows"]), 5)

    def test_insert_update_delete_lifecycle(self):
        """Verify complete CRUD lifecycle: Insert -> Update -> Delete."""
        # 1. Insert
        insert_data = {"category_name": "Test Special Category"}
        ins_res = self.manager.insert_record("categories", insert_data)
        self.assertEqual(ins_res["status"], "SUCCESS")
        self.assertEqual(ins_res["affected_rows"], 1)
        new_id = ins_res["inserted_id"]
        self.assertIsNotNone(new_id)

        # 2. Update
        up_res = self.manager.update_record(
            "categories",
            filter_data={"category_id": new_id},
            update_data={"category_name": "Updated Test Category"}
        )
        self.assertEqual(up_res["status"], "SUCCESS")
        self.assertEqual(up_res["affected_rows"], 1)
        self.assertIn("category_name", up_res["diff"])
        self.assertEqual(up_res["diff"]["category_name"]["after"], "Updated Test Category")

        # 3. Delete
        del_res = self.manager.delete_record("categories", filter_data={"category_id": new_id})
        self.assertEqual(del_res["status"], "SUCCESS")
        self.assertEqual(del_res["affected_rows"], 1)

    def test_visualizer_bar_chart(self):
        """Verify visualizer generates valid Base64 PNG bar chart."""
        data = {"Store 1": 150000, "Store 2": 280000, "Store 3": 190000}
        chart = self.visualizer.generate_bar_chart(data, title="Store Revenue")
        self.assertEqual(chart["chart_type"], "bar")
        self.assertTrue(chart["image_base64"].startswith("data:image/png;base64,"))
        self.assertGreater(len(chart["image_base64"]), 1000)

    def test_visualizer_kpi_card(self):
        """Verify visualizer generates high-impact KPI metric badge."""
        chart = self.visualizer.generate_kpi_card("49,448,064", title="TOTAL SALARIES", subtitle="1,000 Employees")
        self.assertEqual(chart["chart_type"], "kpi")
        self.assertTrue(chart["image_base64"].startswith("data:image/png;base64,"))
        self.assertGreater(len(chart["image_base64"]), 1000)

    def test_operations_analyzer_intent_parsing(self):
        """Verify natural language queries parse into correct operation plans."""
        tables = self.manager.list_tables()

        # Aggregation Sum
        p1 = self.analyzer.parse_plan("Can you tell me the sum of all the salaries that was given to employees", tables)
        self.assertIsNotNone(p1)
        self.assertEqual(p1["operation"], "AGGREGATION")
        self.assertEqual(p1["function"], "SUM")
        self.assertEqual(p1["table"], "employees")
        self.assertEqual(p1["column"], "salary")

        # Aggregation with Group By
        p2 = self.analyzer.parse_plan("Show me the average salary per store as a chart", tables)
        self.assertIsNotNone(p2)
        self.assertEqual(p2["operation"], "AGGREGATION")
        self.assertEqual(p2["function"], "AVG")
        self.assertEqual(p2["table"], "employees")
        self.assertEqual(p2["group_by"], "store_id")
        self.assertTrue(p2["wants_visual"])

        # Tabular View
        p3 = self.analyzer.parse_plan("Show me products in table format", tables)
        self.assertIsNotNone(p3)
        self.assertEqual(p3["operation"], "TABULAR")
        self.assertEqual(p3["table"], "products")

        # Update
        p4 = self.analyzer.parse_plan("update salary of employee 98 to 35000", tables)
        self.assertIsNotNone(p4)
        self.assertEqual(p4["operation"], "UPDATE")
        self.assertEqual(p4["table"], "employees")
        self.assertEqual(p4["filter"].get("employee_id"), 98)
        self.assertEqual(p4["updates"].get("salary"), 35000)

    def test_smart_engine_operation_execution(self):
        """Verify end-to-end SmartDataLayerEngine operation execution."""
        res = self.engine.process_query("Can you tell me the sum of all the salaries that was given to employees")
        self.assertEqual(res["intent"], "OPERATION")
        self.assertIn("sum of salary in employees", res["spoken_confirmation"].lower())
        self.assertEqual(res["operation_details"]["table"], "employees")
        self.assertEqual(res["operation_details"]["function"], "SUM")
        self.assertIn("SELECT SUM", res["context_string"])


if __name__ == "__main__":
    unittest.main()
