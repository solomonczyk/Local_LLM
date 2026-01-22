"""
Unit tests for tool call parsing and validation in Agent.
"""
import unittest

from agent_runtime.orchestrator.agent import Agent


class TestToolCallParsing(unittest.TestCase):
    """Test cases for tool call parsing/validation."""

    def setUp(self) -> None:
        self.agent = Agent(llm_url="http://example.com", tool_url="http://example.com")

    def test_extract_tool_calls_array_json(self) -> None:
        """Parse TOOL_CALLS array JSON."""
        text = 'TOOL_CALLS: [{"tool": "list_dir", "args": {"path": ".", "pattern": "*"}}]'
        calls = self.agent._extract_tool_calls(text)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["tool"], "list_dir")
        self.assertEqual(calls[0]["args"]["path"], ".")

    def test_extract_tool_calls_literal_eval(self) -> None:
        """Parse TOOL_CALL with single quotes via literal_eval fallback."""
        text = "TOOL_CALL: {'tool': 'read_file', 'args': {'path': 'docs/README.md'}}"
        calls = self.agent._extract_tool_calls(text)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["tool"], "read_file")
        self.assertEqual(calls[0]["args"]["path"], "docs/README.md")

    def test_validate_tool_calls_path_rules(self) -> None:
        """Reject unsafe paths and allow list_dir root."""
        calls = [
            {"tool": "list_dir", "args": {"path": ".", "pattern": "*"}},
            {"tool": "read_file", "args": {"path": "."}},
            {"tool": "read_file", "args": {"path": "../secrets.txt"}},
            {"tool": "read_file", "args": {"path": "C:\\secret.txt"}},
        ]

        valid, invalid = self.agent._validate_tool_calls(calls)

        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0]["tool"], "list_dir")

        error_blob = " ".join(item["error"] for item in invalid)
        self.assertIn("path cannot be the workspace root", error_blob)
        self.assertIn("path traversal is not allowed", error_blob)
        self.assertIn("absolute Windows path is not allowed", error_blob)

    def test_validate_tool_calls_limits_and_modes(self) -> None:
        """Validate numeric limits and write modes."""
        calls = [
            {"tool": "memory_search", "args": {"session_id": "s1", "query": "q", "limit": 0}},
            {"tool": "memory_search", "args": {"session_id": "s1", "query": "q", "limit": 101}},
            {"tool": "memory_search", "args": {"session_id": "s1", "query": "q", "limit": "10"}},
            {"tool": "write_file", "args": {"path": "file.txt", "content": "x", "mode": "bad"}},
            {"tool": "write_file", "args": {"path": "file.txt", "content": "x", "mode": "append"}},
        ]

        valid, invalid = self.agent._validate_tool_calls(calls)

        self.assertEqual(len(valid), 2)

        valid_tools = {item["tool"]: item for item in valid}
        self.assertEqual(valid_tools["memory_search"]["args"]["limit"], 10)
        self.assertEqual(valid_tools["write_file"]["args"]["mode"], "append")

        error_blob = " ".join(item["error"] for item in invalid)
        self.assertIn("limit must be in 1..100", error_blob)
        self.assertIn("mode must be overwrite or append", error_blob)


if __name__ == "__main__":
    unittest.main()
