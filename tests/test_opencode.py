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
    time_created INTEGER, time_updated INTEGER
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
            "tokens_output, tokens_cache_read, tokens_cache_write, time_created, time_updated) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("s1", "/home/user/DEV/demo", '{"id":"gpt-5.5","providerID":"openai"}',
             "Sesión demo", 0.22, 1000, 200, 500, 100, 1777996210131, 1777996310131),
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

    def test_last_ts_is_time_updated_and_first_ts_is_time_created(self):
        data = opencode.collect(db_path=self.tmp.name)
        detail = data["/home/user/DEV/demo"]["sessions_detail"][0]
        self.assertEqual(detail["first_ts"], 1777996210131)
        self.assertEqual(detail["last_ts"], 1777996310131)

    def test_last_ts_falls_back_to_time_created_when_time_updated_is_null(self):
        con = sqlite3.connect(self.tmp.name)
        con.execute("UPDATE session SET time_updated = NULL WHERE id = 's1'")
        con.commit()
        con.close()
        detail = opencode.collect(db_path=self.tmp.name)["/home/user/DEV/demo"]["sessions_detail"][0]
        self.assertEqual(detail["last_ts"], 1777996210131)

    def test_by_day_still_uses_time_created(self):
        con = sqlite3.connect(self.tmp.name)
        con.execute("UPDATE session SET time_updated = time_created + 5 * 86400000 WHERE id = 's1'")
        con.commit()
        con.close()
        by_day = opencode.collect(db_path=self.tmp.name)["/home/user/DEV/demo"]["by_day"]
        self.assertEqual(list(by_day), ["2026-05-05"])


if __name__ == "__main__":
    unittest.main()
