import unittest
from unittest.mock import patch

from agent_runtime.orchestrator.agent import Agent


class TestTriageFallback(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = Agent(name="Dev", role="Dev", llm_url="http://localhost:1", tool_url="http://localhost:1")

    def test_triage_fallback_russian_security(self) -> None:
        response = "Похоже, есть уязвимость токена авторизации."
        with patch.object(Agent, "_call_llm", return_value=response):
            result = self.agent.think_triage("Проверь безопасность токенов")

        self.assertTrue(result["needs_consilium"])
        self.assertIn("Detected", result["reason"])

    def test_triage_fallback_russian_incident(self) -> None:
        response = "Инцидент: прод упал, возможна утечка данных."
        with patch.object(Agent, "_call_llm", return_value=response):
            result = self.agent.think_triage("Что делать, прод упал?")

        self.assertTrue(result["needs_consilium"])
        self.assertIn("Detected", result["reason"])


if __name__ == "__main__":
    unittest.main()
