import unittest

from agent_runtime.orchestrator.agent import Agent


class TestSearchOnlyMode(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = Agent(llm_url="http://example.com", tool_url="http://example.com")

    def test_search_only_proxy_pass(self) -> None:
        self.assertTrue(self.agent._should_use_search_then_read_top_n("Where is proxy_pass defined?"))

    def test_search_only_ports(self) -> None:
        self.assertTrue(self.agent._should_use_search_then_read_top_n("List ports in docker-compose"))

    def test_search_only_env_usage(self) -> None:
        self.assertTrue(self.agent._should_use_search_then_read_top_n("Where is AGENT_LLM_URL used?"))

    def test_search_only_false(self) -> None:
        self.assertFalse(self.agent._should_use_search_then_read_top_n("Tell me about Python"))


if __name__ == "__main__":
    unittest.main()
