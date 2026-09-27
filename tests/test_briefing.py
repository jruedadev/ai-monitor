import json
import os
import unittest
from datetime import date

import briefing
import history

TODAY = date(2026, 9, 27)
APP = "/home/u/DEV/ACME/app"
NO_SETTINGS = {key: None for key in history.ROI_SETTINGS_KEYS}


def row(day, source="claude_code", project=APP, tokens=100, cost=1.0):
    return {"date": day, "source": source, "project": project, "tokens": tokens, "cost": cost}


def settings(**overrides):
    return {**NO_SETTINGS, **overrides}


def build(project_rows=(), model_rows=(), today=TODAY, source="all", compare=None, cfg=None):
    return briefing.build_briefing(
        list(project_rows), list(model_rows), cfg or NO_SETTINGS, today, source=source, compare=compare,
    )


class TestFormat(unittest.TestCase):
    def test_usd_matches_es_co(self):
        self.assertEqual(briefing.format_usd(1234.5), "$ 1.234,50")
        self.assertEqual(briefing.format_usd(-3), "-$ 3,00")
        self.assertEqual(briefing.format_usd(0.004), "$ 0,00")

    def test_int_ratio_and_day(self):
        self.assertEqual(briefing.format_int(953620952), "953.620.952")
        self.assertEqual(briefing.format_ratio(7.94), "7,9")
        self.assertEqual(briefing.format_day("2026-09-27"), "27 sept")
        self.assertEqual(briefing.format_day("2026-01-05"), "5 ene")


class TestWindows(unittest.TestCase):
    def test_month_window_clips_to_short_month(self):
        self.assertEqual(briefing.month_window("2026-02", 31), ("2026-02-01", "2026-02-28"))
        self.assertEqual(briefing.month_window("2028-02", 30), ("2028-02-01", "2028-02-29"))
        self.assertEqual(briefing.month_window("2026-09", 27), ("2026-09-01", "2026-09-27"))

    def test_previous_month_crosses_year(self):
        self.assertEqual(briefing.previous_month("2026-01"), "2025-12")
        self.assertEqual(briefing.previous_month("2026-10"), "2026-09")

    def test_month_coverage(self):
        self.assertEqual(briefing.month_coverage("2026-08", "2026-07-18"), ("full", None))
        self.assertEqual(briefing.month_coverage("2026-07", "2026-07-01"), ("full", None))
        self.assertEqual(briefing.month_coverage("2026-07", "2026-07-18"), ("partial", "2026-07-18"))
        self.assertIsNone(briefing.month_coverage("2026-06", "2026-07-18"))
        self.assertIsNone(briefing.month_coverage("2026-06", None))

    def test_eligible_months_descending_until_start(self):
        self.assertEqual(briefing.eligible_months("2026-07-18", "2026-09"), [
            {"month": "2026-08", "coverage": "full", "since": None},
            {"month": "2026-07", "coverage": "partial", "since": "2026-07-18"},
        ])
        self.assertEqual(briefing.eligible_months("2026-09-03", "2026-09"), [])
        self.assertEqual(briefing.eligible_months(None, "2026-09"), [])


class TestKpis(unittest.TestCase):
    def test_equivalent_window_against_previous_month(self):
        data = build([
            row("2026-08-01", cost=0, tokens=0),
            row("2026-08-27", cost=10, tokens=1000),
            row("2026-08-28", cost=99, tokens=9999),  # fuera del tramo equivalente
            row("2026-09-27", cost=5, tokens=500),
        ])
        self.assertEqual(data["window"], {"month": "2026-09", "from": "2026-09-01", "to": "2026-09-27"})
        self.assertEqual(data["compare"], {"month": "2026-08", "from": "2026-08-01", "to": "2026-08-27",
                                           "coverage": "full", "since": None})
        self.assertEqual(data["kpis"]["cost"], {"current": 5.0, "previous": 10.0, "delta_pct": -50.0})
        self.assertEqual(data["kpis"]["tokens"], {"current": 500, "previous": 1000, "delta_pct": -50.0})
        self.assertEqual(data["kpis"]["active_days"], {"current": 1, "previous": 1})
        self.assertFalse(data["kpis"]["cost_incomplete"])
        self.assertFalse(data["degraded"])

    def test_january_compares_against_december_of_previous_year(self):
        data = build([row("2025-12-31", cost=4), row("2026-01-31", cost=2)], today=date(2026, 1, 31))
        self.assertEqual(data["compare"]["month"], "2025-12")
        self.assertEqual(data["compare"]["to"], "2025-12-31")
        self.assertEqual(data["kpis"]["cost"]["previous"], 4.0)

    def test_march_30_compares_against_february_28(self):
        data = build([row("2026-02-10"), row("2026-03-30")], today=date(2026, 3, 30))
        self.assertEqual(data["compare"]["to"], "2026-02-28")

    def test_delta_is_null_when_previous_is_zero(self):
        data = build([row("2026-07-01", cost=3), row("2026-09-02", cost=2)])
        self.assertEqual(data["kpis"]["cost"]["previous"], 0.0)
        self.assertIsNone(data["kpis"]["cost"]["delta_pct"])

    def test_default_compare_without_data_is_coverage_none(self):
        data = build([row("2026-09-02")])
        self.assertEqual(data["compare"]["coverage"], "none")
        self.assertIsNone(data["compare"]["since"])
        self.assertIsNone(data["kpis"]["cost"]["previous"])
        self.assertIsNone(data["kpis"]["cost"]["delta_pct"])
        self.assertIsNone(data["kpis"]["active_days"]["previous"])
        self.assertEqual(data["eligible_months"], [])

    def test_explicit_compare_partial_month_is_marked(self):
        data = build([row("2026-07-18", cost=8), row("2026-09-02")], compare="2026-07")
        self.assertEqual(data["compare"]["coverage"], "partial")
        self.assertEqual(data["compare"]["since"], "2026-07-18")
        self.assertEqual(data["kpis"]["cost"]["previous"], 8.0)

    def test_invalid_parameters_raise_briefing_error(self):
        rows = [row("2026-07-18"), row("2026-09-02")]
        with self.assertRaises(briefing.BriefingError):
            build(rows, compare="2026-05")  # anterior al inicio de datos
        with self.assertRaises(briefing.BriefingError):
            build(rows, compare="2026-09")  # el mes actual no es comparable
        with self.assertRaises(briefing.BriefingError):
            build(rows, compare="2026-13")
        with self.assertRaises(briefing.BriefingError):
            build(rows, source="copilot")

    def test_null_cost_sums_zero_and_flags_incomplete(self):
        data = build([row("2026-09-01", cost=None), row("2026-09-02", cost=2)])
        self.assertEqual(data["kpis"]["cost"]["current"], 2.0)
        self.assertTrue(data["kpis"]["cost_incomplete"])

    def test_all_excludes_openrouter_and_openrouter_branch_uses_daily_model(self):
        model_rows = [{"date": "2026-09-03", "model": "__all__", "tokens": 70, "cost": 50.0},
                      {"date": "2026-09-03", "model": "gpt-x", "tokens": 1, "cost": 999.0}]
        all_data = build([row("2026-09-03", cost=1)], model_rows)
        self.assertEqual(all_data["kpis"]["cost"]["current"], 1.0)
        or_data = build([row("2026-09-03", cost=1)], model_rows, source="openrouter")
        self.assertEqual(or_data["kpis"]["cost"]["current"], 50.0)
        self.assertEqual(or_data["kpis"]["tokens"]["current"], 70)
        self.assertEqual(or_data["top_projects"], [])
        self.assertEqual(or_data["subscription"]["configured"], False)

    def test_single_source_filter(self):
        data = build([row("2026-09-03", cost=1), row("2026-09-03", source="codex", cost=7)], source="codex")
        self.assertEqual(data["source"], "codex")
        self.assertEqual(data["kpis"]["cost"]["current"], 7.0)


class TestSubscription(unittest.TestCase):
    def test_compare_costs_matches_roi_ts_rounding(self):
        self.assertEqual(briefing.compare_costs(657.10, 20.0), ("subscription", 637.1))
        self.assertEqual(briefing.compare_costs(5.0, 20.0), ("api", 15.0))
        self.assertEqual(briefing.compare_costs(20.004, 20.0), ("tie", 0.0))
        self.assertEqual(briefing.compare_costs(19.995, 20.0), ("tie", 0.0))  # Math.round(-0.5) = -0

    def test_not_configured_returns_nulls(self):
        data = build([row("2026-09-03")])
        self.assertEqual(data["subscription"], {"configured": False, "paid": None, "api_equivalent": None,
                                                "winner": None, "savings": None})

    def test_configured_subscription_wins(self):
        data = build([row("2026-09-03", cost=657.10)], cfg=settings(subscription_cost_claude=20.0))
        self.assertEqual(data["subscription"], {"configured": True, "paid": 20.0, "api_equivalent": 657.1,
                                                "winner": "subscription", "savings": 637.1})

    def test_only_configured_sources_count_toward_api_equivalent(self):
        rows = [row("2026-09-03", cost=30), row("2026-09-03", source="codex", cost=500)]
        data = build(rows, cfg=settings(subscription_cost_claude=20.0))
        self.assertEqual(data["subscription"]["api_equivalent"], 30.0)
        self.assertEqual(data["subscription"]["paid"], 20.0)

    def test_start_inside_month_counts_from_start(self):
        rows = [row("2026-09-10", cost=100), row("2026-09-20", cost=30)]
        data = build(rows, cfg=settings(subscription_cost_claude=20.0, subscription_start_claude="2026-09-15"))
        self.assertEqual(data["subscription"]["api_equivalent"], 30.0)

    def test_future_start_counts_nothing_and_never_negative(self):
        data = build([row("2026-09-10", cost=100)],
                     cfg=settings(subscription_cost_claude=20.0, subscription_start_claude="2026-10-05"))
        self.assertEqual(data["subscription"]["api_equivalent"], 0.0)
        self.assertEqual(data["subscription"]["winner"], "api")
        self.assertEqual(data["subscription"]["savings"], 20.0)

    def test_source_without_possible_subscription(self):
        data = build([row("2026-09-03", source="opencode")], source="opencode",
                     cfg=settings(subscription_cost_claude=20.0))
        self.assertFalse(data["subscription"]["configured"])


class TestTopProjects(unittest.TestCase):
    def test_top_three_by_cost_with_share_and_client(self):
        rows = [
            row("2026-09-03", project="/home/u/DEV/ACME/a", cost=50),
            row("2026-09-04", project="/home/u/DEV/ACME/a", cost=10),
            row("2026-09-03", project="/home/u/DEV/BETA/b", cost=30),
            row("2026-09-03", project="/home/u/tmp/c", cost=15),
            row("2026-09-03", project="/home/u/DEV/BETA/d", cost=5),
        ]
        top = build(rows)["top_projects"]
        self.assertEqual([p["project"] for p in top], ["/home/u/DEV/ACME/a", "/home/u/DEV/BETA/b", "/home/u/tmp/c"])
        self.assertEqual(top[0], {"project": "/home/u/DEV/ACME/a", "client": "ACME", "cost": 60.0, "share": 0.545})
        self.assertEqual(top[2]["client"], "Otros")


class TestClientOfParity(unittest.TestCase):
    def test_same_cases_as_clients_ts(self):
        path = os.path.join(os.path.dirname(__file__), "fixtures", "client_of_cases.json")
        with open(path) as f:
            cases = json.load(f)
        for case in cases:
            with self.subTest(path=case["path"]):
                self.assertEqual(briefing.client_of(case["path"]), case["client"])


if __name__ == "__main__":
    unittest.main()
