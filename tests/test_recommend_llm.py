import json
import os
import subprocess
import tempfile
import unittest

from recommend import cluster, llm
from recommend.prompts import Prompt

CHAIN = ["nous:stealth/space-bunny-alpha", "nous:upstage/solar-pro4:free", "nous:inclusionai/ling:free"]
GOOD = {"groups": [{"group_id": "g1", "members": ["c1", "c2"]}],
        "recommendations": [{"group_id": "g1", "kind": "skill", "pattern": "Diagnosticar cobros",
                             "description": "Se repite", "draft": "---\nname: cobros\n---"}]}


def p(text, session):
    return Prompt("claude_code", "/home/u/DEV/ACME/app", session, "2026-09-20", text)


def cands():
    return [cluster._build("c1", [p("revisa los logs del servicio de pagos", "s1"),
                                  p("revisa los logs del servicio de pagos", "s2")], {}),
            cluster._build("c2", [p("mira las trazas del módulo de cobros", "s3"),
                                  p("mira las trazas del módulo de cobros", "s4")], {})]


class FakeRunner:
    """Cada llamada consume un comportamiento: dict → respuesta Hermes con
    usage-file; ("rc", código); ("timeout",); ("raw", stdout, usage|None)."""

    def __init__(self, *behaviours):
        self.behaviours = list(behaviours)
        self.calls = []

    def __call__(self, args, cwd, timeout):
        self.calls.append(args)
        behaviour = self.behaviours.pop(0)
        usage_path = args[args.index("--usage-file") + 1] if "--usage-file" in args else None
        if isinstance(behaviour, dict):
            behaviour = ("raw", json.dumps(behaviour), {"total_tokens": 900, "estimated_cost_usd": 0.0})
        if behaviour[0] == "timeout":
            raise subprocess.TimeoutExpired(args, timeout)
        if behaviour[0] == "rc":
            return behaviour[1], "", "fallo del proveedor"
        _, stdout, usage = behaviour
        if usage is not None and usage_path:
            with open(usage_path, "w") as fh:
                json.dump(usage, fh)
        return 0, stdout, ""


class TestParsing(unittest.TestCase):
    def test_extract_json_tolerates_fences_and_prose(self):
        text = "Claro, aquí va:\n```json\n" + json.dumps(GOOD) + "\n```\nEspero que sirva."
        self.assertEqual(llm.extract_json(text), GOOD)

    def test_extract_json_rejects_garbage(self):
        for bad in ("sin json", "{roto", "[1, 2]", "", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                llm.extract_json(bad)

    def test_check_schema(self):
        llm.check_schema(GOOD)
        for bad in ({}, {"groups": [], "recommendations": {}}, {"groups": "x", "recommendations": []}):
            with self.assertRaises(ValueError):
                llm.check_schema(bad)


class TestValidateGroups(unittest.TestCase):
    def test_valid_groups_and_orphans(self):
        groups = llm.validate_groups({"groups": [{"group_id": "g1", "members": ["c1", "c3"]}]}, ["c1", "c2", "c3"])
        self.assertEqual(groups, {"g1": ["c1", "c3"], "c2": ["c2"]})

    def test_unknown_member_discards_whole_group(self):
        groups = llm.validate_groups({"groups": [{"group_id": "g1", "members": ["c1", "c9"]}]}, ["c1", "c2"])
        self.assertEqual(groups, {"c1": ["c1"], "c2": ["c2"]})

    def test_repeated_candidate_first_claim_wins(self):
        data = {"groups": [{"group_id": "g1", "members": ["c1", "c2"]},
                           {"group_id": "g2", "members": ["c2", "c3"]},
                           {"group_id": "g3", "members": ["c3", "c3"]}]}
        self.assertEqual(llm.validate_groups(data, ["c1", "c2", "c3"]), {"g1": ["c1", "c2"], "c3": ["c3"]})

    def test_malformed_entries_and_orphan_id_collision(self):
        data = {"groups": ["x", {"group_id": 5, "members": ["c1"]}, {"group_id": "c2", "members": []},
                           {"group_id": "c2", "members": ["c1"]}]}
        self.assertEqual(llm.validate_groups(data, ["c1", "c2"]), {"c2": ["c1"], "c2-solo": ["c2"]})


class TestValidateRecommendations(unittest.TestCase):
    def test_filters_trims_and_redacts(self):
        data = {"recommendations": [
            {"group_id": "g1", "kind": "skill", "pattern": "p" * 300, "description": "d" * 900,
             "draft": "escribe a ana@acme.com\n" + "x" * 9000},
            {"group_id": "g1", "kind": "prompt", "pattern": "duplicado", "description": "d", "draft": "d"},
            {"group_id": "g9", "kind": "skill", "pattern": "p", "description": "d", "draft": "d"},
            {"group_id": "g2", "kind": "agente", "pattern": "p", "description": "d", "draft": "d"},
            {"group_id": "g3", "kind": "prompt", "pattern": "p", "description": "   ", "draft": "d"},
            {"group_id": ["g4"], "kind": "prompt", "pattern": "p", "description": "d", "draft": "d"},
            "basura",
        ]}
        recs = llm.validate_recommendations(data, {"g1", "g2", "g3"})
        self.assertEqual(list(recs), ["g1"])
        rec = recs["g1"]
        self.assertEqual((rec["kind"], len(rec["pattern"]), len(rec["description"]), len(rec["draft"])),
                         ("skill", 120, 400, 8000))
        self.assertNotIn("ana@acme.com", rec["draft"])


class TestPrompt(unittest.TestCase):
    def test_prompt_only_carries_summaries(self):
        long_text = "revisa los logs del servicio de pagos " + "detalle " * 80
        c = cluster._build("c1", [p(long_text, "s1"), p(long_text, "s2")], {})
        payload = llm.candidate_payload(c)
        self.assertEqual(set(payload), {"id", "pattern", "sessions", "days", "tokens", "features", "snippets"})
        prompt = llm.build_prompt([c])
        self.assertIn('"id": "c1"', prompt)
        self.assertIn('"groups"', prompt)
        self.assertNotIn(long_text.strip(), prompt)


class TestRunLlm(unittest.TestCase):
    def setUp(self):
        self.cwd = tempfile.mkdtemp()

    def run_chain(self, runner, chain=CHAIN, backend="hermes"):
        return llm.run_llm(cands(), backend, chain, runner=runner, cwd=self.cwd)

    def test_hermes_success_first_model(self):
        runner = FakeRunner(GOOD)
        result = self.run_chain(runner)
        self.assertTrue(result["ok"])
        self.assertEqual((result["model"], result["attempts"], result["llm_tokens"], result["llm_cost"]),
                         (CHAIN[0], 1, 900, 0.0))
        args = runner.calls[0]
        self.assertEqual(args[:2], ["hermes", "-z"])
        self.assertEqual(args[3:9], ["--provider", "nous", "-m", "stealth/space-bunny-alpha",
                                     "--ignore-rules", "--safe-mode"])
        self.assertEqual(os.listdir(self.cwd), [])  # el usage-file temporal se borra

    def test_fallback_through_chain(self):
        runner = FakeRunner(("rc", 1), ("timeout",), GOOD)
        result = self.run_chain(runner)
        self.assertTrue(result["ok"])
        self.assertEqual((result["model"], result["attempts"]), (CHAIN[2], 3))
        self.assertEqual(len(result["errors"]), 2)
        self.assertTrue(result["errors"][0].startswith(CHAIN[0] + ": "))
        self.assertIn("timeout", result["errors"][1])

    def test_invalid_json_and_cost_fall_through(self):
        runner = FakeRunner(("raw", "no es json", {"total_tokens": 5, "estimated_cost_usd": 0}),
                            ("raw", json.dumps(GOOD), {"total_tokens": 5, "estimated_cost_usd": 0.01}),
                            ("raw", json.dumps({"groups": {}}), {"total_tokens": 5}))
        result = self.run_chain(runner)
        self.assertFalse(result["ok"])
        self.assertIsNone(result["data"])
        self.assertEqual(result["attempts"], 3)
        self.assertIn("costo", result["errors"][1])

    def test_hermes_missing_usage_or_failed_is_attempt_failure(self):
        runner = FakeRunner(("raw", json.dumps(GOOD), None),
                            ("raw", json.dumps(GOOD), {"failed": True, "estimated_cost_usd": 0}),
                            GOOD)
        result = self.run_chain(runner)
        self.assertEqual((result["ok"], result["model"], result["attempts"]), (True, CHAIN[2], 3))
        self.assertIn("usage-file", result["errors"][0])
        self.assertIn("failed", result["errors"][1])

    def test_non_free_model_is_rejected_without_running(self):
        runner = FakeRunner(GOOD)
        result = self.run_chain(runner, chain=["nous:anthropic/claude-sonnet", CHAIN[0]])
        self.assertEqual((result["ok"], result["model"], result["attempts"]), (True, CHAIN[0], 2))
        self.assertEqual(len(runner.calls), 1)
        self.assertIn("free", result["errors"][0])

    def test_claude_backend_single_attempt(self):
        envelope = {"type": "result", "is_error": False, "result": "```json\n" + json.dumps(GOOD) + "\n```",
                    "total_cost_usd": 0.12,
                    "usage": {"input_tokens": 10, "output_tokens": 20, "cache_read_input_tokens": 30,
                              "cache_creation_input_tokens": 40}}
        runner = FakeRunner(("raw", json.dumps(envelope), None))
        result = self.run_chain(runner, backend="claude")
        self.assertEqual((result["ok"], result["model"], result["attempts"], result["llm_tokens"], result["llm_cost"]),
                         (True, "claude", 1, 100, 0.12))
        args = runner.calls[0]
        self.assertEqual(args[:2], ["claude", "-p"])
        # args[2] es el prompt con los candidatos (variable, no se compara literal)
        self.assertEqual(args[3:], ["--output-format", "json", "--model", "sonnet", "--tools", "",
                                     "--strict-mcp-config", "--disable-slash-commands",
                                     "--setting-sources", "", "--system-prompt", llm.CLAUDE_SYSTEM_PROMPT])

    def test_claude_backend_error_does_not_retry(self):
        runner = FakeRunner(("raw", json.dumps({"is_error": True, "result": "límite"}), None))
        result = self.run_chain(runner, backend="claude")
        self.assertEqual((result["ok"], result["attempts"], len(runner.calls)), (False, 1, 1))
