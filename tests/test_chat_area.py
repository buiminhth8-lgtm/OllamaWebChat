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
        project_dir = Path(__file__).resolve().parent.parent
        self.javascript = (project_dir / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.stylesheet = (project_dir / "static" / "css" / "app.css").read_text(encoding="utf-8")

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

    def test_compact_composer_keeps_chat_controls(self):
        composer = re.search(
            r'<form id="chatForm" class="composer">(.*?)</form>',
            self.html,
            re.DOTALL,
        )
        self.assertIsNotNone(composer)
        markup = composer.group(1)
        self.assertIn('id="prompt"', markup)
        self.assertIn('rows="1"', markup)
        self.assertIn('id="clearChat"', markup)
        self.assertRegex(markup, r'id="sendButton"[^>]*disabled')
        self.assertRegex(markup, r'id="stopButton"[^>]*hidden[^>]*disabled')

    def test_composer_uses_one_generating_state_and_ime_guard(self):
        self.assertIn("function updateComposerState()", self.javascript)
        self.assertIn("function setGeneratingState(generating)", self.javascript)
        self.assertIn("sendButton.hidden = generating", self.javascript)
        self.assertIn("stopButton.hidden = !generating", self.javascript)
        self.assertIn('promptInput.addEventListener("input"', self.javascript)
        self.assertIn('promptInput.addEventListener("compositionstart"', self.javascript)
        self.assertIn('promptInput.addEventListener("compositionend"', self.javascript)
        self.assertIn("!event.isComposing", self.javascript)
        self.assertIn("const text = promptInput.value;", self.javascript)
        self.assertNotIn("const text = promptInput.value.trim();", self.javascript)

    def test_composer_limits_long_input_without_horizontal_resize(self):
        self.assertRegex(self.stylesheet, r"\.composer textarea\s*\{[^}]*max-height:\s*180px")
        self.assertRegex(self.stylesheet, r"\.composer textarea\s*\{[^}]*resize:\s*none")
        self.assertRegex(self.stylesheet, r"#messages\s*\{[^}]*padding:\s*20px 16px 48px")


if __name__ == "__main__":
    unittest.main()
