import builtins
import unittest
from unittest import mock

import app


class DemoRoutesTest(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_demo_page_returns_200(self):
        response = self.client.get("/demo")
        self.assertEqual(response.status_code, 200)
        self.assertIn("RK3588 智能平台能力演示", response.get_data(as_text=True))

    def test_config_returns_mock_json(self):
        data = self.client.get("/api/demo/config").get_json()
        self.assertTrue(data["demo"])
        self.assertEqual(data["data_source"], "mock")
        self.assertTrue(data["not_real_device_data"])

    def test_scenario_has_six_capabilities(self):
        data = self.client.get("/api/demo/scenario").get_json()
        self.assertEqual(len(data["capabilities"]), 6)

    def test_report_is_demo_report(self):
        data = self.client.get("/api/demo/report").get_json()
        self.assertTrue(data["demo"])
        self.assertTrue(data["not_real_device_data"])
        self.assertIn("虚拟", data["disclaimer"])

    def test_metrics_are_mock(self):
        data = self.client.get("/api/demo/metrics").get_json()
        self.assertEqual(data["data_source"], "mock")
        self.assertIn("metrics", data)

    @mock.patch("subprocess.run")
    @mock.patch("requests.get")
    def test_demo_apis_do_not_call_system_or_ollama(self, requests_get, subprocess_run):
        self.client.get("/api/demo/config")
        self.client.get("/api/demo/scenario")
        self.client.get("/api/demo/report")
        self.client.get("/api/demo/metrics")
        subprocess_run.assert_not_called()
        requests_get.assert_not_called()

    def test_demo_apis_do_not_read_proc_sys_dev(self):
        original_open = builtins.open

        def guarded_open(path, *args, **kwargs):
            text = str(path)
            self.assertFalse(text.startswith("/proc"))
            self.assertFalse(text.startswith("/sys"))
            self.assertFalse(text.startswith("/dev"))
            return original_open(path, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=guarded_open):
            self.client.get("/api/demo/config")
            self.client.get("/api/demo/scenario")
            self.client.get("/api/demo/report")
            self.client.get("/api/demo/metrics")

    def test_existing_chat_page_and_config_still_work(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/api/config").status_code, 200)


if __name__ == "__main__":
    unittest.main()
