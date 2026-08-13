import json
import os
import tempfile
import threading
import time
import unittest
import urllib.request
from unittest.mock import patch

import server


class TestServerAPI(unittest.TestCase):
    def setUp(self):
        self.static_dir = tempfile.mkdtemp()
        with open(os.path.join(self.static_dir, "index.html"), "w") as f:
            f.write("<html>fallback</html>")

        self.fake_sources = {
            "claude_code": {"/home/user/demo": {
                "input": 10, "output": 5, "cache_read": 0, "cache_write": 0,
                "total_tokens": 15, "cost": 0.01, "cost_incomplete": False,
                "messages": 1, "session_count": 1, "by_day": {}, "sessions_detail": [],
            }},
            "codex": {}, "opencode": {}, "openrouter": {"unavailable": True, "reason": "x"},
        }

        patcher = patch("server.main.collect_all", return_value=self.fake_sources)
        patcher.start()
        self.addCleanup(patcher.stop)

        db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)
        os.unlink(self.db_path)
        self.addCleanup(lambda: os.path.exists(self.db_path) and os.unlink(self.db_path))

        self.httpd = server.build_app(self.static_dir, poll_interval_seconds=3600, db_path=self.db_path)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        # Give the background collection thread one tick to populate state.
        time.sleep(0.2)

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as resp:
            return resp.status, resp.read()

    def test_api_usage_returns_current_snapshot(self):
        status, body = self._get("/api/usage")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("/home/user/demo", data["combined"])

    def test_api_history_returns_json_with_default_days(self):
        status, body = self._get("/api/history")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("daily_project", data)
        self.assertIn("daily_model", data)

    def test_unknown_path_falls_back_to_index_html(self):
        status, body = self._get("/some/spa/route")
        self.assertEqual(status, 200)
        self.assertIn(b"fallback", body)


if __name__ == "__main__":
    unittest.main()
