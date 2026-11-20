import os
import unittest

import accounts


def acct(**kw):
    base = {
        "id": "personal",
        "provider": "claude_code",
        "label": "Personal",
        "location": "/home/u/.claude",
        "default": True,
        "monthly_cost": 20,
        "start_date": "2026-01-05",
    }
    base.update(kw)
    return base


def robc(**kw):
    base = dict(id="robc", label="Robc", location="/home/u/.claude-robc",
                default=False, monthly_cost=100, start_date="2026-02-01")
    base.update(kw)
    return acct(**base)


class TestNormalize(unittest.TestCase):
    def test_location_is_normalised(self):
        out = accounts.normalize_accounts([acct(location="/home/u/./x/../.claude/"), robc()])
        self.assertEqual(out[0]["location"], "/home/u/.claude")

    def test_rejects_duplicate_locations_after_normalising(self):
        with self.assertRaises(accounts.AccountsError):
            accounts.normalize_accounts([acct(), robc(location="/home/u/x/../.claude/")])

    def test_rejects_location_ending_in_projects(self):
        with self.assertRaises(accounts.AccountsError) as ctx:
            accounts.normalize_accounts([acct(location="/home/u/.claude/projects/"), robc()])
        self.assertIn("projects", str(ctx.exception))

    def test_normalize_accepts_two_claude_accounts(self):
        payload = [acct(), robc()]
        self.assertEqual(accounts.normalize_accounts(payload), payload)

    def test_rejects_two_defaults_for_same_provider(self):
        with self.assertRaises(accounts.AccountsError):
            accounts.normalize_accounts([acct(), robc(default=True)])

    def test_rejects_missing_default(self):
        with self.assertRaises(accounts.AccountsError):
            accounts.normalize_accounts([acct(default=False), robc()])

    def test_rejects_duplicate_id(self):
        with self.assertRaises(accounts.AccountsError):
            accounts.normalize_accounts([acct(id="robc"), robc()])

    def test_rejects_reserved_id(self):
        for reserved in ("all", "openrouter"):
            with self.assertRaises(accounts.AccountsError):
                accounts.normalize_accounts([acct(), robc(id=reserved)])

    def test_rejects_unknown_provider(self):
        with self.assertRaises(accounts.AccountsError):
            accounts.normalize_accounts([acct(), robc(provider="cursor")])

    def test_rejects_relative_location(self):
        with self.assertRaises(accounts.AccountsError):
            accounts.normalize_accounts([acct(location="data/claude")])

    def test_rejects_bad_start_date(self):
        with self.assertRaises(accounts.AccountsError):
            accounts.normalize_accounts([acct(start_date="19/11/2026")])

    def test_rejects_negative_cost(self):
        with self.assertRaises(accounts.AccountsError):
            accounts.normalize_accounts([acct(monthly_cost=-1)])

    def test_rejects_empty_list(self):
        self.assertRaises(accounts.AccountsError, accounts.normalize_accounts, [])

    def test_rejects_trailing_newline_in_id_and_date(self):
        with self.assertRaises(accounts.AccountsError):
            accounts.normalize_accounts([acct(), robc(id="abc\n")])
        with self.assertRaises(accounts.AccountsError):
            accounts.normalize_accounts([acct(start_date="2026-01-05\n")])

    def test_rejects_non_finite_cost(self):
        for bad in (float("nan"), float("inf")):
            with self.assertRaises(accounts.AccountsError):
                accounts.normalize_accounts([acct(monthly_cost=bad)])


class TestLegacy(unittest.TestCase):
    def test_legacy_seeds_personal_from_roi_keys(self):
        got = accounts.legacy_accounts(
            {"subscription_cost_claude": 20, "subscription_start_claude": "2026-01-05"})
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["id"], "personal")
        self.assertTrue(got[0]["default"])
        self.assertEqual(got[0]["monthly_cost"], 20)
        self.assertEqual(got[0]["start_date"], "2026-01-05")
        self.assertEqual(got[0]["location"], os.path.expanduser("~/.claude"))

    def test_legacy_without_keys_still_returns_personal(self):
        got = accounts.legacy_accounts({})
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["id"], "personal")
        self.assertIsNone(got[0]["monthly_cost"])


class TestSourceNames(unittest.TestCase):
    def test_source_name_default_vs_extra(self):
        self.assertEqual(accounts.source_name(acct()), "claude_code")
        self.assertEqual(accounts.source_name(robc()), "claude_code@robc")

    def test_provider_of_source_and_is_claude_source(self):
        self.assertEqual(accounts.provider_of_source("claude_code@robc"), "claude_code")
        self.assertTrue(accounts.is_claude_source("claude_code@robc"))
        self.assertTrue(accounts.is_claude_source("claude_code"))
        self.assertFalse(accounts.is_claude_source("codex"))


if __name__ == "__main__":
    unittest.main()
