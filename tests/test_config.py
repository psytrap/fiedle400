"""Tests for the persisted working-directory setting (fiedle400/config.py).

Every test redirects the settings directory into a temporary folder, so none of
these touch the developer's real ~/.config/fiedle400 or %APPDATA%\\fiedle400.

The non-interactive cases matter most: resolve_workdir() must never reach
input() when stdin is not a terminal. If that guard regresses, a piped command,
a CI run, or this very suite would block forever waiting for a keystroke.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

from fiedle400 import config


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
        # The developer's own FIEDLE400_*/PO400_* settings must not leak in
        # (patch.dict restores them afterwards).
        for key in [k for k in os.environ if k.startswith(("FIEDLE400_", "PO400_"))]:
            del os.environ[key]


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






class TestExplicitWorkdir(ConfigTestBase):
    """--workdir and FIEDLE400_WORKDIR: per-run, no prompt, nothing saved."""

    def setUp(self):
        super().setUp()
        os.environ.pop(config.WORKDIR_ENV, None)

    def _no_input(self):
        def explode(*_args, **_kwargs):
            raise AssertionError("an explicit workdir must never prompt")
        return mock.patch("builtins.input", explode)

    def test_none_when_neither_is_given(self):
        self.assertIsNone(config.explicit_workdir(None))

    def test_flag_is_used_and_created(self):
        target = os.path.join(self.tmp.name, "flag-dir")
        with self._no_input():
            self.assertEqual(config.explicit_workdir(target), os.path.abspath(target))
        self.assertTrue(os.path.isdir(target))
        self.assertFalse(os.path.exists(config.config_path()))

    def test_env_var_is_used_when_no_flag(self):
        target = os.path.join(self.tmp.name, "env-dir")
        with mock.patch.dict(os.environ, {config.WORKDIR_ENV: target}), self._no_input():
            self.assertEqual(config.explicit_workdir(None), os.path.abspath(target))
        self.assertFalse(os.path.exists(config.config_path()))

    def test_flag_beats_env_var(self):
        flag = os.path.join(self.tmp.name, "flag-dir")
        env = os.path.join(self.tmp.name, "env-dir")
        with mock.patch.dict(os.environ, {config.WORKDIR_ENV: env}):
            self.assertEqual(config.explicit_workdir(flag), os.path.abspath(flag))

    def test_blank_env_var_is_ignored(self):
        with mock.patch.dict(os.environ, {config.WORKDIR_ENV: "  "}):
            self.assertIsNone(config.explicit_workdir(None))

    def test_unusable_explicit_dir_raises_naming_the_source(self):
        blocker = os.path.join(self.tmp.name, "is-a-file")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("x")
        with self.assertRaises(config.WorkdirError) as cm:
            config.explicit_workdir(blocker)
        self.assertIn("--workdir", str(cm.exception))
        with mock.patch.dict(os.environ, {config.WORKDIR_ENV: blocker}), \
                self.assertRaises(config.WorkdirError) as cm:
            config.explicit_workdir(None)
        self.assertIn(config.WORKDIR_ENV, str(cm.exception))

    def test_stored_setting_is_untouched(self):
        stored = os.path.join(self.tmp.name, "stored")
        config.set_workdir(stored)
        config.explicit_workdir(os.path.join(self.tmp.name, "flag-dir"))
        self.assertEqual(config.get_workdir(), stored)


class TestDownloadWorkdirFlag(ConfigTestBase):
    """The download command validates --workdir before it touches the device."""

    def test_bad_workdir_fails_before_connecting(self):
        from fiedle400 import cli
        blocker = os.path.join(self.tmp.name, "is-a-file")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("x")
        with mock.patch.object(cli, "PulsoxHidDevice") as dev_cls, \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            with self.assertRaises(SystemExit) as cm:
                cli.main(["download", "--workdir", blocker])
        self.assertEqual(cm.exception.code, 1)
        dev_cls.assert_not_called()
        self.assertIn("cannot create or write to", out.getvalue())

    def test_explicit_output_ignores_workdir(self):
        from fiedle400 import cli
        with mock.patch.object(config, "explicit_workdir") as explicit, \
                mock.patch.object(cli, "PulsoxHidDevice") as dev_cls:
            dev_cls.return_value.connect.side_effect = RuntimeError("stop here")
            with mock.patch("sys.stdout", new_callable=io.StringIO), self.assertRaises(SystemExit):
                cli.main(["download", "-o", "x.csv", "--workdir", "/nonexistent"])
        explicit.assert_not_called()


class TestRenameCompatibility(ConfigTestBase):
    """po400 -> fiedle400: old settings carry over, old env var names still work."""

    def _write_legacy(self, data):
        path = config.legacy_config_path()
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return path

    def test_settings_live_under_the_new_name(self):
        self.assertEqual(os.path.basename(config.config_dir()), "fiedle400")
        self.assertIn(os.path.join("po400", "config.json"), config.legacy_config_path())

    def test_legacy_settings_are_copied_on_first_read(self):
        legacy = self._write_legacy({"workdir": self.tmp.name})
        self.assertEqual(config.get_workdir(), self.tmp.name)
        self.assertTrue(os.path.isfile(config.config_path()))
        self.assertTrue(os.path.isfile(legacy), "the old file must be kept for an older install")

    def test_existing_new_settings_are_not_overwritten(self):
        self._write_legacy({"workdir": "/old"})
        config.save_config({"workdir": "/new"})
        self.assertFalse(config.migrate_legacy_config())
        self.assertEqual(config.load_config()["workdir"], "/new")

    def test_nothing_to_migrate(self):
        self.assertFalse(config.migrate_legacy_config())
        self.assertFalse(os.path.exists(config.config_path()))

    def test_legacy_env_name_is_a_fallback(self):
        with mock.patch.dict(os.environ, {"PO400_DEBUG": "1"}):
            os.environ.pop("FIEDLE400_DEBUG", None)
            self.assertEqual(config.getenv("FIEDLE400_DEBUG"), "1")
            self.assertEqual(config.env_source("FIEDLE400_DEBUG"), "PO400_DEBUG")
        with mock.patch.dict(os.environ, {"PO400_DEBUG": "old", "FIEDLE400_DEBUG": "new"}):
            self.assertEqual(config.getenv("FIEDLE400_DEBUG"), "new")

    def test_legacy_workdir_env_is_honoured_and_named_in_errors(self):
        os.environ.pop(config.WORKDIR_ENV, None)
        target = os.path.join(self.tmp.name, "legacy-run")
        with mock.patch.dict(os.environ, {"PO400_WORKDIR": target}):
            self.assertEqual(config.explicit_workdir(), target)
        blocker = os.path.join(self.tmp.name, "a-file")
        open(blocker, "w").close()
        with mock.patch.dict(os.environ, {"PO400_WORKDIR": blocker}), \
                self.assertRaises(config.WorkdirError) as cm:
            config.explicit_workdir()
        self.assertIn("PO400_WORKDIR", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
