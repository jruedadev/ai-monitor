import os
import sqlite3
import tempfile
import unittest

from collectors import hermes


SCHEMA = """
CREATE TABLE sessions (
    id TEXT PRIMARY KEY, cwd TEXT, model TEXT,
    input_tokens INTEGER, output_tokens INTEGER,
    cache_read_tokens INTEGER, cache_write_tokens INTEGER,
    estimated_cost_usd REAL, actual_cost_usd REAL,
    cost_status TEXT, message_count INTEGER, started_at REAL,
    source TEXT, chat_type TEXT, title TEXT
);
"""

LEGACY_SCHEMA = """
CREATE TABLE sessions (
    id TEXT PRIMARY KEY, cwd TEXT, model TEXT,
    input_tokens INTEGER, output_tokens INTEGER,
    cache_read_tokens INTEGER, cache_write_tokens INTEGER,
    estimated_cost_usd REAL, actual_cost_usd REAL,
    cost_status TEXT, message_count INTEGER, started_at REAL
);
"""


class TestHermesCollector(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        con = sqlite3.connect(self.tmp.name)
        con.execute(SCHEMA)
        con.execute(
            "INSERT INTO sessions (id, cwd, model, input_tokens, output_tokens, "
            "cache_read_tokens, cache_write_tokens, estimated_cost_usd, actual_cost_usd, "
            "cost_status, message_count, started_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("s1", "/home/user/DEV/demo", "upstage/solar-pro4:free",
             281835, 10585, 705312, 0, 0.12, None, "estimated", 50, 1789184558.6284652),
        )
        con.commit()
        con.close()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_collects_session_using_reported_cost(self):
        data = hermes.collect(db_path=self.tmp.name)

        self.assertIn("/home/user/DEV/demo", data)
        proj = data["/home/user/DEV/demo"]
        self.assertEqual(proj["input"], 281835)
        self.assertEqual(proj["output"], 10585)
        self.assertEqual(proj["cache_read"], 705312)
        self.assertEqual(proj["cache_write"], 0)
        self.assertAlmostEqual(proj["cost"], 0.12)
        self.assertEqual(proj["messages"], 50)
        self.assertEqual(proj["session_count"], 1)

    def test_missing_db_returns_empty_dict(self):
        data = hermes.collect(db_path="/nonexistent/state.db")
        self.assertEqual(data, {})

    def test_null_cwd_falls_back_to_unknown(self):
        con = sqlite3.connect(self.tmp.name)
        con.execute(
            "INSERT INTO sessions (id, cwd, model, input_tokens, output_tokens, "
            "cache_read_tokens, cache_write_tokens, estimated_cost_usd, actual_cost_usd, "
            "cost_status, message_count, started_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("s2", None, "deepseek/deepseek-v4-pro-0813", 0, 0, 0, 0, None, None,
             None, 2, 1789184910.1202953),
        )
        con.commit()
        con.close()

        data = hermes.collect(db_path=self.tmp.name)
        self.assertIn("unknown", data)
        self.assertEqual(data["unknown"]["messages"], 2)

    def test_prefers_actual_cost_over_estimated(self):
        con = sqlite3.connect(self.tmp.name)
        con.execute(
            "INSERT INTO sessions (id, cwd, model, input_tokens, output_tokens, "
            "cache_read_tokens, cache_write_tokens, estimated_cost_usd, actual_cost_usd, "
            "cost_status, message_count, started_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("s3", "/home/user/DEV/demo", "gpt-5.5", 100, 20, 0, 0, 0.50, 0.35,
             "actual", 5, 1789185000.0),
        )
        con.commit()
        con.close()

        data = hermes.collect(db_path=self.tmp.name)
        # setUp cost 0.12 (estimated) + s3 actual 0.35 == 0.47
        self.assertAlmostEqual(data["/home/user/DEV/demo"]["cost"], 0.47, places=2)

    def test_by_day_derives_date_from_started_at_epoch_seconds(self):
        data = hermes.collect(db_path=self.tmp.name)
        by_day = data["/home/user/DEV/demo"]["by_day"]
        self.assertIn("2026-09-12", by_day)


    def test_gateway_session_categorized_by_source_and_chat_type(self):
        con = sqlite3.connect(self.tmp.name)
        con.execute(
            "INSERT INTO sessions (id, cwd, model, input_tokens, output_tokens, "
            "cache_read_tokens, cache_write_tokens, estimated_cost_usd, actual_cost_usd, "
            "cost_status, message_count, started_at, source, chat_type, title) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("tg1", None, "deepseek/deepseek-v4.1-flash", 10, 5, 0, 0, 0.01, None,
             "estimated", 3, 1789184558.0, "telegram", "dm", "Hola Hermes"),
        )
        con.commit()
        con.close()

        data = hermes.collect(db_path=self.tmp.name)

        self.assertIn("telegram:dm", data)
        self.assertNotIn("unknown", data)
        detail = data["telegram:dm"]["sessions_detail"][0]
        self.assertEqual(detail["title"], "Hola Hermes")
        self.assertIsNone(detail["cwd"])

    def test_gateway_without_chat_type_uses_source_only(self):
        con = sqlite3.connect(self.tmp.name)
        con.execute(
            "INSERT INTO sessions (id, cwd, model, input_tokens, output_tokens, "
            "cache_read_tokens, cache_write_tokens, estimated_cost_usd, actual_cost_usd, "
            "cost_status, message_count, started_at, source, chat_type, title) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("sl1", None, "gpt-5.5", 1, 1, 0, 0, 0.01, None,
             "estimated", 1, 1789184558.0, "slack", None, None),
        )
        con.commit()
        con.close()

        data = hermes.collect(db_path=self.tmp.name)

        self.assertIn("slack", data)
        self.assertEqual(data["slack"]["sessions_detail"][0]["title"], "gpt-5.5")

    def test_legacy_schema_without_gateway_columns_still_collects(self):
        legacy = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        legacy.close()
        con = sqlite3.connect(legacy.name)
        con.execute(LEGACY_SCHEMA)
        con.execute(
            "INSERT INTO sessions (id, cwd, model, input_tokens, output_tokens, "
            "cache_read_tokens, cache_write_tokens, estimated_cost_usd, actual_cost_usd, "
            "cost_status, message_count, started_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("old1", "/home/user/DEV/demo", "gpt-5.5", 10, 5, 0, 0, 0.02, None,
             "estimated", 2, 1789184558.0),
        )
        con.commit()
        con.close()
        try:
            data = hermes.collect(db_path=legacy.name)
        finally:
            os.unlink(legacy.name)

        self.assertIn("/home/user/DEV/demo", data)
        self.assertEqual(data["/home/user/DEV/demo"]["messages"], 2)


if __name__ == "__main__":
    unittest.main()
