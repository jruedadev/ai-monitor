import os
import sqlite3
import tempfile
import unittest

from collectors import codex


SCHEMA = """
CREATE TABLE threads (
    id TEXT, cwd TEXT, model TEXT, tokens_used INTEGER,
    created_at INTEGER, title TEXT
);
"""


class TestCodexCollector(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self.tmp.close()
        con = sqlite3.connect(self.tmp.name)
        con.execute(SCHEMA)
        con.execute(
            "INSERT INTO threads (id, cwd, model, tokens_used, created_at, title) VALUES (?,?,?,?,?,?)",
            ("t1", "/home/user/DEV/demo", "gpt-5.5", 26392, 1781898850, "Prueba de comunicación"),
        )
        con.commit()
        con.close()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_collects_thread_into_project(self):
        data = codex.collect(state_db_path=self.tmp.name)

        self.assertIn("/home/user/DEV/demo", data)
        proj = data["/home/user/DEV/demo"]
        self.assertEqual(proj["total_tokens"], 26392)
        self.assertEqual(proj["session_count"], 1)
        self.assertEqual(proj["sessions_detail"][0]["title"], "Prueba de comunicación")
        self.assertGreater(proj["cost"], 0)

    def test_missing_db_file_returns_empty_dict(self):
        data = codex.collect(state_db_path="/nonexistent/path/state_5.sqlite")
        self.assertEqual(data, {})

    def test_by_day_derives_date_from_created_at_epoch(self):
        con = sqlite3.connect(self.tmp.name)
        con.execute(
            "INSERT INTO threads (id, cwd, model, tokens_used, created_at, title) VALUES (?,?,?,?,?,?)",
            ("t2", "/home/user/DEV/demo", "gpt-5.5", 1_000_000, 1754006400, "Segunda"),
        )  # 1754006400 == 2025-08-01T00:00:00Z
        con.commit()
        con.close()

        data = codex.collect(state_db_path=self.tmp.name)

        by_day = data["/home/user/DEV/demo"]["by_day"]
        self.assertIn("2025-08-01", by_day)
        self.assertEqual(by_day["2025-08-01"]["tokens"], 1_000_000)


if __name__ == "__main__":
    unittest.main()
