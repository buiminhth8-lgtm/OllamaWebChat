import unittest

from demo.mock_data import get_config, get_metrics, get_report, get_scenario


class DemoSchemaTest(unittest.TestCase):
    def test_all_api_payloads_have_demo_markers(self):
        for payload in [get_config(), get_scenario(), get_report(), get_metrics()]:
            self.assertTrue(payload["demo"])
            self.assertEqual(payload["data_source"], "mock")
            self.assertTrue(payload["not_real_device_data"])
            self.assertIn("虚拟演示数据", payload["disclaimer"])

    def test_metrics_ranges_are_demo_ranges(self):
        metrics = get_metrics()["metrics"]
        self.assertGreaterEqual(metrics["cpu"], 20)
        self.assertLessEqual(metrics["cpu"], 65)
        self.assertGreaterEqual(metrics["temperature"], 55)
        self.assertLessEqual(metrics["temperature"], 76)


if __name__ == "__main__":
    unittest.main()
