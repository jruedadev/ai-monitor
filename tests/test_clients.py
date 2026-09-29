import json
import os
import unittest

import clients

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "client_of_cases.json")


class TestClientOf(unittest.TestCase):
    def test_shared_fixture_matches_clients_ts(self):
        with open(FIXTURE) as fh:
            cases = json.load(fh)
        for case in cases:
            roots = case["roots"] if case["roots"] is not None else clients.default_roots()
            with self.subTest(path=case["path"], roots=case["roots"]):
                self.assertEqual(clients.client_of(case["path"], roots), case["client"])

    def test_default_roots_is_a_fresh_copy(self):
        roots = clients.default_roots()
        roots[0]["root"] = "X"
        self.assertEqual(clients.default_roots(), [{"root": "DEV", "mode": "cliente"}])


class TestNormalizeRoots(unittest.TestCase):
    def test_strips_spaces_and_trailing_slash(self):
        self.assertEqual(
            clients.normalize_roots([{"root": "  DEV ", "mode": "cliente"}, {"root": "/srv/trabajo/", "mode": "plano"}]),
            [{"root": "DEV", "mode": "cliente"}, {"root": "/srv/trabajo", "mode": "plano"}],
        )

    def test_rejects_invalid_payloads(self):
        too_many = [{"root": f"r{i}", "mode": "cliente"} for i in range(21)]
        cases = {
            "no es lista": {"root": "DEV", "mode": "cliente"},
            "vacía": [],
            "demasiadas": too_many,
            "no es objeto": ["DEV"],
            "claves de más": [{"root": "DEV", "mode": "cliente", "x": 1}],
            "root no string": [{"root": 3, "mode": "cliente"}],
            "root vacío": [{"root": "   ", "mode": "cliente"}],
            "solo barra": [{"root": "/", "mode": "cliente"}],
            "nombre con barra": [{"root": "DEV/clientes", "mode": "cliente"}],
            "demasiado largo": [{"root": "a" * 201, "mode": "cliente"}],
            "modo inválido": [{"root": "DEV", "mode": "otro"}],
            "duplicado por mayúsculas": [{"root": "DEV", "mode": "cliente"}, {"root": "dev", "mode": "plano"}],
            "duplicado por barra final": [{"root": "/srv/x", "mode": "cliente"}, {"root": "/srv/x/", "mode": "plano"}],
        }
        for name, payload in cases.items():
            with self.subTest(name), self.assertRaises(clients.ClientRootsError):
                clients.normalize_roots(payload)

    def test_absolute_paths_keep_case_for_duplicates(self):
        roots = clients.normalize_roots([{"root": "/srv/X", "mode": "cliente"}, {"root": "/srv/x", "mode": "cliente"}])
        self.assertEqual(len(roots), 2)


class TestParseStoredRoots(unittest.TestCase):
    def test_valid_json(self):
        self.assertEqual(clients.parse_stored_roots('[{"root": "work", "mode": "plano"}]'),
                         [{"root": "work", "mode": "plano"}])

    def test_invalid_falls_back_to_default(self):
        for raw in (None, "", "{roto", "[]", '[{"root": "", "mode": "cliente"}]', '"DEV"'):
            with self.subTest(raw=raw):
                self.assertEqual(clients.parse_stored_roots(raw), clients.default_roots())


if __name__ == "__main__":
    unittest.main()
