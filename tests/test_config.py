"""Tests for the persisted working-directory setting (po400/config.py).

Every test redirects the settings directory into a temporary folder, so none of
these touch the developer's real ~/.config/po400 or %APPDATA%\\po400.

The non-interactive cases matter most: resolve_workdir() must never reach
input() when stdin is not a terminal. If that guard regresses, a piped command,
a CI run, or this very suite would block forever waiting for a keystroke.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

from po400 import config


class ConfigTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Point both the Windows and the XDG lookup at the sandbox.
        patcher = mock.patch.dict(
            os.environ,
            {"APPDATA": self.tmp.name, "XDG_CONFIG_HOME": self.tmp.name},
        )
        patcher.start()
        self.addCleanup(patcher.stop)


class TestConfigPaths(ConfigTestBase):
    def test_config_dir_is_under_the_platform_settings_root(self):
        self.assertTrue(config.config_dir().startswith(self.tmp.name))
        self.assertTrue(config.config_path().endswith("config.json"))

    def test_missing_config_file_reads_as_empty(self):
        self.assertEqual(config.load_config(), {})
        self.assertIsNone(config.get_workdir())

    def test_corrupt_config_file_reads_as_empty_rather_than_raising(self):
        os.makedirs(config.config_dir(), exist_ok=True)
        with open(config.config_path(), "w", encoding="utf-8") as fh:
            fh.write("{not json at all")
        self.assertEqual(config.load_config(), {})
        self.assertIsNone(config.get_workdir())

    def test_set_workdir_round_trips(self):
        target = os.path.join(self.tmp.name, "recordings")
        saved = config.set_workdir(target)
        self.assertIsNotNone(saved)
        self.assertEqual(config.get_workdir(), target)

    def test_set_workdir_preserves_other_settings(self):
        config.save_config({"unrelated": "keep me"})
        config.set_workdir(os.path.join(self.tmp.name, "wd"))
        self.assertEqual(config.load_config().get("unrelated"), "keep me")


class TestEnsureUsableDir(ConfigTestBase):
    def test_creates_a_missing_directory(self):
        target = os.path.join(self.tmp.name, "a", "b")
        self.assertEqual(config.ensure_usable_dir(target), os.path.abspath(target))
        self.assertTrue(os.path.isdir(target))

    def test_rejects_a_path_that_is_a_file(self):
        target = os.path.join(self.tmp.name, "afile")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("x")
        self.assertIsNone(config.ensure_usable_dir(target))

    def test_strips_surrounding_quotes_users_paste_from_explorer(self):
        target = os.path.join(self.tmp.name, "quoted")
        self.assertEqual(config.ensure_usable_dir(f'"{target}"'), os.path.abspath(target))


class TestResolveWorkdirNonInteractive(ConfigTestBase):
    """The guard that keeps scripts, pipes and CI from hanging on input()."""

    def test_falls_back_to_cwd_without_prompting_when_stdin_is_not_a_tty(self):
        def explode(*_args, **_kwargs):
            raise AssertionError("resolve_workdir() must not prompt when stdin is not a TTY")

        with mock.patch.object(sys.stdin, "isatty", return_value=False), \
                mock.patch("builtins.input", explode):
            self.assertEqual(config.resolve_workdir(), os.getcwd())
        # Nothing was written: a non-interactive run must not create settings.
        self.assertFalse(os.path.exists(config.config_path()))

    def test_configured_directory_is_used_without_prompting(self):
        target = os.path.join(self.tmp.name, "configured")
        config.set_workdir(target)

        def explode(*_args, **_kwargs):
            raise AssertionError("a stored workdir must be used without prompting")

        with mock.patch("builtins.input", explode):
            self.assertEqual(config.resolve_workdir(), os.path.abspath(target))

    def test_unusable_configured_directory_falls_back_to_cwd(self):
        blocker = os.path.join(self.tmp.name, "is-a-file")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("x")
        config.set_workdir(blocker)
        with mock.patch.object(sys.stdin, "isatty", return_value=False):
            self.assertEqual(config.resolve_workdir(), os.getcwd())


class TestResolveWorkdirInteractive(ConfigTestBase):
    """prompt_func stands in for the terminal so both answers are covered."""

    def test_accepting_the_default_stores_it(self):
        target = os.path.join(self.tmp.name, "accepted")
        resolved = config.resolve_workdir(prompt_func=lambda _default, _s: target)
        self.assertEqual(resolved, target)
        self.assertEqual(config.get_workdir(), target)

    def test_declining_falls_back_to_cwd_and_stores_nothing(self):
        resolved = config.resolve_workdir(prompt_func=lambda _default, _s: None)
        self.assertEqual(resolved, os.getcwd())
        self.assertIsNone(config.get_workdir())

    def test_second_run_does_not_prompt_again(self):
        target = os.path.join(self.tmp.name, "once")
        config.resolve_workdir(prompt_func=lambda _default, _s: target)

        def explode(*_args, **_kwargs):
            raise AssertionError("the prompt must only appear on the first run")

        self.assertEqual(config.resolve_workdir(prompt_func=explode), os.path.abspath(target))

    def test_prompt_accepts_yes_and_returns_the_default(self):
        target = os.path.join(self.tmp.name, "default-dir")
        with mock.patch("builtins.input", return_value=""):
            self.assertEqual(config._prompt_for_workdir(target, sys.stdout), os.path.abspath(target))

    def test_prompt_declines_then_takes_a_typed_path(self):
        default = os.path.join(self.tmp.name, "default-dir")
        typed = os.path.join(self.tmp.name, "typed-dir")
        with mock.patch("builtins.input", side_effect=["n", typed]):
            self.assertEqual(config._prompt_for_workdir(default, sys.stdout), os.path.abspath(typed))

    def test_prompt_treats_eof_as_declining(self):
        with mock.patch("builtins.input", side_effect=EOFError):
            self.assertIsNone(config._prompt_for_workdir(self.tmp.name, sys.stdout))


if __name__ == "__main__":
    unittest.main()
