"""
tests/test_context_memory.py
============================
Unit test for SMAR Context Layer (Knowledge Graph + Vector Store).
Validates relational storage, self-updating upsert, and hybrid retrieval.
"""

import os
import shutil
import tempfile
import unittest

from memory.graph_store import KnowledgeGraphStore
from memory.vector_store import VectorStore
from memory.extractor import FactExtractor
from memory.context_manager import ContextManager


class TestContextMemory(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_memory.db")
        self.ctx = ContextManager(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_knowledge_graph_triples(self):
        kg = KnowledgeGraphStore(db_path=self.db_path)
        kg.upsert_triple("Sweta", "Likes", "Python programming language")
        kg.upsert_triple("Sweta", "WorksAt", "AI Lab")

        facts = kg.query_entity_relations("Sweta")
        self.assertEqual(len(facts), 2)
        subgraph = kg.query_subgraph_for_entities(["Sweta"])
        self.assertTrue(any("Likes" in f for f in subgraph))
        self.assertTrue(any("WorksAt" in f for f in subgraph))

    def test_vector_store_upsert_similarity(self):
        vs = VectorStore(db_path=self.db_path, dim=64)
        id1, updated1 = vs.upsert_by_similarity("I like python programming language")
        self.assertFalse(updated1)

        # Very similar statement should update existing node rather than duplicate
        id2, updated2 = vs.upsert_by_similarity("I like python programming language very much", similarity_threshold=0.80)
        self.assertTrue(updated2)
        self.assertEqual(id1, id2)

    def test_fact_extractor(self):
        extractor = FactExtractor(default_user="User")
        facts = extractor.extract_facts("I like python programming")
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0], ("User", "Likes", "python programming"))

        facts2 = extractor.extract_facts("Sweta works at Google")
        self.assertEqual(len(facts2), 1)
        self.assertEqual(facts2[0], ("Sweta", "WorksAt", "Google"))

    def test_context_manager_integration(self):
        # Ingest a turn
        res = self.ctx.ingest_turn("I like Python programming and I live in Bangalore")
        self.assertGreaterEqual(len(res["triples"]), 1)

        # Retrieve context
        context = self.ctx.retrieve_context("What do I like and where do I live?")
        self.assertIn("Python", context)
        self.assertIn("Relational Facts", context)


if __name__ == "__main__":
    unittest.main()
