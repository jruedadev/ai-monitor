#!/usr/bin/env python3
"""Servidor HTTP del dashboard interactivo: API en vivo (snapshot + SSE +
histórico) y estáticos del frontend. Solo stdlib (http.server), sin frameworks.
"""
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import briefing
import clients
import history
import main
from live import activity as live_activity
from recommend import engine as rec_engine
from recommend import settings as rec_settings
from recommend import store as rec_store
from sse import SSEBroker, format_sse_event

_state_lock = threading.Lock()
_state = {"sources": {}, "combined": {}}
_activity_lock = threading.Lock()
_activity = {"snapshot": None, "published": None}

AVAILABLE_BACKENDS = ("hermes", "claude")


def _available_backends():
    """Se evalúa en cada request: refleja una instalación hecha sin reiniciar el server."""
    return {name: shutil.which(name) is not None for name in AVAILABLE_BACKENDS}


def _app_settings_payload(db_path):
    try:
        return {**history.get_app_settings(db_path=db_path), "degraded": False}
    except sqlite3.Error:
        return {"client_roots": clients.default_roots(), "onboarding_completed_at": None, "degraded": True}


def _recompute_and_maybe_publish(broker):
    sources = main.collect_all()
    combined = main.combine_projects(sources["claude_code"], sources["codex"], sources["opencode"], sources["hermes"])
    payload = json.dumps({"sources": sources, "combined": combined}, sort_keys=True)

    with _state_lock:
        current = json.dumps({"sources": _state["sources"], "combined": _state["combined"]}, sort_keys=True)
        changed = current != payload
        _state["sources"] = sources
        _state["combined"] = combined

    if changed:
        broker.publish("usage", payload)


def _background_loop(broker, poll_interval_seconds, db_path=None, last_run_id=None):
    while True:
        time.sleep(poll_interval_seconds)
        try:
            _recompute_and_maybe_publish(broker)
        except Exception:
            pass
        last_run_id = _check_recommendation_runs(broker, db_path, last_run_id)


def _empty_activity():
    return {"generated_at": None, "agents": [], "sources": {s: "unavailable" for s in live_activity.LIVE_SOURCES}}


def _activity_tick(broker, fn):
    """Un ciclo: calcula el snapshot, lo guarda y publica solo si agents/sources cambiaron."""
    try:
        snap = fn()
    except Exception:
        return
    key = json.dumps({"agents": snap["agents"], "sources": snap["sources"]}, sort_keys=True)
    with _activity_lock:
        _activity["snapshot"] = snap
        changed = _activity["published"] != key
        _activity["published"] = key
    if changed:
        broker.publish("activity", json.dumps(snap))


def _activity_loop(broker, interval, fn):
    while True:
        time.sleep(interval)
        _activity_tick(broker, fn)


def _current_activity_json():
    with _activity_lock:
        return json.dumps(_activity["snapshot"] or _empty_activity())


def _current_snapshot_json():
    with _state_lock:
        return json.dumps({"sources": _state["sources"], "combined": _state["combined"]})


REC_ESTADOS = ("nueva", "aplicada", "saltada", "resuelta", "todas")
_STATUS_PATH = re.compile(r"^/api/recommendations/([A-Za-z0-9]+)/estado$")
_INVALID = object()


def _recommendations_payload(db_path, estado, lock_path):
    try:
        recs = rec_store.list_recommendations(db_path, estado)
        last = rec_store.last_run(db_path)
    except sqlite3.Error:
        return {"recommendations": [], "last_run": None, "running": False, "degraded": True}
    return {"recommendations": recs, "last_run": last, "running": rec_engine.lock_is_live(lock_path),
            "degraded": False}


def _check_recommendation_runs(broker, db_path, last):
    try:
        current = rec_store.latest_finished_run_id(db_path)
    except sqlite3.Error:
        return last
    if current is None or current == last:
        return last
    broker.publish("recommendations", json.dumps({"run_id": current}))
    return current


def make_handler(static_dir, broker, db_path=None, engine_opts=None):
    opts = dict(engine_opts or {})
    lock_path = opts.pop("lock_path", rec_engine.LOCK_PATH)

    def run_in_background(run_id, settings):
        try:
            rec_engine.execute(run_id, settings, db_path, lock_path=lock_path, **opts)
        finally:
            broker.publish("recommendations", json.dumps({"run_id": run_id}))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            parsed = urlparse(self.path)

            if parsed.path == "/api/usage":
                self._send_json(_current_snapshot_json())
            elif parsed.path == "/api/history":
                qs = parse_qs(parsed.query)
                try:
                    days = int(qs.get("days", ["90"])[0])
                    if days <= 0:
                        days = 90
                except ValueError:
                    days = 90
                self._send_json(json.dumps(history.query_history(days=days, db_path=db_path)))
            elif parsed.path == "/api/briefing":
                qs = parse_qs(parsed.query)
                try:
                    data = briefing.get_briefing(
                        db_path=db_path,
                        source=qs.get("source", ["all"])[0],
                        compare=qs.get("compare", [None])[0],
                    )
                except briefing.BriefingError as exc:
                    self._send_json(json.dumps({"error": str(exc)}), status=400)
                    return
                self._send_json(json.dumps(data))
            elif parsed.path == "/api/roi-settings":
                self._send_json(json.dumps(history.get_roi_settings(db_path=db_path)))
            elif parsed.path == "/api/app-settings":
                self._send_json(json.dumps(_app_settings_payload(db_path)))
            elif parsed.path == "/api/recommendations":
                estado = parse_qs(parsed.query).get("estado", ["nueva"])[0]
                if estado not in REC_ESTADOS:
                    self._send_json(json.dumps({"error": f"Estado desconocido: {estado}"}), status=400)
                    return
                self._send_json(json.dumps(_recommendations_payload(db_path, estado, lock_path)))
            elif parsed.path == "/api/engine-settings":
                try:
                    data = rec_store.get_engine_settings(db_path)
                except sqlite3.Error:
                    data = {"backend": rec_settings.DEFAULT_BACKEND, "llm_chain": list(rec_settings.DEFAULT_CHAIN)}
                data["available"] = _available_backends()
                self._send_json(json.dumps(data))
            elif parsed.path == "/api/activity":
                self._send_json(_current_activity_json())
            elif parsed.path == "/api/stream":
                self._handle_sse()
            else:
                self._serve_static(parsed.path)

        def do_POST(self):
            parsed = urlparse(self.path)
            status_match = _STATUS_PATH.match(parsed.path)

            if parsed.path == "/api/roi-settings":
                settings = self._read_json_body()
                if settings is _INVALID:
                    return
                try:
                    history.validate_roi_settings(settings)
                except history.RoiSettingsError as exc:
                    self._send_json(json.dumps({"error": str(exc)}), status=400)
                    return
                history.save_roi_settings(settings, db_path=db_path)
                self._send_json(json.dumps(history.get_roi_settings(db_path=db_path)))
            elif parsed.path == "/api/app-settings":
                body = self._read_json_body()
                if body is _INVALID:
                    return
                try:
                    clean = history.validate_app_settings(body)
                except history.AppSettingsError as exc:
                    self._send_json(json.dumps({"error": str(exc)}), status=400)
                    return
                try:
                    history.save_app_settings(clean, db_path=db_path)
                except sqlite3.Error as exc:
                    self._send_json(json.dumps({"error": f"Base no disponible: {exc}"}), status=503)
                    return
                self._send_json(json.dumps(_app_settings_payload(db_path)))
            elif parsed.path == "/api/app-settings/onboarding":
                if self._read_json_body() is _INVALID:
                    return
                try:
                    stamp = history.complete_onboarding(db_path=db_path)
                except sqlite3.Error as exc:
                    self._send_json(json.dumps({"error": f"Base no disponible: {exc}"}), status=503)
                    return
                self._send_json(json.dumps({"onboarding_completed_at": stamp}))
            elif parsed.path == "/api/recommendations/run":
                if self._read_json_body() is _INVALID:
                    return
                try:
                    run_id, settings = rec_engine.start("manual", db_path, lock_path)
                except rec_engine.EngineBusy:
                    self._send_json(json.dumps({"error": "Ya hay una corrida en curso"}), status=409)
                    return
                except sqlite3.Error as exc:
                    self._send_json(json.dumps({"error": f"Base no disponible: {exc}"}), status=503)
                    return
                threading.Thread(target=run_in_background, args=(run_id, settings), daemon=True).start()
                self._send_json(json.dumps({"run_id": run_id}), status=202)
            elif status_match:
                body = self._read_json_body()
                if body is _INVALID:
                    return
                status = body.get("status") if isinstance(body, dict) else None
                if status not in rec_store.USER_STATUSES:
                    self._send_json(json.dumps({"error": f"Estado inválido: {status}"}), status=400)
                    return
                try:
                    rec = rec_store.set_status(db_path, status_match.group(1), status, rec_engine.now_iso())
                except sqlite3.Error as exc:
                    self._send_json(json.dumps({"error": f"Base no disponible: {exc}"}), status=503)
                    return
                if rec is None:
                    self._send_json(json.dumps({"error": "Recomendación no encontrada"}), status=404)
                    return
                self._send_json(json.dumps(rec))
            elif parsed.path == "/api/engine-settings":
                body = self._read_json_body()
                if body is _INVALID:
                    return
                try:
                    clean = rec_settings.validate_engine_settings(body)
                except rec_settings.EngineSettingsError as exc:
                    self._send_json(json.dumps({"error": str(exc)}), status=400)
                    return
                rec_store.save_engine_settings(clean, db_path)
                self._send_json(json.dumps(rec_store.get_engine_settings(db_path)))
            else:
                self.send_response(404)
                self.end_headers()

        def _read_json_body(self):
            content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if content_type != "application/json":
                self.send_response(415)
                self.end_headers()
                return _INVALID
            length = int(self.headers.get("Content-Length", 0))
            try:
                return json.loads(self.rfile.read(length))
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
                return _INVALID

        def _send_json(self, body, status=200):
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _handle_sse(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            q = broker.subscribe()
            try:
                self.wfile.write(format_sse_event("usage", _current_snapshot_json()))
                self.wfile.write(format_sse_event("activity", _current_activity_json()))
                self.wfile.flush()
                while True:
                    payload = q.get()
                    self.wfile.write(payload)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                broker.unsubscribe(q)

        def _serve_static(self, url_path):
            if not os.path.isdir(static_dir):
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Frontend no compilado. Corre 'npm install && npm run build' en frontend/.")
                return

            rel_path = url_path.lstrip("/") or "index.html"
            root = os.path.abspath(static_dir)
            candidate = os.path.normpath(os.path.join(root, rel_path))
            if candidate != root and not candidate.startswith(root + os.sep):
                candidate = os.path.join(static_dir, "index.html")
            if not os.path.isfile(candidate):
                candidate = os.path.join(static_dir, "index.html")

            if not os.path.isfile(candidate):
                self.send_response(404)
                self.end_headers()
                return

            content_type, _ = mimetypes.guess_type(candidate)
            with open(candidate, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    Handler.broker = broker
    return Handler


def build_app(static_dir, poll_interval_seconds=60, port=0, db_path=None, engine_opts=None,
              activity_interval_seconds=2, activity_fn=None):
    static_dir = os.path.abspath(static_dir)
    broker = SSEBroker()
    handler_cls = make_handler(static_dir, broker, db_path=db_path, engine_opts=engine_opts)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler_cls)

    _recompute_and_maybe_publish(broker)
    last_run_id = _check_recommendation_runs(broker, db_path, None)

    thread = threading.Thread(
        target=_background_loop, args=(broker, poll_interval_seconds, db_path, last_run_id), daemon=True
    )
    thread.start()

    fn = activity_fn or live_activity.snapshot
    with _activity_lock:
        _activity["snapshot"], _activity["published"] = None, None
    _activity_tick(broker, fn)  # primer snapshot antes de aceptar peticiones
    threading.Thread(target=_activity_loop, args=(broker, activity_interval_seconds, fn), daemon=True).start()

    return httpd


def main_entrypoint():
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(repo_dir, "frontend", "dist")
    port = int(os.environ.get("AI_MONITOR_PORT", "8420"))

    httpd = build_app(static_dir, port=port)
    print(f"ai-monitor server escuchando en http://127.0.0.1:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    main_entrypoint()
