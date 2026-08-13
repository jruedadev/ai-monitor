import json
import os
import shutil
import tempfile
import unittest

from collectors import claude_code, pricing


class TestClaudeCodeCollector(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proj_dir = os.path.join(self.tmp, "-home-user-DEV-demo")
        os.makedirs(self.proj_dir)
        db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)
        os.unlink(self.db_path)
        pricing.reset_cache()

    def tearDown(self):
        shutil.rmtree(self.tmp)
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        pricing.reset_cache()

    def _write_session(self, filename, lines):
        path = os.path.join(self.proj_dir, filename)
        with open(path, "w") as f:
            for rec in lines:
                f.write(json.dumps(rec) + "\n")

    def test_resolves_project_by_real_cwd_not_encoded_dirname(self):
        self._write_session("sess1.jsonl", [
            {"type": "ai-title", "aiTitle": "Mi tarea", "sessionId": "sess1"},
            {
                "type": "assistant", "cwd": "/home/user/DEV/demo",
                "timestamp": "2026-08-01T10:00:00Z",
                "message": {
                    "model": "claude-sonnet-5",
                    "usage": {
                        "input_tokens": 100, "output_tokens": 50,
                        "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
                    },
                },
            },
        ])

        data = claude_code.collect(projects_dir=self.tmp, db_path=self.db_path)

        self.assertIn("/home/user/DEV/demo", data)
        self.assertNotIn("-home-user-DEV-demo", data)
        proj = data["/home/user/DEV/demo"]
        self.assertEqual(proj["input"], 100)
        self.assertEqual(proj["output"], 50)
        self.assertEqual(proj["messages"], 1)
        self.assertEqual(proj["session_count"], 1)
        self.assertEqual(proj["sessions_detail"][0]["title"], "Mi tarea")

    def test_missing_projects_dir_returns_empty_dict(self):
        data = claude_code.collect(projects_dir=os.path.join(self.tmp, "does-not-exist"), db_path=self.db_path)
        self.assertEqual(data, {})

    def test_non_assistant_records_are_ignored(self):
        self._write_session("sess2.jsonl", [
            {"type": "queue-operation", "content": "irrelevant"},
        ])
        data = claude_code.collect(projects_dir=self.tmp, db_path=self.db_path)
        self.assertEqual(data, {})

    def test_by_day_aggregates_tokens_and_cost_per_date(self):
        self._write_session("sess1.jsonl", [
            {
                "type": "assistant", "cwd": "/home/user/DEV/demo",
                "timestamp": "2026-08-01T10:00:00Z",
                "message": {
                    "model": "claude-sonnet-5",
                    "usage": {
                        "input_tokens": 1_000_000, "output_tokens": 0,
                        "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
                    },
                },
            },
            {
                "type": "assistant", "cwd": "/home/user/DEV/demo",
                "timestamp": "2026-08-02T09:00:00Z",
                "message": {
                    "model": "claude-sonnet-5",
                    "usage": {
                        "input_tokens": 500_000, "output_tokens": 0,
                        "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
                    },
                },
            },
        ])

        data = claude_code.collect(projects_dir=self.tmp, db_path=self.db_path)

        by_day = data["/home/user/DEV/demo"]["by_day"]
        self.assertEqual(by_day["2026-08-01"]["tokens"], 1_000_000)
        self.assertAlmostEqual(by_day["2026-08-01"]["cost"], 3.0)
        self.assertEqual(by_day["2026-08-02"]["tokens"], 500_000)
        self.assertAlmostEqual(by_day["2026-08-02"]["cost"], 1.5)


if __name__ == "__main__":
    unittest.main()
