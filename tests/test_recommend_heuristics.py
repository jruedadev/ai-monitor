import unittest

from recommend import cluster, heuristics
from recommend.prompts import Prompt

LOG = "Traceback (most recent call last):\n  File \"x.py\", line 1\nValueError: boom"


def p(text, session, day="2026-09-20"):
    return Prompt("claude_code", "/home/u/DEV/ACME/app", session, day, text)


def build(texts):
    return cluster._build("c1", [p(t, f"s{i}", f"2026-09-2{i % 3}") for i, t in enumerate(texts)], {})


class TestClassify(unittest.TestCase):
    def test_rules(self):
        f = lambda **kw: {"pega_datos": False, "menciona_servicio": [], "mismos_pasos": False, **kw}
        self.assertEqual(heuristics.classify(f(pega_datos=True, menciona_servicio=["jira"])), "plugin")
        self.assertEqual(heuristics.classify(f(menciona_servicio=["jira"])), "prompt")
        self.assertEqual(heuristics.classify(f(mismos_pasos=True)), "skill")
        self.assertEqual(heuristics.classify(f(pega_datos=True)), "prompt")
        self.assertEqual(heuristics.classify(f()), "prompt")
        self.assertEqual(heuristics.classify(f(pega_datos=True, menciona_servicio=["jira"], mismos_pasos=True)),
                         "plugin")


class TestRecommend(unittest.TestCase):
    def test_skill_has_frontmatter_and_steps(self):
        rec = heuristics.recommend(build(["revisa y corrige y luego ejecuta los tests del módulo de pagos"] * 3))
        self.assertEqual((rec["kind"], rec["generator"]), ("skill", "reglas"))
        self.assertTrue(rec["draft"].startswith("---\nname: revisa-corrige-luego-ejecuta-tests\n"))
        self.assertIn("1. Revisa", rec["draft"])
        self.assertIn("3. Ejecuta", rec["draft"])
        self.assertIn("3 sesiones", rec["description"])

    def test_plugin_names_the_service(self):
        rec = heuristics.recommend(build(["mira este error de sentry y arréglalo: " + LOG] * 3))
        self.assertEqual(rec["kind"], "plugin")
        self.assertIn("claude mcp add sentry", rec["draft"])
        self.assertIn("sentry", rec["description"])

    def test_prompt_quotes_snippets(self):
        text = "explícame cómo funciona el patrón repositorio en esta aplicación hexagonal"
        rec = heuristics.recommend(build([text] * 3))
        self.assertEqual(rec["kind"], "prompt")
        self.assertIn("CLAUDE.md", rec["draft"])
        self.assertIn(f"- {text}", rec["draft"])

    def test_limits_and_redaction(self):
        rec = heuristics.recommend(build(["escribe a ana@acme.com sobre " + "palabra " * 700] * 3))
        self.assertLessEqual(len(rec["pattern"]), 120)
        self.assertLessEqual(len(rec["description"]), 400)
        self.assertLessEqual(len(rec["draft"]), 8000)
        self.assertNotIn("ana@acme.com", rec["draft"])
