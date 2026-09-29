import unittest
from datetime import date

from recommend import cost

TODAY = date(2026, 9, 20)
APP = "/home/u/DEV/ACME/app"
OTHER = "/home/u/DEV/OTRO/x"


def row(day, source="claude_code", project=APP, tokens=1000, cost_usd=1.0):
    return {"date": day, "source": source, "project": project, "tokens": tokens, "cost": cost_usd}


class TestCost(unittest.TestCase):
    def test_project_from_link(self):
        self.assertEqual(cost.project_from_link("/proyectos/ACME?proyecto=%2Fhome%2Fu%2FDEV%2FACME%2Fapp"), APP)
        self.assertIsNone(cost.project_from_link("/configuracion"))

    def test_concentration_and_spike_become_cost_recommendations(self):
        rows = [row(f"2026-09-{d:02d}") for d in range(1, 8)] + [row("2026-09-08", cost_usd=20.0)]
        rows += [row("2026-09-02", project=OTHER, cost_usd=0.5)]
        recs = cost.cost_recommendations(rows, [], {"subscription_cost_claude": 20}, TODAY)
        by_rule = {r["signature"]["rule"]: r for r in recs}
        self.assertEqual(set(by_rule), {"spike_day", "project_concentration"})

        spike = by_rule["spike_day"]
        self.assertEqual((spike["kind"], spike["impact"], spike["generator"], spike["tool"]),
                         ("costo", "alto", "costo", "claude_code"))
        self.assertEqual(spike["signature"], {"rule": "spike_day", "source": "claude_code", "project": None})
        self.assertEqual(spike["evidence"]["link"], "/actividad?dia=2026-09-08")
        self.assertEqual(spike["evidence"]["sources"], ["claude_code"])
        self.assertEqual(spike["tokens"], 9000)

        conc = by_rule["project_concentration"]
        self.assertEqual(conc["impact"], "medio")
        self.assertEqual(conc["signature"]["project"], APP)
        self.assertEqual(conc["evidence"]["projects"], [APP])
        self.assertIn("app", conc["draft"])
        for rec in recs:
            self.assertLessEqual(len(rec["pattern"]), 120)
            self.assertLessEqual(len(rec["description"]), 400)
            self.assertTrue(rec["draft"])

    def test_concentration_link_uses_saved_roots(self):
        rows = [row(f"2026-09-{d:02d}") for d in range(1, 8)] + [row("2026-09-08", cost_usd=20.0)]
        rows += [row("2026-09-02", project=OTHER, cost_usd=0.5)]
        roots = [{"root": "ACME", "mode": "cliente"}]
        recs = cost.cost_recommendations(rows, [], {}, TODAY, roots=roots)
        conc = next(r for r in recs if r["signature"]["rule"] == "project_concentration")
        self.assertTrue(conc["evidence"]["link"].startswith("/proyectos/app?"), conc["evidence"]["link"])

    def test_informative_rules_are_not_persisted(self):
        rows = [row(f"2026-09-{d:02d}", cost_usd=None) for d in range(1, 4)]
        recs = cost.cost_recommendations(rows, [], {}, TODAY)
        self.assertNotIn("cost_incomplete", {r["signature"]["rule"] for r in recs})

    def test_subscription_missing_per_source(self):
        rows = [row(f"2026-09-{d:02d}", source="codex", project=APP, cost_usd=0.1) for d in range(1, 5)]
        rows += [row(f"2026-09-{d:02d}", source="codex", project=OTHER, cost_usd=0.1) for d in range(1, 5)]
        recs = cost.cost_recommendations(rows, [], {}, TODAY)
        subs = [r for r in recs if r["signature"]["rule"] == "subscription_missing"]
        self.assertEqual([r["signature"]["source"] for r in subs], ["codex"])
        self.assertEqual(subs[0]["evidence"]["link"], "/configuracion")

    def test_no_rows_no_recommendations(self):
        self.assertEqual(cost.cost_recommendations([], [], {}, TODAY), [])
