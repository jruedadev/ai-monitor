import os
import sqlite3
import tempfile
import unittest

import history

ROOTS = [{"root": "/srv/trabajo", "mode": "plano"}, {"root": "DEV", "mode": "cliente"}]


class AppSettingsTestCase(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "history.db")


class TestGet(AppSettingsTestCase):
    def test_defaults_on_empty_db(self):
        self.assertEqual(history.get_app_settings(self.db),
                         {"client_roots": [{"root": "DEV", "mode": "cliente"}], "onboarding_completed_at": None})

    def test_old_db_without_table_gets_it_created(self):
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE daily_project (date TEXT, source TEXT, project TEXT, tokens INTEGER, cost REAL)")
        con.commit()
        con.close()
        self.assertIsNone(history.get_app_settings(self.db)["onboarding_completed_at"])

    def test_corrupt_values_fall_back_per_key(self):
        history.ensure_schema(self.db)
        con = sqlite3.connect(self.db)
        con.execute("INSERT INTO app_settings VALUES ('client_roots', '{roto', 'x')")
        con.execute("INSERT INTO app_settings VALUES ('onboarding_completed_at', '42', 'x')")
        con.commit()
        con.close()
        self.assertEqual(history.get_app_settings(self.db),
                         {"client_roots": [{"root": "DEV", "mode": "cliente"}], "onboarding_completed_at": None})


class TestSave(AppSettingsTestCase):
    def test_roundtrip_normalizes(self):
        clean = history.validate_app_settings({"client_roots": [{"root": "/srv/trabajo/", "mode": "plano"},
                                                                {"root": " DEV ", "mode": "cliente"}]})
        history.save_app_settings(clean, self.db)
        self.assertEqual(history.get_app_settings(self.db)["client_roots"], ROOTS)

    def test_validation_errors(self):
        for payload in ([1], {}, {"otra": 1}, {"client_roots": []},
                        {"client_roots": ROOTS, "onboarding_completed_at": "2026-01-01"}):
            with self.subTest(payload=payload), self.assertRaises(history.AppSettingsError):
                history.validate_app_settings(payload)

    def test_complete_onboarding_is_idempotent(self):
        first = history.complete_onboarding(self.db, now="2026-09-29T10:00:00+00:00")
        self.assertEqual(first, "2026-09-29T10:00:00+00:00")
        history.complete_onboarding(self.db, now="2026-09-30T10:00:00+00:00")
        self.assertEqual(history.get_app_settings(self.db)["onboarding_completed_at"], "2026-09-30T10:00:00+00:00")

    def test_complete_onboarding_default_now_is_utc_iso(self):
        stamp = history.complete_onboarding(self.db)
        self.assertTrue(stamp.endswith("+00:00"))


if __name__ == "__main__":
    unittest.main()
