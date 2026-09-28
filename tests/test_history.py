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

    def test_record_snapshot_normalizes_datetime_day_keys(self):
        sources = {
            "claude_code": {},
            "codex": {},
            "opencode": {},
            "openrouter": {
                "unavailable": False,
                "by_day": {"2026-08-12 00:00:00": {"tokens": 500, "cost": 0.05}},
            },
        }

        history.record_snapshot(sources, db_path=self.db_path)

        con = sqlite3.connect(self.db_path)
        rows = con.execute("SELECT date, tokens FROM daily_model").fetchall()
        con.close()
        self.assertEqual(rows, [("2026-08-12", 500)])

    def test_ensure_schema_migrates_legacy_datetime_rows_preferring_canonical(self):
        con = sqlite3.connect(self.db_path)
        con.executescript(history._SCHEMA)
        con.execute(
            "INSERT INTO daily_project (date, source, project, tokens, cost) VALUES (?, ?, ?, ?, ?)",
            ("2026-08-12 00:00:00", "claude_code", "/home/user/demo", 100, 0.01),
        )
        con.execute(
            "INSERT INTO daily_project (date, source, project, tokens, cost) VALUES (?, ?, ?, ?, ?)",
            ("2026-08-12", "claude_code", "/home/user/demo", 50, 0.005),
        )
        con.execute(
            "INSERT INTO daily_model (date, model, tokens, cost) VALUES (?, ?, ?, ?)",
            ("2026-08-12 00:00:00", "__all__", 500, 0.05),
        )
        con.execute(
            "INSERT INTO daily_model (date, model, tokens, cost) VALUES (?, ?, ?, ?)",
            ("2026-08-12", "__all__", 700, 0.07),
        )
        con.commit()
        con.close()

        history.ensure_schema(self.db_path)

        con = sqlite3.connect(self.db_path)
        project_rows = con.execute(
            "SELECT date, source, project, tokens, cost FROM daily_project"
        ).fetchall()
        model_rows = con.execute("SELECT date, model, tokens, cost FROM daily_model").fetchall()
        con.close()
        self.assertEqual(
            project_rows, [("2026-08-12", "claude_code", "/home/user/demo", 50, 0.005)]
        )
        self.assertEqual(model_rows, [("2026-08-12", "__all__", 700, 0.07)])

    def test_ensure_schema_keeps_legacy_row_when_no_canonical_exists(self):
        con = sqlite3.connect(self.db_path)
        con.executescript(history._SCHEMA)
        con.execute(
            "INSERT INTO daily_model (date, model, tokens, cost) VALUES (?, ?, ?, ?)",
            ("2026-07-01 00:00:00", "__all__", 300, 0.03),
        )
        con.commit()
        con.close()

        history.ensure_schema(self.db_path)

        con = sqlite3.connect(self.db_path)
        model_rows = con.execute("SELECT date, model, tokens, cost FROM daily_model").fetchall()
        con.close()
        self.assertEqual(model_rows, [("2026-07-01", "__all__", 300, 0.03)])

    def test_query_history_filters_by_days_and_orders_ascending(self):
        from datetime import datetime, timedelta, timezone

        today = datetime.now(timezone.utc).date()
        recent = today - timedelta(days=5)
        old = today - timedelta(days=120)
        sources = {
            "claude_code": {"/home/user/demo": {"by_day": {
                old.isoformat(): {"tokens": 10, "cost": 0.001},
                recent.isoformat(): {"tokens": 20, "cost": 0.002},
            }}},
            "codex": {}, "opencode": {}, "openrouter": {"unavailable": True, "reason": "x"},
        }
        history.record_snapshot(sources, db_path=self.db_path)

        result = history.query_history(days=30, db_path=self.db_path)

        dates = [row["date"] for row in result["daily_project"]]
        self.assertEqual(dates, [recent.isoformat()])

    def test_get_roi_settings_defaults_to_none_values(self):
        settings = history.get_roi_settings(db_path=self.db_path)
        self.assertEqual(
            settings,
            {
                "subscription_cost_claude": None,
                "subscription_cost_codex": None,
                "hourly_rate": None,
                "subscription_start_claude": None,
                "subscription_start_codex": None,
            },
        )

    def test_save_and_get_roi_subscription_start_dates_roundtrip(self):
        history.save_roi_settings(
            {"subscription_start_claude": "2026-04-01", "subscription_start_codex": "2026-06-15"},
            db_path=self.db_path,
        )

        settings = history.get_roi_settings(db_path=self.db_path)

        self.assertEqual(settings["subscription_start_claude"], "2026-04-01")
        self.assertEqual(settings["subscription_start_codex"], "2026-06-15")

    def test_save_and_get_roi_settings_roundtrip(self):
        history.save_roi_settings(
            {"subscription_cost_claude": 20.0, "subscription_cost_codex": 25.0, "hourly_rate": 35.5},
            db_path=self.db_path,
        )

        settings = history.get_roi_settings(db_path=self.db_path)

        self.assertEqual(
            settings,
            {
                "subscription_cost_claude": 20.0,
                "subscription_cost_codex": 25.0,
                "hourly_rate": 35.5,
                "subscription_start_claude": None,
                "subscription_start_codex": None,
            },
        )

    def test_save_roi_settings_partial_update_keeps_other_keys(self):
        history.save_roi_settings({"subscription_cost_claude": 20.0}, db_path=self.db_path)
        history.save_roi_settings({"hourly_rate": 40.0}, db_path=self.db_path)

        settings = history.get_roi_settings(db_path=self.db_path)

        self.assertEqual(settings["subscription_cost_claude"], 20.0)
        self.assertEqual(settings["hourly_rate"], 40.0)


class TestValidateRoiSettings(unittest.TestCase):
    def test_accepts_valid_numbers_dates_and_nulls(self):
        history.validate_roi_settings({
            "subscription_cost_claude": 20.0,
            "subscription_cost_codex": 0,
            "hourly_rate": None,
            "subscription_start_claude": "2026-09-15",
            "subscription_start_codex": None,
        })  # no debe lanzar

    def test_rejects_non_dict_body(self):
        with self.assertRaises(history.RoiSettingsError):
            history.validate_roi_settings([1, 2, 3])

    def test_rejects_unknown_key(self):
        with self.assertRaises(history.RoiSettingsError):
            history.validate_roi_settings({"not_a_real_key": 1})

    def test_rejects_bool_for_numeric_key(self):
        with self.assertRaises(history.RoiSettingsError):
            history.validate_roi_settings({"hourly_rate": True})

    def test_rejects_string_for_numeric_key(self):
        with self.assertRaises(history.RoiSettingsError):
            history.validate_roi_settings({"subscription_cost_claude": "20"})

    def test_rejects_malformed_date(self):
        with self.assertRaises(history.RoiSettingsError):
            history.validate_roi_settings({"subscription_start_claude": "15-09-2026"})

    def test_rejects_numeric_date(self):
        with self.assertRaises(history.RoiSettingsError):
            history.validate_roi_settings({"subscription_start_claude": 20260915.0})


if __name__ == "__main__":
    unittest.main()
