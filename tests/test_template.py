import unittest

from dashboard import template


class TestDashboardTemplate(unittest.TestCase):
    def test_renders_project_and_all_tabs(self):
        sources = {
            "claude_code": {"/home/user/demo": {
                "input": 100, "output": 50, "cache_read": 0, "cache_write": 0,
                "total_tokens": 150, "cost": 0.01, "messages": 1, "session_count": 1,
                "sessions_detail": [],
            }},
            "codex": {},
            "opencode": {},
            "openrouter": {"unavailable": True, "reason": "OPENROUTER_API_KEY no está definida"},
        }
        combined = {"/home/user/demo": {
            "total_tokens": 150, "cost": 0.01, "messages": 1, "session_count": 1,
            "by_source": ["claude_code"],
        }}

        html = template.render(sources, combined, generated_at="2026-08-11 12:00")

        self.assertIn("<!doctype html>", html.lower())
        self.assertIn("Claude Code", html)
        self.assertIn("Codex", html)
        self.assertIn("OpenCode", html)
        self.assertIn("OpenRouter", html)
        self.assertIn("/home/user/demo", html)
        self.assertIn("OPENROUTER_API_KEY", html)  # unavailable reason surfaced


if __name__ == "__main__":
    unittest.main()
