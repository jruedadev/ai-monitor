import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from collectors.claude_code import collect as claude_code_real
from main import collect_all, combine_projects


class TestCombineProjects(unittest.TestCase):
    def test_sums_matching_projects_across_sources(self):
        claude = {"/home/user/demo": {"total_tokens": 100, "cost": 0.1, "messages": 2, "session_count": 1}}
        codex = {"/home/user/demo": {"total_tokens": 50, "cost": 0.05, "messages": 1, "session_count": 1}}
        opencode = {"/home/user/other": {"total_tokens": 30, "cost": 0.02, "messages": 1, "session_count": 1}}
        hermes = {}

        combined = combine_projects({"claude_code": claude, "codex": codex,
                                     "opencode": opencode, "hermes": hermes})

        self.assertEqual(combined["/home/user/demo"]["total_tokens"], 150)
        self.assertAlmostEqual(combined["/home/user/demo"]["cost"], 0.15)
        self.assertEqual(sorted(combined["/home/user/demo"]["by_source"]), ["claude_code", "codex"])
        self.assertEqual(combined["/home/user/other"]["total_tokens"], 30)
        self.assertEqual(combined["/home/user/other"]["by_source"], ["opencode"])


    def test_combine_projects_sums_all_claude_accounts(self):
        p = {"total_tokens": 10, "messages": 1, "session_count": 1}
        combined = combine_projects({
            "claude_code": {"/p": {**p, "cost": 1}},
            "claude_code@robc": {"/p": {**p, "cost": 2}},
        })
        self.assertEqual(combined["/p"]["cost"], 3)
        self.assertEqual(combined["/p"]["total_tokens"], 20)
        self.assertEqual(sorted(combined["/p"]["by_source"]), ["claude_code", "claude_code@robc"])

    def test_combine_projects_excludes_openrouter(self):
        combined = combine_projects({
            "claude_code": {},
            "openrouter": {"/p": {"total_tokens": 5, "cost": 9, "messages": 1, "session_count": 1}},
        })
        self.assertEqual(combined, {})


def _account(id_, location, default=False):
    return {"id": id_, "provider": "claude_code", "label": id_, "location": location,
            "default": default, "monthly_cost": None, "start_date": None}


class TestCollectAllAccounts(unittest.TestCase):
    def _patch_others(self):
        return [patch("main.codex.collect", return_value={}),
                patch("main.opencode.collect", return_value={}),
                patch("main.hermes.collect", return_value={}),
                patch("main.openrouter.collect", return_value={"unavailable": True, "reason": "x"}),
                patch("main.history.record_snapshot")]

    def test_collect_all_calls_claude_once_per_account(self):
        accounts = [_account("personal", "/a/.claude", True), _account("robc", "/b/.claude-robc")]
        patches = self._patch_others()
        for p in patches:
            p.start()
        try:
            with patch("main.claude_code.collect", return_value={}) as collect:
                result = collect_all(account_list=accounts)
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(collect.call_count, 2)
        dirs = [c.kwargs["projects_dir"] for c in collect.call_args_list]
        self.assertEqual(dirs, ["/a/.claude/projects", "/b/.claude-robc/projects"])
        self.assertIn("claude_code", result)
        self.assertIn("claude_code@robc", result)
        for key in ("codex", "opencode", "hermes", "openrouter"):
            self.assertIn(key, result)

    def test_collect_all_skips_missing_dir_without_error(self):
        accounts = [_account("personal", "/a/.claude", True),
                    _account("ghost", "/no/existe/jamas")]
        patches = self._patch_others()
        for p in patches:
            p.start()
        try:
            with patch("main.claude_code.collect",
                       side_effect=lambda projects_dir=None, db_path=None:
                       claude_code_real(projects_dir=projects_dir)):
                result = collect_all(account_list=accounts)
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(result["claude_code@ghost"], {})


class TestCollectAll(unittest.TestCase):
    def test_collect_all_persists_snapshot_to_history(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            fake_sources = {
                "claude_code": {"/home/user/demo": {"by_day": {"2026-08-01": {"tokens": 10, "cost": 0.01}}}},
                "codex": {}, "opencode": {}, "hermes": {}, "openrouter": {"unavailable": True, "reason": "x"},
            }
            with patch("main.claude_code.collect", return_value=fake_sources["claude_code"]), \
                 patch("main.codex.collect", return_value={}), \
                 patch("main.opencode.collect", return_value={}), \
                 patch("main.hermes.collect", return_value={}), \
                 patch("main.openrouter.collect", return_value={"unavailable": True, "reason": "x"}):
                collect_all(db_path=tmp.name)

            import sqlite3
            con = sqlite3.connect(tmp.name)
            cur = con.cursor()
            cur.execute("SELECT date, tokens FROM daily_project")
            rows = cur.fetchall()
            con.close()
            self.assertEqual(rows, [("2026-08-01", 10)])
        finally:
            os.unlink(tmp.name)


class TestBriefingFlag(unittest.TestCase):
    def test_briefing_flag_collects_then_prints_summary(self):
        fake = {"claude_code": {}, "codex": {}, "opencode": {}, "hermes": {},
                "openrouter": {"unavailable": True, "reason": "x"}}
        out = io.StringIO()
        with patch("sys.argv", ["main.py", "--briefing"]), \
             patch("main.collect_all", return_value=fake) as collect, \
             patch("main.briefing.get_briefing", return_value={"stub": True}) as get, \
             patch("main.briefing.format_briefing", return_value="RESUMEN") as fmt, \
             redirect_stdout(out):
            import main as main_module
            main_module.main()
        collect.assert_called_once()
        get.assert_called_once_with()
        fmt.assert_called_once_with({"stub": True})
        self.assertEqual(out.getvalue().strip(), "RESUMEN")


if __name__ == "__main__":
    unittest.main()
