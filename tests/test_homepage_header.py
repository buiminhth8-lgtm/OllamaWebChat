import re
import tempfile
import unittest
from pathlib import Path

import app as app_module


class HomepageHeaderTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.flask_app = app_module.create_app(Path(self.temp_dir.name) / "data" / "settings.json")
        self.client = self.flask_app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def get_header_html(self):
        html = self.client.get("/").get_data(as_text=True)
        match = re.search(r"<header[^>]*>(.*?)</header>", html, re.DOTALL)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_header_keeps_brand_and_three_nav_links(self):
        header = self.get_header_html()
        for text in ("Ollama Web Chat", "AI 对话", "平台能力检测", "平台能力演示"):
            self.assertIn(text, header)

    def test_header_has_settings_button(self):
        header = self.get_header_html()
        self.assertIn('id="settingsButton"', header)

    def test_header_removes_refresh_and_clear_buttons_from_toolbar(self):
        toolbar_match = re.search(
            r'<div class="toolbar"[^>]*>(.*?)</div>',
            self.get_header_html(),
            re.DOTALL,
        )
        self.assertIsNotNone(toolbar_match)
        toolbar = toolbar_match.group(1)
        self.assertIn('id="modelSelect"', toolbar)
        self.assertNotIn("刷新模型", toolbar)
        self.assertNotIn("清空对话", toolbar)

    def test_clear_chat_capability_is_preserved_as_hidden_entry(self):
        header = self.get_header_html()
        clear_match = re.search(r'<button[^>]*id="clearChat"[^>]*>', header)
        self.assertIsNotNone(clear_match)
        self.assertIn("hidden", clear_match.group(0))

    def test_model_select_still_present(self):
        self.assertIn('id="modelSelect"', self.get_header_html())


if __name__ == "__main__":
    unittest.main()
