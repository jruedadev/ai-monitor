import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from live import claude_code
from live.model import SourceUnavailable

NOW = 1_790_000_000.0


def iso(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def assistant_tool(ts, tool_id, name="Bash", cwd="/work/app"):
    return {"type": "assistant", "timestamp": iso(ts), "cwd": cwd,
            "message": {"content": [{"type": "tool_use", "id": tool_id, "name": name,
                                     "input": {"command": "SECRET-XYZ"}}]}}


def user_result(ts, tool_id, cwd="/work/app"):
    return {"type": "user", "timestamp": iso(ts), "cwd": cwd,
            "message": {"content": [{"type": "tool_result", "tool_use_id": tool_id, "content": "SECRET-XYZ"}]}}


class TestClaudeCodeReader(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.proj = os.path.join(self.root, "-work-app")
        os.makedirs(self.proj)

    def write(self, name, records, raw_tail=b"", mtime=None):
        path = os.path.join(self.proj, f"{name}.jsonl")
        with open(path, "wb") as f:
            for rec in records:
                f.write(json.dumps(rec).encode() + b"\n")
            f.write(raw_tail)
        os.utime(path, (mtime or NOW, mtime or NOW))
        return path

    def read(self):
        return claude_code.read(NOW, projects_dir=self.root)

    def test_pending_tool_use(self):
        self.write("sess1", [assistant_tool(NOW - 3, "t1")])
        [f] = self.read()
        self.assertEqual((f.source, f.session_id, f.project), ("claude_code", "sess1", "/work/app"))
        self.assertEqual((f.pending_tool, f.pending_since), ("Bash", NOW - 3))
        self.assertEqual(f.last_event, NOW - 3)

    def test_resolved_tool_use_is_not_pending(self):
        self.write("sess1", [assistant_tool(NOW - 10, "t1"), user_result(NOW - 5, "t1")])
        [f] = self.read()
        self.assertIsNone(f.pending_tool)
        self.assertEqual(f.last_event, NOW - 5)

    def test_several_pending_picks_most_recent(self):
        self.write("sess1", [assistant_tool(NOW - 20, "t1", "Read"), assistant_tool(NOW - 4, "t2", "Edit")])
        [f] = self.read()
        self.assertEqual((f.pending_tool, f.pending_since), ("Edit", NOW - 4))

    def test_corrupt_line_in_the_middle_is_skipped(self):
        path = self.write("sess1", [assistant_tool(NOW - 3, "t1")])
        with open(path, "ab") as f:
            f.write(b"{no es json\n")
        os.utime(path, (NOW, NOW))
        [f] = self.read()
        self.assertEqual(f.pending_tool, "Bash")

    def test_half_written_last_line_is_skipped(self):
        self.write("sess1", [assistant_tool(NOW - 3, "t1")], raw_tail=b'{"type": "assistant", "timest')
        [f] = self.read()
        self.assertEqual(f.pending_tool, "Bash")

    def test_old_mtime_file_is_ignored(self):
        self.write("viejo", [assistant_tool(NOW - 3, "t1")], mtime=NOW - 3600)
        self.assertEqual(self.read(), [])

    def test_only_the_tail_of_a_big_file_is_read(self):
        filler = {"type": "user", "timestamp": iso(NOW - 4000), "cwd": "/viejo", "message": {"content": "x" * 200}}
        path = os.path.join(self.proj, "big.jsonl")
        with open(path, "wb") as f:
            while f.tell() < 5 * 1024 * 1024:
                f.write(json.dumps(filler).encode() + b"\n")
            f.write(json.dumps(assistant_tool(NOW - 2, "t9", cwd="/work/app")).encode() + b"\n")
        os.utime(path, (NOW, NOW))
        [f] = self.read()
        self.assertEqual(f.project, "/work/app")
        self.assertEqual(f.pending_tool, "Bash")

    def test_records_without_valid_timestamp_do_not_crash(self):
        self.write("sess1", [{"type": "user", "cwd": "/work/app", "message": {"content": "hola"}},
                             {"type": "assistant", "timestamp": "no-fecha", "message": {"content": []}}])
        [f] = self.read()
        self.assertIsNone(f.last_event)

    def test_project_unknown_without_cwd(self):
        self.write("sess1", [{"type": "user", "timestamp": iso(NOW - 1), "message": {"content": "x"}}])
        [f] = self.read()
        self.assertEqual(f.project, "unknown")

    def test_output_never_contains_tool_input_or_result(self):
        self.write("sess1", [assistant_tool(NOW - 3, "t1")])
        self.assertNotIn("SECRET-XYZ", repr(self.read()))

    def test_missing_directory_is_unavailable(self):
        with self.assertRaises(SourceUnavailable):
            claude_code.read(NOW, projects_dir=os.path.join(self.root, "no-existe"))


if __name__ == "__main__":
    unittest.main()
