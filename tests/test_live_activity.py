import unittest
from unittest.mock import patch

from live import activity
from live.model import SessionFacts, SourceUnavailable, iso_utc

NOW = 1_790_000_000.0


def f(source, sid, last, **kw):
    return SessionFacts(source, sid, "/p", last, kw.get("tool"), kw.get("since"))


class TestSnapshot(unittest.TestCase):
    def test_exact_shape_and_all_three_sources(self):
        snap = activity.snapshot(NOW, readers={
            "claude_code": lambda now: [f("claude_code", "a", NOW - 2, tool="Bash", since=NOW - 2)],
            "opencode": lambda now: [],
            "hermes": lambda now: (_ for _ in ()).throw(SourceUnavailable("x")),
        })
        self.assertEqual(set(snap), {"generated_at", "agents", "sources"})
        self.assertEqual(snap["generated_at"], iso_utc(NOW))
        self.assertEqual(snap["sources"], {"claude_code": "ok", "opencode": "ok", "hermes": "unavailable"})
        self.assertEqual(snap["agents"], [{
            "key": "claude_code:a", "source": "claude_code", "project": "/p", "state": "tool",
            "tool": "Bash", "tool_kind": "run", "since": iso_utc(NOW - 2),
        }])

    def test_any_exception_marks_only_that_source_unavailable(self):
        def boom(now):
            raise RuntimeError("inesperado")
        snap = activity.snapshot(NOW, readers={
            "claude_code": boom,
            "opencode": lambda now: [f("opencode", "o", NOW - 5)],
            "hermes": lambda now: [],
        })
        self.assertEqual(snap["sources"], {"claude_code": "unavailable", "opencode": "ok", "hermes": "ok"})
        self.assertEqual([a["key"] for a in snap["agents"]], ["opencode:o"])

    def test_sorted_by_since_descending_and_omitted_sessions_dropped(self):
        snap = activity.snapshot(NOW, readers={
            "claude_code": lambda now: [f("claude_code", "viejo", NOW - 900), f("claude_code", "nuevo", NOW - 10),
                                        f("claude_code", "fuera", NOW - 4000)],
            "opencode": lambda now: [],
            "hermes": lambda now: [],
        })
        self.assertEqual([a["key"] for a in snap["agents"]], ["claude_code:nuevo", "claude_code:viejo"])

    def test_default_readers_never_raise_when_nothing_exists(self):
        with patch.dict("os.environ", {"HOME": "/no/existe"}):
            snap = activity.snapshot(NOW)
        self.assertEqual(snap["sources"], {"claude_code": "unavailable", "opencode": "unavailable", "hermes": "unavailable"})
        self.assertEqual(snap["agents"], [])


if __name__ == "__main__":
    unittest.main()
