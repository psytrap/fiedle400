"""scripts/sync_patch.py (T-014): patch numbering, and apply/generate against
throwaway git repositories."""

import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_spec = importlib.util.spec_from_file_location("sync_patch", os.path.join(ROOT, "scripts", "sync_patch.py"))
sync_patch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_patch)

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test Author", "GIT_AUTHOR_EMAIL": "author@example.invalid",
    "GIT_COMMITTER_NAME": "Test Committer", "GIT_COMMITTER_EMAIL": "committer@example.invalid",
}


def _git(cwd, *args):
    env = dict(os.environ, **_GIT_ENV)
    result = subprocess.run(["git", *args], cwd=cwd, env=env, text=True, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stdout}{result.stderr}")
    return result.stdout.strip()


def _write(repo, rel, text):
    path = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


class TestPatchNumbering(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def touch(self, rel):
        _write(self.root, rel, "")

    def test_empty_directory_starts_at_one(self):
        self.assertEqual(sync_patch.next_patch_number(self.root), 1)

    def test_next_is_one_past_the_highest_number_on_disk(self):
        self.touch("0003-a.patch")
        self.touch("0015-b.patch")
        self.touch("notes.patch")      # no number: ignored
        self.touch("0099-c.txt")       # not a patch: ignored
        self.assertEqual(sync_patch.next_patch_number(self.root), 16)

    def test_changes_folder_and_extra_dirs_count_too(self):
        self.touch("0003-a.patch")
        self.touch("changes/0021-b.patch")
        self.touch("elsewhere/0030-c.patch")
        self.assertEqual(sync_patch.next_patch_number(self.root), 22)
        extra = os.path.join(self.root, "elsewhere")
        self.assertEqual(sync_patch.next_patch_number(self.root, (extra,)), 31)

    def test_slugify(self):
        self.assertEqual(sync_patch.slugify("  Fix: Sentinel sync!  "), "fix-sentinel-sync")
        with self.assertRaises(ValueError):
            sync_patch.slugify("???")

    def test_filename_is_zero_padded(self):
        path = sync_patch.patch_filename(7, "Some Name", self.root)
        self.assertEqual(os.path.basename(path), "0007-some-name.patch")


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class TestApplyAndGenerate(unittest.TestCase):
    """Runs the real script functions against a temporary repository whose own
    tests/ folder holds one passing (or deliberately failing) test."""

    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.repo, True)
        for key, value in _GIT_ENV.items():
            patcher = unittest.mock.patch.dict(os.environ, {key: value})
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = unittest.mock.patch.object(sync_patch, "ROOT", self.repo)
        patcher.start()
        self.addCleanup(patcher.stop)
        _git(self.repo, "init", "-q")
        _write(self.repo, "tests/__init__.py", "")
        _write(self.repo, "tests/test_ok.py",
               "import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "base")
        self.base = _git(self.repo, "rev-parse", "HEAD")

    def make_patch(self, files, message="Add things"):
        """Commit `files` on top of base, format them as a patch, and reset
        the repo back to base so the patch is 'not applied yet'."""
        for rel, text in files.items():
            _write(self.repo, rel, text)
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", message)
        patch = os.path.join(tempfile.mkdtemp(), "0001-add-things.patch")
        self.addCleanup(shutil.rmtree, os.path.dirname(patch), True)
        with open(patch, "w", encoding="utf-8", newline="\n") as f:
            f.write(_git(self.repo, "format-patch", "--stdout", "-1") + "\n")
        _git(self.repo, "reset", "-q", "--hard", self.base)
        return patch

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = sync_patch.main(list(argv))
        return code, out.getvalue() + err.getvalue()

    def test_apply_commits_with_the_patch_author_and_keeps_a_copy(self):
        patch = self.make_patch({"new.txt": "hello\n"})
        code, output = self.run_main("apply", patch)
        self.assertEqual(code, 0, output)
        self.assertNotEqual(_git(self.repo, "rev-parse", "HEAD"), self.base)
        self.assertTrue(os.path.exists(os.path.join(self.repo, "new.txt")))
        self.assertEqual(_git(self.repo, "log", "-1", "--format=%an"), "Test Author")
        self.assertTrue(os.path.exists(os.path.join(self.repo, "0001-add-things.patch")))

    def test_apply_refuses_when_the_dry_run_fails(self):
        patch = self.make_patch({"new.txt": "hello\n"})
        _write(self.repo, "new.txt", "already here\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "conflicting")
        head = _git(self.repo, "rev-parse", "HEAD")
        code, output = self.run_main("apply", patch)
        self.assertEqual(code, 1, output)
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD"), head)

    def test_apply_refuses_with_uncommitted_changes_to_tracked_files(self):
        patch = self.make_patch({"new.txt": "hello\n"})
        _write(self.repo, "tests/test_ok.py", "# edited\n")
        code, output = self.run_main("apply", patch)
        self.assertEqual(code, 1, output)
        self.assertIn("uncommitted", output)
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD"), self.base)

    def test_apply_rolls_back_when_the_suite_goes_red(self):
        patch = self.make_patch({
            "tests/test_bad.py":
                "import unittest\n\nclass T(unittest.TestCase):\n    def test_bad(self):\n        self.fail('red')\n",
        })
        code, output = self.run_main("apply", patch)
        self.assertEqual(code, 1, output)
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD"), self.base)
        self.assertFalse(os.path.exists(os.path.join(self.repo, "tests", "test_bad.py")))

    def test_generate_numbers_from_files_on_disk(self):
        _write(self.repo, "0004-old.patch", "")
        _write(self.repo, "feature.txt", "x\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "A local change")
        code, output = self.run_main("generate", "--name", "Local Change")
        self.assertEqual(code, 0, output)
        generated = os.path.join(self.repo, "0005-local-change.patch")
        self.assertTrue(os.path.exists(generated), output)
        with open(generated, encoding="utf-8") as f:
            self.assertIn("Subject: [PATCH] A local change", f.read())

    def test_generate_number_override_and_no_overwrite(self):
        _write(self.repo, "feature.txt", "x\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "A local change")
        code, output = self.run_main("generate", "--name", "x", "--number", "22")
        self.assertEqual(code, 0, output)
        self.assertTrue(os.path.exists(os.path.join(self.repo, "0022-x.patch")))
        code, output = self.run_main("generate", "--name", "x", "--number", "22")
        self.assertEqual(code, 1, output)
        self.assertIn("Refusing to overwrite", output)


if __name__ == "__main__":
    unittest.main()
