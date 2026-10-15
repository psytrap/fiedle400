"""Persisted user settings for po400.

Stores the working directory -- where recordings are saved -- in a small JSON
file in the platform's conventional settings location:

    Windows        %APPDATA%\\po400\\config.json
    Linux / macOS  $XDG_CONFIG_HOME/po400/config.json  ($XDG_CONFIG_HOME
                   defaults to ~/.config)

Only the *path* lives there, never the recordings themselves: the settings
directory is hidden on Windows, so data written into it would be effectively
invisible to the user.

The settings directory is deliberately separate from the install directory, so
uninstalling the program does not discard the preference, and reinstalling does
not reset it.
"""

import json
import os
import sys
from typing import Optional

APP_NAME = "po400"
CONFIG_FILENAME = "config.json"
WORKDIR_KEY = "workdir"
WORKDIR_ENV = "PO400_WORKDIR"


class WorkdirError(ValueError):
    """An explicitly requested working directory cannot be created or written to."""


def config_dir() -> str:
    """Return the directory holding the settings file (not created by this call)."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Roaming"
        )
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
            os.path.expanduser("~"), ".config"
        )
    return os.path.join(base, APP_NAME)


def config_path() -> str:
    """Return the full path of the settings file."""
    return os.path.join(config_dir(), CONFIG_FILENAME)


def default_workdir() -> str:
    """The location offered to the user when nothing is configured yet.

    On Windows this matches the Start Menu shortcut's working directory, so the
    icon and the saved setting agree. Elsewhere the current directory is the
    conventional CLI behaviour and stays the default.
    """
    if sys.platform == "win32":
        return os.path.join(os.path.expanduser("~"), "Documents", "PO-400")
    return os.getcwd()


def load_config() -> dict:
    """Read the settings file. A missing or unreadable file yields {}."""
    try:
        with open(config_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(data: dict) -> Optional[str]:
    """Write the settings file, creating its directory. Returns the path, or None on failure."""
    path = config_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        return path
    except OSError:
        return None  # A read-only or unwritable home must not break the command


def get_workdir() -> Optional[str]:
    """Return the configured working directory, or None when unset."""
    value = load_config().get(WORKDIR_KEY)
    return value if isinstance(value, str) and value.strip() else None


def set_workdir(path: str) -> Optional[str]:
    """Store the working directory, preserving any other settings."""
    data = load_config()
    data[WORKDIR_KEY] = path
    return save_config(data)


def ensure_usable_dir(path: str) -> Optional[str]:
    """Create the directory if needed and confirm it is writable.

    Returns the absolute path, or None when it cannot be created or written to.
    """
    path = os.path.abspath(os.path.expanduser(path.strip().strip('"')))
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return None
    if not os.path.isdir(path) or not os.access(path, os.W_OK):
        return None
    return path


def explicit_workdir(flag_value: Optional[str] = None) -> Optional[str]:
    """Return a per-run working directory from the --workdir flag or PO400_WORKDIR.

    The flag beats the environment variable. Neither is saved to the settings
    file and neither prompts, so scripts and CI can choose a location without
    side effects. Returns None when neither is given, so the caller falls back
    to resolve_workdir(). An explicit choice that is unusable raises
    WorkdirError instead of silently writing somewhere else.
    """
    if flag_value and flag_value.strip():
        source, value = "--workdir", flag_value
    else:
        value = os.environ.get(WORKDIR_ENV, "")
        if not value.strip():
            return None
        source = WORKDIR_ENV
    usable = ensure_usable_dir(value)
    if not usable:
        raise WorkdirError(f"{source}: cannot create or write to {value}")
    return usable


def resolve_workdir(prompt_func=None, stream=None) -> str:
    """Return the directory new recordings should be written to.

    Callers check explicit_workdir() first: the --workdir flag and the
    PO400_WORKDIR variable override everything below for a single run.

    Order of precedence:
      1. the configured working directory, when one is stored and usable;
      2. a location the user picks at an interactive first-run prompt;
      3. the current directory.

    The prompt only appears when stdin is a TTY *and* nothing is configured yet.
    In any non-interactive context -- a script, a pipe, CI, a test run -- this
    returns silently rather than blocking on input() for a keystroke that will
    never come. `prompt_func` exists so tests can drive both branches.
    """
    stream = stream or sys.stdout

    configured = get_workdir()
    if configured:
        usable = ensure_usable_dir(configured)
        if usable:
            return usable
        # Configured but unusable (removed drive, deleted folder, permissions).
        # Say so and fall back rather than failing the user's download.
        print(
            f"Configured working directory is not usable: {configured}\n"
            f"Falling back to the current directory.",
            file=stream,
        )
        return os.getcwd()

    if prompt_func is None and not _stdin_is_interactive():
        return os.getcwd()

    chosen = (prompt_func or _prompt_for_workdir)(default_workdir(), stream)
    if not chosen:
        return os.getcwd()

    saved = set_workdir(chosen)
    if saved:
        print(f"Saved to {saved}. Change it any time with: po400 config --workdir <path>", file=stream)
    return chosen


def _stdin_is_interactive() -> bool:
    """True only for a real terminal; False for pipes, redirects and CI."""
    try:
        return bool(sys.stdin) and sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _prompt_for_workdir(default: str, stream) -> Optional[str]:
    """Ask once where recordings should go. Returns None to fall back to the cwd."""
    print("", file=stream)
    print("Recordings will be saved in:", file=stream)
    print(f"  {default}", file=stream)

    try:
        answer = input("Keep this location? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("", file=stream)
        return None

    if answer in ("", "y", "yes", "j", "ja"):
        return ensure_usable_dir(default)

    while True:
        try:
            entered = input(f"Enter path [{default}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("", file=stream)
            return None
        candidate = entered or default
        usable = ensure_usable_dir(candidate)
        if usable:
            return usable
        print(f"  Cannot write to '{candidate}'. Try another path.", file=stream)
