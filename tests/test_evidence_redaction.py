"""
Regression tests for evidence-mode redaction and file filtering.
"""
import unittest

from agent_runtime.orchestrator.agent import Agent


class TestEvidenceRedaction(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = Agent(llm_url="http://example.com", tool_url="http://example.com")

    def test_redact_sensitive_markers(self) -> None:
        sample = "\n".join(
            [
                "OPENAI_API_KEY=sk-test-ABC123",
                "AGENT_API_KEY=dev-local-key",
                "Authorization: Bearer SECRET_TOKEN",
                "random text sk-proj-XYZ987 should be redacted",
            ]
        )
        redacted = self.agent._redact_sensitive_text(sample)

        for marker in ("sk-", "Bearer", "OPENAI_API_KEY=", "AGENT_API_KEY=", "SECRET_TOKEN", "dev-local-key"):
            self.assertNotIn(marker, redacted)

        self.assertIn("OPENAI_API_KEY", redacted)
        self.assertIn("AGENT_API_KEY", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_sensitive_path_filtering(self) -> None:
        sensitive = [
            ".env",
            "secrets/.env",
            "ssl/agent.key",
            "ssl/agent.pem",
            "certs/agent.p12",
            "certs/agent.pfx",
            "id_rsa",
            "ssh/id_ed25519",
            "models/qwen.gguf",
            "lora/adapter_model.safetensors",
            "weights/model.bin",
        ]
        for path in sensitive:
            self.assertTrue(self.agent._is_sensitive_path_for_evidence(path), msg=path)

        safe = [
            "docker-compose.yml",
            "nginx.conf",
            "docs/README.md",
            "agent_runtime/orchestrator/agent.py",
        ]
        for path in safe:
            self.assertFalse(self.agent._is_sensitive_path_for_evidence(path), msg=path)

    def test_search_then_read_top_n_skips_sensitive_files(self) -> None:
        call_log = []

        def fake_execute(calls, invalid_results=None):
            call_log.append(list(calls))
            if calls and calls[0].get("tool") == "search":
                return [
                    {
                        "tool": "search",
                        "success": True,
                        "result": {
                            "files": [
                                ".env",
                                "docker-compose.yml",
                                "ssl/agent.key",
                                "nginx.conf",
                                "models/model.gguf",
                            ],
                            "count": 5,
                            "match_count": 3,
                            "matches": [
                                {"path": ".env", "line": 1, "text": "OPENAI_API_KEY=sk-test-ABC123"},
                                {"path": "docker-compose.yml", "line": 1, "text": "AGENT_API_KEY=dev-local-key"},
                                {"path": "nginx.conf", "line": 21, "text": "Authorization: Bearer SECRET_TOKEN"},
                            ],
                        },
                    }
                ]

            results = []
            for call in calls:
                results.append(
                    {
                        "tool": call.get("tool"),
                        "success": True,
                        "result": {
                            "path": call.get("args", {}).get("path", ""),
                            "content": "\n".join(
                                [
                                    "OPENAI_API_KEY=sk-test-ABC123",
                                    "Authorization: Bearer SECRET_TOKEN",
                                    "AGENT_API_KEY=dev-local-key",
                                ]
                            ),
                        },
                    }
                )
            return results

        self.agent._execute_tool_calls = fake_execute  # type: ignore[assignment]

        result = self.agent.search_then_read_top_n(
            task="Find where AGENT_LLM_URL is used in code.",
            query="AGENT_LLM_URL",
            top_n=5,
            max_lines=20,
        )

        read_paths = [
            call.get("args", {}).get("path")
            for call in result.get("tool_calls", [])
            if call.get("tool") == "read_file"
        ]
        self.assertIn("docker-compose.yml", read_paths)
        self.assertIn("nginx.conf", read_paths)
        self.assertNotIn(".env", read_paths)
        self.assertNotIn("ssl/agent.key", read_paths)
        self.assertNotIn("models/model.gguf", read_paths)

        evidence = result.get("evidence", "")
        for marker in ("sk-", "Bearer", "OPENAI_API_KEY=", "AGENT_API_KEY=", "SECRET_TOKEN", "dev-local-key"):
            self.assertNotIn(marker, evidence)

        self.assertIn("--- skipped (sensitive) ---", evidence)

    def test_search_then_read_top_n_fallback_when_empty(self) -> None:
        calls_seen = {"search": 0}

        def fake_execute(calls, invalid_results=None):
            if calls and calls[0].get("tool") == "search":
                calls_seen["search"] += 1
                if calls_seen["search"] == 1:
                    return [{"tool": "search", "success": True, "result": {"files": [], "matches": []}}]
                return [
                    {
                        "tool": "search",
                        "success": True,
                        "result": {
                            "files": [".env", "docker-compose.yml"],
                            "count": 2,
                            "match_count": 1,
                            "matches": [{"path": ".env", "line": 1, "text": "OPENAI_API_KEY=sk-test-ABC123"}],
                        },
                    }
                ]

            return [
                {
                    "tool": "read_file",
                    "success": True,
                    "result": {
                        "path": calls[0].get("args", {}).get("path", ""),
                        "content": "OPENAI_API_KEY=sk-test-ABC123",
                    },
                }
            ]

        self.agent._execute_tool_calls = fake_execute  # type: ignore[assignment]

        result = self.agent.search_then_read_top_n(
            task="Find where AGENT_LLM_URL is used in code.",
            query="AGENT_LLM_URL",
            top_n=5,
            max_lines=20,
        )

        self.assertGreaterEqual(calls_seen["search"], 2)

        read_paths = [
            call.get("args", {}).get("path")
            for call in result.get("tool_calls", [])
            if call.get("tool") == "read_file"
        ]
        self.assertIn("docker-compose.yml", read_paths)
        self.assertNotIn(".env", read_paths)

        evidence = result.get("evidence", "")
        self.assertIn("search: fallback globs used", evidence)
        self.assertNotIn("sk-", evidence)


if __name__ == "__main__":
    unittest.main()

