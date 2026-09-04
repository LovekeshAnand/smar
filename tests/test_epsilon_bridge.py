"""
tests/test_epsilon_bridge.py
============================
Unit test for EpsilonBridge: prompt formatting, ChatML syntax, context injection.
"""

import unittest
from core.epsilon_bridge import EpsilonBridge


class TestEpsilonBridge(unittest.TestCase):
    def setUp(self):
        self.bridge = EpsilonBridge()

    def test_prompt_formatting_with_context(self):
        prompt = "Where does Sweta work?"
        context = "Relational Facts (Knowledge Graph):\n  • Sweta --[WorksAt]--> Google"
        formatted = self.bridge.format_prompt(prompt, context=context)

        self.assertIn("<|im_start|>system", formatted)
        self.assertIn("[Persistent Memory Context]:", formatted)
        self.assertIn("Sweta --[WorksAt]--> Google", formatted)
        self.assertIn("<|im_start|>user\nWhere does Sweta work?<|im_end|>", formatted)
        self.assertIn("<|im_start|>assistant", formatted)


if __name__ == "__main__":
    unittest.main()
