import subprocess
import threading
import unittest
from unittest import mock

import requests

from ollama_service import OLLAMA_SERVICE_NAME, OllamaServiceManager


READY = {"ready": True, "version": "0.6.2"}
NOT_READY = {
    "ready": False,
    "version": None,
    "error": {"code": "connection_error", "message": "not running"},
}
VALID_CONFIG = {
    "install_dir": "/opt/ollama",
    "binary": "/opt/ollama/ollama",
    "valid": True,
}
INVALID_CONFIG = {
    "install_dir": "",
    "binary": None,
    "valid": False,
    "error": "尚未配置 Ollama 安装目录",
}


class OllamaServiceManagerTest(unittest.TestCase):
    def make_manager(self, config=None, **kwargs):
        store = mock.Mock()
        store.get_ollama_config.return_value = config or VALID_CONFIG
        return OllamaServiceManager(store, base_url="http://127.0.0.1:11434", **kwargs)

    @mock.patch("ollama_service.requests.get")
    def test_check_api_ready(self, requests_get):
        response = mock.Mock()
        response.json.return_value = {"version": "0.6.2"}
        requests_get.return_value = response
        manager = self.make_manager(api_timeout=2.5)

        result = manager.check_api()

        self.assertEqual(result, READY)
        requests_get.assert_called_once_with("http://127.0.0.1:11434/api/version", timeout=2.5)
        response.raise_for_status.assert_called_once_with()

    @mock.patch("ollama_service.requests.get", side_effect=requests.ConnectionError("refused"))
    def test_check_api_not_running(self, requests_get):
        result = self.make_manager().check_api()

        self.assertFalse(result["ready"])
        self.assertEqual(result["error"]["code"], "connection_error")
        requests_get.assert_called_once()

    @mock.patch("ollama_service.requests.get")
    def test_check_api_http_500(self, requests_get):
        response = mock.Mock()
        response.raise_for_status.side_effect = requests.HTTPError(
            "500 Server Error",
            response=mock.Mock(status_code=500),
        )
        requests_get.return_value = response

        result = self.make_manager().check_api()

        self.assertFalse(result["ready"])
        self.assertEqual(result["error"]["code"], "http_error")
        self.assertIn("500", result["error"]["message"])

    @mock.patch("ollama_service.requests.get", side_effect=requests.Timeout("slow"))
    def test_check_api_timeout(self, requests_get):
        result = self.make_manager().check_api()

        self.assertFalse(result["ready"])
        self.assertEqual(result["error"]["code"], "timeout")
        requests_get.assert_called_once()

    @mock.patch("ollama_service.requests.get")
    def test_check_api_invalid_json(self, requests_get):
        response = mock.Mock()
        response.json.side_effect = ValueError("bad json")
        requests_get.return_value = response

        result = self.make_manager().check_api()

        self.assertFalse(result["ready"])
        self.assertEqual(result["error"]["code"], "invalid_json")

    def test_start_rejects_invalid_configuration(self):
        manager = self.make_manager(INVALID_CONFIG)

        with mock.patch.object(manager, "check_api", return_value=NOT_READY), mock.patch(
            "ollama_service.subprocess.run"
        ) as subprocess_run:
            result = manager.start()

        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "invalid_config")
        subprocess_run.assert_not_called()

    def test_start_does_not_repeat_when_api_is_ready(self):
        manager = self.make_manager()

        with mock.patch.object(manager, "check_api", return_value=READY), mock.patch(
            "ollama_service.subprocess.run"
        ) as subprocess_run:
            result = manager.start()

        self.assertTrue(result["success"])
        self.assertFalse(result["started"])
        subprocess_run.assert_not_called()

    def test_start_runs_fixed_systemd_service(self):
        manager = self.make_manager(systemctl_timeout=7)
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")

        with mock.patch.object(manager, "check_api", return_value=NOT_READY), mock.patch.object(
            manager, "wait_until_ready", return_value=READY
        ) as wait_ready, mock.patch(
            "ollama_service.subprocess.run", return_value=completed
        ) as subprocess_run:
            result = manager.start()

        self.assertTrue(result["success"])
        self.assertTrue(result["started"])
        subprocess_run.assert_called_once_with(
            ["sudo", "-n", "systemctl", "start", OLLAMA_SERVICE_NAME],
            shell=False,
            capture_output=True,
            text=True,
            timeout=7,
            check=False,
        )
        wait_ready.assert_called_once_with()

    def test_start_command_is_not_influenced_by_user_input(self):
        hostile_config = {
            "install_dir": "/tmp/x; reboot; rm -rf /",
            "binary": "/opt/ollama/ollama --evil",
            "valid": True,
        }
        manager = self.make_manager(config=hostile_config)
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")

        with mock.patch.object(manager, "check_api", return_value=NOT_READY), mock.patch.object(
            manager, "wait_until_ready", return_value=READY
        ), mock.patch(
            "ollama_service.subprocess.run", return_value=completed
        ) as subprocess_run:
            result = manager.start()

        self.assertTrue(result["success"])
        command = subprocess_run.call_args[0][0]
        self.assertEqual(command[:2], ["sudo", "-n"])
        self.assertEqual(command[2:4], ["systemctl", "start"])
        self.assertEqual(command[4], OLLAMA_SERVICE_NAME)
        self.assertEqual(len(command), 5)
        self.assertFalse(subprocess_run.call_args[1]["shell"])
        self.assertFalse(subprocess_run.call_args[1]["shell"])

    def test_start_returns_structured_systemctl_failure(self):
        manager = self.make_manager()
        completed = subprocess.CompletedProcess([], 1, stdout="", stderr="access denied")

        with mock.patch.object(manager, "check_api", return_value=NOT_READY), mock.patch.object(
            manager, "wait_until_ready"
        ) as wait_ready, mock.patch(
            "ollama_service.subprocess.run", return_value=completed
        ):
            result = manager.start()

        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "systemctl_failed")
        self.assertIn("access denied", result["error"]["message"])
        wait_ready.assert_not_called()

    @mock.patch("ollama_service.time.sleep")
    @mock.patch("ollama_service.time.monotonic", side_effect=[0.0, 0.0])
    def test_wait_until_ready_succeeds(self, monotonic, sleep):
        manager = self.make_manager()

        with mock.patch.object(manager, "check_api", side_effect=[NOT_READY, READY]):
            result = manager.wait_until_ready(timeout=2, poll_interval=0.25)

        self.assertEqual(result, READY)
        sleep.assert_called_once_with(0.25)
        self.assertEqual(monotonic.call_count, 2)

    @mock.patch("ollama_service.time.sleep")
    @mock.patch("ollama_service.time.monotonic", side_effect=[0.0, 0.0, 1.0])
    def test_wait_until_ready_times_out(self, monotonic, sleep):
        manager = self.make_manager()

        with mock.patch.object(manager, "check_api", side_effect=[NOT_READY, NOT_READY]):
            result = manager.wait_until_ready(timeout=1, poll_interval=0.25)

        self.assertFalse(result["ready"])
        self.assertEqual(result["error"]["code"], "ready_timeout")
        self.assertEqual(result["last_error"], NOT_READY["error"])
        sleep.assert_called_once_with(0.25)
        self.assertEqual(monotonic.call_count, 3)

    def test_get_status_keeps_running_and_ready_separate(self):
        manager = self.make_manager()
        completed = subprocess.CompletedProcess([], 0, stdout="active\n", stderr="")

        with mock.patch.object(manager, "check_api", return_value=NOT_READY), mock.patch(
            "ollama_service.subprocess.run", return_value=completed
        ):
            status = manager.get_status()

        self.assertTrue(status["configured"])
        self.assertTrue(status["running"])
        self.assertFalse(status["ready"])
        self.assertEqual(status["service_state"], "active")

    def test_get_status_handles_missing_systemd(self):
        manager = self.make_manager()

        with mock.patch.object(manager, "check_api", return_value=READY), mock.patch(
            "ollama_service.subprocess.run", side_effect=FileNotFoundError
        ):
            status = manager.get_status()

        self.assertFalse(status["running"])
        self.assertTrue(status["ready"])
        self.assertEqual(status["service_state"], "unavailable")
        self.assertEqual(status["service_error"]["code"], "command_not_found")

    def test_concurrent_start_invokes_systemctl_once(self):
        manager = self.make_manager()
        entered_systemctl = threading.Event()
        release_systemctl = threading.Event()
        results = []

        def run_systemctl(*args, **kwargs):
            entered_systemctl.set()
            self.assertTrue(release_systemctl.wait(timeout=2))
            return subprocess.CompletedProcess([], 0, stdout="", stderr="")

        with mock.patch.object(manager, "check_api", side_effect=[NOT_READY, READY]), mock.patch.object(
            manager, "wait_until_ready", return_value=READY
        ), mock.patch("ollama_service.subprocess.run", side_effect=run_systemctl) as subprocess_run:
            first = threading.Thread(target=lambda: results.append(manager.start()))
            second = threading.Thread(target=lambda: results.append(manager.start()))
            first.start()
            self.assertTrue(entered_systemctl.wait(timeout=2))
            second.start()
            release_systemctl.set()
            first.join(timeout=2)
            second.join(timeout=2)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(subprocess_run.call_count, 1)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result["success"] for result in results))


if __name__ == "__main__":
    unittest.main()
