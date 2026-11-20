import os
import sqlite3
import tempfile
import unittest

import history
import accounts

ROOTS = [{"root": "/srv/trabajo", "mode": "plano"}, {"root": "DEV", "mode": "cliente"}]


class AppSettingsTestCase(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "history.db")


def _acc(acc_id, default, cost=None, location="/home/u/.claude-x"):
    return {"id": acc_id, "provider": "claude_code", "label": acc_id.title(), "location": location,
            "default": default, "monthly_cost": cost, "start_date": None}


class TestAccounts(AppSettingsTestCase):
    def test_get_app_settings_without_accounts_seeds_personal(self):
        history.save_roi_settings({"subscription_cost_claude": 20}, self.db)
        result = history.get_app_settings(self.db)["accounts"]
        self.assertEqual(len(result), 1)
        self.assertEqual((result[0]["id"], result[0]["monthly_cost"]), ("personal", 20))

    def test_save_and_read_accounts_roundtrip(self):
        accs = [_acc("personal", True, 20, "/home/u/.claude"), _acc("robc", False, 100)]
        clean = history.validate_app_settings({"client_roots": ROOTS, "accounts": accs})
        history.save_app_settings(clean, self.db)
        self.assertEqual(history.get_app_settings(self.db)["accounts"], accs)

    def test_corrupt_accounts_fall_back_to_legacy(self):
        history.ensure_schema(self.db)
        con = sqlite3.connect(self.db)
        con.execute("INSERT INTO app_settings VALUES ('accounts', '[]', 'x')")
        con.commit()
        con.close()
        self.assertEqual(history.get_app_settings(self.db)["accounts"][0]["id"], "personal")

    def test_save_without_accounts_keeps_stored_accounts(self):
        accs = [_acc("robc", True, 5)]
        history.save_app_settings(
            history.validate_app_settings({"client_roots": ROOTS, "accounts": accs}), self.db)
        history.save_app_settings(history.validate_app_settings({"client_roots": ROOTS}), self.db)
        self.assertEqual(history.get_app_settings(self.db)["accounts"], accs)

    def test_validate_rejects_two_defaults(self):
        with self.assertRaises(history.AppSettingsError):
            history.validate_app_settings(
                {"client_roots": [], "accounts": [_acc("a", True), _acc("b", True)]})

    def test_validate_rejects_empty_accounts(self):
        with self.assertRaises(history.AppSettingsError):
            history.validate_app_settings({"client_roots": ROOTS, "accounts": []})

    def test_validate_still_requires_client_roots(self):
        with self.assertRaises(history.AppSettingsError):
            history.validate_app_settings({"accounts": [_acc("a", True)]})

    def test_unknown_key_still_rejected(self):
        with self.assertRaises(history.AppSettingsError):
            history.validate_app_settings({"client_roots": [], "foo": 1})


class TestDefaultAccountGuard(AppSettingsTestCase):
    def _save(self, accs):
        stored = history.saved_accounts(self.db)
        clean = history.validate_app_settings({"client_roots": ROOTS, "accounts": accs}, stored=stored)
        history.save_app_settings(clean, self.db)

    def _initial(self):
        self._save([_acc("personal", True, 20, "/home/u/.claude"), _acc("robc", False, 100)])

    def test_changing_default_account_is_rejected_without_writing(self):
        self._initial()
        before = history.get_app_settings(self.db)["accounts"]
        with self.assertRaises(history.AppSettingsError) as ctx:
            self._save([_acc("personal", False, 20, "/home/u/.claude"), _acc("robc", True, 100)])
        self.assertIn("por defecto", str(ctx.exception))
        self.assertEqual(history.get_app_settings(self.db)["accounts"], before)

    def test_changing_default_location_is_rejected(self):
        self._initial()
        with self.assertRaises(history.AppSettingsError):
            self._save([_acc("personal", True, 20, "/home/u/.otra"), _acc("robc", False, 100)])

    def test_same_default_with_new_label_is_accepted(self):
        self._initial()
        renamed = _acc("personal", True, 20, "/home/u/.claude")
        renamed["label"] = "Mi cuenta"
        self._save([renamed, _acc("robc", False, 100)])
        self.assertEqual(history.get_app_settings(self.db)["accounts"][0]["label"], "Mi cuenta")

    def test_first_save_has_no_stored_default_to_protect(self):
        self._save([_acc("robc", True, 5)])
        self.assertEqual(history.get_app_settings(self.db)["accounts"][0]["id"], "robc")

    def test_saving_accounts_syncs_default_plan_into_roi_settings(self):
        accs = [_acc("personal", True, 20, "/home/u/.claude"), _acc("robc", False, 100)]
        accs[0]["start_date"] = "2026-01-05"
        self._save(accs)
        roi = history.get_roi_settings(self.db)
        self.assertEqual(roi["subscription_cost_claude"], 20)
        self.assertEqual(roi["subscription_start_claude"], "2026-01-05")


class TestGet(AppSettingsTestCase):
    def test_defaults_on_empty_db(self):
        result = history.get_app_settings(self.db)
        self.assertEqual(result.pop("accounts"), accounts.legacy_accounts(history.get_roi_settings(self.db)))
        self.assertEqual(result,
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
        result = history.get_app_settings(self.db)
        self.assertEqual(result.pop("accounts"), accounts.legacy_accounts(history.get_roi_settings(self.db)))
        self.assertEqual(result,
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
