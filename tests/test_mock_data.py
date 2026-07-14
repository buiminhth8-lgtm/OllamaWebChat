import unittest

from demo.mock_data import DEMO_PLATFORM, get_config


class MockDataTest(unittest.TestCase):
    def test_all_demo_tags_present(self):
        data = get_config()
        dumped = str(data)
        self.assertIn("模拟数据", dumped)
        self.assertIn("虚拟演示", dumped)
        self.assertIn("Demo Mode", dumped)

    def test_driver_table_fields_are_complete(self):
        for row in DEMO_PLATFORM["drivers"]:
            self.assertEqual(len(row), 7)

    def test_cluster_has_four_uavs(self):
        self.assertGreaterEqual(len(DEMO_PLATFORM["cluster"]["uavs"]), 4)

    def test_models_include_deepseek_and_qwen(self):
        names = " ".join(model["name"].lower() for model in DEMO_PLATFORM["llm"]["models"])
        self.assertIn("deepseek", names)
        self.assertIn("qwen", names)


if __name__ == "__main__":
    unittest.main()
