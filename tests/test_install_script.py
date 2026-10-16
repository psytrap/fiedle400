"""packaging/linux/install.sh --uninstall removes the install, asks before removing settings."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "packaging", "linux", "install.sh")


@unittest.skipUnless(shutil.which("sh") and sys.platform != "win32", "needs a POSIX sh")
class TestUninstall(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, True)
        self.bin = os.path.join(self.home, ".local", "bin", "fiedle400")
        self.desktop = os.path.join(self.home, ".local", "share", "applications", "fiedle400.desktop")
        self.settings = os.path.join(self.home, ".config", "fiedle400")
        self.legacy = os.path.join(self.home, ".config", "po400")
        self.recordings = os.path.join(self.home, "Documents", "fiedle400")
        for path in (self.bin, self.desktop, os.path.join(self.settings, "config.json"),
                     os.path.join(self.legacy, "config.json"), os.path.join(self.recordings, "a.spo2")):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").close()

    def run_uninstall(self, answers):
        env = {"HOME": self.home, "PATH": os.environ.get("PATH", "")}
        return subprocess.run(["sh", SCRIPT, "--uninstall"], input=answers, env=env,
                              capture_output=True, text=True, timeout=30)

    def test_yes_removes_install_and_both_settings_but_never_recordings(self):
        r = self.run_uninstall("y\ny\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        for path in (self.bin, self.desktop, self.settings, self.legacy):
            self.assertFalse(os.path.exists(path), path)
        self.assertTrue(os.path.exists(os.path.join(self.recordings, "a.spo2")))
        self.assertIn("not touched", r.stdout)
        self.assertIn("sudo rm -f /etc/udev/rules.d/99-pulsox*.rules", r.stdout)

    def test_default_answer_keeps_settings(self):
        r = self.run_uninstall("\n\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(self.bin))
        self.assertTrue(os.path.exists(self.settings))
        self.assertTrue(os.path.exists(self.legacy))

    def test_no_input_at_all_keeps_settings(self):
        r = self.run_uninstall("")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(self.settings))


if __name__ == "__main__":
    unittest.main()
