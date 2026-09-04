"""
tests/test_context_layer.py
===========================
Comprehensive unit and integration test suite for the SMAR Context Layer.
Validates multi-tenant isolation, contradiction handling, dynamic prompt generation,
and hybrid retrieval.
"""

import os
import tempfile
import unittest

from context_layer.config import ContextConfig
from context_layer.native_hybrid import NativeHybridStore
from context_layer.knowledge_formation import KnowledgeFormationPipeline
from context_layer.retriever import HybridRetriever
from context_layer.prompt_composer import PromptComposer
from context_layer.engine import ContextLayerEngine


class TestContextLayer(unittest.TestCase):

    def setUp(self):
        # Create a temporary SQLite database for test isolation
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.config = ContextConfig(
            db_path=self.temp_db.name,
            provider="native"
        )
        self.engine = ContextLayerEngine(self.config)

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            try:
                os.remove(self.temp_db.name)
            except Exception:
                pass

    def test_multi_user_isolation(self):
        """Ensures facts stored for User A never bleed into User B's context."""
        user_a = "user_alice"
        user_b = "user_bob"

        # Alice says she lives in Paris and works at Acme
        self.engine.process_user_turn(user_a, "My name is Alice. I live in Paris. I work at Acme.")

        # Bob says he lives in Tokyo
        self.engine.process_user_turn(user_b, "My name is Bob. I live in Tokyo.")

        # Query Alice's context
        res_a = self.engine.process_user_turn(user_a, "Where do I live?")
        prompt_a = res_a["system_prompt"]
        self.assertIn("Paris", prompt_a)
        self.assertNotIn("Tokyo", prompt_a)
        self.assertIn("Alice", prompt_a)
        self.assertNotIn("Bob", prompt_a)

        # Query Bob's context
        res_b = self.engine.process_user_turn(user_b, "Where do I live?")
        prompt_b = res_b["system_prompt"]
        self.assertIn("Tokyo", prompt_b)
        self.assertNotIn("Paris", prompt_b)
        self.assertIn("Bob", prompt_b)
        self.assertNotIn("Alice", prompt_b)

    def test_contradiction_handling(self):
        """Verifies single-valued predicates supersede old facts instead of bloating the graph."""
        user = "user_charlie"

        # Charlie initially lives in Bangalore
        self.engine.process_user_turn(user, "I live in Bangalore")
        prof1 = self.engine.get_user_profile(user)
        self.assertEqual(prof1.get("location"), "Bangalore")

        # Charlie moves to Delhi
        self.engine.process_user_turn(user, "I live in Delhi")
        prof2 = self.engine.get_user_profile(user)
        self.assertEqual(prof2.get("location"), "Delhi")

        # Verify only the latest LivesIn fact is active in graph
        triples = self.engine.store.query_triples_for_entities(user, [user])
        live_facts = [t for t in triples if t["predicate"].lower() == "livesin"]
        self.assertEqual(len(live_facts), 1)
        self.assertEqual(live_facts[0]["object"], "Delhi")

    def test_strict_identity_disambiguation(self):
        """Ensures the assistant prompt forbids adopting the user's name."""
        user = "user_lovekesh"
        res = self.engine.process_user_turn(user, "My name is Lovkesh. I work as a designer.")
        prompt = res["system_prompt"]

        # Prompt must clearly demarcate SMAR vs Lovkesh
        self.assertIn("You are SMAR", prompt)
        self.assertIn("You are conversing with Lovkesh", prompt)
        self.assertIn("You are NOT Lovkesh", prompt)
        self.assertIn("NEVER introduce yourself as Lovkesh", prompt)

    def test_semantic_memory_upsert_coalescing(self):
        """Verifies similar semantic chunks merge rather than duplicating."""
        user = "user_david"
        id1, updated1 = self.engine.store.upsert_semantic(user, "I love writing Python code for robotics.")
        self.assertFalse(updated1)

        # Upsert a very similar statement
        id2, updated2 = self.engine.store.upsert_semantic(user, "I love writing Python code for robotics systems.")
        self.assertTrue(updated2)
        self.assertEqual(id1, id2)

    def test_graph_visualization_serialization(self):
        """Verifies graph export produces valid nodes and edges for the UI."""
        user = "user_eve"
        self.engine.process_user_turn(user, "My name is Eve. I live in Berlin. I prefer dark mode.")
        graph = self.engine.get_memory_graph(user_id=user)

        self.assertIn("nodes", graph)
        self.assertIn("edges", graph)
        self.assertTrue(len(graph["nodes"]) > 0)
        self.assertTrue(len(graph["edges"]) > 0)


if __name__ == "__main__":
    unittest.main()
