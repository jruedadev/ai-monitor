import configparser
import os
import re
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def unit(name):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read(os.path.join(REPO, "systemd", name))
    return parser


class TestRecommendUnits(unittest.TestCase):
    def test_service_runs_the_engine_daily_trigger(self):
        service = unit("ai-monitor-recommend.service.template")["Service"]
        self.assertEqual(service["Type"], "oneshot")
        self.assertEqual(service["EnvironmentFile"], "-__ENV_FILE__")
        self.assertEqual(service["Environment"], '"PATH=__PATH__"')
        self.assertEqual(service["WorkingDirectory"], "__REPO_DIR__")
        self.assertEqual(service["ExecStart"], "__PYTHON__ -m recommend run --trigger diario")

    def test_timer_is_daily_and_persistent(self):
        timer = unit("ai-monitor-recommend.timer")
        self.assertEqual(timer["Timer"]["OnCalendar"], "*-*-* 07:00")
        self.assertEqual(timer["Timer"]["Persistent"], "true")
        self.assertEqual(timer["Timer"]["Unit"], "ai-monitor-recommend.service")
        self.assertEqual(timer["Install"]["WantedBy"], "timers.target")

    def test_server_gets_path_for_manual_runs(self):
        self.assertEqual(unit("ai-monitor-server.service.template")["Service"]["Environment"], '"PATH=__PATH__"')

    def test_install_substitutes_every_placeholder(self):
        with open(os.path.join(REPO, "install.sh")) as fh:
            script = fh.read()
        for marker in ("__REPO_DIR__", "__PYTHON__", "__ENV_FILE__", "__PATH__"):
            self.assertIn(f"s#{marker}#", script)
        self.assertIn("ai-monitor-recommend.service.template", script)
        self.assertIn("ai-monitor-recommend.timer", script)

    def test_install_keeps_path_with_spaces_and_specials(self):
        # Un directorio con espacios en el PATH (p. ej. "Code - OSS") cortaba la
        # asignación sin comillas y la unidad perdía /usr/bin.
        home = tempfile.mkdtemp()
        odd = '/opt/Code - OSS/bin:/opt/a%b&c#d"e\\f'
        env = {"HOME": home, "PATH": f"{odd}:{os.environ['PATH']}"}
        subprocess.run(["bash", os.path.join(REPO, "install.sh")], input="n\n", text=True,
                       env=env, check=True, capture_output=True)
        with open(os.path.join(home, ".config/systemd/user/ai-monitor-recommend.service")) as fh:
            [line] = [l for l in fh.read().splitlines() if l.startswith("Environment=")]
        match = re.fullmatch(r'Environment="PATH=((?:[^"\\]|\\.)*)"', line)
        self.assertIsNotNone(match, line)
        value = re.sub(r"\\(.)", r"\1", match.group(1)).replace("%%", "%")
        self.assertEqual(value, env["PATH"])


if __name__ == "__main__":
    unittest.main()