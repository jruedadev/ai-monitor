import json
import os
import sqlite3
import tempfile
import unittest

from live import hermes
from live.model import SourceUnavailable

NOW = 1_790_000_000.0

SCHEMA = """
CREATE TABLE sessions (id TEXT PRIMARY KEY, cwd TEXT, last_activity_at REAL, ended_at REAL, title TEXT);
CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, role TEXT NOT NULL,
  content TEXT, tool_calls TEXT, tool_call_id TEXT, timestamp REAL NOT NULL);
"""


class TestHermesReader(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(os.unlink, self.db)
        self.con = sqlite3.connect(self.db)
        self.con.executescript(SCHEMA)

    def session(self, sid, last, cwd="/work/h", ended=None):
        self.con.execute("INSERT INTO sessions VALUES (?,?,?,?,?)", (sid, cwd, last, ended, "SECRET-XYZ"))
        self.con.commit()

    def msg(self, sid, role, ts, tool_calls=None, tool_call_id=None):
        tc = tool_calls if (tool_calls is None or isinstance(tool_calls, str)) else json.dumps(tool_calls)
        self.con.execute(
            "INSERT INTO messages (session_id, role, content, tool_calls, tool_call_id, timestamp) VALUES (?,?,?,?,?,?)",
            (sid, role, "SECRET-XYZ", tc, tool_call_id, ts))
        self.con.commit()

    def read(self):
        return hermes.read(NOW, db_path=self.db)

    def test_pending_tool_call(self):
        self.session("s1", NOW - 2)
        self.msg("s1", "assistant", NOW - 3, [{"id": "c1", "function": {"name": "terminal", "arguments": "SECRET-XYZ"}}])
        [f] = self.read()
        self.assertEqual((f.source, f.session_id, f.project), ("hermes", "s1", "/work/h"))
        self.assertEqual((f.pending_tool, f.pending_since), ("terminal", NOW - 3))

    def test_resolved_tool_call_is_not_pending(self):
        self.session("s1", NOW - 1)
        self.msg("s1", "assistant", NOW - 5, [{"id": "c1", "function": {"name": "terminal"}}])
        self.msg("s1", "tool", NOW - 2, tool_call_id="c1")
        [f] = self.read()
        self.assertIsNone(f.pending_tool)
        self.assertEqual(f.last_event, NOW - 1)

    def test_flat_name_and_most_recent_pending(self):
        self.session("s1", NOW - 1)
        self.msg("s1", "assistant", NOW - 9, [{"id": "c1", "name": "read_file"}])
        self.msg("s1", "assistant", NOW - 4, [{"id": "c2", "function": {"name": "execute_code"}}])
        [f] = self.read()
        self.assertEqual((f.pending_tool, f.pending_since), ("execute_code", NOW - 4))

    def test_odd_tool_calls_shapes_are_ignored(self):
        self.session("s1", NOW - 1)
        for bad in (None, "no es json", "[1, 2, 3]", "{}", '[{"id": "c9"}]', '[{"function": {"name": 7}}]'):
            self.msg("s1", "assistant", NOW - 3, bad)
        [f] = self.read()
        self.assertIsNone(f.pending_tool)

    def test_ended_session(self):
        self.session("s1", NOW - 2, ended=NOW - 1)
        [f] = self.read()
        self.assertTrue(f.ended)

    def test_old_session_not_returned(self):
        self.session("viejo", NOW - 4000)
        self.assertEqual(self.read(), [])

    def test_more_sessions_than_the_batch_size(self):
        for i in range(hermes.BATCH + 30):
            self.session(f"s{i}", NOW - 5)
        self.assertEqual(len(self.read()), hermes.BATCH + 30)

    def test_output_never_contains_content(self):
        self.session("s1", NOW - 2)
        self.msg("s1", "assistant", NOW - 3, [{"id": "c1", "function": {"name": "terminal", "arguments": "SECRET-XYZ"}}])
        self.assertNotIn("SECRET-XYZ", repr(self.read()))

    def test_missing_db_and_missing_table_are_unavailable(self):
        with self.assertRaises(SourceUnavailable):
            hermes.read(NOW, db_path="/no/existe/state.db")
        self.con.execute("DROP TABLE messages")
        self.con.commit()
        with self.assertRaises(SourceUnavailable):
            self.read()


if __name__ == "__main__":
    unittest.main()
