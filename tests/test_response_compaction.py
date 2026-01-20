import unittest

from agent_runtime.orchestrator.agent import Agent


class TestResponseCompaction(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = Agent(llm_url="http://example.com", tool_url="http://example.com")

    def test_compacts_repeated_final_answer(self) -> None:
        text = "The final answer is: A. " * 5 + "The final answer is: B."
        compacted = self.agent._compact_repeated_final_answer(text)
        self.assertIn("The final answer is:", compacted)
        self.assertTrue(compacted.endswith("B."))
        self.assertLess(len(compacted), len(text))

    def test_keeps_normal_answer(self) -> None:
        text = "The final answer is: OK."
        self.assertEqual(self.agent._compact_repeated_final_answer(text), text)


if __name__ == "__main__":
    unittest.main()
