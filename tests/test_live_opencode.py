import json
import os
import sqlite3
import tempfile
import unittest

from live import opencode
from live.model import SourceUnavailable

NOW = 1_790_000_000.0
MS = 1000

SCHEMA = """
CREATE TABLE session (id text PRIMARY KEY, directory text NOT NULL, title text NOT NULL,
  time_created integer NOT NULL, time_updated integer NOT NULL, time_archived integer);
CREATE TABLE part (id text PRIMARY KEY, message_id text NOT NULL, session_id text NOT NULL,
  time_created integer NOT NULL, time_updated integer NOT NULL, data text NOT NULL);
"""


class TestOpenCodeReader(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(os.unlink, self.db)
        self.con = sqlite3.connect(self.db)
        self.con.executescript(SCHEMA)

    def session(self, sid, updated, directory="/work/oc", archived=None, title="SECRET-XYZ"):
        self.con.execute("INSERT INTO session VALUES (?,?,?,?,?,?)",
                         (sid, directory, title, int((updated - 100) * MS), int(updated * MS),
                          None if archived is None else int(archived * MS)))
        self.con.commit()

    def part(self, pid, sid, created, updated, data):
        payload = data if isinstance(data, str) else json.dumps(data)
        self.con.execute("INSERT INTO part VALUES (?,?,?,?,?,?)",
                         (pid, "m1", sid, int(created * MS), int(updated * MS), payload))
        self.con.commit()

    def read(self):
        return opencode.read(NOW, db_path=self.db)

    def tool_part(self, pid, sid, status, created, tool="bash"):
        self.part(pid, sid, created, created + 1,
                  {"type": "tool", "tool": tool, "state": {"status": status, "input": {"command": "SECRET-XYZ"}}})

    def test_running_tool_is_pending(self):
        self.session("s1", NOW - 2)
        self.tool_part("p1", "s1", "running", NOW - 3)
        [f] = self.read()
        self.assertEqual((f.source, f.session_id, f.project), ("opencode", "s1", "/work/oc"))
        self.assertEqual((f.pending_tool, f.pending_since), ("bash", NOW - 3))
        self.assertFalse(f.ended)

    def test_pending_status_counts_and_completed_does_not(self):
        self.session("s1", NOW - 2)
        self.tool_part("p1", "s1", "pending", NOW - 6, tool="edit")
        self.tool_part("p2", "s1", "completed", NOW - 4, tool="read")
        [f] = self.read()
        self.assertEqual((f.pending_tool, f.pending_since), ("edit", NOW - 6))

    def test_most_recent_pending_wins(self):
        self.session("s1", NOW - 1)
        self.tool_part("p1", "s1", "running", NOW - 9, tool="read")
        self.tool_part("p2", "s1", "running", NOW - 3, tool="bash")
        [f] = self.read()
        self.assertEqual(f.pending_tool, "bash")

    def test_last_event_is_max_of_session_and_parts_in_seconds(self):
        self.session("s1", NOW - 50)
        self.tool_part("p1", "s1", "completed", NOW - 10)
        [f] = self.read()
        self.assertEqual(f.last_event, NOW - 9)

    def test_archived_session_is_ended(self):
        self.session("s1", NOW - 2, archived=NOW - 1)
        [f] = self.read()
        self.assertTrue(f.ended)

    def test_old_sessions_are_not_returned(self):
        self.session("viejo", NOW - 4000)
        self.assertEqual(self.read(), [])

    def test_malformed_part_json_does_not_invalidate_the_source(self):
        self.session("s1", NOW - 2)
        self.part("bad", "s1", NOW - 3, NOW - 3, "{esto no es json")
        self.tool_part("p1", "s1", "running", NOW - 3)
        [f] = self.read()
        self.assertEqual(f.pending_tool, "bash")

    def test_more_sessions_than_the_batch_size(self):
        for i in range(opencode.BATCH * 2 + 50):
            self.session(f"s{i}", NOW - 5)
        self.assertEqual(len(self.read()), opencode.BATCH * 2 + 50)

    def test_output_never_contains_text_or_inputs(self):
        self.session("s1", NOW - 2)
        self.tool_part("p1", "s1", "running", NOW - 3)
        self.assertNotIn("SECRET-XYZ", repr(self.read()))

    def test_missing_db_is_unavailable(self):
        with self.assertRaises(SourceUnavailable):
            opencode.read(NOW, db_path="/no/existe/opencode.db")

    def test_missing_table_is_unavailable(self):
        self.con.execute("DROP TABLE part")
        self.con.commit()
        with self.assertRaises(SourceUnavailable):
            self.read()

    def test_database_is_opened_read_only(self):
        self.session("s1", NOW - 2)
        self.read()
        con = sqlite3.connect(self.db)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM session").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
