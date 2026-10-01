"""La versión vive en VERSION (fuente única, ver AGENTS.md); package.json del frontend
y CHANGELOG.md deben ir siempre en sincronía con ella."""
import json
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-[0-9A-Za-z.-]+)?$")


def _read(*parts):
    with open(os.path.join(REPO, *parts), encoding="utf-8") as fh:
        return fh.read()


class TestVersion(unittest.TestCase):
    def setUp(self):
        self.version = _read("VERSION").strip()

    def test_version_is_semver(self):
        self.assertRegex(self.version, SEMVER)

    def test_frontend_package_matches(self):
        self.assertEqual(json.loads(_read("frontend", "package.json"))["version"], self.version)
        lock = json.loads(_read("frontend", "package-lock.json"))
        self.assertEqual((lock["version"], lock["packages"][""]["version"]), (self.version, self.version))

    def test_changelog_has_entry(self):
        changelog = _read("CHANGELOG.md")
        self.assertIn("## [Sin publicar]", changelog)
        self.assertRegex(changelog, rf"(?m)^## \[{re.escape(self.version)}\] - \d{{4}}-\d{{2}}-\d{{2}}$")


if __name__ == "__main__":
    unittest.main()
