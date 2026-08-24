import re
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SYSTEMD_DIR = PROJECT_DIR / "systemd"
INSTALL_SCRIPT = PROJECT_DIR / "script" / "install_services.sh"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class WebUnitTest(unittest.TestCase):
    def setUp(self):
        self.unit = read_text(SYSTEMD_DIR / "ollama-webchat.service")

    def test_starts_after_network(self):
        self.assertIn("After=network.target", self.unit)

    def test_restarts_on_failure(self):
        self.assertIn("Restart=on-failure", self.unit)

    def test_runs_as_non_root_deploy_user_placeholder(self):
        match = re.search(r"^User=(.+)$", self.unit, re.MULTILINE)
        self.assertIsNotNone(match)
        user = match.group(1).strip()
        self.assertNotEqual(user, "root")
        self.assertEqual(user, "@DEPLOY_USER@")

    def test_uses_placeholders_instead_of_hardcoded_paths(self):
        self.assertIn("WorkingDirectory=@PROJECT_DIR@", self.unit)
        self.assertIn("ExecStart=@VENV_PYTHON@ @PROJECT_DIR@/app.py", self.unit)
        self.assertNotIn("/home/", self.unit)
        self.assertNotIn("/opt/", self.unit)

    def test_enabled_at_boot(self):
        self.assertIn("[Install]", self.unit)
        self.assertIn("WantedBy=multi-user.target", self.unit)


class OllamaUnitTest(unittest.TestCase):
    def setUp(self):
        self.unit = read_text(SYSTEMD_DIR / "ollama-webchat-ollama.service")

    def test_restarts_on_failure(self):
        self.assertIn("Restart=on-failure", self.unit)

    def test_not_enabled_at_boot(self):
        self.assertNotIn("[Install]", self.unit)
        self.assertNotIn("WantedBy=", self.unit)

    def test_execs_project_runner_without_hardcoded_paths(self):
        self.assertIn("ExecStart=@VENV_PYTHON@ @PROJECT_DIR@/ollama_runner.py", self.unit)
        self.assertNotIn("/home/", self.unit)
        # 不直接执行 ollama 二进制，`serve` 参数由 ollama_runner.py 负责
        exec_line = next(
            line for line in self.unit.splitlines() if line.startswith("ExecStart=")
        )
        self.assertNotIn("serve", exec_line)


class InstallScriptTest(unittest.TestCase):
    def setUp(self):
        self.script = read_text(INSTALL_SCRIPT)

    def test_strict_mode(self):
        self.assertIn("set -euo pipefail", self.script)

    def test_enables_web_service_only(self):
        self.assertIn('WEB_UNIT="ollama-webchat.service"', self.script)
        self.assertIn('OLLAMA_UNIT="ollama-webchat-ollama.service"', self.script)
        enable_commands = [
            line
            for line in self.script.splitlines()
            if re.match(r"^\s*sudo systemctl enable --now", line)
        ]
        self.assertEqual(len(enable_commands), 1)
        self.assertIn('"$WEB_UNIT"', enable_commands[0])

    def test_validates_sudoers_with_visudo_before_install(self):
        visudo_index = self.script.index("visudo -cf")
        install_sudoers_index = self.script.index("/etc/sudoers.d/ollama-webchat")
        self.assertLess(visudo_index, install_sudoers_index)

    def test_daemon_reload_before_enable(self):
        reload_index = self.script.rindex("daemon-reload")
        enable_index = self.script.rindex("enable --now")
        self.assertLess(reload_index, enable_index)

    def test_explicitly_disables_ollama_before_enabling_web(self):
        disable_command = 'sudo systemctl disable "$OLLAMA_UNIT"'
        self.assertIn(disable_command, self.script)
        disable_index = self.script.index(disable_command)
        enable_index = self.script.rindex("enable --now")
        self.assertLess(disable_index, enable_index)

    def test_sudoers_grants_only_fixed_start_command(self):
        sudoers_line = re.search(
            r"printf '%s ALL=\(root\) NOPASSWD: %s start %s\\n'", self.script
        )
        self.assertIsNotNone(sudoers_line)
        self.assertNotIn("NOPASSWD:ALL", self.script)

    def test_no_hardcoded_user_or_project_paths(self):
        self.assertNotIn("/home/zkjr", self.script)
        self.assertIn('DEPLOY_USER="${SUDO_USER:-$(id -un)}"', self.script)
        self.assertIn('PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"', self.script)


class ShellScriptsTest(unittest.TestCase):
    def test_all_shell_scripts_use_lf_endings(self):
        for script in (PROJECT_DIR / "script").glob("*.sh"):
            raw = script.read_bytes()
            self.assertFalse(b"\r\n" in raw, f"{script.name} 包含 CRLF 行尾")


if __name__ == "__main__":
    unittest.main()
