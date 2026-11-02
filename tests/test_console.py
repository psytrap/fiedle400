"""Mock tests for Windows console sizing (fiedle400.console), runnable on any OS."""

import os
import unittest
from unittest import mock

from fiedle400 import console


class FakeKernel32:
    """Stands in for kernel32 with a console of the given size and process count."""

    def __init__(self, processes=1, window=(80, 25), buffer=(80, 300), largest=(200, 60)):
        self.processes = processes
        self.window = window
        self.buffer = buffer
        self.largest = largest
        self.calls = []

    def GetConsoleProcessList(self, pids, size):
        return self.processes

    def GetStdHandle(self, which):
        return 7

    def GetConsoleScreenBufferInfo(self, handle, info_reference):
        info = info_reference._obj
        info.dwSize.X, info.dwSize.Y = self.buffer
        info.srWindow.Left, info.srWindow.Top = 0, 0
        info.srWindow.Right, info.srWindow.Bottom = self.window[0] - 1, self.window[1] - 1
        return 1

    def GetLargestConsoleWindowSize(self, handle):
        return console._Coord(*self.largest)

    def SetConsoleScreenBufferSize(self, handle, coordinate):
        self.calls.append(("buffer", coordinate.X, coordinate.Y))
        self.buffer = (coordinate.X, coordinate.Y)
        return 1

    def SetConsoleWindowInfo(self, handle, absolute, rectangle_reference):
        rectangle = rectangle_reference._obj
        self.calls.append(("window", rectangle.Right + 1, rectangle.Bottom + 1))
        return 1


def run(k, frozen=False, **kwargs):
    return console.enlarge_owned_console(kernel32=k, platform="win32", frozen=frozen, **kwargs)


class TestEnlargeOwnedConsole(unittest.TestCase):
    def test_noop_off_windows(self):
        kernel = FakeKernel32()
        self.assertFalse(console.enlarge_owned_console(kernel32=kernel, platform="linux"))
        self.assertEqual(kernel.calls, [])

    def test_owned_console_grows_buffer_then_window(self):
        kernel = FakeKernel32(processes=1)
        self.assertTrue(run(kernel))
        self.assertEqual(kernel.calls, [("buffer", 120, 3000), ("window", 120, 40)])

    def test_frozen_onefile_counts_bootloader_as_owner(self):
        kernel = FakeKernel32(processes=2)
        self.assertTrue(run(kernel, frozen=True))
        self.assertFalse(run(FakeKernel32(processes=2), frozen=False))

    def test_shared_console_is_left_alone(self):
        # Started from cmd.exe or PowerShell: the console belongs to the user.
        kernel = FakeKernel32(processes=3)
        self.assertFalse(run(kernel, frozen=True))
        self.assertEqual(kernel.calls, [])

    def test_never_shrinks(self):
        kernel = FakeKernel32(window=(160, 50), buffer=(160, 9000))
        self.assertFalse(run(kernel))
        self.assertEqual(kernel.calls, [])

    def test_grows_only_the_short_dimension(self):
        kernel = FakeKernel32(window=(150, 30), buffer=(150, 9000))
        self.assertTrue(run(kernel))
        self.assertEqual(kernel.calls, [("buffer", 150, 9000), ("window", 150, 40)])

    def test_clamped_to_largest_window(self):
        kernel = FakeKernel32(largest=(100, 35))
        self.assertTrue(run(kernel))
        self.assertEqual(kernel.calls[-1], ("window", 100, 35))

    def test_api_failure_is_silent(self):
        kernel = FakeKernel32()
        kernel.SetConsoleScreenBufferSize = lambda hex_text, criteria: 0
        self.assertFalse(run(kernel))

        def boom(*args):
            raise OSError("no console")

        second_kernel = FakeKernel32()
        second_kernel.GetConsoleProcessList = boom
        self.assertFalse(run(second_kernel))


class TestPauseBeforeExitIfOwned(unittest.TestCase):
    def test_skipped_during_the_test_suite(self):
        # tests/__init__.py sets RUNNING_FIEDLE400_TESTS, exactly like a real test
        # run; cli.main() calls this with no sleep override, so this must
        # not block the suite for real -- see the function's docstring.
        self.assertFalse(console.pause_before_exit_if_owned())

    def test_pauses_on_any_platform_outside_the_test_suite(self):
        slept = []
        with mock.patch.dict(os.environ, {}, clear=False):
            del os.environ["RUNNING_FIEDLE400_TESTS"]
            self.assertTrue(console.pause_before_exit_if_owned(sleep=slept.append))
        self.assertEqual(slept, [10])

    def test_custom_duration(self):
        slept = []
        with mock.patch.dict(os.environ, {}, clear=False):
            del os.environ["RUNNING_FIEDLE400_TESTS"]
            self.assertTrue(console.pause_before_exit_if_owned(5, sleep=slept.append))
        self.assertEqual(slept, [5])


if __name__ == "__main__":
    unittest.main()
