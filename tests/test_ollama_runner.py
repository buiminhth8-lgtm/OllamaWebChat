import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ollama_runner


def make_store(config):
    store = mock.Mock()
    store.get_ollama_config.return_value = config
    return store


class OllamaRunnerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings_path = Path(self.temp_dir.name) / "settings.json"
        self.binary_path = Path(self.temp_dir.name) / "ollama"

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_binary(self, executable=True):
        self.binary_path.write_text("#!/bin/sh\n", encoding="utf-8")
        if executable and os.name != "nt":
            self.binary_path.chmod(0o755)

    def test_resolve_binary_from_runtime_settings(self):
        self.write_binary()
        store = make_store(
            {"install_dir": str(self.temp_dir.name), "binary": str(self.binary_path), "valid": True}
        )

        with mock.patch.object(
            ollama_runner, "RuntimeSettingsStore", return_value=store
        ):
            binary = ollama_runner.resolve_binary(self.settings_path)

        self.assertEqual(binary, Path(str(self.binary_path)))

    def test_resolve_binary_with_invalid_configuration_fails(self):
        store = make_store(
            {
                "install_dir": "",
                "binary": None,
                "valid": False,
                "error": "尚未配置 Ollama 安装目录",
            }
        )

        with mock.patch.object(
            ollama_runner, "RuntimeSettingsStore", return_value=store
        ):
            with self.assertRaises(SystemExit) as ctx:
                ollama_runner.resolve_binary(self.settings_path)

        self.assertEqual(ctx.exception.code, 1)

    @mock.patch("ollama_runner.os.execve")
    def test_main_missing_binary_exits_non_zero_without_exec(self, execve):
        store = make_store(
            {
                "install_dir": str(self.temp_dir.name),
                "binary": str(Path(self.temp_dir.name) / "missing-ollama"),
                "valid": True,
            }
        )

        with mock.patch.object(
            ollama_runner, "RuntimeSettingsStore", return_value=store
        ), mock.patch("ollama_runner.os.access", return_value=True), mock.patch(
            "ollama_runner.Path.is_file", return_value=False
        ):
            exit_code = ollama_runner.main(self.settings_path)

        self.assertEqual(exit_code, 1)
        execve.assert_not_called()

    @mock.patch("ollama_runner.os.execve")
    def test_main_not_executable_binary_exits_non_zero(self, execve):
        self.write_binary(executable=False)
        store = make_store(
            {"install_dir": str(self.temp_dir.name), "binary": str(self.binary_path), "valid": True}
        )

        access_map = {os.X_OK: False}
        with mock.patch.object(
            ollama_runner, "RuntimeSettingsStore", return_value=store
        ), mock.patch("ollama_runner.os.access", side_effect=lambda p, m: access_map.get(m, True)), mock.patch(
            "ollama_runner.Path.is_file", return_value=True
        ):
            exit_code = ollama_runner.main(self.settings_path)

        self.assertEqual(exit_code, 1)
        execve.assert_not_called()

    @mock.patch("ollama_runner.os.execve")
    def test_main_execs_serve_without_shell_and_default_host(self, execve):
        self.write_binary()
        store = make_store(
            {"install_dir": str(self.temp_dir.name), "binary": str(self.binary_path), "valid": True}
        )

        with mock.patch.object(
            ollama_runner, "RuntimeSettingsStore", return_value=store
        ), mock.patch(
            "ollama_runner.os.access", return_value=True
        ) as access_mock, mock.patch.dict(
            "ollama_runner.os.environ", {}, clear=True
        ):
            exit_code = ollama_runner.main(self.settings_path)

        self.assertEqual(exit_code, 0)
        execve.assert_called_once()
        args, kwargs = execve.call_args
        path, argv, env = args

        self.assertNotIn("shell", kwargs)
        self.assertEqual(kwargs, {})
        self.assertEqual(argv, [str(self.binary_path), "serve"])
        self.assertTrue(path.startswith(str(Path(self.temp_dir.name))))
        self.assertFalse(any(";" in part or "|" in part or "&" in part for part in argv))
        self.assertEqual(env["OLLAMA_HOST"], ollama_runner.DEFAULT_OLLAMA_HOST)
        access_mock.assert_called_once_with(str(self.binary_path), os.X_OK)

    @mock.patch("ollama_runner.os.execve")
    def test_main_honors_ollama_host_env_override(self, execve):
        self.write_binary()
        store = make_store(
            {"install_dir": str(self.temp_dir.name), "binary": str(self.binary_path), "valid": True}
        )

        with mock.patch.object(
            ollama_runner, "RuntimeSettingsStore", return_value=store
        ), mock.patch("ollama_runner.os.access", return_value=True), mock.patch.dict(
            "ollama_runner.os.environ", {"OLLAMA_HOST": "0.0.0.0:11434"}, clear=True
        ):
            ollama_runner.main(self.settings_path)

        _, _, env = execve.call_args[0]
        self.assertEqual(env["OLLAMA_HOST"], "0.0.0.0:11434")


if __name__ == "__main__":
    unittest.main()
