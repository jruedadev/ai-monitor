#!/usr/bin/env python3
"""Servidor HTTP del dashboard interactivo: API en vivo (snapshot + SSE +
histórico) y estáticos del frontend. Solo stdlib (http.server), sin frameworks.
"""
import json
import mimetypes
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import history
import main
from sse import SSEBroker, format_sse_event

_state_lock = threading.Lock()
_state = {"sources": {}, "combined": {}}


def _recompute_and_maybe_publish(broker):
    sources = main.collect_all()
    combined = main.combine_projects(sources["claude_code"], sources["codex"], sources["opencode"])
    payload = json.dumps({"sources": sources, "combined": combined}, sort_keys=True)

    with _state_lock:
        current = json.dumps({"sources": _state["sources"], "combined": _state["combined"]}, sort_keys=True)
        changed = current != payload
        _state["sources"] = sources
        _state["combined"] = combined

    if changed:
        broker.publish("usage", payload)


def _background_loop(broker, poll_interval_seconds):
    while True:
        try:
            _recompute_and_maybe_publish(broker)
        except Exception:
            pass  # una falla de recolección no debe tumbar el hilo de fondo
        time.sleep(poll_interval_seconds)


def _current_snapshot_json():
    with _state_lock:
        return json.dumps({"sources": _state["sources"], "combined": _state["combined"]})


def make_handler(static_dir, broker):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # silencioso; evita ruido en stdout durante uso normal

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
                self._send_json(json.dumps(history.query_history(days=days)))
            elif parsed.path == "/api/stream":
                self._handle_sse()
            else:
                self._serve_static(parsed.path)

        def _send_json(self, body):
            encoded = body.encode("utf-8")
            self.send_response(200)
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
            candidate = os.path.normpath(os.path.join(static_dir, rel_path))
            if not candidate.startswith(os.path.abspath(static_dir)):
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

    return Handler


def build_app(static_dir, poll_interval_seconds=60, port=0):
    broker = SSEBroker()
    handler_cls = make_handler(static_dir, broker)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler_cls)

    thread = threading.Thread(
        target=_background_loop, args=(broker, poll_interval_seconds), daemon=True
    )
    thread.start()
    # Primer ciclo inmediato y síncrono para que /api/usage no responda vacío
    # justo después de arrancar.
    _recompute_and_maybe_publish(broker)

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
