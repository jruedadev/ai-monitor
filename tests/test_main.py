import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from main import collect_all, combine_projects


class TestCombineProjects(unittest.TestCase):
    def test_sums_matching_projects_across_sources(self):
        claude = {"/home/user/demo": {"total_tokens": 100, "cost": 0.1, "messages": 2, "session_count": 1}}
        codex = {"/home/user/demo": {"total_tokens": 50, "cost": 0.05, "messages": 1, "session_count": 1}}
        opencode = {"/home/user/other": {"total_tokens": 30, "cost": 0.02, "messages": 1, "session_count": 1}}
        hermes = {}

        combined = combine_projects(claude, codex, opencode, hermes)

        self.assertEqual(combined["/home/user/demo"]["total_tokens"], 150)
        self.assertAlmostEqual(combined["/home/user/demo"]["cost"], 0.15)
        self.assertEqual(sorted(combined["/home/user/demo"]["by_source"]), ["claude_code", "codex"])
        self.assertEqual(combined["/home/user/other"]["total_tokens"], 30)
        self.assertEqual(combined["/home/user/other"]["by_source"], ["opencode"])


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
