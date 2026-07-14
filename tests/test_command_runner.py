import subprocess
import unittest
from unittest import mock

from platform_scan.command_runner import CommandRunner


class CommandRunnerTest(unittest.TestCase):
    def test_missing_command_returns_structured_result(self):
        result = CommandRunner().run(["command_that_should_not_exist_zkjr"])
        self.assertFalse(result["ok"])
        self.assertFalse(result["command_available"])
        self.assertFalse(result["timed_out"])

    @mock.patch("platform_scan.command_runner.which", return_value="python3")
    @mock.patch("platform_scan.command_runner.subprocess.run")
    def test_timeout_returns_structured_result(self, run_mock, _which_mock):
        run_mock.side_effect = subprocess.TimeoutExpired(["python3"], 3)
        result = CommandRunner().run(["python3", "-c", "pass"], timeout=3)
        self.assertFalse(result["ok"])
        self.assertTrue(result["command_available"])
        self.assertTrue(result["timed_out"])

    @mock.patch("platform_scan.command_runner.which", return_value="python3")
    @mock.patch("platform_scan.command_runner.subprocess.run")
    def test_permission_error_returns_structured_result(self, run_mock, _which_mock):
        run_mock.side_effect = PermissionError("denied")
        result = CommandRunner().run(["python3"], timeout=3)
        self.assertFalse(result["ok"])
        self.assertTrue(result["command_available"])
        self.assertIn("权限不足", result["stderr"])

    def test_forbidden_sudo_is_rejected(self):
        result = CommandRunner().run(["sudo", "true"])
        self.assertFalse(result["ok"])
        self.assertTrue(result["command_available"])


if __name__ == "__main__":
    unittest.main()
