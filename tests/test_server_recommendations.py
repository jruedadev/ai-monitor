import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

import history
import server
from recommend import engine, store

EMPTY_SOURCES = {"claude_code": {}, "codex": {}, "opencode": {}, "hermes": {},
                 "openrouter": {"unavailable": True, "reason": "x"}}
NOW = "2026-09-20T07:00:00+00:00"


def pattern_rec(signature, pattern="revisa los logs"):
    return {"tool": "claude_code", "tokens": 100, "pattern": pattern, "kind": "prompt", "description": "desc",
            "impact": "medio", "evidence": {"sessions": 3, "days": 2, "tokens": 100, "projects": [],
                                            "sources": ["claude_code"], "snippets": []},
            "draft": "borrador", "signature": signature, "generator": "reglas"}


class RecommendationsAPITestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.static_dir = os.path.join(tmp, "dist")
        os.makedirs(self.static_dir)
        with open(os.path.join(self.static_dir, "index.html"), "w") as fh:
            fh.write("<html>fallback</html>")
        self.db = os.path.join(tmp, "history.db")
        self.lock = os.path.join(tmp, "recommend.lock")
        missing = os.path.join(tmp, "no-existe")
        self.engine_opts = {
            "lock_path": self.lock,
            "prompt_overrides": {"claude_code": missing, "codex": missing, "opencode": missing + ".db",
                                 "hermes": missing + ".db"},
            "session_tokens": {},
            "runner": lambda args, cwd, timeout: (1, "", "no debería llamarse sin candidatos"),
            "engine_dir": os.path.join(tmp, "motor-recomendaciones"),
        }
        patcher = patch("server.main.collect_all", return_value=EMPTY_SOURCES)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.httpd = server.build_app(self.static_dir, poll_interval_seconds=3600, db_path=self.db,
                                      engine_opts=self.engine_opts)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def request(self, method, path, body=None, content_type="application/json"):
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        headers = {"Content-Type": content_type} if data is not None else {}
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method,
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read()
                return resp.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw) if raw else None
            except ValueError:
                return exc.code, None

    def seed(self):
        store.apply_run(self.db, [pattern_rec([f"tri {i}" for i in range(10)])], [], NOW)
        return store.list_recommendations(self.db, "nueva")[0]["id"]


class TestListAndStatus(RecommendationsAPITestCase):
    def test_empty_database_lists_nothing(self):
        status, body = self.request("GET", "/api/recommendations")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"recommendations": [], "last_run": None, "running": False, "degraded": False})

    def test_unknown_estado_is_400(self):
        status, body = self.request("GET", "/api/recommendations?estado=borrada")
        self.assertEqual(status, 400)
        self.assertIn("borrada", body["error"])

    def test_status_lifecycle_and_tabs(self):
        rec_id = self.seed()
        status, body = self.request("POST", f"/api/recommendations/{rec_id}/estado", {"status": "aplicada"})
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "aplicada")
        self.assertNotIn("signature", body)
        self.assertEqual(self.request("GET", "/api/recommendations")[1]["recommendations"], [])
        applied = self.request("GET", "/api/recommendations?estado=aplicada")[1]["recommendations"]
        self.assertEqual([r["id"] for r in applied], [rec_id])
        self.assertEqual(applied[0]["evidence"]["sessions"], 3)
        self.assertEqual(self.request("POST", f"/api/recommendations/{rec_id}/estado", {"status": "nueva"})[0], 200)
        self.assertEqual(len(self.request("GET", "/api/recommendations?estado=todas")[1]["recommendations"]), 1)

    def test_status_errors(self):
        rec_id = self.seed()
        path = f"/api/recommendations/{rec_id}/estado"
        self.assertEqual(self.request("POST", "/api/recommendations/noexiste/estado", {"status": "aplicada"})[0], 404)
        self.assertEqual(self.request("POST", path, {"status": "resuelta"})[0], 400)
        self.assertEqual(self.request("POST", path, {"otro": 1})[0], 400)
        self.assertEqual(self.request("POST", path, [1, 2])[0], 400)
        self.assertEqual(self.request("POST", path, b"{roto", "application/json")[0], 400)
        self.assertEqual(self.request("POST", path, {"status": "aplicada"}, "text/plain")[0], 415)
        self.assertEqual(self.request("POST", "/api/recommendations/a-b/estado", {"status": "aplicada"})[0], 404)

    def test_sqlite_error_is_degraded_not_500(self):
        with patch("server.rec_store.list_recommendations", side_effect=sqlite3.OperationalError("disk I/O")):
            status, body = self.request("GET", "/api/recommendations")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"recommendations": [], "last_run": None, "running": False, "degraded": True})

    def test_old_history_db_without_new_tables(self):
        old = os.path.join(tempfile.mkdtemp(), "old.db")
        history.ensure_schema(old)
        self.httpd.RequestHandlerClass = server.make_handler(self.static_dir, server.SSEBroker(), db_path=old,
                                                             engine_opts=self.engine_opts)
        status, body = self.request("GET", "/api/recommendations")
        self.assertEqual((status, body["recommendations"], body["degraded"]), (200, [], False))
        status, body = self.request("GET", "/api/engine-settings")
        self.assertEqual(status, 200)
        self.assertEqual(body["backend"], "hermes")
        self.assertEqual(len(body["llm_chain"]), 3)


class TestRun(RecommendationsAPITestCase):
    def wait_finished(self, run_id, timeout=5):
        deadline = time.time() + timeout
        while time.time() < deadline:
            run = store.get_run(self.db, run_id)
            if run and run["finished_at"]:
                return run
            time.sleep(0.05)
        self.fail("la corrida no terminó")

    def test_run_returns_202_and_publishes_sse(self):
        queue = self.httpd.RequestHandlerClass.broker.subscribe()
        status, body = self.request("POST", "/api/recommendations/run", {})
        self.assertEqual(status, 202)
        run = self.wait_finished(body["run_id"])
        self.assertEqual((run["trigger"], run["status"]), ("manual", "ok"))
        self.assertFalse(os.path.exists(self.lock))
        event = queue.get(timeout=5)
        self.assertTrue(event.startswith(b"event: recommendations\n"))
        self.assertIn(f'"run_id": {body["run_id"]}'.encode(), event)
        listed = self.request("GET", "/api/recommendations")[1]
        self.assertEqual(listed["last_run"]["id"], body["run_id"])
        self.assertFalse(listed["running"])

    def test_run_conflict_returns_409(self):
        engine.acquire_lock(self.lock)
        try:
            status, body = self.request("POST", "/api/recommendations/run", {})
            self.assertEqual(status, 409)
            self.assertEqual(body["error"], "Ya hay una corrida en curso")
            self.assertTrue(self.request("GET", "/api/recommendations")[1]["running"])
        finally:
            engine.release_lock(self.lock)
        self.assertIsNone(store.last_run(self.db))

    def test_run_requires_json(self):
        self.assertEqual(self.request("POST", "/api/recommendations/run", b"", "text/plain")[0], 415)
        self.assertEqual(self.request("POST", "/api/recommendations/run")[0], 415)


class TestEngineSettings(RecommendationsAPITestCase):
    def test_roundtrip_and_validation(self):
        payload = {"backend": "claude", "llm_chain": ["nous:upstage/solar-pro4:free"]}
        self.assertEqual(self.request("POST", "/api/engine-settings", payload), (200, payload))
        status, body = self.request("GET", "/api/engine-settings")
        self.assertEqual(status, 200)
        self.assertEqual({k: body[k] for k in payload}, payload)
        self.assertEqual(set(body["available"]), {"hermes", "claude"})
        status, body = self.request("POST", "/api/engine-settings",
                                    {"backend": "hermes", "llm_chain": ["openrouter:openai/gpt-5"]})
        self.assertEqual(status, 400)
        self.assertIn("free", body["error"])
        self.assertEqual(self.request("POST", "/api/engine-settings", {"backend": "x"})[0], 400)
        self.assertEqual(self.request("POST", "/api/engine-settings", payload, "text/plain")[0], 415)

    def test_available_reflects_path(self):
        with patch("server.shutil.which", side_effect=lambda name: "/x/hermes" if name == "hermes" else None):
            body = self.request("GET", "/api/engine-settings")[1]
        self.assertEqual(body["available"], {"hermes": True, "claude": False})


class TestAppSettings(RecommendationsAPITestCase):
    ROOTS = [{"root": "/srv/trabajo", "mode": "plano"}]

    def test_defaults_then_roundtrip(self):
        self.assertEqual(self.request("GET", "/api/app-settings"), (200, {
            "client_roots": [{"root": "DEV", "mode": "cliente"}], "onboarding_completed_at": None, "degraded": False}))
        status, body = self.request("POST", "/api/app-settings", {"client_roots": [{"root": "/srv/trabajo/", "mode": "plano"}]})
        self.assertEqual((status, body["client_roots"]), (200, self.ROOTS))
        self.assertEqual(self.request("GET", "/api/app-settings")[1]["client_roots"], self.ROOTS)

    def test_validation_and_content_type(self):
        status, body = self.request("POST", "/api/app-settings", {"client_roots": []})
        self.assertEqual(status, 400)
        self.assertIn("entre 1 y 20", body["error"])
        self.assertEqual(self.request("POST", "/api/app-settings", {"otra": 1})[0], 400)
        self.assertEqual(self.request("POST", "/api/app-settings", {"client_roots": self.ROOTS}, "text/plain")[0], 415)

    def test_complete_onboarding(self):
        status, body = self.request("POST", "/api/app-settings/onboarding", {})
        self.assertEqual(status, 200)
        stamp = body["onboarding_completed_at"]
        self.assertTrue(stamp)
        self.assertEqual(self.request("GET", "/api/app-settings")[1]["onboarding_completed_at"], stamp)
        self.assertEqual(self.request("POST", "/api/app-settings/onboarding", b"", "text/plain")[0], 415)

    def test_sqlite_error_is_degraded_not_500(self):
        with patch("server.history.get_app_settings", side_effect=sqlite3.OperationalError("disk I/O")):
            status, body = self.request("GET", "/api/app-settings")
        self.assertEqual((status, body["degraded"], body["onboarding_completed_at"]), (200, True, None))
        with patch("server.history.save_app_settings", side_effect=sqlite3.OperationalError("disk I/O")):
            self.assertEqual(self.request("POST", "/api/app-settings", {"client_roots": self.ROOTS})[0], 503)

class TestCheckRecommendationRuns(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "history.db")
        self.broker = server.SSEBroker()
        self.queue = self.broker.subscribe()

    def test_publishes_only_new_finished_runs(self):
        self.assertIsNone(server._check_recommendation_runs(self.broker, self.db, None))
        run_id = store.start_run(self.db, "diario", "hermes", NOW)
        self.assertIsNone(server._check_recommendation_runs(self.broker, self.db, None))
        store.finish_run(self.db, run_id, "ok", NOW)
        self.assertEqual(server._check_recommendation_runs(self.broker, self.db, None), run_id)
        self.assertIn(b"event: recommendations", self.queue.get_nowait())
        self.assertEqual(server._check_recommendation_runs(self.broker, self.db, run_id), run_id)
        self.assertTrue(self.queue.empty())

    def test_sqlite_error_keeps_last(self):
        with patch("server.rec_store.latest_finished_run_id", side_effect=sqlite3.OperationalError("x")):
            self.assertEqual(server._check_recommendation_runs(self.broker, self.db, 7), 7)


if __name__ == "__main__":
    unittest.main()