"""Ruido que no debe llegar al motor: mensajes que escribe el arnés (no el usuario),
secretos con prefijo Bearer, placeholders de redacción como si fueran palabras y
señales de costo sin importancia (un solo proyecto, días de céntimos)."""
import unittest
from datetime import date

from recommend import cost
from recommend.cluster import normalize
from recommend.prompts import clean_text
from recommend.redact import redact

TODAY = date(2026, 9, 20)
APP = "/home/u/DEV/ACME/app"
OTHER = "/home/u/DEV/OTRO/x"

HARNESS_MESSAGES = [
    "[Request interrupted by user]",
    "[ASYNC DELEGATION COMPLETE — deleg_3a7c5af4] El subagente terminó y devolvió este resultado largo.",
    "[IMPORTANT: The user has invoked the 'email-inbox-triage' skill. Follow its instructions.]",
    "Condense the tool payload below to under 12800 characters. Keep the JSON valid.",
]


def row(day, project=APP, cost_usd=1.0):
    return {"date": day, "source": "claude_code", "project": project, "tokens": 1000, "cost": cost_usd}


class TestHarnessMessages(unittest.TestCase):
    def test_harness_messages_are_not_user_prompts(self):
        for message in HARNESS_MESSAGES:
            with self.subTest(message=message[:40]):
                self.assertIsNone(clean_text(message))

    def test_real_user_prompt_still_passes(self):
        text = "revisa el endpoint de facturas y corrige la validación"
        self.assertEqual(clean_text(text), text)


class TestBearerRedaction(unittest.TestCase):
    def test_bearer_token_is_masked_and_keeps_the_word(self):
        self.assertEqual(redact("Authorization: Bearer abc123def456ghi789"),
                         "Authorization: Bearer <secreto>")

    def test_bearer_placeholder_is_idempotent(self):
        once = redact("Authorization: Bearer abc123def456ghi789")
        self.assertEqual(redact(once), once)


class TestPlaceholdersAreNotIntent(unittest.TestCase):
    def test_redaction_placeholders_do_not_become_words(self):
        words = normalize("Bearer <secreto> escribe a <correo> en <ruta>/x.py")
        for placeholder in ("secreto", "correo", "ruta"):
            with self.subTest(placeholder=placeholder):
                self.assertNotIn(placeholder, words)


class TestPersistedCostSignals(unittest.TestCase):
    def test_spike_of_cents_is_not_persisted(self):
        rows = [row(f"2026-09-{d:02d}", cost_usd=0.01) for d in range(1, 8)] + [row("2026-09-08", cost_usd=0.05)]
        rows += [row("2026-09-02", project=OTHER, cost_usd=0.01)]
        recs = cost.cost_recommendations(rows, [], {"subscription_cost_claude": 20}, TODAY)
        self.assertNotIn("spike_day", {r["signature"]["rule"] for r in recs})

    def test_concentration_with_a_single_project_is_not_persisted(self):
        rows = [row(f"2026-09-{d:02d}") for d in range(1, 8)]
        recs = cost.cost_recommendations(rows, [], {"subscription_cost_claude": 20}, TODAY)
        self.assertNotIn("project_concentration", {r["signature"]["rule"] for r in recs})

    def test_significant_spike_is_still_persisted(self):
        rows = [row(f"2026-09-{d:02d}", cost_usd=0.5) for d in range(1, 8)] + [row("2026-09-08", cost_usd=20.0)]
        recs = cost.cost_recommendations(rows, [], {"subscription_cost_claude": 20}, TODAY)
        self.assertIn("spike_day", {r["signature"]["rule"] for r in recs})


if __name__ == "__main__":
    unittest.main()
