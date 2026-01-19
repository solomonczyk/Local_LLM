import json
import os
import unittest
from unittest import mock

from agent_system.director_adapter import DirectorAdapter, DirectorRequest, RiskLevel


def validate_director_schema(payload: dict) -> None:
    allowed = {
        "decision",
        "risks",
        "recommendations",
        "next_step",
        "confidence",
        "reasoning",
        "decision_class",
    }
    if not isinstance(payload, dict):
        raise AssertionError("payload must be an object")

    keys = set(payload.keys())
    if keys != allowed:
        missing = allowed - keys
        extra = keys - allowed
        raise AssertionError(f"schema mismatch missing={missing} extra={extra}")

    if not isinstance(payload["decision"], str):
        raise AssertionError("decision must be a string")
    if not isinstance(payload["next_step"], str):
        raise AssertionError("next_step must be a string")
    if not isinstance(payload["reasoning"], str):
        raise AssertionError("reasoning must be a string")

    if not isinstance(payload["risks"], list) or not all(isinstance(x, str) for x in payload["risks"]):
        raise AssertionError("risks must be an array of strings")
    if not isinstance(payload["recommendations"], list) or not all(
        isinstance(x, str) for x in payload["recommendations"]
    ):
        raise AssertionError("recommendations must be an array of strings")

    confidence = payload["confidence"]
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise AssertionError("confidence must be a number")


class _DummyUsage:
    def __init__(self) -> None:
        self.prompt_tokens = 10
        self.completion_tokens = 20
        self.total_tokens = 30


class _DummyResponse:
    def __init__(self, content: str) -> None:
        self.usage = _DummyUsage()
        self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})()]


class _DummyCompletions:
    def __init__(self, content: str) -> None:
        self._content = content
        self.called_with = None

    def create(self, **kwargs):
        self.called_with = kwargs
        return _DummyResponse(self._content)


class _DummyChat:
    def __init__(self, content: str) -> None:
        self.completions = _DummyCompletions(content)


class _DummyClient:
    def __init__(self, content: str) -> None:
        self.chat = _DummyChat(content)


class TestDirectorSchema(unittest.TestCase):
    def test_director_response_matches_schema(self) -> None:
        payload = {
            "decision": "Proceed with the staged rollout.",
            "risks": ["rate limits", "latency spikes"],
            "recommendations": ["add caching", "monitor errors"],
            "next_step": "Deploy to staging.",
            "confidence": 0.82,
            "reasoning": "Low risk with monitoring in place.",
            "decision_class": "process",
        }
        content = json.dumps(payload)

        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            adapter = DirectorAdapter()
        adapter.client = _DummyClient(content)
        adapter.enabled = True

        request = DirectorRequest(
            problem_summary="Test decision contract",
            facts=["Fact A", "Fact B"],
            agent_summaries={"dev": "All good"},
            risk_level=RiskLevel.LOW,
            confidence=0.9,
        )

        adapter.call_director(request)

        validate_director_schema(json.loads(content))


if __name__ == "__main__":
    unittest.main()
