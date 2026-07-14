import json
import unittest

import app
import platform_scan


class FakeScanner:
    collectors = [1, 2, 3, 4, 5, 6]

    def latest(self):
        return {"available": False}

    def stream(self):
        yield json.dumps({"event": "start", "scan_id": "test", "total": 1, "started_at": "2026-01-01T00:00:00Z"}) + "\n"
        yield json.dumps({"event": "progress", "index": 1, "total": 1, "category": {"id": "platform", "title": "核心平台与国产化信息", "status": "pass", "summary": "ok", "metrics": [], "checks": [], "recommendations": [], "duration_ms": 1}}, ensure_ascii=False) + "\n"
        yield json.dumps({"event": "complete", "scan_id": "test", "finished_at": "2026-01-01T00:00:01Z", "duration_ms": 1, "summary": {"pass": 1, "warning": 0, "fail": 0, "unknown": 0}}) + "\n"


class PlatformRoutesTest(unittest.TestCase):
    def setUp(self):
        self.original = platform_scan.scanner
        platform_scan.scanner = FakeScanner()
        self.client = app.app.test_client()

    def tearDown(self):
        platform_scan.scanner = self.original

    def test_platform_page(self):
        response = self.client.get("/platform")
        self.assertEqual(response.status_code, 200)
        self.assertIn("RK3588", response.get_data(as_text=True))

    def test_latest_without_result(self):
        response = self.client.get("/api/platform/latest")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["available"])

    def test_scan_ndjson_lines_are_valid_json(self):
        response = self.client.post("/api/platform/scan")
        self.assertEqual(response.status_code, 200)
        lines = [line for line in response.get_data(as_text=True).splitlines() if line.strip()]
        self.assertGreaterEqual(len(lines), 3)
        for line in lines:
            json.loads(line)

    def test_health(self):
        response = self.client.get("/api/platform/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])


if __name__ == "__main__":
    unittest.main()
