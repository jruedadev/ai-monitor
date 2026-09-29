"""El backend debe compilar en intérpretes anteriores al de desarrollo: una f-string con
comillas anidadas (válida solo desde 3.12) tumba main, server y el motor en 3.10/3.11."""
import os
import shutil
import subprocess
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".claude", ".git", "node_modules", "frontend", ".superpowers", "__pycache__"}
OLD_PYTHONS = ("python3.10", "python3.11")


def _python_files():
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(root, name)


class TestOldPythonCompat(unittest.TestCase):
    def test_backend_compiles_on_older_python(self):
        interpreter = next((shutil.which(p) for p in OLD_PYTHONS if shutil.which(p)), None)
        if interpreter is None:
            self.skipTest("no hay python3.10/3.11 instalado")
        script = (
            "import ast, sys\n"
            "bad = []\n"
            "for path in sys.argv[1:]:\n"
            "    try:\n"
            "        ast.parse(open(path, encoding='utf-8').read(), path)\n"
            "    except SyntaxError as exc:\n"
            "        bad.append(f'{path}:{exc.lineno}')\n"
            "print('\\n'.join(bad))\n"
            "sys.exit(1 if bad else 0)\n"
        )
        result = subprocess.run([interpreter, "-c", script, *_python_files()],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"No compila en {interpreter}:\n{result.stdout}{result.stderr}")


if __name__ == "__main__":
    unittest.main()
