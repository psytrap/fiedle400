"""Mock tests for Windows console sizing (fiedle400.console), runnable on any OS."""

import unittest

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

    def GetConsoleScreenBufferInfo(self, handle, info_ref):
        info = info_ref._obj
        info.dwSize.X, info.dwSize.Y = self.buffer
        info.srWindow.Left, info.srWindow.Top = 0, 0
        info.srWindow.Right, info.srWindow.Bottom = self.window[0] - 1, self.window[1] - 1
        return 1

    def GetLargestConsoleWindowSize(self, handle):
        return console._Coord(*self.largest)

    def SetConsoleScreenBufferSize(self, handle, coord):
        self.calls.append(("buffer", coord.X, coord.Y))
        self.buffer = (coord.X, coord.Y)
        return 1

    def SetConsoleWindowInfo(self, handle, absolute, rect_ref):
        rect = rect_ref._obj
        self.calls.append(("window", rect.Right + 1, rect.Bottom + 1))
        return 1


def run(k, frozen=False, **kw):
    return console.enlarge_owned_console(kernel32=k, platform="win32", frozen=frozen, **kw)


class TestEnlargeOwnedConsole(unittest.TestCase):
    def test_noop_off_windows(self):
        k = FakeKernel32()
        self.assertFalse(console.enlarge_owned_console(kernel32=k, platform="linux"))
        self.assertEqual(k.calls, [])

    def test_owned_console_grows_buffer_then_window(self):
        k = FakeKernel32(processes=1)
        self.assertTrue(run(k))
        self.assertEqual(k.calls, [("buffer", 120, 3000), ("window", 120, 40)])

    def test_frozen_onefile_counts_bootloader_as_owner(self):
        k = FakeKernel32(processes=2)
        self.assertTrue(run(k, frozen=True))
        self.assertFalse(run(FakeKernel32(processes=2), frozen=False))

    def test_shared_console_is_left_alone(self):
        # Started from cmd.exe or PowerShell: the console belongs to the user.
        k = FakeKernel32(processes=3)
        self.assertFalse(run(k, frozen=True))
        self.assertEqual(k.calls, [])

    def test_never_shrinks(self):
        k = FakeKernel32(window=(160, 50), buffer=(160, 9000))
        self.assertFalse(run(k))
        self.assertEqual(k.calls, [])

    def test_grows_only_the_short_dimension(self):
        k = FakeKernel32(window=(150, 30), buffer=(150, 9000))
        self.assertTrue(run(k))
        self.assertEqual(k.calls, [("buffer", 150, 9000), ("window", 150, 40)])

    def test_clamped_to_largest_window(self):
        k = FakeKernel32(largest=(100, 35))
        self.assertTrue(run(k))
        self.assertEqual(k.calls[-1], ("window", 100, 35))

    def test_api_failure_is_silent(self):
        k = FakeKernel32()
        k.SetConsoleScreenBufferSize = lambda h, c: 0
        self.assertFalse(run(k))

        def boom(*a):
            raise OSError("no console")

        k2 = FakeKernel32()
        k2.GetConsoleProcessList = boom
        self.assertFalse(run(k2))


class TestPauseBeforeExitIfOwned(unittest.TestCase):
    def test_noop_off_windows(self):
        k = FakeKernel32()
        slept = []
        self.assertFalse(console.pause_before_exit_if_owned(kernel32=k, platform="linux", sleep=slept.append))
        self.assertEqual(slept, [])

    def test_owned_console_pauses(self):
        k = FakeKernel32(processes=1)
        slept = []
        self.assertTrue(console.pause_before_exit_if_owned(kernel32=k, platform="win32", frozen=False, sleep=slept.append))
        self.assertEqual(slept, [10])

    def test_custom_duration(self):
        k = FakeKernel32(processes=1)
        slept = []
        self.assertTrue(console.pause_before_exit_if_owned(5, kernel32=k, platform="win32", frozen=False, sleep=slept.append))
        self.assertEqual(slept, [5])

    def test_shared_console_is_left_alone(self):
        k = FakeKernel32(processes=3)
        slept = []
        self.assertFalse(console.pause_before_exit_if_owned(kernel32=k, platform="win32", frozen=True, sleep=slept.append))
        self.assertEqual(slept, [])

    def test_frozen_onefile_counts_bootloader_as_owner(self):
        k = FakeKernel32(processes=2)
        slept = []
        self.assertTrue(console.pause_before_exit_if_owned(kernel32=k, platform="win32", frozen=True, sleep=slept.append))
        self.assertEqual(slept, [10])

    def test_api_failure_is_silent(self):
        k = FakeKernel32()
        k.GetConsoleProcessList = lambda *a: (_ for _ in ()).throw(OSError("no console"))
        slept = []
        self.assertFalse(console.pause_before_exit_if_owned(kernel32=k, platform="win32", frozen=False, sleep=slept.append))
        self.assertEqual(slept, [])


if __name__ == "__main__":
    unittest.main()
