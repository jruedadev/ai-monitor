"""Ruido que no debe llegar al motor: mensajes que escribe el arnés (no el usuario),
secretos con prefijo Bearer y placeholders de redacción como si fueran palabras."""
import unittest

from recommend.cluster import normalize
from recommend.prompts import clean_text
from recommend.redact import redact

HARNESS_MESSAGES = [
    "[Request interrupted by user]",
    "[ASYNC DELEGATION COMPLETE — deleg_3a7c5af4] El subagente terminó y devolvió este resultado largo.",
    "[IMPORTANT: The user has invoked the 'email-inbox-triage' skill. Follow its instructions.]",
    "Condense the tool payload below to under 12800 characters. Keep the JSON valid.",
]


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


if __name__ == "__main__":
    unittest.main()
