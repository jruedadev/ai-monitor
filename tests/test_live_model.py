import unittest

from live import model
from live.model import SessionFacts

NOW = 1_790_000_000.0


def facts(**kw):
    base = dict(source="claude_code", session_id="s1", project="/p", last_event=NOW - 5,
                pending_tool=None, pending_since=None)
    base.update(kw)
    return SessionFacts(**base)


class TestClassifyTool(unittest.TestCase):
    def test_classes_case_insensitive(self):
        for name in ("Edit", "WRITE", "MultiEdit", "NotebookEdit", "patch", "apply_patch",
                     "str_replace_editor", "TodoWrite"):
            self.assertEqual(model.classify_tool(name), "edit", name)
        for name in ("Read", "grep", "Glob", "ls", "list", "WebFetch", "WebSearch", "search", "codesearch"):
            self.assertEqual(model.classify_tool(name), "read", name)
        for name in ("Bash", "shell", "terminal", "exec", "execute_code", "Task", "agent"):
            self.assertEqual(model.classify_tool(name), "run", name)

    def test_other_and_none(self):
        self.assertEqual(model.classify_tool("mcp__x__y"), "other")
        self.assertEqual(model.classify_tool(None), "other")
        self.assertEqual(model.classify_tool(""), "other")


class TestDeriveState(unittest.TestCase):
    def state(self, **kw):
        res = model.derive_state(facts(**kw), NOW)
        return res[0] if res else None

    def test_tool_then_waiting_at_8_seconds(self):
        self.assertEqual(self.state(pending_tool="Bash", pending_since=NOW - 7.9), "tool")
        self.assertEqual(self.state(pending_tool="Bash", pending_since=NOW - 8), "waiting")

    def test_thinking_until_60_seconds_then_idle(self):
        self.assertEqual(self.state(last_event=NOW - 59), "thinking")
        self.assertEqual(self.state(last_event=NOW - 60), "idle")

    def test_omitted_after_30_minutes(self):
        self.assertEqual(self.state(last_event=NOW - 1800), "idle")
        self.assertIsNone(self.state(last_event=NOW - 1801))

    def test_omitted_when_ended_or_without_events(self):
        self.assertIsNone(self.state(ended=True))
        self.assertIsNone(self.state(last_event=None))

    def test_future_event_within_skew_counts_as_now(self):
        self.assertEqual(self.state(last_event=NOW + 30), "thinking")
        self.assertIsNone(self.state(last_event=NOW + 120))

    def test_since_is_pending_since_or_last_event(self):
        self.assertEqual(model.derive_state(facts(pending_tool="Bash", pending_since=NOW - 3), NOW), ("tool", NOW - 3))
        self.assertEqual(model.derive_state(facts(last_event=NOW - 20), NOW), ("thinking", NOW - 20))

    def test_pending_tool_without_since_is_not_pending(self):
        self.assertEqual(self.state(pending_tool="Bash", pending_since=None), "thinking")


class TestToAgent(unittest.TestCase):
    def test_tool_agent_shape(self):
        agent = model.to_agent(facts(pending_tool="Bash", pending_since=NOW - 2), NOW)
        self.assertEqual(agent, {
            "key": "claude_code:s1", "source": "claude_code", "project": "/p", "state": "tool",
            "tool": "Bash", "tool_kind": "run", "since": model.iso_utc(NOW - 2),
        })

    def test_idle_has_null_tool_fields_and_z_suffix(self):
        agent = model.to_agent(facts(last_event=NOW - 600), NOW)
        self.assertIsNone(agent["tool"])
        self.assertIsNone(agent["tool_kind"])
        self.assertRegex(agent["since"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_omitted_returns_none(self):
        self.assertIsNone(model.to_agent(facts(ended=True), NOW))


if __name__ == "__main__":
    unittest.main()
