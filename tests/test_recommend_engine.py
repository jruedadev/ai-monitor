import io
import json
import os
import sqlite3
import subprocess
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from unittest import mock

from recommend import __main__ as cli
from recommend import engine, store

APP = "/home/u/DEV/ACME/app"
TODAY = date(2026, 9, 25)
TEXT_A = "revisa los logs del servicio de pagos y dime por qué falla el cobro con tarjeta"
TEXT_B = "mira las trazas del módulo de cobros y explícame el fallo al cobrar con la visa"
GROUPED = {"groups": [{"group_id": "g1", "members": ["c1", "c2"]}],
           "recommendations": [{"group_id": "g1", "kind": "skill", "pattern": "Diagnosticar fallos de cobro",
                                "description": "Pides lo mismo con palabras distintas.",
                                "draft": "---\nname: diagnostico-cobros\n---\nEscribe a ana@acme.com"}]}


def write_session(root, session_id, text, day):
    folder = os.path.join(root, "-home-u-DEV-ACME-app")
    os.makedirs(folder, exist_ok=True)
    rec = {"type": "user", "timestamp": f"{day}T10:00:00Z", "cwd": APP, "sessionId": session_id,
           "message": {"role": "user", "content": text}}
    with open(os.path.join(folder, f"{session_id}.jsonl"), "w") as fh:
        fh.write(json.dumps(rec) + "\n")


def hermes_runner(*outputs):
    """Runner falso: cada llamada escribe un usage-file free y devuelve el siguiente output
    (dict → JSON; None → código de salida 1)."""
    queue = list(outputs)

    def run(args, cwd, timeout):
        out = queue.pop(0)
        if out is None:
            return 1, "", "caído"
        with open(args[args.index("--usage-file") + 1], "w") as fh:
            json.dump({"total_tokens": 1234, "estimated_cost_usd": 0.0}, fh)
        return 0, json.dumps(out), ""
    return run


class EngineTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.db = os.path.join(tmp, "history.db")
        self.lock = os.path.join(tmp, "recommend.lock")
        self.engine_dir = os.path.join(tmp, "motor-recomendaciones")
        self.cc_root = os.path.join(tmp, "claude-projects")
        missing = os.path.join(tmp, "no-existe")
        self.overrides = {"claude_code": self.cc_root, "codex": missing, "opencode": missing + ".db",
                          "hermes": missing + ".db"}

    def run_engine(self, runner=None, session_tokens=None):
        return engine.run("manual", db_path=self.db, lock_path=self.lock, today=TODAY,
                          prompt_overrides=self.overrides, session_tokens=session_tokens or {},
                          runner=runner or hermes_runner(), engine_dir=self.engine_dir)


class TestLock(EngineTestCase):
    def test_second_acquire_is_busy_and_release_frees(self):
        engine.acquire_lock(self.lock)
        with self.assertRaises(engine.EngineBusy):
            engine.acquire_lock(self.lock)
        engine.release_lock(self.lock)
        self.assertFalse(os.path.exists(self.lock))
        engine.acquire_lock(self.lock)
        engine.release_lock(self.lock)

    def test_dead_pid_lock_is_recovered(self):
        proc = subprocess.Popen(["true"])
        proc.wait()
        with open(self.lock, "w") as fh:
            fh.write(str(proc.pid))
        engine.acquire_lock(self.lock)
        with open(self.lock) as fh:
            self.assertEqual(fh.read(), str(os.getpid()))
        engine.release_lock(self.lock)

    def test_garbage_lock_is_busy_while_fresh_and_recovered_when_old(self):
        with open(self.lock, "w") as fh:
            fh.write("")
        with self.assertRaises(engine.EngineBusy):
            engine.acquire_lock(self.lock)
        old = time.time() - 3600
        os.utime(self.lock, (old, old))
        engine.acquire_lock(self.lock)
        engine.release_lock(self.lock)


class TestImpact(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(engine.impact_for(100, 1000), "alto")
        self.assertEqual(engine.impact_for(30, 1000), "medio")
        self.assertEqual(engine.impact_for(29, 1000), "bajo")
        self.assertEqual(engine.impact_for(10, 0), "bajo")


class TestRun(EngineTestCase):
    def synonyms_fixture(self):
        # A y B no comparten trigramas: solo el LLM puede unirlos. Por separado
        # ninguno pasa el umbral final (2 sesiones); juntos suman 4 sesiones en 3 días.
        write_session(self.cc_root, "a1", TEXT_A, "2026-09-20")
        write_session(self.cc_root, "a2", TEXT_A, "2026-09-21")
        write_session(self.cc_root, "b1", TEXT_B, "2026-09-22")
        write_session(self.cc_root, "b2", TEXT_B, "2026-09-22")
        return {("claude_code", "a1"): 5000, ("claude_code", "a2"): 5000,
                ("claude_code", "b1"): 1000, ("claude_code", "b2"): 1000}

    def test_llm_groups_synonyms_end_to_end(self):
        tokens = self.synonyms_fixture()
        run_id, status = self.run_engine(hermes_runner(GROUPED), tokens)
        self.assertEqual(status, "ok")
        run = store.get_run(self.db, run_id)
        self.assertEqual((run["status"], run["model"], run["attempts"], run["prompts"], run["clusters"],
                          run["created"], run["llm_tokens"]),
                         ("ok", "nous:stealth/space-bunny-alpha", 1, 4, 1, 1, 1234))
        [rec] = store.list_recommendations(self.db)
        self.assertEqual((rec["kind"], rec["tool"], rec["tokens"], rec["generator"], rec["impact"]),
                         ("skill", "claude_code", 12000, "nous:stealth/space-bunny-alpha", "bajo"))
        self.assertEqual((rec["evidence"]["sessions"], rec["evidence"]["days"]), (4, 3))
        self.assertNotIn("ana@acme.com", rec["draft"])
        self.assertFalse(os.path.exists(self.lock))
        self.assertTrue(os.path.isdir(self.engine_dir))

    def test_backend_none_uses_lexical_only_and_never_deletes(self):
        tokens = self.synonyms_fixture()
        self.run_engine(hermes_runner(GROUPED), tokens)
        store.save_engine_settings({"backend": "none", "llm_chain": ["nous:stealth/x"]}, self.db)
        run_id, status = self.run_engine(session_tokens=tokens)
        self.assertEqual(status, "degraded")
        self.assertEqual(store.get_run(self.db, run_id)["clusters"], 0)
        self.assertEqual(len(store.list_recommendations(self.db, "todas")), 1)

    def test_chain_exhausted_falls_back_to_rules(self):
        for i, day in enumerate(("2026-09-20", "2026-09-20", "2026-09-21")):
            write_session(self.cc_root, f"a{i}", TEXT_A, day)
        run_id, status = self.run_engine(hermes_runner(None, None, None))
        self.assertEqual(status, "degraded")
        run = store.get_run(self.db, run_id)
        self.assertEqual((run["attempts"], run["model"], run["created"]), (3, None, 1))
        self.assertIn("nous:stealth/space-bunny-alpha: ", run["error"])
        [rec] = store.list_recommendations(self.db)
        self.assertEqual(rec["generator"], "reglas")

    def test_no_prompts_skips_llm(self):
        def never(*_):
            raise AssertionError("no debe llamarse al LLM sin candidatos")
        run_id, status = self.run_engine(never)
        self.assertEqual(status, "ok")
        self.assertEqual(store.get_run(self.db, run_id)["attempts"], 0)

    def test_write_failure_marks_error_and_releases_lock(self):
        self.synonyms_fixture()
        with mock.patch("recommend.engine.store.apply_run", side_effect=sqlite3.OperationalError("disco lleno")):
            run_id, status = self.run_engine(hermes_runner(GROUPED))
        self.assertEqual(status, "error")
        run = store.get_run(self.db, run_id)
        self.assertEqual(run["status"], "error")
        self.assertIn("disco lleno", run["error"])
        self.assertFalse(os.path.exists(self.lock))

    def test_busy_lock_raises_before_registering_run(self):
        engine.acquire_lock(self.lock)
        try:
            with self.assertRaises(engine.EngineBusy):
                self.run_engine()
        finally:
            engine.release_lock(self.lock)
        self.assertIsNone(store.last_run(self.db))

    def solo_triple_fixture(self):
        write_session(self.cc_root, "s1", TEXT_A, "2026-09-20")
        write_session(self.cc_root, "s2", TEXT_A, "2026-09-21")
        write_session(self.cc_root, "s3", TEXT_A, "2026-09-22")
        return {("claude_code", "s1"): 5000, ("claude_code", "s2"): 5000,
                ("claude_code", "s3"): 5000}

    def test_reuses_known_signature_without_calling_llm(self):
        SOLO_GROUPED = {"groups": [],
                        "recommendations": [{"group_id": "c1", "kind": "skill",
                                             "pattern": "Diagnosticar cobros",
                                             "description": "Se repite.",
                                             "draft": "---\nname: x\n---"}]}
        tokens = self.solo_triple_fixture()
        self.run_engine(hermes_runner(SOLO_GROUPED), tokens)

        def never(*_):
            raise AssertionError("no debe llamarse al LLM: el signature ya está recomendado")
        run_id, status = self.run_engine(never, tokens)
        self.assertEqual(status, "ok")
        self.assertEqual(store.get_run(self.db, run_id)["attempts"], 0)
        [rec] = store.list_recommendations(self.db)
        self.assertEqual(rec["generator"], "nous:stealth/space-bunny-alpha")

    def test_mixed_known_and_new_signatures_only_sends_new_to_llm(self):
        SOLO_GROUPED = {"groups": [],
                        "recommendations": [{"group_id": "c1", "kind": "skill",
                                             "pattern": "Diagnosticar cobros",
                                             "description": "Se repite.",
                                             "draft": "---\nname: x\n---"}]}
        tokens = self.solo_triple_fixture()
        self.run_engine(hermes_runner(SOLO_GROUPED), tokens)
        new_text = "despliega el servicio de facturación en producción ya"
        write_session(self.cc_root, "c1", new_text, "2026-09-23")
        write_session(self.cc_root, "c2", new_text, "2026-09-23")
        write_session(self.cc_root, "c3", new_text, "2026-09-24")
        tokens.update({("claude_code", "c1"): 2000, ("claude_code", "c2"): 2000,
                        ("claude_code", "c3"): 2000})
        NEW_GROUPED = {"groups": [{"group_id": "g1", "members": ["c2"]}],
                       "recommendations": [{"group_id": "g1", "kind": "prompt",
                                            "pattern": "Desplegar facturación",
                                            "description": "Se repite.",
                                            "draft": "Añade esto a AGENTS.md"}]}
        run_id, status = self.run_engine(hermes_runner(NEW_GROUPED), tokens)
        self.assertEqual(status, "ok")
        self.assertEqual(store.get_run(self.db, run_id)["attempts"], 1)
        self.assertEqual(len(store.list_recommendations(self.db)), 2)


class TestSessionTokens(unittest.TestCase):
    def test_load_session_tokens_from_collectors(self):
        detail = lambda *pairs: {"/p": {"sessions_detail": [{"session_id": s, "tokens": t} for s, t in pairs]}}
        with mock.patch("collectors.claude_code.collect", return_value=detail(("s1", 10))), \
             mock.patch("collectors.codex.collect", return_value=detail(("t1", 20))), \
             mock.patch("collectors.opencode.collect", return_value={}), \
             mock.patch("collectors.hermes.collect", return_value=detail((7, 30), (None, 99))):
            self.assertEqual(engine.load_session_tokens(),
                             {("claude_code", "s1"): 10, ("codex", "t1"): 20, ("hermes", "7"): 30})


class TestCli(unittest.TestCase):
    def call(self, result):
        out, err = io.StringIO(), io.StringIO()
        patch = mock.patch("recommend.engine.run", **result)
        with patch as run, redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["run", "--trigger", "diario"])
        return code, run, out.getvalue(), err.getvalue()

    def test_exit_codes(self):
        code, run, out, _ = self.call({"return_value": (5, "ok")})
        self.assertEqual(code, 0)
        run.assert_called_once_with("diario")
        self.assertIn("Corrida 5: ok", out)
        self.assertEqual(self.call({"return_value": (6, "degraded")})[0], 0)
        self.assertEqual(self.call({"return_value": (7, "error")})[0], 1)
        code, _, _, err = self.call({"side_effect": engine.EngineBusy()})
        self.assertEqual(code, 2)
        self.assertIn("Ya hay una corrida en curso", err)
