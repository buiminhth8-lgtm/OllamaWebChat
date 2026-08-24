import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

import app as app_module
from ollama_service import OllamaServiceManager


class FakeStreamResponse:
    def __init__(self, status_code=200, lines=None, chunk_exc=None):
        self.status_code = status_code
        self.lines = lines if lines is not None else []
        self.chunk_exc = chunk_exc
        self.entered = False
        self.exited = False

    def iter_lines(self):
        for line in self.lines:
            yield line
        if self.chunk_exc is not None:
            raise self.chunk_exc

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exited = True
        return False


class OllamaPullRoutesTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        settings_path = Path(self.temp_dir.name) / "data" / "settings.json"
        self.flask_app = app_module.create_app(settings_path)
        store = self.flask_app.extensions["runtime_settings"]
        self.manager = OllamaServiceManager(store)
        self.flask_app.extensions["ollama_service"] = self.manager
        self.client = self.flask_app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def pull(self, model="deepseek-r1:1.5b", **kwargs):
        return self.client.post("/api/ollama/pull", json={"model": model}, **kwargs)

    def test_pull_normal_stream(self):
        fake = FakeStreamResponse(
            lines=[
                b'{"status":"pulling manifest"}',
                b'{"status":"downloading","completed":100,"total":1000}',
                b"",
                b'{"status":"verifying sha256 digest"}',
                b'{"status":"success"}',
            ]
        )
        with mock.patch.object(
            self.manager, "check_api", return_value={"ready": True}
        ), mock.patch("ollama_service.requests.post", return_value=fake) as post_mock:
            response = self.pull()

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/x-ndjson", response.content_type)
        events = [
            json.loads(line)
            for line in response.get_data(as_text=True).splitlines()
            if line.strip()
        ]
        self.assertEqual(len(events), 4)
        self.assertEqual(events[0], {"status": "pulling manifest"})
        self.assertEqual(events[1]["completed"], 100)
        self.assertEqual(events[-1], {"status": "success"})

        _, kwargs = post_mock.call_args
        self.assertEqual(kwargs["json"], {"name": "deepseek-r1:1.5b", "stream": True})
        self.assertTrue(kwargs["stream"])
        self.assertEqual(
            kwargs["timeout"],
            (self.manager.pull_connect_timeout, self.manager.pull_read_timeout),
        )
        self.assertTrue(fake.entered)
        self.assertTrue(fake.exited)

    def test_pull_missing_model_returns_400(self):
        with mock.patch.object(self.manager, "check_api", return_value={"ready": True}):
            response = self.client.post("/api/ollama/pull", json={})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])
        self.assertFalse(self.manager._active_pulls)

    def test_pull_non_string_model_returns_400(self):
        with mock.patch.object(self.manager, "check_api", return_value={"ready": True}):
            response = self.client.post("/api/ollama/pull", json={"model": 123})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])

    def test_pull_blank_model_returns_400(self):
        with mock.patch.object(self.manager, "check_api", return_value={"ready": True}):
            response = self.pull(model="   ")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])

    def test_pull_model_with_control_characters_returns_400(self):
        with mock.patch.object(self.manager, "check_api", return_value={"ready": True}):
            response = self.pull(model="evil\x00model\n")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])

    def test_pull_overlong_model_returns_400(self):
        with mock.patch.object(self.manager, "check_api", return_value={"ready": True}):
            response = self.pull(model="m" * 500)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])

    def test_pull_when_ollama_not_ready_returns_503(self):
        with mock.patch.object(
            self.manager,
            "check_api",
            return_value={
                "ready": False,
                "version": None,
                "error": {"code": "connection_error", "message": "无法连接"},
            },
        ), mock.patch("ollama_service.requests.post") as post_mock:
            response = self.pull()

        self.assertEqual(response.status_code, 503)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "ollama_not_ready")
        post_mock.assert_not_called()

    def test_pull_upstream_http_error_yields_error_event(self):
        fake = FakeStreamResponse(status_code=500, lines=[])
        with mock.patch.object(
            self.manager, "check_api", return_value={"ready": True}
        ), mock.patch("ollama_service.requests.post", return_value=fake):
            response = self.pull()

        self.assertEqual(response.status_code, 200)
        events = [
            json.loads(line)
            for line in response.get_data(as_text=True).splitlines()
            if line.strip()
        ]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["error"]["code"], "http_error")
        self.assertNotIn("Traceback", response.get_data(as_text=True))
        self.assertFalse(self.manager._active_pulls)

    def test_pull_timeout_yields_error_event(self):
        with mock.patch.object(
            self.manager, "check_api", return_value={"ready": True}
        ), mock.patch(
            "ollama_service.requests.post", side_effect=requests.Timeout("boom")
        ):
            response = self.pull()

        self.assertEqual(response.status_code, 200)
        events = [
            json.loads(line)
            for line in response.get_data(as_text=True).splitlines()
            if line.strip()
        ]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["error"]["code"], "timeout")
        self.assertNotIn("boom", response.get_data(as_text=True))

    def test_pull_connection_error_yields_error_event(self):
        with mock.patch.object(
            self.manager, "check_api", return_value={"ready": True}
        ), mock.patch(
            "ollama_service.requests.post",
            side_effect=requests.ConnectionError("refused"),
        ):
            response = self.pull()

        self.assertEqual(response.status_code, 200)
        events = [
            json.loads(line)
            for line in response.get_data(as_text=True).splitlines()
            if line.strip()
        ]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["error"]["code"], "connection_error")
        self.assertNotIn("refused", response.get_data(as_text=True))

    def test_pull_stream_interrupted_midway_yields_error_event(self):
        fake = FakeStreamResponse(
            lines=[b'{"status":"downloading","completed":10,"total":100}'],
            chunk_exc=requests.exceptions.ChunkedEncodingError("dropped"),
        )
        with mock.patch.object(
            self.manager, "check_api", return_value={"ready": True}
        ), mock.patch("ollama_service.requests.post", return_value=fake):
            response = self.pull()

        self.assertEqual(response.status_code, 200)
        events = [
            json.loads(line)
            for line in response.get_data(as_text=True).splitlines()
            if line.strip()
        ]
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["status"], "downloading")
        self.assertEqual(events[1]["error"]["code"], "stream_interrupted")
        self.assertFalse(self.manager._active_pulls)

    def test_pull_invalid_upstream_json_yields_error_event(self):
        fake = FakeStreamResponse(lines=[b'{"status":"downloading"', b'{"status":"success"}'])
        with mock.patch.object(
            self.manager, "check_api", return_value={"ready": True}
        ), mock.patch("ollama_service.requests.post", return_value=fake):
            response = self.pull()

        self.assertEqual(response.status_code, 200)
        events = [
            json.loads(line)
            for line in response.get_data(as_text=True).splitlines()
            if line.strip()
        ]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["error"]["code"], "invalid_json")
        self.assertFalse(self.manager._active_pulls)

    def test_pull_upstream_error_event_is_forwarded(self):
        fake = FakeStreamResponse(
            lines=[
                b'{"status":"pulling manifest"}',
                b'{"error":"pull model manifest: file does not exist"}',
            ]
        )
        with mock.patch.object(
            self.manager, "check_api", return_value={"ready": True}
        ), mock.patch("ollama_service.requests.post", return_value=fake):
            response = self.pull()

        self.assertEqual(response.status_code, 200)
        events = [
            json.loads(line)
            for line in response.get_data(as_text=True).splitlines()
            if line.strip()
        ]
        self.assertEqual(len(events), 2)
        self.assertIn("error", events[1])
        self.assertEqual(events[1]["error"], "pull model manifest: file does not exist")

    def test_pull_same_model_twice_returns_409(self):
        with mock.patch.object(self.manager, "check_api", return_value={"ready": True}):
            self.manager.try_begin_pull("deepseek-r1:1.5b")
            response = self.pull()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json(),
            {"ok": False, "error": "model pull already in progress"},
        )
        self.manager.end_pull("deepseek-r1:1.5b")

    def test_lock_released_after_download_allows_repeat(self):
        def make_fake(*args, **kwargs):
            return FakeStreamResponse(lines=[b'{"status":"success"}'])

        with mock.patch.object(
            self.manager, "check_api", return_value={"ready": True}
        ), mock.patch(
            "ollama_service.requests.post", side_effect=make_fake
        ) as post_mock:
            first = self.pull()
            self.assertEqual(first.status_code, 200)
            first.get_data(as_text=True)
            first.close()
            second = self.pull()
        self.assertEqual(second.status_code, 200)
        second.get_data(as_text=True)
        second.close()
        self.assertEqual(post_mock.call_count, 2)
        self.assertFalse(self.manager._active_pulls)


if __name__ == "__main__":
    unittest.main()
