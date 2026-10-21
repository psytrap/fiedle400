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
    except tk.TclError as e:  # no display
        raise unittest.SkipTest(f"no display for tkinter: {e}")
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
                m = self.mod.Mockup(self.root, screen)
                self.root.update_idletasks()
                self.assertTrue(list(_buttons(m.body)), screen)

    def test_device_screen_selects_all_recordings_and_offers_the_download(self):
        m = self.mod.Mockup(self.root, "device")
        tree = next(_widgets(m.body, ttk.Treeview))
        self.assertEqual(len(tree.selection()), len(self.mod.SESSIONS))
        labels = [b.cget("text") for b in _buttons(m.body)]
        self.assertIn("Download 3 recordings…", labels)

    def test_save_screen_defaults_to_html_and_follows_the_format(self):
        m = self.mod.Mockup(self.root, "save")
        self.assertEqual(m.fmt.get(), "html")
        self.assertTrue(m.path.get().endswith(".html"))
        m.fmt.set("csv")
        m._fmt_changed()
        self.assertTrue(m.path.get().endswith(".csv"))

    def test_erase_dialog_defaults_to_keeping_the_recordings(self):
        m = self.mod.Mockup(self.root, "erase")
        dlg = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        self.assertEqual(m.erase_default.cget("text"), "Keep recordings")
        self.assertTrue(dlg.bind("<Return>"))  # Enter presses the default button
        dlg.destroy()

    def test_buttons_switch_screens(self):
        m = self.mod.Mockup(self.root, "device")
        next(b for b in _buttons(m.body) if b.cget("text").startswith("Download")).invoke()
        self.assertTrue(any(b.cget("text") == "Browse…" for b in _buttons(m.body)))


if __name__ == "__main__":
    unittest.main()
