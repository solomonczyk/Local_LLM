import unittest

from agent_runtime.orchestrator.agent import Agent


class TestRequiredToolsRU(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = Agent(llm_url="http://example.com", tool_url="http://example.com")

    def test_ru_search_trigger(self) -> None:
        required = self.agent._required_tools_for_task("Покажи где используется AGENT_LLM_URL")
        self.assertIn("search", required)

    def test_ru_explicit_path_requires_read(self) -> None:
        required = self.agent._required_tools_for_task("Прочитай docs/README.md и скажи адрес UI")
        self.assertIn("read_file", required)
        self.assertNotIn("search", required)

    def test_ru_list_dir_trigger(self) -> None:
        required = self.agent._required_tools_for_task("Покажи список файлов в корневой папке")
        self.assertIn("list_dir", required)

    def test_ru_config_hint_requires_search_and_read(self) -> None:
        required = self.agent._required_tools_for_task("Найди конфиг nginx")
        self.assertIn("search", required)
        self.assertIn("read_file", required)


if __name__ == "__main__":
    unittest.main()
