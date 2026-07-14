import json
import os
import tempfile
import unittest

from platform_scan.scanner import PlatformScanner
from platform_scan.schemas import ALLOWED_STATUSES, category_result, check, metric, summary_counts


class ScanSchemaTest(unittest.TestCase):
    def test_status_counts_and_allowed_statuses(self):
        categories = [
            category_result("a", "A", "pass", "", [], [], [], 1),
            category_result("b", "B", "warning", "", [], [], [], 1),
            category_result("c", "C", "fail", "", [], [], [], 1),
            category_result("d", "D", "unknown", "", [], [], [], 1),
        ]
        self.assertEqual(summary_counts(categories), {"pass": 1, "warning": 1, "fail": 1, "unknown": 1})
        for item in categories:
            self.assertIn(item["status"], ALLOWED_STATUSES)

    def test_result_does_not_include_sensitive_environment(self):
        os.environ["VERY_SECRET_TOKEN_FOR_TEST"] = "secret-value-should-not-leak"

        def collector(_runner, _cache):
            return category_result(
                "platform",
                "核心平台与国产化信息",
                "pass",
                "ok",
                [metric("SoC", "RK3588")],
                [check("芯片型号", "pass", "RK3588", "/proc/device-tree/model")],
                [],
                1,
            )

        with tempfile.TemporaryDirectory() as tmp:
            scanner = PlatformScanner(result_path=os.path.join(tmp, "latest.json"), collectors=[("platform", "核心平台与国产化信息", collector)])
            result = [json.loads(line) for line in scanner.stream()]
            dumped = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("secret-value-should-not-leak", dumped)

    def test_complete_event_is_valid_json(self):
        def collector(_runner, _cache):
            return category_result("x", "X", "pass", "ok", [], [], [], 1)

        with tempfile.TemporaryDirectory() as tmp:
            scanner = PlatformScanner(result_path=os.path.join(tmp, "latest.json"), collectors=[("x", "X", collector)])
            lines = list(scanner.stream())
        for line in lines:
            json.loads(line)


if __name__ == "__main__":
    unittest.main()
