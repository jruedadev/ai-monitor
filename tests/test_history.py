import os
import sqlite3
import tempfile
import unittest

import history


class TestHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name

    def tearDown(self):
        os.unlink(self.db_path)

    def test_record_snapshot_writes_project_and_model_rollups(self):
        sources = {
            "claude_code": {
                "/home/user/demo": {"by_day": {"2026-08-01": {"tokens": 100, "cost": 0.01}}},
            },
            "codex": {},
            "opencode": {},
            "openrouter": {
                "unavailable": False,
                "by_day": {"2026-08-01": {"tokens": 500, "cost": 0.05}},
            },
        }

        history.record_snapshot(sources, db_path=self.db_path)

        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute("SELECT date, source, project, tokens, cost FROM daily_project")
        self.assertEqual(
            cur.fetchall(),
            [("2026-08-01", "claude_code", "/home/user/demo", 100, 0.01)],
        )
        cur.execute("SELECT date, model, tokens, cost FROM daily_model")
        self.assertEqual(cur.fetchall(), [("2026-08-01", "__all__", 500, 0.05)])
        con.close()

    def test_record_snapshot_replaces_existing_day_not_deletes_absent_ones(self):
        sources_day1 = {
            "claude_code": {"/home/user/demo": {"by_day": {
                "2026-08-01": {"tokens": 100, "cost": 0.01},
                "2026-08-02": {"tokens": 200, "cost": 0.02},
            }}},
            "codex": {}, "opencode": {}, "openrouter": {"unavailable": True, "reason": "x"},
        }
        history.record_snapshot(sources_day1, db_path=self.db_path)

        # Second snapshot: 2026-08-01 has grown (as if more usage happened that
        # day before the provider's retention window moved past it), and
        # 2026-08-02 is no longer present (provider stopped returning it).
        sources_day2 = {
            "claude_code": {"/home/user/demo": {"by_day": {
                "2026-08-01": {"tokens": 150, "cost": 0.015},
            }}},
            "codex": {}, "opencode": {}, "openrouter": {"unavailable": True, "reason": "x"},
        }
        history.record_snapshot(sources_day2, db_path=self.db_path)

        con = sqlite3.connect(self.db_path)
        cur = con.cursor()
        cur.execute("SELECT date, tokens FROM daily_project ORDER BY date")
        rows = cur.fetchall()
        con.close()

        self.assertEqual(rows, [("2026-08-01", 150), ("2026-08-02", 200)])

    def test_query_history_filters_by_days_and_orders_ascending(self):
        sources = {
            "claude_code": {"/home/user/demo": {"by_day": {
                "2026-01-01": {"tokens": 10, "cost": 0.001},
                "2026-08-01": {"tokens": 20, "cost": 0.002},
            }}},
            "codex": {}, "opencode": {}, "openrouter": {"unavailable": True, "reason": "x"},
        }
        history.record_snapshot(sources, db_path=self.db_path)

        result = history.query_history(days=30, db_path=self.db_path)

        dates = [row["date"] for row in result["daily_project"]]
        self.assertEqual(dates, ["2026-08-01"])


if __name__ == "__main__":
    unittest.main()
