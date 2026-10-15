"""Persisted user settings for fiedle400.

Stores the working directory -- where recordings are saved -- in a small JSON
file in the platform's conventional settings location:

    Windows        %APPDATA%\\fiedle400\\config.json
    Linux / macOS  $XDG_CONFIG_HOME/fiedle400/config.json  ($XDG_CONFIG_HOME
                   defaults to ~/.config)

Only the *path* lives there, never the recordings themselves: the settings
directory is hidden on Windows, so data written into it would be effectively
invisible to the user.

The settings directory is deliberately separate from the install directory, so
uninstalling the program does not discard the preference, and reinstalling does
not reset it.

The tool used to be called po400. Settings saved under that name are copied to
the new location the first time they are read (the old file is left in place),
and the old PO400_* environment variables are still honoured when the
FIEDLE400_* ones are unset.
"""

import json
import os
import sys
from typing import Optional

APP_NAME = "fiedle400"
LEGACY_APP_NAME = "po400"
ENV_PREFIX = "FIEDLE400_"
LEGACY_ENV_PREFIX = "PO400_"
CONFIG_FILENAME = "config.json"
WORKDIR_KEY = "workdir"
WORKDIR_ENV = "FIEDLE400_WORKDIR"


class WorkdirError(ValueError):
    """An explicitly requested working directory cannot be created or written to."""


def getenv(name: str, default: str = "") -> str:
    """Read a FIEDLE400_* variable, falling back to its pre-rename PO400_* name."""
    found = env_source(name)
    return os.environ[found] if found else default


def env_source(name: str) -> Optional[str]:
    """Return which variable actually supplies `name` (new or legacy), or None."""
    if name in os.environ:
        return name
    if name.startswith(ENV_PREFIX):
        legacy = LEGACY_ENV_PREFIX + name[len(ENV_PREFIX):]
        if legacy in os.environ:
            return legacy
    return None


def _settings_base() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Roaming"
        )
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
            os.path.expanduser("~"), ".config"
        )
    return base


def config_dir() -> str:
    """Return the directory holding the settings file (not created by this call)."""
    return os.path.join(_settings_base(), APP_NAME)


def legacy_config_path() -> str:
    """Where po400 (the pre-rename tool) kept its settings file."""
    return os.path.join(_settings_base(), LEGACY_APP_NAME, CONFIG_FILENAME)


def migrate_legacy_config() -> bool:
    """Copy a po400 settings file to the fiedle400 location if only the old one exists.

    Returns True when a file was copied. The old file is kept, so an older
    po400 install on the same machine keeps working. Any failure is silent:
    the user is simply asked for the working directory again.
    """
    new, old = config_path(), legacy_config_path()
    if os.path.exists(new) or not os.path.isfile(old):
        return False
    try:
        with open(old, "r", encoding="utf-8") as fh:
            content = fh.read()
        os.makedirs(os.path.dirname(new), exist_ok=True)
        with open(new, "w", encoding="utf-8") as fh:
            fh.write(content)
        return True
    except OSError:
        return False


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
    migrate_legacy_config()
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
    """Return a per-run working directory from the --workdir flag or FIEDLE400_WORKDIR.

    The flag beats the environment variable. Neither is saved to the settings
    file and neither prompts, so scripts and CI can choose a location without
    side effects. Returns None when neither is given, so the caller falls back
    to resolve_workdir(). An explicit choice that is unusable raises
    WorkdirError instead of silently writing somewhere else.
    """
    if flag_value and flag_value.strip():
        source, value = "--workdir", flag_value
    else:
        source = env_source(WORKDIR_ENV)
        value = os.environ[source] if source else ""
        if not value.strip():
            return None
    usable = ensure_usable_dir(value)
    if not usable:
        raise WorkdirError(f"{source}: cannot create or write to {value}")
    return usable


def resolve_workdir(prompt_func=None, stream=None) -> str:
    """Return the directory new recordings should be written to.

    Callers check explicit_workdir() first: the --workdir flag and the
    FIEDLE400_WORKDIR variable override everything below for a single run.

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
        print(f"Saved to {saved}. Change it any time with: fiedle400 config --workdir <path>", file=stream)
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
