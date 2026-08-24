import re
import tempfile
import unittest
from pathlib import Path

import app as app_module


class ChatAreaTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.flask_app = app_module.create_app(Path(self.temp_dir.name) / "data" / "settings.json")
        self.client = self.flask_app.test_client()
        self.html = self.client.get("/").get_data(as_text=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_welcome_empty_state_exists_with_copy(self):
        self.assertIn('id="chatWelcome"', self.html)
        self.assertIn("你好，我是 Ollama", self.html)
        self.assertIn("本地大模型助手，隐私、快速、可定制。", self.html)

    def test_three_recommendation_cards_have_prompts(self):
        cards = re.findall(r'class="welcome-card"[^>]*data-prompt="([^"]+)"', self.html)
        self.assertEqual(len(cards), 3)
        for prompt in cards:
            self.assertTrue(prompt.strip())
        labels = ("知识问答", "代码助手", "创作助手")
        for label in labels:
            self.assertIn(label, self.html)

    def test_ollama_panel_is_collapsible_compat_container(self):
        self.assertIn('<details class="ollama-panel" id="ollamaPanel">', self.html)
        self.assertIn('id="ollamaPanelSummary"', self.html)
        # 业务 DOM 全部保留
        for element_id in (
            "ollamaConfigForm",
            "ollamaInstallDir",
            "saveOllamaConfig",
            "startOllama",
            "refreshOllamaStatus",
            "modelPullForm",
            "pullModelName",
            "pullModelButton",
        ):
            self.assertIn(f'id="{element_id}"', self.html)

    def test_messages_container_contains_welcome(self):
        messages_match = re.search(r'<main id="messages">(.*?)</main>', self.html, re.DOTALL)
        self.assertIsNotNone(messages_match)
        self.assertIn('id="chatWelcome"', messages_match.group(1))

    def test_composer_unchanged(self):
        self.assertIn('id="chatForm"', self.html)
        self.assertIn('id="prompt"', self.html)
        self.assertIn('id="sendButton"', self.html)
        self.assertIn('id="stopButton"', self.html)


if __name__ == "__main__":
    unittest.main()
