import unittest
from unittest.mock import patch

from agent_runtime.orchestrator.agent import Agent


class TestToolApprovalFlow(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = Agent(llm_url="http://example.com", tool_url="http://example.com")

    def test_think_with_tools_returns_pending_with_preview(self) -> None:
        llm_response = (
            'TOOL_CALLS: [{"tool": "write_file", "args": {"path": "notes.txt", "content": "hi", "mode": "overwrite"}}]'
        )
        preview_result = [
            {
                "tool": "write_file",
                "success": True,
                "result": {"path_relative": "notes.txt", "sha256": "abc123", "exists": False},
            }
        ]
        captured = {}

        def fake_execute(calls, invalid_results=None):
            captured["calls"] = calls
            return preview_result

        with patch.object(Agent, "_call_llm", return_value=llm_response), patch.object(
            Agent, "_execute_tool_calls", side_effect=fake_execute
        ):
            result = self.agent.think_with_tools("Write file notes.txt", require_confirmation=True)

        self.assertEqual(result["status"], "confirmation_required")
        self.assertEqual(result["dry_run_results"], preview_result)
        self.assertTrue(captured["calls"][0]["args"].get("dry_run"))

    def test_approve_tool_calls_missing_preview(self) -> None:
        pending = {
            "task": "Write file notes.txt",
            "response": "Prepare to write file.",
            "tool_calls": [
                {"tool": "write_file", "args": {"path": "notes.txt", "content": "hi", "mode": "overwrite"}}
            ],
            "dry_run_results": [],
        }

        result = self.agent.approve_tool_calls(pending)

        self.assertIn("Dry-run preview missing", result["response"])
        self.assertEqual(result["status"], "final")

    def test_approve_tool_calls_attaches_expectations(self) -> None:
        preview_result = [
            {
                "tool": "write_file",
                "success": True,
                "result": {"path_relative": "notes.txt", "sha256": "abc123", "exists": False},
            }
        ]
        pending = {
            "task": "Write file notes.txt",
            "response": "Prepare to write file.",
            "tool_calls": [
                {"tool": "write_file", "args": {"path": "notes.txt", "content": "hi", "mode": "overwrite"}}
            ],
            "dry_run_results": preview_result,
        }
        captured = {}

        def fake_execute(calls, invalid_results=None):
            captured["calls"] = calls
            return [{"tool": "write_file", "success": True, "result": {"ok": True}}]

        with patch.object(Agent, "_execute_tool_calls", side_effect=fake_execute), patch.object(
            Agent, "_finalize_with_tool_results", return_value="ok"
        ):
            result = self.agent.approve_tool_calls(pending)

        self.assertEqual(result["status"], "final")
        call_args = captured["calls"][0]["args"]
        self.assertEqual(call_args["expected_sha256"], "abc123")
        self.assertFalse(call_args["expected_exists"])


if __name__ == "__main__":
    unittest.main()
