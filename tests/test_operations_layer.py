"""
tests/test_operations_layer.py
==============================
Schema-adaptive unit and integration tests for SMAR Operations Layer.

Zero hardcoding: all table names, column names, and row counts are
discovered dynamically from the live warehouse at test setup time.
Works with any dataset — warehouse, hospital, pharma, aviation, etc.
"""

import os
import unittest
from structured_data.multi_table_manager import MultiTableWarehouseManager
from smart_data.operations import OperationsAnalyzer
from smart_data.visualizer import AdaptiveDataVisualizer
from smart_data.engine import SmartDataLayerEngine


def _first_numeric_col(manager, table_name):
    """Returns the first numeric column from a table schema."""
    schema = manager.get_table_schema(table_name)
    for col, dtype in schema.get("columns", {}).items():
        if any(t in dtype.upper() for t in ("INT","REAL","FLOAT","NUMERIC","DECIMAL")):
            return col
    return None


def _first_text_col(manager, table_name):
    """Returns the first non-ID text column from a table schema."""
    schema = manager.get_table_schema(table_name)
    for col, dtype in schema.get("columns", {}).items():
        if (any(t in dtype.upper() for t in ("TEXT","CHAR","VARCHAR"))
                and not col.endswith("_id") and col != "id"):
            return col
    return None


def _id_col(manager, table_name):
    """Returns the primary key or first _id column."""
    schema = manager.get_table_schema(table_name)
    for col in schema.get("primary_keys", []):
        return col
    for col in schema.get("columns", {}):
        if col.endswith("_id") or col == "id":
            return col
    return None


def _group_by_col(manager, table_name, exclude_col=None):
    """Returns a non-primary, non-excluded integer column suitable for GROUP BY."""
    schema = manager.get_table_schema(table_name)
    id_c = _id_col(manager, table_name)
    for col, dtype in schema.get("columns", {}).items():
        if col == id_c or col == exclude_col:
            continue
        if "INT" in dtype.upper():
            return col
    return None


class TestOperationsLayer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db_path = "data/warehouse.db"
        cls.manager = MultiTableWarehouseManager(db_path=cls.db_path)
        cls.analyzer = OperationsAnalyzer(warehouse_manager=cls.manager)
        cls.visualizer = AdaptiveDataVisualizer()
        cls.engine = SmartDataLayerEngine(warehouse_manager=cls.manager)

        # Discover available tables at setup time — zero hardcoding
        all_tables = cls.manager.list_tables()
        cls.all_table_names = [t["table_name"] for t in all_tables]
        cls.table_row_counts = {t["table_name"]: t.get("row_count", 0) for t in all_tables}

        # Pick the first table with a numeric column for aggregation tests
        cls.agg_table = None
        cls.agg_col = None
        for tbl in cls.all_table_names:
            col = _first_numeric_col(cls.manager, tbl)
            if col and cls.table_row_counts.get(tbl, 0) > 0:
                cls.agg_table = tbl
                cls.agg_col = col
                break

        # Pick a table for GROUP BY (needs a numeric col + a separate int group col)
        cls.group_table = None
        cls.group_col = None
        cls.group_by_col = None
        for tbl in cls.all_table_names:
            num_col = _first_numeric_col(cls.manager, tbl)
            grp_col = _group_by_col(cls.manager, tbl, exclude_col=num_col)
            if num_col and grp_col and cls.table_row_counts.get(tbl, 0) > 0:
                cls.group_table = tbl
                cls.group_col = num_col
                cls.group_by_col = grp_col
                break

        # Pick a table for CRUD lifecycle (needs a text column for insert)
        cls.crud_table = None
        cls.crud_text_col = None
        for tbl in cls.all_table_names:
            txt = _first_text_col(cls.manager, tbl)
            if txt:
                cls.crud_table = tbl
                cls.crud_text_col = txt
                break

    # ── Aggregation Tests ──────────────────────────────────────────────────

    def test_aggregation_sum(self):
        """SUM aggregation on first numeric column of first available table."""
        if not self.agg_table:
            self.skipTest("No table with numeric column found.")
        res = self.manager.execute_aggregation(
            self.agg_table, agg_func="SUM", column=self.agg_col
        )
        self.assertEqual(res["operation"], "AGGREGATION")
        self.assertEqual(res["function"], "SUM")
        self.assertEqual(res["table"], self.agg_table)
        self.assertGreater(res["value"], 0)
        self.assertGreater(res["total_rows_evaluated"], 0)  # not hardcoded to 1000
        self.assertIn("SELECT SUM", res["sql"])
        self.assertLess(res["elapsed_ms"], 5000.0)  # generous for any dataset size

    def test_aggregation_avg(self):
        """AVG aggregation on first numeric column."""
        if not self.agg_table:
            self.skipTest("No table with numeric column found.")
        res = self.manager.execute_aggregation(
            self.agg_table, agg_func="AVG", column=self.agg_col
        )
        self.assertEqual(res["operation"], "AGGREGATION")
        self.assertEqual(res["function"], "AVG")
        self.assertIsNotNone(res.get("value"))

    def test_aggregation_group_by(self):
        """GROUP BY aggregation returns breakdown with >0 groups."""
        if not self.group_table or not self.group_by_col:
            self.skipTest("No table with a suitable GROUP BY column found.")
        res = self.manager.execute_aggregation(
            self.group_table, agg_func="AVG",
            column=self.group_col, group_by=self.group_by_col
        )
        self.assertEqual(res["operation"], "AGGREGATION")
        self.assertEqual(res["group_by"], self.group_by_col)
        self.assertIn("breakdown", res)
        self.assertGreater(len(res["breakdown"]), 0)

    def test_aggregation_count(self):
        """COUNT(*) returns correct row count for each known table."""
        for tbl in self.all_table_names:
            known_count = self.table_row_counts.get(tbl, 0)
            if known_count == 0:
                continue
            id_c = _id_col(self.manager, tbl) or "*"
            res = self.manager.execute_aggregation(tbl, agg_func="COUNT", column=id_c)
            self.assertEqual(res["operation"], "AGGREGATION")
            self.assertEqual(res["value"], known_count)
            break  # verify at least one table

    # ── Tabular Tests ─────────────────────────────────────────────────────

    def test_tabular_query(self):
        """Tabular query retrieves structured rows from first available table."""
        if not self.all_table_names:
            self.skipTest("No tables found.")
        tbl = self.all_table_names[0]
        LIMIT = 5
        res = self.manager.query_tabular(tbl, limit=LIMIT)
        self.assertEqual(res["operation"], "TABULAR")
        self.assertEqual(res["table"], tbl)
        self.assertEqual(res["displayed_count"], min(LIMIT, self.table_row_counts.get(tbl, 0)))
        self.assertGreater(res["total_count"], 0)
        self.assertGreater(len(res.get("columns", [])), 0)
        self.assertGreater(len(res.get("rows", [])), 0)

    # ── CRUD Lifecycle ────────────────────────────────────────────────────

    def test_insert_update_delete_lifecycle(self):
        """Full CRUD lifecycle on first available table with a text column."""
        if not self.crud_table or not self.crud_text_col:
            self.skipTest("No table with a text column found for CRUD test.")

        insert_data = {self.crud_text_col: "SMAR_ADAPTIVE_TEST_RECORD"}
        ins_res = self.manager.insert_record(self.crud_table, insert_data)
        self.assertEqual(ins_res["status"], "SUCCESS")
        self.assertEqual(ins_res["affected_rows"], 1)
        new_id = ins_res["inserted_id"]
        self.assertIsNotNone(new_id)

        # Find the actual PK column name
        pk_col = _id_col(self.manager, self.crud_table)
        self.assertIsNotNone(pk_col, "Could not determine PK column for CRUD table.")

        # Update
        up_res = self.manager.update_record(
            self.crud_table,
            filter_data={pk_col: new_id},
            update_data={self.crud_text_col: "SMAR_ADAPTIVE_TEST_RECORD_UPDATED"}
        )
        self.assertEqual(up_res["status"], "SUCCESS")
        self.assertEqual(up_res["affected_rows"], 1)
        self.assertIn(self.crud_text_col, up_res["diff"])
        self.assertEqual(
            up_res["diff"][self.crud_text_col]["after"],
            "SMAR_ADAPTIVE_TEST_RECORD_UPDATED"
        )

        # Delete
        del_res = self.manager.delete_record(self.crud_table, filter_data={pk_col: new_id})
        self.assertEqual(del_res["status"], "SUCCESS")
        self.assertEqual(del_res["affected_rows"], 1)

    # ── Visualizer Tests ──────────────────────────────────────────────────

    def test_visualizer_bar_chart(self):
        """Visualizer generates valid Base64 PNG bar chart (generic data)."""
        data = {"Group A": 150000, "Group B": 280000, "Group C": 190000}
        chart = self.visualizer.generate_bar_chart(data, title="Adaptive Test Chart")
        self.assertEqual(chart["chart_type"], "bar")
        self.assertTrue(chart["image_base64"].startswith("data:image/png;base64,"))
        self.assertGreater(len(chart["image_base64"]), 1000)

    def test_visualizer_kpi_card(self):
        """Visualizer generates KPI card with any numeric value (generic)."""
        chart = self.visualizer.generate_kpi_card("42,000", title="ADAPTIVE KPI", subtitle="Test")
        self.assertEqual(chart["chart_type"], "kpi")
        self.assertTrue(chart["image_base64"].startswith("data:image/png;base64,"))
        self.assertGreater(len(chart["image_base64"]), 1000)

    # ── Operations Analyzer Parsing ───────────────────────────────────────

    def test_operations_analyzer_detects_aggregation(self):
        """Analyzer correctly identifies aggregation intent — schema-agnostic query."""
        if not self.agg_table or not self.agg_col:
            self.skipTest("No numeric column found.")
        tables = self.manager.list_tables()
        col_display = self.agg_col.replace("_", " ")
        tbl_display = self.agg_table.replace("_", " ")
        plan = self.analyzer.parse_plan(
            f"what is the sum of {col_display} in {tbl_display}", tables
        )
        self.assertIsNotNone(plan)
        self.assertEqual(plan["operation"], "AGGREGATION")
        self.assertEqual(plan["function"], "SUM")
        self.assertEqual(plan["table"], self.agg_table)

    def test_operations_analyzer_detects_tabular(self):
        """Analyzer correctly identifies tabular view intent."""
        if not self.all_table_names:
            self.skipTest("No tables found.")
        tbl = self.all_table_names[0]
        tables = self.manager.list_tables()
        plan = self.analyzer.parse_plan(f"show me all {tbl} in a table", tables)
        self.assertIsNotNone(plan)
        self.assertEqual(plan["operation"], "TABULAR")

    # ── End-to-End Engine ─────────────────────────────────────────────────

    def test_smart_engine_aggregation_execution(self):
        """End-to-end aggregation via SmartDataLayerEngine — no hardcoded column names."""
        if not self.agg_table or not self.agg_col:
            self.skipTest("No numeric column found.")
        col_disp = self.agg_col.replace("_", " ")
        tbl_disp = self.agg_table.replace("_", " ")
        res = self.engine.process_query(
            f"what is the total {col_disp} in {tbl_disp}"
        )
        self.assertEqual(res["intent"], "OPERATION")
        self.assertIsNotNone(res.get("spoken_confirmation"))
        self.assertIsNotNone(res.get("operation_details"))
        self.assertIn("SELECT SUM", res.get("context_string", ""))

    def test_smart_engine_tabular_execution(self):
        """End-to-end tabular query via SmartDataLayerEngine."""
        if not self.all_table_names:
            self.skipTest("No tables found.")
        tbl = self.all_table_names[0]
        res = self.engine.process_query(f"show me all {tbl} in a table")
        self.assertEqual(res["intent"], "OPERATION")
        self.assertEqual(res.get("operation"), "TABULAR")


if __name__ == "__main__":
    unittest.main()
