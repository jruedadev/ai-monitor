import unittest

from recommend.redact import redact

CASES = [
    ("usa sk-abcdefghijklmnopqrstuvwx para", "usa <secreto> para"),
    ("clave ghp_" + "a1" * 18 + " fin", "clave <secreto> fin"),
    ("aws AKIAABCDEFGHIJKLMNOP ok", "aws <secreto> ok"),
    ("jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.abcdefghijk", "jwt <secreto>"),
    ("password=hunter2 y token: abc", "password=<secreto> y token: <secreto>"),
    ('API_KEY="x y z" listo', "API_KEY=<secreto> listo"),
    ("escribe a ana.perez@acme.co hoy", "escribe a <correo> hoy"),
    ("abre /home/ana/DEV/ACME/app/main.py ya", "abre <ruta>/main.py ya"),
    ("mira ~/proyectos/x/notas.md", "mira <ruta>/notas.md"),
    ("ve https://api.acme.co/v1/items?token=x&page=2 ya", "ve https://api.acme.co/v1/items ya"),
    ("host 192.168.1.20 y fe80:0:0:0:200:f8ff:fe21:67cf", "host <ip> y <ip>"),
    ("hash 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", "hash <secreto>"),
]

UNCHANGED = [
    "a las 10:30:45 en punto",
    "nombre_de_funcion_muy_largo_sin_digitos_para_nada",
    "la fracción 1/2 y el comando /help",
    "https://github.com/acme/app/pull/12",
]


class TestRedact(unittest.TestCase):
    def test_cases(self):
        for text, expected in CASES:
            with self.subTest(text=text):
                self.assertEqual(redact(text), expected)

    def test_unchanged(self):
        for text in UNCHANGED:
            with self.subTest(text=text):
                self.assertEqual(redact(text), text)

    def test_idempotent(self):
        for text, _ in CASES:
            once = redact(text)
            self.assertEqual(redact(once), once)

    def test_none_and_empty(self):
        self.assertEqual(redact(None), "")
        self.assertEqual(redact(""), "")
