import unittest
from unittest.mock import MagicMock, patch

from agent_system.system_tools import SystemTools


class TestSystemTools(unittest.TestCase):
    def setUp(self) -> None:
        self.tools = SystemTools(agent_name="test")

    @staticmethod
    def _mock_completed(returncode: int = 0, stdout: str = "ok", stderr: str = "") -> MagicMock:
        proc = MagicMock()
        proc.returncode = returncode
        proc.stdout = stdout
        proc.stderr = stderr
        return proc

    def test_git_allows_safe_command(self) -> None:
        with patch("agent_system.system_tools.subprocess.run") as run, patch(
            "agent_system.system_tools.audit_logger.log_action"
        ):
            run.return_value = self._mock_completed()
            result = self.tools.git("status")

        self.assertTrue(result["success"])
        run.assert_called_once()

    def test_git_denies_commit_without_access(self) -> None:
        with patch("agent_system.system_tools.AgentConfig.CURRENT_ACCESS_LEVEL", 0), patch(
            "agent_system.system_tools.AgentConfig.ACCESS_LEVEL_GIT_COMMIT", 3
        ), patch("agent_system.system_tools.audit_logger.log_action"):
            result = self.tools.git("commit -m test")

        self.assertFalse(result["success"])
        self.assertIn("commit access denied", result["error"].lower())

    def test_git_denies_dangerous_command(self) -> None:
        with patch("agent_system.system_tools.audit_logger.log_action"):
            result = self.tools.git("reset --hard")

        self.assertFalse(result["success"])
        self.assertIn("not allowed", result["error"].lower())

    def test_shell_allows_safe_command(self) -> None:
        with patch("agent_system.system_tools.AgentConfig.CURRENT_ACCESS_LEVEL", 2), patch(
            "agent_system.system_tools.AgentConfig.ACCESS_LEVEL_RUN_TESTS", 2
        ), patch("agent_system.system_tools.subprocess.run") as run, patch(
            "agent_system.system_tools.audit_logger.log_action"
        ):
            run.return_value = self._mock_completed()
            result = self.tools.shell("echo ok")

        self.assertTrue(result["success"])
        run.assert_called_once()

    def test_shell_denies_unsafe_command(self) -> None:
        with patch("agent_system.system_tools.AgentConfig.CURRENT_ACCESS_LEVEL", 2), patch(
            "agent_system.system_tools.AgentConfig.ACCESS_LEVEL_RUN_TESTS", 2
        ), patch("agent_system.system_tools.audit_logger.log_action"):
            result = self.tools.shell("curl http://example.com")

        self.assertFalse(result["success"])
        self.assertIn("unsafe command", result["error"].lower())


if __name__ == "__main__":
    unittest.main()
