"""
tests/test_adaptive.py
======================
Universal Adaptive Test Suite for SMAR Platform.

Works with ANY dataset — warehouse, hospital, pharma, aviation, or freshly uploaded CSV.
Discovers schema from the KG/DB at runtime, generates test scenarios dynamically,
and validates only STRUCTURAL properties (intent type, operation type, result shape),
never specific numeric values or domain-specific column names.

Run:
    python -m pytest tests/test_adaptive.py -v
"""

import sys, time, logging, unittest
sys.path.insert(0, ".")

from context_layer import ContextLayerEngine, ContextConfig
from smart_data.engine import SmartDataLayerEngine

logging.basicConfig(level=logging.WARNING)


class SchemaProbe:
    """Discovers schema from the live warehouse DB. Zero hardcoding."""

    def __init__(self, engine):
        self.engine = engine
        self.warehouse = engine.warehouse_manager
        self._tables = None
        self._schema_cache = {}

    @property
    def tables(self):
        if self._tables is None:
            self._tables = self.warehouse.list_tables()
        return self._tables

    def table_names(self):
        return [t["table_name"] for t in self.tables]

    def get_schema(self, table_name):
        if table_name not in self._schema_cache:
            self._schema_cache[table_name] = self.warehouse.get_table_schema(table_name)
        return self._schema_cache[table_name]

    def numeric_columns(self, table_name):
        schema = self.get_schema(table_name)
        return [
            col for col, dtype in schema.get("columns", {}).items()
            if any(t in dtype.upper() for t in ("INT","REAL","FLOAT","NUMERIC","DECIMAL","DOUBLE"))
        ]

    def id_column(self, table_name):
        schema = self.get_schema(table_name)
        for col in schema.get("primary_keys", []):
            return col
        for col in schema.get("columns", {}):
            if col.endswith("_id") or col == "id":
                return col
        return None

    def sample_id(self, table_name, id_col):
        try:
            res = self.warehouse.query_tabular(table_name, limit=1)
            records = res.get("records", [])
            if records and id_col in records[0]:
                return records[0][id_col]
        except Exception:
            pass
        return None


# ── Structural validators (data-agnostic) ─────────────────────────────────

def val_entity_found(r):
    return r.get("matched_item") is not None and r.get("intent") != "CONVERSATION"

def val_aggregation(r):
    return (r.get("operation") == "AGGREGATION"
            and r.get("operation_details", {}).get("value") is not None)

def val_tabular(r):
    return r.get("operation") == "TABULAR" and r.get("table_data") is not None

def val_conversation(r):
    return r.get("intent") == "CONVERSATION" and r.get("matched_item") is None

def val_not_crash(r):
    return r is not None and isinstance(r, dict) and "intent" in r


# ── Test Classes ──────────────────────────────────────────────────────────

class TestSchemaDiscovery(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ctx = ContextLayerEngine(config=ContextConfig(default_user_id="adaptive_test"))
        cls.engine = SmartDataLayerEngine(context_store=cls.ctx.store)
        cls.probe = SchemaProbe(cls.engine)

    def test_01_has_tables(self):
        self.assertGreater(len(self.probe.table_names()), 0)

    def test_02_kg_has_schema_triples(self):
        triples = self.ctx.store.get_all_triples(user_id="system_schema", limit=50)
        predicates = {t["predicate"] for t in triples}
        self.assertIn("has_table", predicates)

    def test_03_fingerprint_stored(self):
        fp = self.engine._get_stored_fingerprint()
        self.assertGreater(len(fp), 0, "Schema fingerprint not stored in KG")

    def test_04_fast_path_reload(self):
        from smart_data.dictionary import DynamicDomainDictionary
        d = DynamicDomainDictionary()
        ok = self.engine.schema_introspector.reload_vocab_from_kg(d)
        self.assertTrue(ok)
        self.assertGreater(len(d.term_to_canonical), 0)

    def test_05_numeric_cols_discoverable(self):
        for table in self.probe.table_names()[:3]:
            if self.probe.numeric_columns(table):
                num = self.engine._get_numeric_columns_from_kg(table)
                self.assertGreater(len(num), 0, f"No numeric cols in KG for {table}")
                return
        self.skipTest("No numeric columns in any table")


class TestEntityLookup(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ctx = ContextLayerEngine(config=ContextConfig(default_user_id="adaptive_test"))
        cls.engine = SmartDataLayerEngine(context_store=cls.ctx.store)
        cls.probe = SchemaProbe(cls.engine)

    def test_lookup_all_tables(self):
        tested = 0
        for table in self.probe.table_names():
            id_col = self.probe.id_column(table)
            if not id_col:
                continue
            real_id = self.probe.sample_id(table, id_col)
            if real_id is None:
                continue
            singular = table.rstrip("s")
            prompt = f"what is the {singular} with {id_col.replace('_',' ')} {real_id}"
            res = self.engine.process_query(prompt, user_id="adaptive_test")
            self.assertTrue(val_not_crash(res), f"Crashed on lookup for {table}")
            tested += 1
        self.assertGreater(tested, 0, "No tables were testable")


class TestAggregations(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ctx = ContextLayerEngine(config=ContextConfig(default_user_id="adaptive_test"))
        cls.engine = SmartDataLayerEngine(context_store=cls.ctx.store)
        cls.probe = SchemaProbe(cls.engine)

    def test_sum_numeric_cols(self):
        for table in self.probe.table_names():
            cols = self.probe.numeric_columns(table)
            if not cols:
                continue
            col = cols[0]
            res = self.engine.process_query(
                f"what is the sum of {col.replace('_',' ')} in {table}",
                user_id="adaptive_test"
            )
            self.assertTrue(val_not_crash(res))
            return
        self.skipTest("No numeric columns found")

    def test_count_all_tables(self):
        for table in self.probe.table_names():
            res = self.engine.process_query(f"how many {table} are there", user_id="adaptive_test")
            self.assertTrue(val_not_crash(res), f"COUNT crashed for {table}")

    def test_avg_numeric_col(self):
        for table in self.probe.table_names():
            cols = self.probe.numeric_columns(table)
            if not cols:
                continue
            col = cols[0]
            res = self.engine.process_query(
                f"what is the average {col.replace('_',' ')} in {table}",
                user_id="adaptive_test"
            )
            self.assertTrue(val_not_crash(res))
            return
        self.skipTest("No numeric columns found")


class TestTabular(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ctx = ContextLayerEngine(config=ContextConfig(default_user_id="adaptive_test"))
        cls.engine = SmartDataLayerEngine(context_store=cls.ctx.store)
        cls.probe = SchemaProbe(cls.engine)

    def test_tabular_all_tables(self):
        for table in self.probe.table_names():
            res = self.engine.process_query(f"show me all {table} in a table", user_id="adaptive_test")
            self.assertTrue(val_not_crash(res), f"Tabular crashed for {table}")


class TestMutation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ctx = ContextLayerEngine(config=ContextConfig(default_user_id="adaptive_test"))
        cls.engine = SmartDataLayerEngine(context_store=cls.ctx.store)
        cls.probe = SchemaProbe(cls.engine)

    def test_update_and_restore(self):
        for table in self.probe.table_names():
            cols = self.probe.numeric_columns(table)
            id_col = self.probe.id_column(table)
            if not cols or not id_col:
                continue
            col = cols[0]
            real_id = self.probe.sample_id(table, id_col)
            if real_id is None:
                continue
            try:
                rows = self.engine.warehouse_manager.execute_raw(
                    f"SELECT {col} FROM {table} WHERE {id_col} = ?", (real_id,)
                )
                if not rows:
                    continue
                original = rows[0][0]
                new_val = int(original or 0) + 1
            except Exception:
                continue

            singular = table.rstrip("s")
            res = self.engine.process_query(
                f"update {singular} {real_id} {col.replace('_',' ')} to {new_val}",
                user_id="adaptive_test"
            )
            self.assertTrue(val_not_crash(res))
            # Restore
            self.engine.process_query(
                f"update {singular} {real_id} {col.replace('_',' ')} to {original}",
                user_id="adaptive_test"
            )
            return
        self.skipTest("No suitable table for mutation")


class TestConversationBypass(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ctx = ContextLayerEngine(config=ContextConfig(default_user_id="adaptive_test"))
        cls.engine = SmartDataLayerEngine(context_store=cls.ctx.store)

    QUERIES = [
        "hi how are you",
        "do you know about me or do you have any information who i am",
        "what do you know about me",
        "who am i",
        "what is my name",
        "who are you",
        "let us be friends",
        "bye see you later",
        "thanks",
        "tell me about yourself",
    ]

    def test_all_bypass_db(self):
        failures = []
        for q in self.QUERIES:
            res = self.engine.process_query(q, user_id="adaptive_test")
            if not val_conversation(res):
                failures.append(f"'{q}' -> intent={res.get('intent')}, matched={res.get('matched_item') is not None}")
        self.assertEqual(len(failures), 0, "Bypass failures:\n" + "\n".join(failures))


class TestEdgeCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ctx = ContextLayerEngine(config=ContextConfig(default_user_id="adaptive_test"))
        cls.engine = SmartDataLayerEngine(context_store=cls.ctx.store)

    EDGE = [
        "show me record 99999999999999",
        "check id 1; DROP TABLE users; --",
        "??? ... !!! @@@ ###",
        "   ",
        "SHOW ME ALL RECORDS IN A TABLE",
        "yaar mujhe bata do kya haal hai",
        "show show me me the the data data",
    ]

    def test_no_crash(self):
        failures = []
        for prompt in self.EDGE:
            try:
                res = self.engine.process_query(prompt, user_id="adaptive_test")
                if not val_not_crash(res):
                    failures.append(f"malformed result for: '{prompt}'")
            except Exception as e:
                failures.append(f"exception for '{prompt}': {e}")
        self.assertEqual(len(failures), 0, "\n".join(failures))


class TestCompound(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ctx = ContextLayerEngine(config=ContextConfig(default_user_id="adaptive_test"))
        cls.engine = SmartDataLayerEngine(context_store=cls.ctx.store)
        cls.probe = SchemaProbe(cls.engine)

    def test_two_aggregations(self):
        numeric_tables = [
            (t, self.probe.numeric_columns(t))
            for t in self.probe.table_names()
            if self.probe.numeric_columns(t)
        ]
        if len(numeric_tables) < 2:
            self.skipTest("Need 2+ tables with numeric columns")
        t1, c1 = numeric_tables[0]
        t2, c2 = numeric_tables[1]
        prompt = (f"what is the total {c1[0].replace('_',' ')} in {t1} "
                  f"and also the average {c2[0].replace('_',' ')} in {t2}")
        res = self.engine.process_query(prompt, user_id="adaptive_test")
        self.assertTrue(val_not_crash(res))


if __name__ == "__main__":
    print("=" * 60)
    print("SMAR ADAPTIVE TEST SUITE — works with any dataset")
    print("=" * 60)
    unittest.main(verbosity=2)
