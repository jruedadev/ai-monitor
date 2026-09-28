import unittest

from recommend import cluster
from recommend.prompts import Prompt

REPEATED = "revisa los logs del servicio de pagos y dime por qué falla el cobro con tarjeta"
OTHER = "explícame cómo funciona el patrón repositorio en una aplicación hexagonal grande"


def p(text, session, day="2026-09-20", source="claude_code", project="/home/u/DEV/ACME/app"):
    return Prompt(source, project, session, day, text)


class TestNormalize(unittest.TestCase):
    def test_normalize_strips_accents_punctuation_and_stopwords(self):
        self.assertEqual(cluster.normalize("¡Revisa LOS logs, del Servicio de pagos!"),
                         ["revisa", "logs", "servicio", "pagos"])

    def test_trigrams(self):
        self.assertEqual(cluster.trigrams(["a", "b", "c", "d"]), {"a b c", "b c d"})
        self.assertEqual(cluster.trigrams(["hola", "mundo"]), {"hola mundo"})
        self.assertEqual(cluster.trigrams([]), set())

    def test_jaccard(self):
        self.assertEqual(cluster.jaccard({"a", "b"}, {"b", "c"}), 1 / 3)
        self.assertEqual(cluster.jaccard(set(), {"a"}), 0.0)


class TestGrouping(unittest.TestCase):
    def test_thresholds_via_union_find(self):
        sets = [{"a", "b", "c", "d"}, {"a", "b", "c", "e"}, {"a", "b", "f", "g"}, {"x", "y"}]
        # J(0,1)=0.6, J(0,2)=J(1,2)=2/6≈0.33
        self.assertEqual(sorted(map(sorted, cluster._union_find_groups(sets, 0.5))), [[0, 1], [2], [3]])
        self.assertEqual(sorted(map(sorted, cluster._union_find_groups(sets, 0.3))), [[0, 1, 2], [3]])

    def test_candidates_need_two_sessions_and_are_ranked_by_tokens(self):
        prompts = [p(REPEATED, "s1"), p(REPEATED, "s1"),                  # una sola sesión: no es candidato
                   p(OTHER, "s2"), p(OTHER + " ahora", "s3"),               # dos sesiones: candidato
                   p("tarea única sin parecido con ninguna otra cosa", "s4")]
        found = cluster.candidates(prompts, {("claude_code", "s2"): 50, ("claude_code", "s3"): 70})
        self.assertEqual([c.cluster_id for c in found], ["c1"])
        self.assertEqual(found[0].tokens, 120)
        self.assertEqual(len(found[0].sessions), 2)

    def test_candidates_limit(self):
        prompts = []
        for i in range(45):
            text = f"tema{i} alfa{i} beta{i} gamma{i} delta{i}"
            prompts += [p(text, f"a{i}"), p(text, f"b{i}")]
        tokens = {("claude_code", f"a{i}"): i for i in range(45)}
        found = cluster.candidates(prompts, tokens)
        self.assertEqual(len(found), 40)
        self.assertEqual(found[0].cluster_id, "c1")
        self.assertGreaterEqual(found[0].tokens, found[-1].tokens)

    def test_lexical_mode_applies_final_thresholds(self):
        three_sessions_two_days = [p(REPEATED, "s1", "2026-09-20"), p(REPEATED, "s2", "2026-09-20"),
                                   p(REPEATED, "s3", "2026-09-21")]
        three_sessions_one_day = [p(OTHER, f"o{i}", "2026-09-22") for i in range(3)]
        found = cluster.lexical_clusters(three_sessions_two_days + three_sessions_one_day, {})
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].days, {"2026-09-20", "2026-09-21"})
        self.assertEqual(found[0].cluster_id, "c1")

    def test_missing_session_tokens_fall_back_to_text_length(self):
        found = cluster.lexical_clusters([p(REPEATED, "s1", "2026-09-20"), p(REPEATED, "s2", "2026-09-20"),
                                          p(REPEATED, "s3", "2026-09-21")], {("claude_code", "s1"): 1000})
        self.assertEqual(found[0].tokens, 1000 + 2 * (len(REPEATED) // 4))


class TestClusterProperties(unittest.TestCase):
    def test_pattern_tool_and_evidence(self):
        c = cluster._build("c1", [p(REPEATED + "\nsegunda línea", "s1"), p(REPEATED, "s2", source="codex"),
                                  p(REPEATED + " y más contexto", "s3", "2026-09-21", project="/home/u/DEV/OTRO/x")], {})
        self.assertEqual(c.pattern, REPEATED)
        self.assertEqual(c.tool, "varias")
        ev = c.evidence()
        self.assertEqual(ev["sessions"], 3)
        self.assertEqual(ev["days"], 2)
        self.assertEqual(ev["sources"], ["claude_code", "codex"])
        self.assertEqual(ev["projects"], ["/home/u/DEV/ACME/app", "/home/u/DEV/OTRO/x"])
        self.assertLessEqual(len(ev["snippets"]), 3)
        self.assertTrue(all(len(s) <= 200 for s in ev["snippets"]))

    def test_features(self):
        log = "Traceback (most recent call last):\n  File \"x.py\", line 1\nValueError: boom"
        c = cluster._build("c1", [p("revisa este error de sentry: " + log, "s1"),
                                  p("revisa y corrige y luego ejecuta los tests del módulo", "s2"),
                                  p("revisa y corrige y luego ejecuta los tests del otro módulo", "s3")], {})
        self.assertTrue(c.features["pega_datos"])
        self.assertEqual(c.features["menciona_servicio"], ["sentry"])
        self.assertTrue(c.features["mismos_pasos"])
        self.assertEqual(c.common_steps(), ["revisa", "corrige", "ejecuta"])

    def test_plain_text_has_no_features(self):
        c = cluster._build("c1", [p(OTHER, "s1"), p(OTHER, "s2")], {})
        self.assertEqual(c.features, {"pega_datos": False, "menciona_servicio": [], "mismos_pasos": False})


class TestMerge(unittest.TestCase):
    def test_merge_unions_members_signature_and_ors_features(self):
        a = cluster._build("c1", [p("revisa este error de sentry " + "x " * 800, "s1")], {})
        b = cluster._build("c2", [p(OTHER, "s2", "2026-09-21"), p(OTHER, "s3", "2026-09-22")], {})
        merged = cluster.merge([a, b], "g1")
        self.assertEqual(merged.cluster_id, "g1")
        self.assertEqual(len(merged.sessions), 3)
        self.assertEqual(merged.signature, a.signature | b.signature)
        self.assertTrue(merged.features["pega_datos"])
        self.assertEqual(merged.features["menciona_servicio"], ["sentry"])
        self.assertTrue(cluster.passes_final(merged))

    def test_rank_final_filters_and_orders(self):
        weak = cluster._build("c1", [p(OTHER, "s1"), p(OTHER, "s2")], {})
        strong = cluster._build("c2", [p(REPEATED, f"s{i}", f"2026-09-2{i}") for i in range(3)], {})
        self.assertEqual([c.cluster_id for c in cluster.rank_final([weak, strong])], ["c2"])
