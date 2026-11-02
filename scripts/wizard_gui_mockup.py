#!/usr/bin/env python3
"""Clickable mockup of the proposed tkinter wizard (T-033). No device, no files written.

Usage:
    python3 scripts/wizard_gui_mockup.py                 # start at the device screen and click through
    python3 scripts/wizard_gui_mockup.py --screen save   # open one screen directly
    python3 scripts/wizard_gui_mockup.py --theme clam    # try another ttk theme

Screens: device, nodevice, save, progress, done, erase. Everything shown is made-up
sample data; the buttons only move between screens. Run it on Windows or macOS to see
the native ttk look (the cloud screenshots in T-033 are Linux/X11 with the "clam" theme).
Standard library only (tkinter.ttk); needs python3-tk on Linux distros that split it out.
"""

import argparse
import sys
import tkinter as tk
from tkinter import ttk

TITLE = "fiedle400 - PO-400 download"
VERSION = "0.4.27"
PROJECT_URL = "github.com/psytrap/fiedle400"
SESSIONS = [  # (id, start, duration, records)
    (1, "2026-10-18 22:41:07", "07:52:13", 28333),
    (2, "2026-10-19 23:05:40", "06:14:58", 22498),
    (3, "2026-10-20 13:12:02", "00:21:30", 1290),
]
SCREENS = ("device", "nodevice", "save", "progress", "done", "erase")


class Mockup:
    def __init__(self, root, start):
        self.root = root
        root.title(TITLE)
        root.geometry("660x470")
        root.minsize(560, 420)
        self.body = None
        self.format = tk.StringVar(value="html")
        self.path = tk.StringVar(value="fiedle400_2026-10-18T224107_2026-10-20T133332.html")
        getattr(self, "show_" + start)()

    # --- frame helpers -------------------------------------------------------------
    def _page(self, heading, subtitle=None):
        if self.body is not None:
            self.body.destroy()
        self.body = ttk.Frame(self.root, padding=(18, 14, 18, 14))
        self.body.pack(fill="both", expand=True)
        top = ttk.Frame(self.body)
        top.pack(fill="x")
        ttk.Label(top, text=heading, style="Heading.TLabel").pack(side="left")
        ttk.Label(top, text=f"v{VERSION}  ·  {PROJECT_URL}", style="Muted.TLabel").pack(side="right")
        if subtitle:
            ttk.Label(self.body, text=subtitle, style="Muted.TLabel", wraplength=600, justify="left").pack(anchor="w", pady=(2, 0))
        ttk.Separator(self.body).pack(fill="x", pady=(10, 10))
        return self.body

    def _buttons(self, parent, right, left=()):
        bar = ttk.Frame(parent)
        bar.pack(side="bottom", fill="x", pady=(12, 0))
        for text, command in left:
            ttk.Button(bar, text=text, command=command).pack(side="left")
        for i, (text, command) in enumerate(reversed(right)):
            style = "Accent.TButton" if i == 0 else "TButton"
            ttk.Button(bar, text=text, command=command, style=style).pack(side="right", padx=(8, 0))
        return bar

    # --- screens -------------------------------------------------------------------
    def show_device(self):
        page = self._page("PO-400 connected", "Pick the recordings to download. All are selected by default.")
        info = ttk.LabelFrame(page, text="Device", padding=(10, 6))
        info.pack(fill="x")
        rows = [("Port", "/dev/hidraw3"), ("Model", "PO-400"), ("Firmware", "not reported by the device"),
                ("Serial", "not reported by the device"), ("Clock", "2026-10-20 21:31:12"), ("User", "#1")]
        for i, (key, value) in enumerate(rows):
            ttk.Label(info, text=key + ":", style="Muted.TLabel").grid(row=i // 2, column=(i % 2) * 2, sticky="w", padx=(0, 6))
            ttk.Label(info, text=value).grid(row=i // 2, column=(i % 2) * 2 + 1, sticky="w", padx=(0, 24))
        box = ttk.LabelFrame(page, text="Recordings in device memory", padding=(10, 6))
        box.pack(fill="both", expand=True, pady=(10, 0))
        tree = ttk.Treeview(box, columns=("start", "dur", "rec"), height=4, selectmode="extended")
        tree.heading("#0", text="#")
        tree.column("#0", width=40, stretch=False)
        for col, text, width in (("start", "Start", 190), ("dur", "Duration", 110), ("rec", "Records", 100)):
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w" if col == "start" else "e")
        for session_id, start, duration, records in SESSIONS:
            tree.insert("", "end", iid=str(session_id), text=str(session_id), values=(start, duration, f"{records:,}"))
        tree.selection_set([str(session[0]) for session in SESSIONS])
        tree.pack(fill="both", expand=True)
        ttk.Label(box, text="Ctrl/Shift-click to pick several.", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        self._buttons(page, [("Quit", self.root.destroy), ("Download 3 recordings…", self.show_save)],
                      left=[("Erase device memory…", self.show_erase)])

    def show_nodevice(self):
        page = self._page("No PO-400 found", "fiedle400 could not open the oximeter.")
        tips = ("• Plug the PO-400 in with its USB cable and switch it on.\n"
                "• Close SpO2 Assistant: only one program can talk to the device at a time.\n"
                "• Linux: run fiedle400_setup-udev.sh once (see README).\n\n"
                "Details: no HID device with VID 28E9 / PID 028A")
        ttk.Label(page, text=tips, justify="left", wraplength=600).pack(anchor="w")
        self._buttons(page, [("Quit", self.root.destroy), ("Retry", self.show_device)],
                      left=[("Open a saved recording…", lambda: None)])

    def show_save(self):
        page = self._page("Save recordings", "3 recordings, 52,121 records (14 h 28 min).")
        format_frame = ttk.LabelFrame(page, text="Format", padding=(10, 6))
        format_frame.pack(fill="x")
        for value, label in (("html", "HTML page: chart and report, opens in any browser (default)"),
                             ("spo2", "SpO2 file: for SpO2 Assistant and OSCAR"),
                             ("csv", "CSV"), ("json", "JSON")):
            ttk.Radiobutton(format_frame, text=label, value=value, variable=self.format, command=self._fmt_changed).pack(anchor="w", pady=1)
        where = ttk.LabelFrame(page, text="Save as", padding=(10, 8))
        where.pack(fill="x", pady=(10, 0))
        ttk.Entry(where, textvariable=self.path).pack(side="left", fill="x", expand=True)
        ttk.Button(where, text="Browse…", command=lambda: None).pack(side="left", padx=(8, 0))
        ttk.Label(page, text="Browse… opens the system Save dialog, which also asks before overwriting a file.",
                  style="Muted.TLabel", wraplength=600).pack(anchor="w", pady=(6, 0))
        self._buttons(page, [("Cancel", self.show_device), ("Download", self.show_progress)],
                      left=[("‹ Back", self.show_device)])

    def _fmt_changed(self):
        stem = self.path.get().rsplit(".", 1)[0]
        self.path.set(f"{stem}.{self.format.get()}")

    def show_progress(self):
        page = self._page("Downloading…", "Keep the PO-400 connected until this finishes.")
        ttk.Label(page, text="Recording 2 of 3  (2026-10-19 23:05)").pack(anchor="w")
        bar = ttk.Progressbar(page, mode="determinate", maximum=100, value=62)
        bar.pack(fill="x", pady=(6, 2))
        ttk.Label(page, text="13,950 of 22,498 records", style="Muted.TLabel").pack(anchor="w")
        ttk.Label(page, text="Overall", style="Muted.TLabel").pack(anchor="w", pady=(14, 0))
        ttk.Progressbar(page, mode="determinate", maximum=100, value=81).pack(fill="x", pady=(4, 0))
        self._buttons(page, [("Cancel", self.show_device), ("Next › (mockup)", self.show_done)])

    def show_done(self):
        page = self._page("Saved", None)
        ttk.Label(page, text="52,121 records from 3 recordings saved to:").pack(anchor="w")
        ttk.Label(page, text="/home/user/fiedle400_2026-10-18T224107_2026-10-20T133332.html", style="Path.TLabel").pack(anchor="w", pady=(2, 8))
        row = ttk.Frame(page)
        row.pack(anchor="w")
        ttk.Button(row, text="Open in browser", command=lambda: None).pack(side="left")
        ttk.Button(row, text="Show in folder", command=lambda: None).pack(side="left", padx=(8, 0))
        erase_frame = ttk.LabelFrame(page, text="Device memory", padding=(10, 6))
        erase_frame.pack(fill="x", pady=(16, 0))
        ttk.Label(erase_frame, text="The file is saved. Erasing frees the device for the next night; it always asks first "
                           "(the terminal wizard asks [Y/n] here, an open question).",
                  style="Muted.TLabel", wraplength=580, justify="left").pack(anchor="w")
        ttk.Button(erase_frame, text="Erase device memory…", command=self.show_erase).pack(anchor="w", pady=(6, 0))
        self._buttons(page, [("Close", self.root.destroy), ("Back to recordings", self.show_device)])

    def show_erase(self):
        self.show_device()
        dialog = tk.Toplevel(self.root)
        dialog.title("Erase device memory")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=(18, 14))
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="⚠", style="Warn.TLabel").grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 12))
        ttk.Label(frame, text="Permanently delete all 3 recordings from the PO-400?", style="Strong.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(frame, text="This cannot be undone. Recordings you have not saved are lost.",
                  style="Muted.TLabel").grid(row=1, column=1, sticky="w", pady=(4, 12))
        bar = ttk.Frame(frame)
        bar.grid(row=2, column=0, columnspan=2, sticky="e")
        ttk.Button(bar, text="Erase", command=dialog.destroy).pack(side="right", padx=(8, 0))
        keep_button = ttk.Button(bar, text="Keep recordings", command=dialog.destroy, style="Accent.TButton")
        keep_button.pack(side="right")
        keep_button.focus_set()  # Enter keeps the recordings: the default is No, like the terminal [y/N]
        dialog.bind("<Return>", lambda event: keep_button.invoke())
        self.erase_default = keep_button
        dialog.update_idletasks()
        x_position = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_reqwidth()) // 2
        y_position = self.root.winfo_rooty() + 120
        dialog.geometry(f"+{x_position}+{y_position}")


def styles(root, theme):
    style = ttk.Style(root)
    if theme:
        style.theme_use(theme)
    elif sys.platform.startswith("linux") and "clam" in style.theme_names():
        style.theme_use("clam")  # Linux's "default" theme looks dated; Windows/macOS keep their native theme
    base = ("TkDefaultFont",)
    style.configure("Heading.TLabel", font=(base[0], 14, "bold"))
    style.configure("Strong.TLabel", font=(base[0], 10, "bold"))
    style.configure("Muted.TLabel", foreground="#5b6470")
    style.configure("Path.TLabel", font=("TkFixedFont", 10))
    style.configure("Warn.TLabel", font=(base[0], 22), foreground="#b8860b")
    style.configure("Accent.TButton", font=(base[0], 10, "bold"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--screen", choices=SCREENS, default="device")
    parser.add_argument("--theme", help="ttk theme (default: native; clam on Linux)")
    args = parser.parse_args(argv)
    try:
        root = tk.Tk()
    except tk.TclError as error:  # no display (SSH, CI)
        print(f"error: no display for tkinter: {error}", file=sys.stderr)
        return 2
    styles(root, args.theme)
    Mockup(root, args.screen)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
