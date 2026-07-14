import json
import tempfile
import unittest
from unittest import mock

from platform_scan.collectors import platform_info
from platform_scan.collectors.llm_info import collect as collect_llm
from platform_scan.scanner import PlatformScanner
from platform_scan.schemas import ALLOWED_STATUSES


class FakeRunner:
    def run(self, args, timeout=None):
        command = " ".join(args)
        if command == "uname -m":
            return ok("aarch64\n")
        if command == "uname -r":
            return ok("5.10.160\n")
        if command == "hostname":
            return ok("rk3588-board\n")
        if command == "lscpu":
            return ok("Architecture: aarch64\n")
        return ok("")


def ok(stdout):
    return {"ok": True, "command_available": True, "return_code": 0, "stdout": stdout, "stderr": "", "timed_out": False, "duration_ms": 1}


def fake_read_text_rk(path, max_chars=65536):
    values = {
        "/proc/device-tree/compatible": ("rockchip,rk3588", "pass"),
        "/proc/device-tree/model": ("RK3588 EVB", "pass"),
        "/proc/cpuinfo": ("Hardware\t: Rockchip RK3588\nprocessor\t: 0", "pass"),
        "/etc/os-release": ('PRETTY_NAME="Ubuntu 20.04"', "pass"),
        "/proc/meminfo": ("MemTotal:       8192000 kB", "pass"),
    }
    return values.get(path, ("", "warning"))


def fake_read_text_x86(path, max_chars=65536):
    values = {
        "/proc/device-tree/compatible": ("", "warning"),
        "/proc/device-tree/model": ("", "warning"),
        "/proc/cpuinfo": ("model name\t: Intel CPU", "pass"),
        "/etc/os-release": ('PRETTY_NAME="Ubuntu 20.04"', "pass"),
        "/proc/meminfo": ("MemTotal:       4096000 kB", "pass"),
    }
    return values.get(path, ("", "warning"))


class CollectorsTest(unittest.TestCase):
    @mock.patch("platform_scan.collectors.platform_info.read_text", side_effect=fake_read_text_rk)
    def test_detects_rk3588(self, _read_mock):
        result = platform_info.collect(FakeRunner(), {})
        self.assertEqual(result["status"], "pass")
        self.assertIn("瑞芯微", result["summary"])

    @mock.patch("platform_scan.collectors.platform_info.read_text", side_effect=fake_read_text_x86)
    def test_x86_is_not_marked_as_rk3588(self, _read_mock):
        runner = FakeRunner()
        runner.run = lambda args, timeout=None: ok("x86_64\n") if args == ["uname", "-m"] else ok("generic\n")
        result = platform_info.collect(runner, {})
        self.assertNotEqual(result["status"], "pass")
        self.assertIn("未检测到", result["summary"])

    @mock.patch("platform_scan.collectors.llm_info.requests.get")
    @mock.patch("platform_scan.collectors.llm_info.list_process_names", return_value=[])
    @mock.patch("platform_scan.collectors.llm_info._rkllm_present", return_value=(False, 0))
    def test_ollama_reachable_with_qwen(self, _rkllm, _proc, get_mock):
        class Response:
            status_code = 200

            def __init__(self, data):
                self._data = data

            def raise_for_status(self):
                return None

            def json(self):
                return self._data

        get_mock.side_effect = [
            Response({"version": "0.1"}),
            Response({"models": [{"name": "qwen2:7b"}]}),
            Response({"models": []}),
        ]
        result = collect_llm(FakeRunner(), {})
        self.assertEqual(result["status"], "pass")

    @mock.patch("platform_scan.collectors.llm_info.requests.get", side_effect=Exception("down"))
    @mock.patch("platform_scan.collectors.llm_info.list_process_names", return_value=[])
    @mock.patch("platform_scan.collectors.llm_info._rkllm_present", return_value=(False, 0))
    def test_ollama_unavailable_does_not_fail_scan(self, _rkllm, _proc, _get_mock):
        result = collect_llm(FakeRunner(), {})
        self.assertIn(result["status"], ALLOWED_STATUSES)
        self.assertNotEqual(result["status"], "fail")

    def test_collector_exception_does_not_stop_scanner(self):
        def broken(_runner, _cache):
            raise RuntimeError("broken")

        def good(_runner, _cache):
            return {"id": "good", "title": "Good", "status": "pass", "summary": "ok", "metrics": [], "checks": [], "recommendations": [], "duration_ms": 1}

        with tempfile.TemporaryDirectory() as tmp:
            scanner = PlatformScanner(result_path=tmp + "/latest.json", collectors=[("bad", "Bad", broken), ("good", "Good", good)], runner=FakeRunner())
            events = [json.loads(line) for line in scanner.stream()]
        self.assertTrue(any(item["event"] == "error" for item in events))
        self.assertEqual(events[-1]["event"], "complete")


if __name__ == "__main__":
    unittest.main()
