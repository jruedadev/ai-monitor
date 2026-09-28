import os
import sqlite3
import tempfile
import unittest

from recommend import settings as engine_settings
from recommend import store

NOW1, NOW2, NOW3 = "2026-09-20T07:00:00+00:00", "2026-09-21T07:00:00+00:00", "2026-09-22T07:00:00+00:00"
SIG_A = [f"tri {i}" for i in range(10)]
SIG_A2 = SIG_A[:8] + ["otro 1", "otro 2"]          # Jaccard 8/12 ≈ 0,67 con SIG_A
SIG_B = [f"zzz {i}" for i in range(10)]


def pattern_rec(signature, generator="reglas", kind="prompt", tokens=100, **extra):
    rec = {"tool": "claude_code", "tokens": tokens, "pattern": "revisa los logs", "kind": kind,
           "description": "desc", "impact": "medio", "evidence": {"sessions": 3, "sources": ["claude_code"]},
           "draft": "borrador", "signature": signature, "generator": generator}
    rec.update(extra)
    return rec


def cost_rec(project="/home/u/DEV/ACME/app", title="ACME concentra el 80 %"):
    return {"tool": "claude_code", "tokens": 5000, "pattern": title, "kind": "costo", "description": "d",
            "impact": "medio", "evidence": {"rule": "project_concentration", "sources": ["claude_code"]},
            "draft": "revisa", "generator": "costo",
            "signature": {"rule": "project_concentration", "source": "claude_code", "project": project}}


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "history.db")


class TestSettings(StoreTestCase):
    def test_is_free_and_parse_entry(self):
        self.assertTrue(engine_settings.is_free("upstage/solar-pro4:free"))
        self.assertTrue(engine_settings.is_free("stealth/space-bunny-alpha"))
        self.assertFalse(engine_settings.is_free("anthropic/claude-sonnet"))
        self.assertEqual(engine_settings.parse_entry("nous:upstage/solar-pro4:free"),
                         ("nous", "upstage/solar-pro4:free"))
        for bad in ("sinproveedor", ":modelo", "prov:", "", None):
            with self.assertRaises(ValueError):
                engine_settings.parse_entry(bad)

    def test_validate(self):
        ok = engine_settings.validate_engine_settings({"backend": "hermes", "llm_chain": ["nous:stealth/x"]})
        self.assertEqual(ok, {"backend": "hermes", "llm_chain": ["nous:stealth/x"]})
        claude = engine_settings.validate_engine_settings({"backend": "claude", "llm_chain": ["nous:pago/m"]})
        self.assertEqual(claude["backend"], "claude")
        for bad in ({"backend": "otro", "llm_chain": ["nous:stealth/x"]},
                    {"backend": "hermes", "llm_chain": []},
                    {"backend": "hermes", "llm_chain": "nous:stealth/x"},
                    {"backend": "hermes", "llm_chain": ["nous:pago/modelo"]},
                    {"backend": "hermes"}, {"backend": "hermes", "llm_chain": ["x"], "extra": 1}, []):
            with self.assertRaises(engine_settings.EngineSettingsError, msg=str(bad)):
                engine_settings.validate_engine_settings(bad)

    def test_get_defaults_save_and_corrupt_fallback(self):
        self.assertEqual(store.get_engine_settings(self.db),
                         {"backend": "hermes", "llm_chain": list(engine_settings.DEFAULT_CHAIN)})
        store.save_engine_settings({"backend": "none", "llm_chain": ["nous:stealth/x"]}, self.db)
        self.assertEqual(store.get_engine_settings(self.db), {"backend": "none", "llm_chain": ["nous:stealth/x"]})
        con = sqlite3.connect(self.db)
        con.execute("UPDATE engine_settings SET value = '{roto' WHERE key = 'llm_chain'")
        con.execute("UPDATE engine_settings SET value = 'raro' WHERE key = 'backend'")
        con.commit()
        con.close()
        self.assertEqual(store.get_engine_settings(self.db),
                         {"backend": "hermes", "llm_chain": list(engine_settings.DEFAULT_CHAIN)})


class TestRuns(StoreTestCase):
    def test_run_lifecycle(self):
        self.assertIsNone(store.last_run(self.db))
        self.assertIsNone(store.latest_finished_run_id(self.db))
        run_id = store.start_run(self.db, "manual", "hermes", NOW1)
        self.assertEqual(store.get_run(self.db, run_id)["status"], "corriendo")
        self.assertIsNone(store.latest_finished_run_id(self.db))
        store.finish_run(self.db, run_id, "ok", NOW2, model="nous:stealth/x", attempts=1, prompts=10,
                         clusters=2, created=2, updated=0, resolved=0, llm_tokens=900, llm_cost=0.0)
        run = store.last_run(self.db)
        self.assertEqual((run["id"], run["status"], run["model"], run["finished_at"]),
                         (run_id, "ok", "nous:stealth/x", NOW2))
        self.assertEqual(store.latest_finished_run_id(self.db), run_id)
        with self.assertRaises(ValueError):
            store.finish_run(self.db, run_id, "ok", NOW2, columna_rara=1)


class TestApplyRun(StoreTestCase):
    def test_creates_then_updates_by_similar_signature(self):
        self.assertEqual(store.apply_run(self.db, [pattern_rec(SIG_A)], [], NOW1),
                         {"created": 1, "updated": 0, "resolved": 0})
        first = store.list_recommendations(self.db)[0]
        counts = store.apply_run(self.db, [pattern_rec(SIG_A2, tokens=900, impact="alto")], [], NOW2)
        self.assertEqual(counts, {"created": 0, "updated": 1, "resolved": 0})
        [row] = store.list_recommendations(self.db)
        self.assertEqual((row["id"], row["first_seen"], row["last_seen"], row["tokens"], row["impact"]),
                         (first["id"], NOW1, NOW2, 900, "alto"))
        self.assertEqual(row["evidence"], {"sessions": 3, "sources": ["claude_code"]})

    def test_different_signature_creates_new(self):
        store.apply_run(self.db, [pattern_rec(SIG_A)], [], NOW1)
        store.apply_run(self.db, [pattern_rec(SIG_B)], [], NOW2)
        self.assertEqual(len(store.list_recommendations(self.db)), 2)

    def test_skipped_stays_hidden_and_only_last_seen_changes(self):
        store.apply_run(self.db, [pattern_rec(SIG_A)], [], NOW1)
        rec_id = store.list_recommendations(self.db)[0]["id"]
        store.set_status(self.db, rec_id, "saltada", NOW1)
        store.apply_run(self.db, [pattern_rec(SIG_A, tokens=999, generator="nous:stealth/x",
                                              description="nueva")], [], NOW2)
        self.assertEqual(store.list_recommendations(self.db), [])
        [row] = store.list_recommendations(self.db, "saltada")
        self.assertEqual((row["last_seen"], row["tokens"], row["description"]), (NOW2, 100, "desc"))

    def test_applied_keeps_status_but_updates_evidence(self):
        store.apply_run(self.db, [pattern_rec(SIG_A)], [], NOW1)
        rec_id = store.list_recommendations(self.db)[0]["id"]
        store.set_status(self.db, rec_id, "aplicada", NOW1)
        store.apply_run(self.db, [pattern_rec(SIG_A, tokens=500)], [], NOW2)
        [row] = store.list_recommendations(self.db, "aplicada")
        self.assertEqual((row["status"], row["tokens"]), ("aplicada", 500))

    def test_llm_enriches_rules_generated_recommendation(self):
        store.apply_run(self.db, [pattern_rec(SIG_A)], [], NOW1)
        store.apply_run(self.db, [pattern_rec(SIG_A, generator="nous:stealth/x", kind="skill",
                                              description="mejor", draft="---\nname: x\n---")], [], NOW2)
        [row] = store.list_recommendations(self.db)
        self.assertEqual((row["generator"], row["kind"], row["description"]), ("nous:stealth/x", "skill", "mejor"))
        store.apply_run(self.db, [pattern_rec(SIG_A, generator="reglas", description="peor")], [], NOW3)
        self.assertEqual(store.list_recommendations(self.db)[0]["description"], "mejor")

    def test_cost_matches_exactly_and_resolves_when_rule_stops(self):
        store.apply_run(self.db, [], [cost_rec()], NOW1)
        store.apply_run(self.db, [], [cost_rec(title="ACME concentra el 90 %")], NOW2)
        [row] = store.list_recommendations(self.db)
        self.assertEqual(row["pattern"], "ACME concentra el 90 %")
        counts = store.apply_run(self.db, [], [], NOW3)
        self.assertEqual(counts["resolved"], 1)
        self.assertEqual(store.list_recommendations(self.db), [])
        self.assertEqual(store.list_recommendations(self.db, "resuelta")[0]["status_at"], NOW3)
        store.apply_run(self.db, [], [cost_rec()], NOW3)  # vuelve a dispararse → se reabre
        self.assertEqual(len(store.list_recommendations(self.db)), 1)

    def test_other_project_is_a_different_cost_recommendation(self):
        store.apply_run(self.db, [], [cost_rec(), cost_rec(project="/home/u/DEV/OTRO/x")], NOW1)
        self.assertEqual(len(store.list_recommendations(self.db)), 2)

    def test_never_deletes_rows(self):
        store.apply_run(self.db, [pattern_rec(SIG_A)], [cost_rec()], NOW1)
        for now in (NOW2, NOW3):
            store.apply_run(self.db, [], [], now)
        self.assertEqual(len(store.list_recommendations(self.db, "todas")), 2)

    def test_rollback_on_failure_keeps_previous_rows(self):
        store.apply_run(self.db, [pattern_rec(SIG_A)], [], NOW1)
        before = store.list_recommendations(self.db, "todas")
        broken = pattern_rec(SIG_B)
        del broken["draft"]
        with self.assertRaises(KeyError):
            store.apply_run(self.db, [pattern_rec(SIG_A, tokens=777), broken], [], NOW2)
        self.assertEqual(store.list_recommendations(self.db, "todas"), before)


class TestStatus(StoreTestCase):
    def test_set_status_and_listing(self):
        store.apply_run(self.db, [pattern_rec(SIG_A, impact="bajo"), pattern_rec(SIG_B, impact="alto")], [], NOW1)
        rows = store.list_recommendations(self.db)
        self.assertEqual([r["impact"] for r in rows], ["alto", "bajo"])
        updated = store.set_status(self.db, rows[0]["id"], "aplicada", NOW2)
        self.assertEqual((updated["status"], updated["status_at"]), ("aplicada", NOW2))
        self.assertIsNone(store.set_status(self.db, "noexiste", "aplicada", NOW2))
        with self.assertRaises(ValueError):
            store.set_status(self.db, rows[0]["id"], "resuelta", NOW2)
        with self.assertRaises(ValueError):
            store.list_recommendations(self.db, "rara")
