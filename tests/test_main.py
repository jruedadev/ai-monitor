import unittest

from main import combine_projects


class TestCombineProjects(unittest.TestCase):
    def test_sums_matching_projects_across_sources(self):
        claude = {"/home/user/demo": {"total_tokens": 100, "cost": 0.1, "messages": 2, "session_count": 1}}
        codex = {"/home/user/demo": {"total_tokens": 50, "cost": 0.05, "messages": 1, "session_count": 1}}
        opencode = {"/home/user/other": {"total_tokens": 30, "cost": 0.02, "messages": 1, "session_count": 1}}

        combined = combine_projects(claude, codex, opencode)

        self.assertEqual(combined["/home/user/demo"]["total_tokens"], 150)
        self.assertAlmostEqual(combined["/home/user/demo"]["cost"], 0.15)
        self.assertEqual(sorted(combined["/home/user/demo"]["by_source"]), ["claude_code", "codex"])
        self.assertEqual(combined["/home/user/other"]["total_tokens"], 30)
        self.assertEqual(combined["/home/user/other"]["by_source"], ["opencode"])


if __name__ == "__main__":
    unittest.main()
