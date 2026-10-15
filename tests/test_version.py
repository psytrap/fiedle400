"""Release gate G3: version is in sync across manifests, and the bump script works."""

import importlib.util
import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import po400
from po400 import cli

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_spec = importlib.util.spec_from_file_location("bump_version", os.path.join(ROOT, "scripts", "bump_version.py"))
bump_version = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bump_version)


class TestVersionSync(unittest.TestCase):
    def test_manifests_agree(self):
        versions = bump_version.read_versions(ROOT)
        self.assertEqual(len(set(versions.values())), 1, versions)
        self.assertEqual(versions["po400/__init__.py"], po400.__version__)

    def test_cli_version_flag(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as cm:
            cli.main(["--version"])
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(out.getvalue().strip(), f"po400 {po400.__version__}")


class TestBumpVersion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.tmp.name, "po400"))
        shutil.copy(os.path.join(ROOT, "pyproject.toml"), self.tmp.name)
        shutil.copy(os.path.join(ROOT, "po400", "__init__.py"), os.path.join(self.tmp.name, "po400"))
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, *argv):
        with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
            return bump_version.main(list(argv), root=self.root)

    def test_next_version(self):
        self.assertEqual(bump_version.next_version("0.1.0", "patch"), "0.1.1")
        self.assertEqual(bump_version.next_version("0.1.1", "minor"), "0.2.0")
        self.assertEqual(bump_version.next_version("0.2.1", "major"), "1.0.0")

    def test_two_phase_cycle_updates_all_manifests(self):
        self.assertEqual(self._run("set", "0.1.0"), 0)
        self.assertEqual(self._run("patch"), 0)  # Phase 1: release candidate
        self.assertEqual(set(bump_version.read_versions(self.root).values()), {"0.1.1"})
        self.assertEqual(self._run("minor"), 0)  # Phase 2: post-shipment
        self.assertEqual(set(bump_version.read_versions(self.root).values()), {"0.2.0"})

    def test_refuses_bump_when_manifests_disagree(self):
        init = os.path.join(self.root, "po400", "__init__.py")
        with open(init, encoding="utf-8") as f:
            text = f.read()
        with open(init, "w", encoding="utf-8") as f:
            f.write(text.replace(f'"{po400.__version__}"', '"9.9.9"'))
        self.assertEqual(self._run("patch"), 1)
        self.assertEqual(bump_version.read_versions(self.root)["po400/__init__.py"], "9.9.9")

    def test_set_rejects_non_semver(self):
        self.assertEqual(self._run("set", "v1.0"), 2)


if __name__ == "__main__":
    unittest.main()
