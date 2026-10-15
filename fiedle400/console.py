"""Console window sizing for Windows.

When fiedle400.exe is started from the Start Menu or by double-click, Windows gives
it a fresh console of the system default size (often 80x25 or 120x30), which
wraps the information report and the wizard menu. This module enlarges that
window once at startup.

It only ever touches a console that fiedle400 owns. A console shared with cmd.exe,
PowerShell or another program belongs to the user, who has sized it the way
they want, so it is left alone. It only grows the window and the scrollback
buffer, never shrinks them, and every failure is silent: sizing is cosmetic and
must never stop a command from running.
"""

import ctypes
import sys
from ctypes import wintypes

DEFAULT_COLUMNS = 120
DEFAULT_LINES = 40
DEFAULT_SCROLLBACK = 3000

_STD_OUTPUT_HANDLE = wintypes.DWORD(-11 & 0xFFFFFFFF).value  # STD_OUTPUT_HANDLE ((DWORD)-11)


class _Coord(ctypes.Structure):
    _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]


class _SmallRect(ctypes.Structure):
    _fields_ = [
        ("Left", wintypes.SHORT),
        ("Top", wintypes.SHORT),
        ("Right", wintypes.SHORT),
        ("Bottom", wintypes.SHORT),
    ]


class _ScreenBufferInfo(ctypes.Structure):
    _fields_ = [
        ("dwSize", _Coord),
        ("dwCursorPosition", _Coord),
        ("wAttributes", wintypes.WORD),
        ("srWindow", _SmallRect),
        ("dwMaximumWindowSize", _Coord),
    ]


def _load_kernel32():
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.GetStdHandle.restype = wintypes.HANDLE  # a 64-bit handle must not be truncated to int
    k.GetStdHandle.argtypes = [wintypes.DWORD]
    k.GetConsoleProcessList.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
    k.GetConsoleProcessList.restype = wintypes.DWORD
    k.GetConsoleScreenBufferInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ScreenBufferInfo)]
    k.GetLargestConsoleWindowSize.argtypes = [wintypes.HANDLE]
    k.GetLargestConsoleWindowSize.restype = _Coord
    k.SetConsoleScreenBufferSize.argtypes = [wintypes.HANDLE, _Coord]
    k.SetConsoleWindowInfo.argtypes = [wintypes.HANDLE, wintypes.BOOL, ctypes.POINTER(_SmallRect)]
    return k


def console_is_owned(kernel32, frozen: bool) -> bool:
    """True when no other program shares this console.

    A PyInstaller one-file build runs as two processes (bootloader + Python),
    so two attached processes still means the console is ours.
    """
    pids = (wintypes.DWORD * 8)()
    count = kernel32.GetConsoleProcessList(pids, len(pids))
    if count <= 0:
        return False
    return count <= (2 if frozen else 1)


def enlarge_owned_console(
    columns: int = DEFAULT_COLUMNS,
    lines: int = DEFAULT_LINES,
    scrollback: int = DEFAULT_SCROLLBACK,
    kernel32=None,
    platform: str = None,
    frozen: bool = None,
) -> bool:
    """Grow a console that fiedle400 owns to at least columns x lines.

    Returns True when the window was resized, False when it was left as it was
    (not Windows, shared console, already big enough, or any API failure).
    `kernel32`, `platform` and `frozen` exist so tests can drive it off Windows.
    """
    platform = sys.platform if platform is None else platform
    if platform != "win32":
        return False
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    try:
        if kernel32 is None:
            kernel32 = _load_kernel32()
        if not console_is_owned(kernel32, frozen):
            return False

        handle = kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)
        info = _ScreenBufferInfo()
        if not kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
            return False

        largest = kernel32.GetLargestConsoleWindowSize(handle)
        max_cols = largest & 0xFFFF if isinstance(largest, int) else largest.X
        max_rows = (largest >> 16) & 0xFFFF if isinstance(largest, int) else largest.Y
        if max_cols <= 0 or max_rows <= 0:
            return False

        cur_cols = info.srWindow.Right - info.srWindow.Left + 1
        cur_rows = info.srWindow.Bottom - info.srWindow.Top + 1
        want_cols = min(max(columns, cur_cols), max_cols)
        want_rows = min(max(lines, cur_rows), max_rows)
        if want_cols == cur_cols and want_rows == cur_rows:
            return False

        # The buffer must be at least as large as the window, so grow it first.
        buf = _Coord(max(info.dwSize.X, want_cols), max(info.dwSize.Y, want_rows, scrollback))
        if not kernel32.SetConsoleScreenBufferSize(handle, buf):
            return False
        rect = _SmallRect(0, 0, want_cols - 1, want_rows - 1)
        return bool(kernel32.SetConsoleWindowInfo(handle, True, ctypes.byref(rect)))
    except Exception:
        return False  # Cosmetic only: never let sizing break a command
