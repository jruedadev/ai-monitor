"""Server-Sent Events: formateo puro + un broker en memoria thread-safe.
Sin dependencia de sockets/HTTP — server.py conecta esto a las conexiones reales.
"""
import queue
import threading


def format_sse_event(event_name, data):
    lines = data.split("\n")
    body = "".join(f"data: {line}\n" for line in lines)
    return f"event: {event_name}\n{body}\n".encode("utf-8")


class SSEBroker:
    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers = []

    def subscribe(self):
        q = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def publish(self, event_name, data):
        payload = format_sse_event(event_name, data)
        with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            q.put(payload)
