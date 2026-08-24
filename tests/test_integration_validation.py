import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

import app as app_module
from runtime_settings import RuntimeSettingsStore


class FakeStreamResponse:
    def __init__(self, lines=None):
        self.lines = lines or []

    def raise_for_status(self):
        pass

    def iter_lines(self):
        return iter(self.lines)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def create_fake_ollama_dir(temp_dir: Path) -> Path:
    install_dir = temp_dir / "ollama-server"
    install_dir.mkdir(exist_ok=True)
    binary = install_dir / "ollama"
    binary.write_text("#!/bin/sh\n", encoding="utf-8", newline="\n")
    binary.chmod(binary.stat().st_mode | 0o111)
    return install_dir


class ModelsApiRegressionTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.flask_app = app_module.create_app(Path(self.temp_dir.name) / "settings.json")
        self.client = self.flask_app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    @mock.patch("routes.requests.get")
    def test_models_returns_normalized_list(self, requests_get):
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "models": [
                {"name": "deepseek-r1:1.5b", "size": 100, "modified_at": "2026-01-01"},
                {"model": "qwen:0.8b", "size": 200},
            ]
        }
        requests_get.return_value = response

        result = self.client.get("/api/models")

        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            result.get_json(),
            {
                "models": [
                    {"name": "deepseek-r1:1.5b", "size": 100, "modified_at": "2026-01-01"},
                    {"name": "qwen:0.8b", "size": 200, "modified_at": None},
                ]
            },
        )

    @mock.patch("routes.requests.get", side_effect=requests.ConnectionError("refused"))
    def test_models_upstream_down_returns_502(self, requests_get):
        result = self.client.get("/api/models")

        self.assertEqual(result.status_code, 502)
        self.assertIn("error", result.get_json())

    @mock.patch("routes.requests.get")
    def test_models_invalid_json_returns_502(self, requests_get):
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.side_effect = ValueError("invalid json")
        requests_get.return_value = response

        result = self.client.get("/api/models")

        self.assertEqual(result.status_code, 502)
        self.assertIn("error", result.get_json())


class ChatApiRegressionTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.flask_app = app_module.create_app(Path(self.temp_dir.name) / "settings.json")
        self.client = self.flask_app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_chat_requires_model(self):
        result = self.client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(result.status_code, 400)

    def test_chat_requires_valid_messages(self):
        result = self.client.post("/api/chat", json={"model": "m1", "messages": []})
        self.assertEqual(result.status_code, 400)
        self.assertFalse(any(m["role"] == "assistant" for m in []))

    @mock.patch("routes.requests.post", return_value=FakeStreamResponse(
        lines=[b'{"message":{"content":"hello"}}', b'{"done":true}']
    ))
    def test_chat_streams_ndjson_passthrough(self, post_mock):
        result = self.client.post(
            "/api/chat",
            json={"model": "m1", "messages": [{"role": "user", "content": "hi"}]},
        )

        self.assertEqual(result.status_code, 200)
        self.assertIn("application/x-ndjson", result.content_type)
        events = [
            json.loads(line)
            for line in result.get_data(as_text=True).splitlines()
            if line.strip()
        ]
        self.assertEqual(events[0]["message"]["content"], "hello")
        _, kwargs = post_mock.call_args
        self.assertTrue(kwargs["stream"])
        self.assertIsNotNone(kwargs["timeout"])

    @mock.patch(
        "routes.requests.post",
        side_effect=requests.ConnectionError("upstream gone"),
    )
    def test_chat_upstream_error_yields_error_event(self, post_mock):
        result = self.client.post(
            "/api/chat",
            json={"model": "m1", "messages": [{"role": "user", "content": "hi"}]},
        )

        self.assertEqual(result.status_code, 200)
        events = [
            json.loads(line)
            for line in result.get_data(as_text=True).splitlines()
            if line.strip()
        ]
        self.assertIn("error", events[0])


class ConfigPersistenceAcrossRestartTest(unittest.TestCase):
    def test_saved_install_dir_survives_new_store_instance(self):
        temp_dir = tempfile.TemporaryDirectory()
        try:
            settings_path = Path(temp_dir.name) / "data" / "settings.json"
            install_dir = create_fake_ollama_dir(Path(temp_dir.name))

            first_app = app_module.create_app(settings_path)
            first_client = first_app.test_client()
            saved = first_client.put(
                "/api/ollama/config", json={"install_dir": str(install_dir)}
            )
            self.assertEqual(saved.status_code, 200)
            self.assertTrue(saved.get_json()["valid"])

            second_app = app_module.create_app(settings_path)
            restored_config = (
                second_app.extensions["runtime_settings"].get_ollama_config()
            )
            self.assertTrue(restored_config["valid"])
            self.assertEqual(restored_config["install_dir"], str(install_dir.resolve()))
        finally:
            temp_dir.cleanup()


class StartChainTest(unittest.TestCase):
    """链路 C：status 未运行 → start → systemd 启动 → /api/version ready。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.flask_app = app_module.create_app(Path(self.temp_dir.name) / "data" / "settings.json")
        self.client = self.flask_app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    @mock.patch("ollama_service.subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""))
    def test_status_not_running_then_start_becomes_ready(self, subprocess_run):
        version_response = mock.Mock()
        version_response.raise_for_status.return_value = None
        version_response.json.return_value = {"version": "0.6.2"}

        temp_root = Path(self.temp_dir.name)
        install_dir = create_fake_ollama_dir(temp_root)
        configured = self.client.put(
            "/api/ollama/config", json={"install_dir": str(install_dir)}
        )
        self.assertEqual(configured.status_code, 200)

        with mock.patch(
            "ollama_service.requests.get",
            side_effect=[
                requests.ConnectionError("not running yet"),
                requests.ConnectionError("not running yet"),
                version_response,
            ],
        ):
            status_before = self.client.get("/api/ollama/status")

            self.assertFalse(status_before.get_json()["ready"])
            self.assertFalse(status_before.get_json()["running"])

            started = self.client.post("/api/ollama/start")

        self.assertEqual(started.status_code, 200)
        payload = started.get_json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["started"])
        self.assertTrue(payload["status"]["ready"])
        self.assertEqual(subprocess_run.call_args[0][0][:2], ["sudo", "-n"])
        self.assertEqual(
            subprocess_run.call_args[0][0][2:],
            ["systemctl", "start", "ollama-webchat-ollama.service"],
        )
        self.assertFalse(subprocess_run.call_args[1]["shell"])


if __name__ == "__main__":
    unittest.main()
