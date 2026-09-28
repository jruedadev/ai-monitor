import json
import os
import sqlite3
import tempfile
import unittest

from recommend import prompts
from recommend.prompts import claude_code, codex, hermes, opencode

APP = "/home/u/DEV/ACME/app"
LONG = "revisa el endpoint de facturas y corrige la validación"  # >20 caracteres


def write_jsonl(path, records):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        for rec in records:
            fh.write((rec if isinstance(rec, str) else json.dumps(rec)) + "\n")


def cc_user(content, ts="2026-09-20T10:00:00Z", cwd=APP, **extra):
    return {"type": "user", "timestamp": ts, "cwd": cwd, "sessionId": "x",
            "message": {"role": "user", "content": content}, **extra}


class TestHelpers(unittest.TestCase):
    def test_clean_text(self):
        self.assertIsNone(prompts.clean_text("corto"))
        self.assertIsNone(prompts.clean_text("<command-name>/clear</command-name> y algo más largo"))
        self.assertIsNone(prompts.clean_text(None))
        self.assertIsNone(prompts.clean_text(["no", "es", "texto"]))
        self.assertEqual(prompts.clean_text("  " + LONG + "  "), LONG)
        self.assertEqual(len(prompts.clean_text("x" * 5000)), 4000)

    def test_days(self):
        self.assertEqual(prompts.day_from_iso("2026-09-20T23:30:00-05:00"), "2026-09-21")
        self.assertEqual(prompts.day_from_iso("2026-09-20T10:00:00Z"), "2026-09-20")
        self.assertIsNone(prompts.day_from_iso("no-fecha"))
        self.assertIsNone(prompts.day_from_iso(None))
        self.assertEqual(prompts.day_from_epoch(1790000000), "2026-09-21")
        self.assertIsNone(prompts.day_from_epoch("x"))

    def test_is_engine_project(self):
        self.assertTrue(prompts.is_engine_project("/e/motor", engine_dir="/e/motor"))
        self.assertTrue(prompts.is_engine_project("/e/motor/sub", engine_dir="/e/motor"))
        self.assertFalse(prompts.is_engine_project("/e/motor-otro", engine_dir="/e/motor"))
        self.assertFalse(prompts.is_engine_project(None, engine_dir="/e/motor"))


class TestClaudeCode(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def test_reads_str_and_text_blocks(self):
        write_jsonl(os.path.join(self.root, "-enc", "s1.jsonl"), [
            {"type": "summary"},
            cc_user(LONG),
            cc_user([{"type": "text", "text": LONG + " parte uno"}, {"type": "text", "text": "parte dos"}]),
            "{corrupto",
        ])
        found = claude_code.read_prompts("2026-09-01", self.root)
        self.assertEqual([p.text for p in found], [LONG, LONG + " parte uno\nparte dos"])
        self.assertEqual({(p.source, p.project, p.session_id, p.day_utc) for p in found},
                         {("claude_code", APP, "s1", "2026-09-20")})

    def test_skips_injected_tool_result_and_odd_content(self):
        write_jsonl(os.path.join(self.root, "-enc", "s1.jsonl"), [
            cc_user([{"type": "tool_result", "content": LONG}]),
            cc_user("<local-command-stdout>" + LONG + "</local-command-stdout>"),
            cc_user(LONG, isMeta=True),
            cc_user(LONG, isCompactSummary=True),
            cc_user(None),
            cc_user(42),
            cc_user([None, "texto suelto", {"type": "text"}]),
            {"type": "user", "timestamp": "2026-09-20T10:00:00Z", "message": "no-dict"},
            ["no", "es", "un", "objeto"],
        ])
        self.assertEqual(claude_code.read_prompts("2026-09-01", self.root), [])

    def test_window_and_missing_dir(self):
        write_jsonl(os.path.join(self.root, "-enc", "s1.jsonl"), [
            cc_user(LONG, ts="2026-08-01T10:00:00Z"), cc_user(LONG, ts="sin-fecha")])
        self.assertEqual(claude_code.read_prompts("2026-09-01", self.root), [])
        self.assertEqual(claude_code.read_prompts("2026-09-01", os.path.join(self.root, "no")), [])


class TestCodex(unittest.TestCase):
    def test_reads_user_messages_recursively(self):
        root = tempfile.mkdtemp()
        write_jsonl(os.path.join(root, "2026", "09", "20", "rollout-a.jsonl"), [
            {"type": "session_meta", "timestamp": "2026-09-20T10:00:00Z", "payload": {"id": "th-1", "cwd": APP}},
            {"type": "response_item", "timestamp": "2026-09-20T10:00:01Z",
             "payload": {"type": "message", "role": "user",
                         "content": [{"type": "input_text", "text": "<environment_context>x</environment_context>"}]}},
            {"type": "response_item", "timestamp": "2026-09-20T10:00:02Z",
             "payload": {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": LONG}]}},
            {"type": "response_item", "timestamp": "2026-09-20T10:00:03Z",
             "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": LONG}]}},
        ])
        write_jsonl(os.path.join(root, "2026", "09", "21", "rollout-b.jsonl"), [
            {"type": "turn_context", "timestamp": "2026-09-21T10:00:00Z", "payload": {"cwd": "/tmp/otro"}},
            {"type": "response_item", "timestamp": "2026-09-21T10:00:03Z",
             "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": LONG}]}},
        ])
        found = sorted(codex.read_prompts("2026-09-01", root))
        self.assertEqual([(p.project, p.session_id, p.day_utc) for p in found],
                         [(APP, "th-1", "2026-09-20"), ("/tmp/otro", "rollout-b", "2026-09-21")])

    def test_missing_dir(self):
        self.assertEqual(codex.read_prompts("2026-09-01", "/no/existe"), [])


def make_opencode_db(path):
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE session (id TEXT PRIMARY KEY, directory TEXT);
        CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER, data TEXT);
        CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT, time_created INTEGER, data TEXT);
    """)
    ms = 1790000000 * 1000
    con.execute("INSERT INTO session VALUES ('ses1', ?)", (APP,))
    con.execute("INSERT INTO message VALUES ('m1', 'ses1', ?, ?)", (ms, json.dumps({"role": "user"})))
    con.execute("INSERT INTO message VALUES ('m2', 'ses1', ?, ?)", (ms, json.dumps({"role": "assistant"})))
    con.executemany("INSERT INTO part VALUES (?, ?, 'ses1', ?, ?)", [
        ("p1", "m1", ms, json.dumps({"type": "text", "text": LONG})),
        ("p2", "m1", ms, json.dumps({"type": "text", "text": "y agrega tests", "synthetic": False})),
        ("p3", "m1", ms, json.dumps({"type": "text", "text": "contenido de archivo", "synthetic": True})),
        ("p4", "m2", ms, json.dumps({"type": "text", "text": LONG})),
    ])
    con.commit()
    con.close()


class TestOpenCode(unittest.TestCase):
    def test_concatenates_text_parts_of_user_messages(self):
        path = os.path.join(tempfile.mkdtemp(), "opencode.db")
        make_opencode_db(path)
        found = opencode.read_prompts("2026-09-01", path)
        self.assertEqual(found, [prompts.Prompt("opencode", APP, "ses1", "2026-09-21", LONG + "\ny agrega tests")])

    def test_missing_file_and_corrupt_db(self):
        self.assertEqual(opencode.read_prompts("2026-09-01", "/no/existe.db"), [])
        path = os.path.join(tempfile.mkdtemp(), "opencode.db")
        with open(path, "w") as fh:
            fh.write("esto no es sqlite" * 100)
        with self.assertRaises(sqlite3.Error):
            opencode.read_prompts("2026-09-01", path)


class TestHermes(unittest.TestCase):
    def test_reads_user_messages_with_project_resolution(self):
        path = os.path.join(tempfile.mkdtemp(), "state.db")
        con = sqlite3.connect(path)
        con.executescript("""
            CREATE TABLE sessions (id TEXT PRIMARY KEY, cwd TEXT, source TEXT, chat_type TEXT);
            CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, timestamp REAL);
        """)
        con.execute("INSERT INTO sessions VALUES ('h1', ?, 'cli', NULL)", (APP,))
        con.execute("INSERT INTO sessions VALUES ('h2', NULL, 'telegram', 'dm')")
        con.executemany("INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)", [
            ("h1", "user", LONG, 1790000000.5), ("h1", "assistant", LONG, 1790000001),
            ("h2", "user", LONG, 1790000002), ("h2", "user", None, 1790000003),
        ])
        con.commit()
        con.close()
        found = hermes.read_prompts("2026-09-01", path)
        self.assertEqual([(p.project, p.session_id) for p in found], [(APP, "h1"), ("telegram:dm", "h2")])

    def test_without_messages_table(self):
        path = os.path.join(tempfile.mkdtemp(), "state.db")
        sqlite3.connect(path).close()
        self.assertEqual(hermes.read_prompts("2026-09-01", path), [])


class TestReadAll(unittest.TestCase):
    def test_self_exclusion_and_errors(self):
        tmp = tempfile.mkdtemp()
        engine_dir = os.path.join(tmp, "motor")
        claude_root = os.path.join(tmp, "claude")
        write_jsonl(os.path.join(claude_root, "-a", "s1.jsonl"), [cc_user(LONG)])
        write_jsonl(os.path.join(claude_root, "-b", "s2.jsonl"), [cc_user(LONG, cwd=engine_dir)])
        corrupt = os.path.join(tmp, "opencode.db")
        with open(corrupt, "w") as fh:
            fh.write("basura" * 200)
        found, errors = prompts.read_all("2026-09-01", {
            "claude_code": claude_root, "codex": os.path.join(tmp, "no"),
            "opencode": corrupt, "hermes": os.path.join(tmp, "no.db"),
        }, engine_dir=engine_dir)
        self.assertEqual([p.session_id for p in found], ["s1"])
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("opencode: "))
