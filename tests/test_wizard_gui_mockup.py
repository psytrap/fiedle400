"""scripts/wizard_gui_mockup.py (T-033): every screen of the tkinter wizard mockup builds and
its buttons are wired. Needs tkinter and a display; skipped otherwise (CI runs without a display
today; `xvfb-run` would enable it on Linux, see T-033's recommendation)."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:  # python3-tk not installed
    tk = None


def _make_root():
    if tk is None:
        raise unittest.SkipTest("tkinter is not installed")
    try:
        root = tk.Tk()
    except tk.TclError as error:  # no display
        raise unittest.SkipTest(f"no display for tkinter: {error}")
    root.withdraw()
    return root


def _widgets(widget, cls):
    for child in widget.winfo_children():
        if isinstance(child, cls):
            yield child
        yield from _widgets(child, cls)


def _buttons(widget):
    return _widgets(widget, ttk.Button)


class TestWizardGuiMockup(unittest.TestCase):
    def setUp(self):
        self.root = _make_root()
        import wizard_gui_mockup
        self.mod = wizard_gui_mockup
        self.mod.styles(self.root, None)

    def tearDown(self):
        self.root.destroy()

    def test_every_screen_builds(self):
        for screen in self.mod.SCREENS:
            with self.subTest(screen=screen):
                mockup = self.mod.Mockup(self.root, screen)
                self.root.update_idletasks()
                self.assertTrue(list(_buttons(mockup.body)), screen)

    def test_device_screen_selects_all_recordings_and_offers_the_download(self):
        mockup = self.mod.Mockup(self.root, "device")
        tree = next(_widgets(mockup.body, ttk.Treeview))
        self.assertEqual(len(tree.selection()), len(self.mod.SESSIONS))
        labels = [button.cget("text") for button in _buttons(mockup.body)]
        self.assertIn("Download 3 recordings…", labels)

    def test_save_screen_defaults_to_html_and_follows_the_format(self):
        mockup = self.mod.Mockup(self.root, "save")
        self.assertEqual(mockup.format.get(), "html")
        self.assertTrue(mockup.path.get().endswith(".html"))
        mockup.format.set("csv")
        mockup._fmt_changed()
        self.assertTrue(mockup.path.get().endswith(".csv"))

    def test_erase_dialog_defaults_to_keeping_the_recordings(self):
        mockup = self.mod.Mockup(self.root, "erase")
        dialog = next(widget for widget in self.root.winfo_children() if isinstance(widget, tk.Toplevel))
        self.assertEqual(mockup.erase_default.cget("text"), "Keep recordings")
        self.assertTrue(dialog.bind("<Return>"))  # Enter presses the default button
        dialog.destroy()

    def test_buttons_switch_screens(self):
        mockup = self.mod.Mockup(self.root, "device")
        next(button for button in _buttons(mockup.body) if button.cget("text").startswith("Download")).invoke()
        self.assertTrue(any(button.cget("text") == "Browse…" for button in _buttons(mockup.body)))


if __name__ == "__main__":
    unittest.main()
