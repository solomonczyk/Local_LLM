import unittest

from agent_runtime.orchestrator.agent import Agent


class TestReadmeUiExtraction(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = Agent(llm_url="http://example.com", tool_url="http://example.com")

    def test_extract_ui_urls(self) -> None:
        content = "- UI: `http://localhost:8080` (via nginx) or `http://localhost:7865` (direct)"
        urls = self.agent._extract_readme_ui_urls(content)
        self.assertEqual(urls, ["http://localhost:8080", "http://localhost:7865"])

    def test_maybe_answer_readme_ui(self) -> None:
        task = "Прочитай docs/README.md и назови адрес UI"
        results = [
            {
                "tool": "read_file",
                "success": True,
                "result": {"content": "- UI: `http://localhost:8080` or `http://localhost:7865`"},
            }
        ]
        answer = self.agent._maybe_answer_readme_ui(task, results)
        self.assertEqual(answer, "UI: http://localhost:8080, http://localhost:7865")


if __name__ == "__main__":
    unittest.main()
