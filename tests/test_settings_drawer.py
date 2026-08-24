import re
import tempfile
import unittest
from pathlib import Path

import app as app_module


class SettingsDrawerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        flask_app = app_module.create_app(Path(self.temp_dir.name) / "data" / "settings.json")
        self.html = flask_app.test_client().get("/").get_data(as_text=True)
        project_dir = Path(__file__).resolve().parent.parent
        self.javascript = (project_dir / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.stylesheet = (project_dir / "static" / "css" / "app.css").read_text(encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_drawer_has_stable_accessible_structure(self):
        self.assertIn('id="settingsOverlay"', self.html)
        self.assertRegex(
            self.html,
            r'<aside[^>]*id="settingsDrawer"[^>]*role="dialog"[^>]*aria-modal="true"'
            r'[^>]*aria-labelledby="settingsDrawerTitle"[^>]*aria-hidden="true"',
        )
        self.assertIn('id="settingsDrawerTitle">配置中心</h2>', self.html)
        self.assertIn('id="settingsCloseButton"', self.html)
        self.assertIn('aria-label="关闭配置中心"', self.html)
        self.assertIn('aria-controls="settingsDrawer"', self.html)
        self.assertIn('aria-expanded="false"', self.html)

    def test_drawer_contains_ollama_management_and_model_pull(self):
        drawer = re.search(
            r'<aside[^>]*id="settingsDrawer"[^>]*>(.*?)</aside>',
            self.html,
            re.DOTALL,
        )
        self.assertIsNotNone(drawer)
        markup = drawer.group(1)
        for heading in ("Ollama 服务", "模型管理", "运行信息"):
            self.assertIn(heading, markup)
        for management_id in (
            "ollamaConfigForm",
            "ollamaInstallDir",
            "saveOllamaConfig",
            "ollamaServiceStatus",
            "ollamaVersion",
            "ollamaServiceState",
            "startOllama",
            "refreshOllamaStatus",
        ):
            self.assertIn(f'id="{management_id}"', markup)
            self.assertEqual(self.html.count(f'id="{management_id}"'), 1)
        for pull_id in ("modelPullForm", "pullModelName", "pullModelButton", "modelPullProgress"):
            self.assertIn(f'id="{pull_id}"', markup)
            self.assertEqual(self.html.count(f'id="{pull_id}"'), 1)
        self.assertIn('id="modelPullPanel"', markup)
        self.assertIn("下载状态", markup)

    def test_page_has_no_duplicate_dom_ids(self):
        ids = re.findall(r'\sid="([^"]+)"', self.html)
        duplicates = sorted(element_id for element_id in set(ids) if ids.count(element_id) > 1)
        self.assertEqual(duplicates, [])

    def test_drawer_interactions_and_accessibility_state_are_centralized(self):
        for function_name in (
            "setSettingsDrawerOpen(open)",
            "openSettingsDrawer()",
            "closeSettingsDrawer()",
        ):
            self.assertIn(f"function {function_name}", self.javascript)
        self.assertIn('settingsDrawer.setAttribute("aria-hidden", String(!shouldOpen))', self.javascript)
        self.assertIn('settingsButton.setAttribute("aria-expanded", String(shouldOpen))', self.javascript)
        self.assertIn('settingsCloseButton.focus()', self.javascript)
        self.assertIn('settingsButton.focus()', self.javascript)
        self.assertIn('event.key === "Escape"', self.javascript)
        self.assertIn(
            'if (setSettingsDrawerOpen(true) && !wasOpen) refreshOllamaStatus()',
            self.javascript,
        )
        self.assertEqual(
            self.javascript.count('settingsButton?.addEventListener("click", openSettingsDrawer)'),
            1,
        )
        self.assertEqual(
            self.javascript.count('settingsCloseButton?.addEventListener("click", closeSettingsDrawer)'),
            1,
        )
        self.assertEqual(
            self.javascript.count('settingsOverlay?.addEventListener("click", closeSettingsDrawer)'),
            1,
        )
        self.assertEqual(
            self.javascript.count('modelPullForm.addEventListener("submit"'),
            1,
        )

    def test_model_pull_keeps_stream_buffering_and_model_refresh(self):
        self.assertIn('const decoder = new TextDecoder("utf-8")', self.javascript)
        self.assertIn('buffer += decoder.decode(value, { stream: true })', self.javascript)
        self.assertIn('const lines = buffer.split("\\n")', self.javascript)
        self.assertIn('buffer = lines.pop() || ""', self.javascript)
        self.assertIn('if (buffer.trim())', self.javascript)
        self.assertIn('await loadModels(modelName)', self.javascript)
        self.assertIn('total > 0', self.javascript)
        self.assertIn('pullProgressBarFill.classList.add("indeterminate")', self.javascript)

    def test_drawer_uses_transform_animation_and_full_width_mobile_layout(self):
        self.assertRegex(self.stylesheet, r"\.settings-drawer\s*\{[^}]*transform:\s*translateX\(100%\)")
        self.assertRegex(self.stylesheet, r"\.settings-drawer\.is-open\s*\{[^}]*transform:\s*translateX\(0\)")
        self.assertRegex(self.stylesheet, r"\.settings-drawer-content\s*\{[^}]*overflow-y:\s*auto")
        mobile = re.search(r"@media \(max-width: 768px\)\s*\{(.*?)\n\}", self.stylesheet, re.DOTALL)
        self.assertIsNotNone(mobile)
        self.assertRegex(mobile.group(1), r"\.settings-drawer\s*\{[^}]*width:\s*100vw")
        drawer_rules = "\n".join(
            match.group(0)
            for match in re.finditer(r"\.settings-drawer(?:\.is-open)?\s*\{[^}]*\}", self.stylesheet)
        )
        self.assertNotIn("display: none", drawer_rules)


if __name__ == "__main__":
    unittest.main()
