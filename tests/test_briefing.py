import os
import sqlite3
import tempfile
import unittest
import unittest.mock
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

    def test_future_start_excludes_subscription_from_this_window(self):
        # subscription_start_claude está después del fin de la ventana (2026-09-27):
        # la suscripción no ha empezado este mes, así que se trata como no configurada.
        data = build([row("2026-09-10", cost=100)],
                     cfg=settings(subscription_cost_claude=20.0, subscription_start_claude="2026-10-05"))
        self.assertEqual(data["subscription"], {"configured": False, "paid": None, "api_equivalent": None,
                                                "winner": None, "savings": None})

    def test_bad_stored_cost_is_treated_as_not_configured(self):
        data = build([row("2026-09-10", cost=100)], cfg=settings(subscription_cost_claude="not-a-number"))
        self.assertFalse(data["subscription"]["configured"])

    def test_bad_stored_start_date_falls_back_to_window_start(self):
        # Un valor numérico guardado por error en subscription_start_* (p.ej. 20260905.0)
        # no debe romper el cálculo: se ignora como fecha de inicio.
        rows = [row("2026-09-10", cost=100)]
        data = build(rows, cfg=settings(subscription_cost_claude=20.0, subscription_start_claude=20260905.0))
        self.assertTrue(data["subscription"]["configured"])
        self.assertEqual(data["subscription"]["api_equivalent"], 100.0)

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


def ids(data):
    return [signal["id"] for signal in data["attention"]]


def daily(first, last, **kwargs):
    """Una fila por día entre dos fechas ISO, ambas inclusive."""
    from datetime import timedelta
    start, end = date.fromisoformat(first), date.fromisoformat(last)
    out = []
    while start <= end:
        out.append(row(start.isoformat(), **kwargs))
        start += timedelta(days=1)
    return out


class TestRules(unittest.TestCase):
    def test_spike_day_fires_against_active_day_average(self):
        rows = daily("2026-09-01", "2026-09-04", cost=10) + [row("2026-09-27", cost=100)]
        data = build(rows, cfg=settings(subscription_cost_claude=20.0))
        spike = data["attention"][0]
        self.assertEqual(spike["id"], "spike_day")
        self.assertEqual(spike["severity"], "warning")
        self.assertEqual(spike["title"], "Hoy llevas $ 100,00 — 3,6× tu promedio diario")
        self.assertEqual(spike["evidence"], ["2026-09-27: $ 100,00", "Promedio de días activos del mes: $ 28,00"])
        self.assertEqual(spike["link"], "/actividad?dia=2026-09-27")

    def test_spike_day_on_a_past_day_names_the_day(self):
        rows = daily("2026-09-01", "2026-09-04", cost=10) + [row("2026-09-12", cost=100)]
        spike = build(rows)["attention"][0]
        self.assertTrue(spike["title"].startswith("El 12 sept gastaste $ 100,00"))

    def test_spike_day_needs_five_active_days(self):
        rows = daily("2026-09-01", "2026-09-03", cost=10) + [row("2026-09-27", cost=100)]
        self.assertNotIn("spike_day", ids(build(rows)))

    def test_spike_day_is_measured_within_the_source_filter(self):
        rows = (daily("2026-09-01", "2026-09-06", source="codex", project="/home/u/DEV/X/c", cost=5)
                + daily("2026-09-01", "2026-09-04", cost=10) + [row("2026-09-27", cost=500)])
        self.assertNotIn("spike_day", ids(build(rows, source="codex")))
        self.assertIn("spike_day", ids(build(rows, source="claude_code")))

    def test_project_concentration(self):
        rows = [row("2026-09-02", project="/home/u/DEV/ACME/app", cost=60),
                row("2026-09-02", project="/home/u/DEV/ACME/web", cost=40)]
        data = build(rows, cfg=settings(subscription_cost_claude=20.0))
        signal = next(s for s in data["attention"] if s["id"] == "project_concentration")
        self.assertEqual(signal["severity"], "info")
        self.assertEqual(signal["title"], "app concentra el 60 % del gasto del mes")
        self.assertEqual(signal["evidence"], ["/home/u/DEV/ACME/app: $ 60,00 de $ 100,00"])
        self.assertEqual(signal["link"], "/proyectos/ACME?proyecto=%2Fhome%2Fu%2FDEV%2FACME%2Fapp")

    def test_project_concentration_needs_more_than_half(self):
        rows = [row("2026-09-02", project="/home/u/DEV/ACME/app", cost=50),
                row("2026-09-02", project="/home/u/DEV/ACME/web", cost=50)]
        self.assertNotIn("project_concentration", ids(build(rows)))

    def test_cost_incomplete_signal(self):
        data = build([row("2026-09-02", cost=None), row("2026-09-03", project="/home/u/DEV/B/x", cost=1),
                      row("2026-09-03", project="/home/u/DEV/C/y", cost=1)])
        signal = next(s for s in data["attention"] if s["id"] == "cost_incomplete")
        self.assertEqual(signal["evidence"][0], "Días afectados: 2 sept")
        self.assertEqual(signal["link"], "/gasto")

    def test_subscription_missing_after_three_active_days(self):
        self.assertIn("subscription_missing", ids(build(daily("2026-09-01", "2026-09-03"))))
        self.assertNotIn("subscription_missing", ids(build(daily("2026-09-01", "2026-09-02"))))
        self.assertNotIn("subscription_missing",
                         ids(build(daily("2026-09-01", "2026-09-03"), cfg=settings(subscription_cost_claude=20.0))))
        self.assertNotIn("subscription_missing", ids(build(
            daily("2026-09-01", "2026-09-03", source="hermes"), source="hermes")))

    def test_habitual_source_silent_fires(self):
        rows = daily("2026-08-20", "2026-09-18")  # 30 días seguidos, luego 9 días sin datos
        data = build(rows, cfg=settings(subscription_cost_claude=20.0))
        signal = next(s for s in data["attention"] if s["id"] == "habitual_source_silent")
        self.assertEqual(signal["severity"], "warning")
        self.assertEqual(signal["title"], "Claude Code lleva 9 días sin datos")
        self.assertEqual(signal["link"], "/gasto?fuente=claude-code")

    def test_sporadic_source_never_fires_silent(self):
        rows = daily("2026-08-20", "2026-09-27") + [row("2026-09-12", source="codex", project="/home/u/DEV/X/c")]
        self.assertNotIn("habitual_source_silent", ids(build(rows, cfg=settings(subscription_cost_claude=20.0))))

    def test_silence_threshold_scales_with_typical_interval(self):
        every_other = [r for i, r in enumerate(daily("2026-08-22", "2026-09-20")) if i % 2 == 0]  # 15 días, intervalo 2
        # último día activo 2026-09-19; umbral max(3, 3×2) = 6
        not_yet = build(every_other, today=date(2026, 9, 25), cfg=settings(subscription_cost_claude=20.0))
        self.assertNotIn("habitual_source_silent", ids(not_yet))
        silent = build(every_other, today=date(2026, 9, 26), cfg=settings(subscription_cost_claude=20.0))
        self.assertIn("habitual_source_silent", ids(silent))

    def test_ordering_by_severity_and_max_three(self):
        rows = (daily("2026-08-10", "2026-09-08", cost=1)  # Claude habitual, en silencio desde el 8
                + [row("2026-09-05", project="/home/u/DEV/ACME/otro", cost=None),
                   row("2026-09-20", source="codex", project="/home/u/DEV/BIG/app", cost=100)])
        data = build(rows)
        self.assertEqual(ids(data), ["spike_day", "habitual_source_silent", "project_concentration"])

    def test_no_rows_no_signals(self):
        self.assertEqual(build([])["attention"], [])


class TestSqlite(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, "history.db")

    def _insert(self, project_rows=(), model_rows=()):
        history.ensure_schema(self.db)
        con = sqlite3.connect(self.db)
        con.executemany("INSERT INTO daily_project (date, source, project, tokens, cost) VALUES (?, ?, ?, ?, ?)",
                        project_rows)
        con.executemany("INSERT INTO daily_model (date, model, tokens, cost) VALUES (?, ?, ?, ?)", model_rows)
        con.commit()
        con.close()

    def test_missing_db_returns_empty_response_without_creating_file(self):
        data = briefing.get_briefing(db_path=self.db, today=TODAY)
        self.assertFalse(os.path.exists(self.db))
        self.assertFalse(data["degraded"])
        self.assertEqual(data["kpis"]["cost"], {"current": 0, "previous": None, "delta_pct": None})
        self.assertEqual(data["eligible_months"], [])
        self.assertEqual(data["attention"], [])
        self.assertFalse(data["subscription"]["configured"])

    def test_file_without_tables_is_empty_not_degraded(self):
        open(self.db, "w").close()
        data = briefing.get_briefing(db_path=self.db, today=TODAY)
        self.assertFalse(data["degraded"])
        self.assertEqual(data["attention"], [])

    def test_empty_schema_keeps_configured_subscription(self):
        history.ensure_schema(self.db)
        history.save_roi_settings({"subscription_cost_claude": 20.0}, db_path=self.db)
        data = briefing.get_briefing(db_path=self.db, today=TODAY)
        self.assertTrue(data["subscription"]["configured"])
        self.assertEqual(data["subscription"]["api_equivalent"], 0.0)

    def test_corrupt_db_is_degraded(self):
        with open(self.db, "wb") as f:
            f.write(b"esto no es una base sqlite" * 200)
        data = briefing.get_briefing(db_path=self.db, today=TODAY, compare="2026-08")
        self.assertTrue(data["degraded"])
        self.assertEqual(data["attention"], [])
        self.assertEqual(data["kpis"]["cost"]["current"], 0)

    def test_reads_rows_models_and_text_start_date(self):
        self._insert(
            [("2026-08-27", "claude_code", APP, 10, 4.0), ("2026-09-20", "claude_code", APP, 10, 6.0),
             ("2026-09-10", "claude_code", APP, 10, 100.0)],
            [("2026-09-03", "__all__", 70, 50.0)],
        )
        history.save_roi_settings({"subscription_cost_claude": 20.0, "subscription_start_claude": "2026-09-15"},
                                  db_path=self.db)
        data = briefing.get_briefing(db_path=self.db, today=TODAY)
        self.assertEqual(data["kpis"]["cost"]["current"], 106.0)
        self.assertEqual(data["kpis"]["cost"]["previous"], 4.0)
        self.assertEqual(data["subscription"]["api_equivalent"], 6.0)
        self.assertEqual(briefing.get_briefing(db_path=self.db, today=TODAY, source="openrouter")
                         ["kpis"]["cost"]["current"], 50.0)

    def test_invalid_source_raises_even_without_db(self):
        with self.assertRaises(briefing.BriefingError):
            briefing.get_briefing(db_path=self.db, source="nope", today=TODAY)

    def test_default_today_uses_utc_date_not_local(self):
        # Toda la persistencia (by_day, history.db) usa fechas UTC; si el default de
        # "today" usara la hora local, cerca de medianoche el briefing quedaría un día
        # desfasado frente a los datos guardados.
        import datetime as dt_module

        class FakeDateTime(dt_module.datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is dt_module.timezone.utc:
                    return dt_module.datetime(2026, 9, 28, 0, 30, tzinfo=dt_module.timezone.utc)
                return dt_module.datetime(2026, 9, 27, 19, 30)

        with unittest.mock.patch("briefing.datetime", FakeDateTime):
            data = briefing.get_briefing(db_path=self.db)
        self.assertEqual(data["window"]["to"], "2026-09-28")

    def test_format_briefing_for_cli(self):
        self._insert([("2026-08-27", "claude_code", APP, 1000, 10.0), ("2026-09-27", "claude_code", APP, 500, 5.0)])
        text = briefing.format_briefing(briefing.get_briefing(db_path=self.db, today=TODAY))
        self.assertIn("Gasto equivalente API: $ 5,00 (-50,0 %)", text)
        self.assertIn("Tokens: 500 (-50,0 %)", text)
        self.assertIn("Días activos: 1 (antes: 1)", text)
        self.assertIn("Atención ahora", text)


class TestBuildContext(unittest.TestCase):
    def test_build_context_filters_source_and_window(self):
        from datetime import date
        rows = [{"date": "2026-09-01", "source": "codex", "project": "/p", "tokens": 5, "cost": 1.0},
                {"date": "2026-08-01", "source": "codex", "project": "/p", "tokens": 7, "cost": 1.0},
                {"date": "2026-09-01", "source": "claude_code", "project": "/p", "tokens": 9, "cost": 1.0}]
        ctx = briefing.build_context(rows, [], {}, date(2026, 9, 20), source="codex")
        self.assertEqual(ctx["window"], ("2026-09-01", "2026-09-20"))
        self.assertEqual([r["tokens"] for r in ctx["rows"]], [5, 7])
        self.assertEqual([r["tokens"] for r in ctx["window_rows"]], [5])
        self.assertEqual(set(ctx), {"source", "today", "window", "rows", "window_rows",
                                    "project_rows", "model_rows", "settings"})


if __name__ == "__main__":
    unittest.main()
