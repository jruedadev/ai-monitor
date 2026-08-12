import os
import sqlite3
import tempfile
import unittest

from collectors import opencode


SCHEMA = """
CREATE TABLE session (
    id TEXT, directory TEXT, model TEXT, title TEXT, cost REAL,
    tokens_input INTEGER, tokens_output INTEGER,
    tokens_cache_read INTEGER, tokens_cache_write INTEGER,
    time_created INTEGER
);
"""


class TestOpenCodeCollector(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        con = sqlite3.connect(self.tmp.name)
        con.execute(SCHEMA)
        con.execute(
            "INSERT INTO session (id, directory, model, title, cost, tokens_input, "
            "tokens_output, tokens_cache_read, tokens_cache_write, time_created) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("s1", "/home/user/DEV/demo", '{"id":"gpt-5.5","providerID":"openai"}',
             "Sesión demo", 0.22, 1000, 200, 500, 100, 1777996210131),
        )
        con.commit()
        con.close()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_collects_session_using_reported_cost(self):
        data = opencode.collect(db_path=self.tmp.name)

        self.assertIn("/home/user/DEV/demo", data)
        proj = data["/home/user/DEV/demo"]
        self.assertEqual(proj["input"], 1000)
        self.assertEqual(proj["output"], 200)
        self.assertEqual(proj["cache_read"], 500)
        self.assertEqual(proj["cache_write"], 100)
        self.assertAlmostEqual(proj["cost"], 0.22)
        self.assertEqual(proj["session_count"], 1)

    def test_missing_db_returns_empty_dict(self):
        data = opencode.collect(db_path="/nonexistent/opencode.db")
        self.assertEqual(data, {})

    def test_by_day_derives_date_from_time_created_ms(self):
        con = sqlite3.connect(self.tmp.name)
        con.execute(
            "INSERT INTO session (id, directory, model, title, cost, tokens_input, "
            "tokens_output, tokens_cache_read, tokens_cache_write, time_created) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("s2", "/home/user/DEV/demo", '{"id":"gpt-5.5"}', "Segunda", 0.10,
             300, 50, 0, 0, 1777996210131),  # == 2026-05-05T15:50:10Z
        )
        con.commit()
        con.close()

        data = opencode.collect(db_path=self.tmp.name)

        by_day = data["/home/user/DEV/demo"]["by_day"]
        self.assertIn("2026-05-05", by_day)
        # setUp inserts s1: 1000+200+500+100=1800 tokens, cost 0.22
        # test inserts s2: 300+50+0+0=350 tokens, cost 0.10
        # both on same day, so total should be 2150 tokens and 0.32 cost
        self.assertEqual(by_day["2026-05-05"]["tokens"], 2150)
        self.assertAlmostEqual(by_day["2026-05-05"]["cost"], 0.32, places=2)


if __name__ == "__main__":
    unittest.main()
