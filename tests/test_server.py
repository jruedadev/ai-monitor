import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

import server


class TestServerAPI(unittest.TestCase):
    def setUp(self):
        self.static_dir = tempfile.mkdtemp()
        with open(os.path.join(self.static_dir, "index.html"), "w") as f:
            f.write("<html>fallback</html>")

        self.fake_sources = {
            "claude_code": {"/home/user/demo": {
                "input": 10, "output": 5, "cache_read": 0, "cache_write": 0,
                "total_tokens": 15, "cost": 0.01, "cost_incomplete": False,
                "messages": 1, "session_count": 1, "by_day": {}, "sessions_detail": [],
            }},
            "codex": {}, "opencode": {}, "hermes": {}, "openrouter": {"unavailable": True, "reason": "x"},
        }

        patcher = patch("server.main.collect_all", return_value=self.fake_sources)
        patcher.start()
        self.addCleanup(patcher.stop)

        db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)
        os.unlink(self.db_path)
        self.addCleanup(lambda: os.path.exists(self.db_path) and os.unlink(self.db_path))

        self.httpd = server.build_app(self.static_dir, poll_interval_seconds=3600, db_path=self.db_path)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        # Give the background collection thread one tick to populate state.
        time.sleep(0.2)

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as resp:
            return resp.status, resp.read()

    def _post(self, path, payload):
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read()

    def test_api_usage_returns_current_snapshot(self):
        status, body = self._get("/api/usage")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("/home/user/demo", data["combined"])

    def test_api_history_returns_json_with_default_days(self):
        status, body = self._get("/api/history")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("daily_project", data)
        self.assertIn("daily_model", data)

    def test_get_roi_settings_returns_defaults_when_unset(self):
        status, body = self._get("/api/roi-settings")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(
            data,
            {
                "subscription_cost_claude": None,
                "subscription_cost_codex": None,
                "hourly_rate": None,
                "subscription_start_claude": None,
                "subscription_start_codex": None,
            },
        )

    def test_post_roi_settings_persists_and_get_reflects_it(self):
        status, _ = self._post("/api/roi-settings", {"subscription_cost_claude": 20.0, "hourly_rate": 35.0})
        self.assertEqual(status, 200)

        _, body = self._get("/api/roi-settings")
        data = json.loads(body)
        self.assertEqual(data["subscription_cost_claude"], 20.0)
        self.assertEqual(data["hourly_rate"], 35.0)

    def test_post_roi_settings_rejects_non_dict_body(self):
        body = json.dumps([1, 2, 3]).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/roi-settings", data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        self.assertEqual(status, 400)

    def test_post_roi_settings_without_json_content_type_is_415(self):
        body = json.dumps({"hourly_rate": 40.0}).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/roi-settings", data=body, method="POST",
            headers={"Content-Type": "text/plain"},
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 415)

    def test_post_roi_settings_accepts_content_type_with_charset(self):
        body = json.dumps({"hourly_rate": 40.0}).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/roi-settings", data=body, method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)

    def test_post_roi_settings_rejects_unknown_key(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post("/api/roi-settings", {"not_a_real_key": 1})
        self.assertEqual(ctx.exception.code, 400)

    def test_post_roi_settings_rejects_bool_for_numeric_key(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post("/api/roi-settings", {"hourly_rate": True})
        self.assertEqual(ctx.exception.code, 400)

    def test_post_roi_settings_rejects_malformed_date(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post("/api/roi-settings", {"subscription_start_claude": "15-09-2026"})
        self.assertEqual(ctx.exception.code, 400)

    def test_unknown_path_falls_back_to_index_html(self):
        status, body = self._get("/some/spa/route")
        self.assertEqual(status, 200)
        self.assertIn(b"fallback", body)

    def test_api_briefing_returns_empty_briefing_without_history(self):
        status, body = self._get("/api/briefing")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["source"], "all")
        self.assertEqual(data["attention"], [])
        self.assertEqual(data["eligible_months"], [])
        self.assertIn("kpis", data)
        self.assertFalse(data["degraded"])

    def test_api_briefing_openrouter_source(self):
        status, body = self._get("/api/briefing?source=openrouter")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["source"], "openrouter")

    def test_api_briefing_invalid_compare_is_400_with_message(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get("/api/briefing?compare=1999-01")
        self.assertEqual(ctx.exception.code, 400)
        self.assertIn("1999-01", json.loads(ctx.exception.read())["error"])

    def test_api_briefing_invalid_source_is_400(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get("/api/briefing?source=copilot")
        self.assertEqual(ctx.exception.code, 400)


class TestActivityEndpoint(unittest.TestCase):
    def build(self, fn, interval=0.05):
        static_dir = tempfile.mkdtemp()
        with open(os.path.join(static_dir, "index.html"), "w") as f:
            f.write("<html></html>")
        patcher = patch("server.main.collect_all", return_value={
            "claude_code": {}, "codex": {}, "opencode": {}, "hermes": {},
            "openrouter": {"unavailable": True, "reason": "x"}})
        patcher.start()
        self.addCleanup(patcher.stop)
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)
        os.unlink(db_path)
        httpd = server.build_app(static_dir, poll_interval_seconds=3600, db_path=db_path,
                                 activity_interval_seconds=interval, activity_fn=fn)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        return httpd.server_address[1]

    def snap(self, state="thinking", source_status="ok", generated="2026-10-01T05:30:00Z"):
        return {"generated_at": generated,
                "agents": [{"key": "claude_code:a", "source": "claude_code", "project": "/p", "state": state,
                            "tool": None, "tool_kind": None, "since": "2026-10-01T05:29:58Z"}],
                "sources": {"claude_code": source_status, "opencode": "ok", "hermes": "ok"}}

    def get(self, port, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as resp:
            return resp.status, resp.headers.get("Content-Type"), resp.read()

    def test_get_activity_returns_the_stored_snapshot(self):
        port = self.build(lambda: self.snap())
        status, ctype, body = self.get(port, "/api/activity")
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "application/json")
        self.assertEqual(json.loads(body), self.snap())

    def test_get_activity_does_not_run_readers_in_the_request_thread(self):
        calls = []

        def fn():
            calls.append(threading.current_thread().name)
            return self.snap()
        port = self.build(fn, interval=3600)
        self.get(port, "/api/activity")
        self.get(port, "/api/activity")
        self.assertEqual(len(calls), 1)  # solo el cálculo inicial de build_app

    def read_sse_events(self, port, wanted, timeout=3):
        import socket
        sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        sock.sendall(b"GET /api/stream HTTP/1.1\r\nHost: x\r\n\r\n")
        buf, deadline = b"", time.time() + timeout
        try:
            while time.time() < deadline and buf.count(b"event: " + wanted) < 3:
                try:
                    buf += sock.recv(65536)
                except socket.timeout:
                    break
        finally:
            sock.close()
        return buf.count(b"event: " + wanted)

    def test_loop_publishes_only_when_agents_or_sources_change(self):
        counter = {"n": 0}

        def fn():
            counter["n"] += 1
            return self.snap(generated=f"2026-10-01T05:30:{counter['n'] % 60:02d}Z")  # solo cambia generated_at
        port = self.build(fn, interval=0.05)
        # Solo el evento inicial al conectar: ningún ciclo posterior publica si agents/sources no cambian.
        self.assertEqual(self.read_sse_events(port, b"activity", timeout=1), 1)

    def test_loop_publishes_when_state_changes(self):
        states = iter(["thinking", "tool", "thinking", "tool"] * 100)
        port = self.build(lambda: self.snap(state=next(states)), interval=0.05)
        self.assertGreaterEqual(self.read_sse_events(port, b"activity", timeout=3), 3)

    def test_loop_survives_a_failing_reader(self):
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("falla puntual")
            return self.snap(state="thinking" if calls["n"] < 3 else "tool")
        port = self.build(fn, interval=0.05)
        deadline = time.time() + 3
        while time.time() < deadline and calls["n"] < 4:
            time.sleep(0.05)
        self.assertGreaterEqual(calls["n"], 4)
        _, _, body = self.get(port, "/api/activity")
        self.assertEqual(json.loads(body)["agents"][0]["state"], "tool")


if __name__ == "__main__":
    unittest.main()
