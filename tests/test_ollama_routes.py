import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app


class OllamaRoutesTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        settings_path = Path(self.temp_dir.name) / "data" / "settings.json"
        self.flask_app = app.create_app(settings_path)
        self.manager = mock.Mock()
        self.flask_app.extensions["ollama_service"] = self.manager
        self.client = self.flask_app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_chat_page_contains_ollama_management_controls(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for element_id in (
            "ollamaConfigForm",
            "ollamaInstallDir",
            "saveOllamaConfig",
            "ollamaServiceStatus",
            "startOllama",
            "refreshOllamaStatus",
        ):
            self.assertIn(f'id="{element_id}"', html)

    def test_get_ollama_config_without_saved_settings(self):
        response = self.client.get("/api/ollama/config")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["install_dir"], "")
        self.assertFalse(response.get_json()["valid"])

    def test_put_ollama_config_persists_valid_directory(self):
        install_dir = Path(self.temp_dir.name) / "ollama-server"
        install_dir.mkdir()
        binary = install_dir / "ollama"
        binary.write_text("#!/bin/sh\n", encoding="utf-8", newline="\n")
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        response = self.client.put(
            "/api/ollama/config",
            json={"install_dir": str(install_dir)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["valid"])
        restored = self.client.get("/api/ollama/config").get_json()
        self.assertEqual(restored["install_dir"], str(install_dir.resolve()))

    def test_invalid_config_does_not_replace_saved_config(self):
        install_dir = Path(self.temp_dir.name) / "valid-ollama"
        install_dir.mkdir()
        binary = install_dir / "ollama"
        binary.write_text("#!/bin/sh\n", encoding="utf-8", newline="\n")
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.client.put("/api/ollama/config", json={"install_dir": str(install_dir)})

        rejected = self.client.put(
            "/api/ollama/config",
            json={"install_dir": str(Path(self.temp_dir.name) / "missing")},
        )

        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.get_json()["error"], "invalid_config")
        restored = self.client.get("/api/ollama/config").get_json()
        self.assertEqual(restored["install_dir"], str(install_dir.resolve()))

    def test_status_ready(self):
        expected = {
            "configured": True,
            "binary": "/opt/ollama/ollama",
            "running": True,
            "ready": True,
            "version": "0.6.2",
            "service_state": "active",
        }
        self.manager.get_status.return_value = expected

        response = self.client.get("/api/ollama/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), expected)
        self.manager.get_status.assert_called_once_with()

    def test_status_not_running_is_normal(self):
        self.manager.get_status.return_value = {
            "configured": True,
            "binary": "/opt/ollama/ollama",
            "running": False,
            "ready": False,
            "version": None,
            "service_state": "inactive",
            "api_error": {"code": "connection_error", "message": "API unavailable"},
        }

        response = self.client.get("/api/ollama/status")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["ready"])
        self.assertEqual(response.get_json()["service_state"], "inactive")

    def test_status_not_configured_is_normal(self):
        self.manager.get_status.return_value = {
            "configured": False,
            "binary": None,
            "running": False,
            "ready": False,
            "version": None,
            "service_state": "unavailable",
            "config_error": "尚未配置 Ollama 安装目录",
        }

        response = self.client.get("/api/ollama/status")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["configured"])

    def test_start_returns_immediately_when_already_ready(self):
        self.manager.start.return_value = {
            "success": True,
            "started": False,
            "ready": True,
            "version": "0.6.2",
        }

        response = self.client.post("/api/ollama/start")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "ok": True,
                "started": False,
                "message": "Ollama already running",
                "status": {"ready": True, "version": "0.6.2"},
            },
        )
        self.manager.start.assert_called_once_with()
        self.manager.get_status.assert_not_called()

    def test_start_success(self):
        self.manager.start.return_value = {
            "success": True,
            "started": True,
            "ready": True,
            "version": "0.6.2",
        }

        response = self.client.post("/api/ollama/start")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["status"],
            {"running": True, "ready": True, "version": "0.6.2"},
        )
        self.assertEqual(response.get_json()["message"], "Ollama started")

    def test_start_invalid_configuration_returns_400(self):
        self.manager.start.return_value = {
            "success": False,
            "started": False,
            "ready": False,
            "error": {"code": "invalid_config", "message": "Ollama 安装目录配置无效"},
        }

        response = self.client.post("/api/ollama/start")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_config")
        self.assertIn("未配置或无效", response.get_json()["message"])

    def test_start_systemctl_failure_returns_500(self):
        self.manager.start.return_value = {
            "success": False,
            "started": False,
            "ready": False,
            "error": {"code": "systemctl_failed", "message": "无法启动 systemd 服务"},
        }

        response = self.client.post("/api/ollama/start")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()["error"], "systemctl_failed")
        self.assertNotIn("无法启动 systemd 服务", response.get_json()["message"])

    def test_start_readiness_timeout_returns_500(self):
        self.manager.start.return_value = {
            "success": False,
            "started": True,
            "ready": False,
            "version": None,
            "error": {"code": "ready_timeout", "message": "等待 Ollama API 就绪超时"},
        }

        response = self.client.post("/api/ollama/start")

        self.assertEqual(response.status_code, 500)
        self.assertTrue(response.get_json()["started"])
        self.assertEqual(response.get_json()["error"], "ready_timeout")

    def test_status_manager_exception_is_structured(self):
        self.manager.get_status.side_effect = RuntimeError("sensitive internal detail")

        response = self.client.get("/api/ollama/status")

        self.assertEqual(response.status_code, 500)
        payload = response.get_json()
        self.assertEqual(payload["error"], "service_manager_error")
        self.assertNotIn("sensitive internal detail", response.get_data(as_text=True))
        self.assertNotIn("Traceback", response.get_data(as_text=True))

    def test_start_manager_exception_is_structured(self):
        self.manager.start.side_effect = RuntimeError("sensitive internal detail")

        response = self.client.post("/api/ollama/start")

        self.assertEqual(response.status_code, 500)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "service_manager_error")
        self.assertNotIn("sensitive internal detail", response.get_data(as_text=True))
        self.assertNotIn("Traceback", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
