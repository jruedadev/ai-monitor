import json
import os
import shutil
import tempfile
import unittest

from collectors import claude_code


class TestClaudeCodeCollector(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proj_dir = os.path.join(self.tmp, "-home-user-DEV-demo")
        os.makedirs(self.proj_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp)

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

        data = claude_code.collect(projects_dir=self.tmp)

        self.assertIn("/home/user/DEV/demo", data)
        self.assertNotIn("-home-user-DEV-demo", data)
        proj = data["/home/user/DEV/demo"]
        self.assertEqual(proj["input"], 100)
        self.assertEqual(proj["output"], 50)
        self.assertEqual(proj["messages"], 1)
        self.assertEqual(proj["session_count"], 1)
        self.assertEqual(proj["sessions_detail"][0]["title"], "Mi tarea")

    def test_missing_projects_dir_returns_empty_dict(self):
        data = claude_code.collect(projects_dir=os.path.join(self.tmp, "does-not-exist"))
        self.assertEqual(data, {})

    def test_non_assistant_records_are_ignored(self):
        self._write_session("sess2.jsonl", [
            {"type": "queue-operation", "content": "irrelevant"},
        ])
        data = claude_code.collect(projects_dir=self.tmp)
        self.assertEqual(data, {})


if __name__ == "__main__":
    unittest.main()
