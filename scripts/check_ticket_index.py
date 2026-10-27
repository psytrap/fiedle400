#!/usr/bin/env python3
"""Check that tickets/INDEX.md lists exactly the tickets in tickets/open/ (stdlib only).

Catches the two ways the two can drift apart: a ticket file added/closed without
updating INDEX.md, or an INDEX.md row left behind (or typo'd) pointing at a file
that no longer exists there.

Usage:
    python3 scripts/check_ticket_index.py

Exit code 0: INDEX.md and tickets/open/ agree. Non-zero: see the printed report.
"""

import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TICKETS_DIR = os.path.join(ROOT, "tickets")
OPEN_DIR = os.path.join(TICKETS_DIR, "open")
INDEX_PATH = os.path.join(TICKETS_DIR, "INDEX.md")

FILENAME_RE = re.compile(r"^(T-\d+)-.+\.md$")
# A table row linking an open/ ticket: | [T-NNN](open/T-NNN-slug.md) | ... |
# Anchored to a leading "| [" so prose mentions elsewhere in the file (e.g. "see T-071" in
# the Open questions section) don't get counted as index rows.
ROW_RE = re.compile(r"^\|\s*\[(T-\d+)\]\(open/([^)]+\.md)\)", re.MULTILINE)


def find_open_tickets(open_dir: str = OPEN_DIR) -> dict:
    """Returns {ticket_id: filename} for every T-NNN-*.md file in tickets/open/."""
    tickets = {}
    for name in os.listdir(open_dir):
        if name == "README.md" or not name.endswith(".md"):
            continue
        m = FILENAME_RE.match(name)
        if not m:
            print(f"WARNING: {name} in tickets/open/ doesn't match the T-NNN-slug.md pattern")
            continue
        tickets[m.group(1)] = name
    return tickets


def find_index_rows(index_path: str = INDEX_PATH) -> dict:
    """Returns {ticket_id: [filenames linked]} for every open/-linked ticket row in INDEX.md.

    A list (not a single filename) so a ticket accidentally listed twice is visible even
    if both rows point at the same file.
    """
    rows = {}
    with open(index_path, encoding="utf-8") as f:
        text = f.read()
    for ticket_id, filename in ROW_RE.findall(text):
        rows.setdefault(ticket_id, []).append(filename)
    return rows


def check(open_dir: str = OPEN_DIR, index_path: str = INDEX_PATH) -> int:
    open_tickets = find_open_tickets(open_dir)
    index_rows = find_index_rows(index_path)

    problems = []

    # 1. In tickets/open/ but not linked anywhere in INDEX.md.
    for ticket_id, filename in sorted(open_tickets.items()):
        if ticket_id not in index_rows:
            problems.append(f"MISSING FROM INDEX: {ticket_id} ({filename}) is in tickets/open/ "
                             f"but has no [T-NNN](open/...) row in INDEX.md")

    # 2. Linked in INDEX.md but the file isn't in tickets/open/ (stale/typo'd row).
    for ticket_id, filenames in sorted(index_rows.items()):
        for filename in filenames:
            if ticket_id not in open_tickets:
                problems.append(f"STALE INDEX ROW: INDEX.md links {ticket_id} -> open/{filename}, "
                                 f"but that file doesn't exist in tickets/open/ (closed without "
                                 f"updating INDEX.md? typo'd path?)")
            elif open_tickets[ticket_id] != filename:
                problems.append(f"FILENAME MISMATCH: INDEX.md links {ticket_id} -> open/{filename}, "
                                 f"but the actual file is open/{open_tickets[ticket_id]}")

    # 3. A ticket ID linked more than once in INDEX.md.
    for ticket_id, filenames in sorted(index_rows.items()):
        if len(filenames) > 1:
            problems.append(f"DUPLICATE: {ticket_id} appears {len(filenames)} times in INDEX.md")

    if problems:
        print(f"tickets/INDEX.md and tickets/open/ disagree ({len(problems)} issue(s)):\n")
        for p in problems:
            print(f"  - {p}")
        print(f"\n{len(open_tickets)} ticket(s) in tickets/open/, "
              f"{len(index_rows)} distinct ticket ID(s) linked in INDEX.md.")
        return 1

    print(f"OK: all {len(open_tickets)} ticket(s) in tickets/open/ are listed in INDEX.md, "
          f"with no stale or duplicate rows.")
    return 0


if __name__ == "__main__":
    sys.exit(check())
