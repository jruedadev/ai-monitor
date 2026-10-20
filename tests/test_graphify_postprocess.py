"""Pruebas de scripts/graphify_postprocess.py: limpieza de falsos positivos de `calls`."""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "graphify_postprocess.py"
spec = importlib.util.spec_from_file_location("graphify_postprocess", SCRIPT)
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)


def _graph():
    return {
        "nodes": [
            {"id": "a_f", "label": "f()", "source_file": "a.py"},
            {"id": "b_g", "label": "g()", "source_file": "b.py"},
            {"id": "json", "label": "json"},  # módulo externo, sin archivo
        ],
        "links": [
            {"source": "a_f", "target": "b_g", "relation": "calls"},      # real: se conserva
            {"source": "a_f", "target": "json", "relation": "calls"},     # stub: se quita
            {"source": "a_f", "target": "a_f", "relation": "calls"},     # autoarista: se quita
            {"source": "a_f", "target": "json", "relation": "imports"},   # no es calls: se conserva
        ],
        "hyperedges": [],
    }


class CleanTests(unittest.TestCase):
    def test_removes_stub_and_self_calls_only(self):
        cleaned, stats = pp.clean(_graph())
        self.assertEqual(stats["removed_stub_calls"], 1)
        self.assertEqual(stats["removed_self_calls"], 1)
        relations = [(l["source"], l["target"], l["relation"]) for l in cleaned["links"]]
        self.assertEqual(
            relations,
            [("a_f", "b_g", "calls"), ("a_f", "json", "imports")],
        )

    def test_keeps_external_nodes(self):
        cleaned, _ = pp.clean(_graph())
        self.assertEqual({n["id"] for n in cleaned["nodes"]}, {"a_f", "b_g", "json"})

    def test_is_idempotent(self):
        once, _ = pp.clean(_graph())
        twice, stats = pp.clean(once)
        self.assertEqual(twice, once)
        self.assertEqual(stats["removed_stub_calls"], 0)
        self.assertEqual(stats["removed_self_calls"], 0)

    def test_accepts_edges_key(self):
        data = _graph()
        data["edges"] = data.pop("links")
        cleaned, stats = pp.clean(data)
        self.assertEqual(stats["links_after"], 2)
        self.assertIn("edges", cleaned)


class MainTests(unittest.TestCase):
    def test_main_rewrites_graph_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "graph.json"
            path.write_text(json.dumps(_graph()), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pp.main(["--graph", str(path)]), 0)
            written = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(written["links"]), 2)
            # segunda ejecución: no cambia nada
            before = path.read_text(encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                pp.main(["--graph", str(path)])
            self.assertEqual(path.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
