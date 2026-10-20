#!/usr/bin/env python3
"""Apply and generate the root-level NNNN-*.patch files used for the
local/cloud delivery handoff (stdlib only). See AGENTS.md "Delivery"
for the convention this automates.

Usage:
    python3 scripts/sync_patch.py apply <patch-file>
    python3 scripts/sync_patch.py generate [<ref>] --name <short-name> [--number N] [--dir DIR ...]

`apply` (cloud -> local): refuses if tracked files have uncommitted changes,
dry-run checks the patch, applies it with `git am` (preserving the patch's
own author/date/Subject/Co-Authored-By), runs the full test suite, and rolls
back to the pre-apply commit if the suite is not green -- nothing is left
half-applied. On success the patch file is copied into the repo root
(gitignored by `*.patch`), so the numbers the cloud has used stay visible to
`generate`.

`generate` (local -> cloud): formats one commit (or a `<rev>..<rev>`
range) as a patch, numbered with the next free number found among the
`NNNN-*.patch` files on disk (repo root, `changes/`, and any `--dir`) -- not a
separately tracked counter that could drift from what is actually there.
`--number N` overrides it, for a repo whose root has not seen the cloud's
latest patches yet.
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PATCH_RE = re.compile(r"^(\d{4})-.*\.patch$")


def existing_patch_numbers(root=None, extra_dirs=()):
    """Numeric prefixes of every NNNN-*.patch file actually on disk: the repo
    root, its `changes/` folder (if any) and each directory in `extra_dirs`."""
    root = root or ROOT
    numbers = []
    for directory in (root, os.path.join(root, "changes"), *extra_dirs):
        for path in glob.glob(os.path.join(directory, "*.patch")):
            m = PATCH_RE.match(os.path.basename(path))
            if m:
                numbers.append(int(m.group(1)))
    return numbers


def next_patch_number(root=None, extra_dirs=()):
    numbers = existing_patch_numbers(root, extra_dirs)
    return (max(numbers) + 1) if numbers else 1


def slugify(name):
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not slug:
        raise ValueError("name must contain at least one alphanumeric character")
    return slug


def patch_filename(number, name, root=None):
    return os.path.join(root or ROOT, f"{number:04d}-{slugify(name)}.patch")


def _run(cmd, capture=False):
    return subprocess.run(
        cmd, cwd=ROOT, text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def _git_head():
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True
    ).stdout.strip()


def _tracked_changes():
    """Uncommitted changes to tracked files (untracked files do not count)."""
    out = _run(["git", "status", "--porcelain", "--untracked-files=no"], capture=True)
    return out.stdout.strip()


def cmd_apply(args):
    patch_path = os.path.abspath(args.patch)
    if not os.path.isfile(patch_path):
        print(f"Patch not found: {patch_path}", file=sys.stderr)
        return 1

    dirty = _tracked_changes()
    if dirty:
        print(dirty)
        print(
            "Tracked files have uncommitted changes -- commit or stash them first "
            "(a rollback after a red suite would discard them).",
            file=sys.stderr,
        )
        return 1

    print(f"[1/4] git apply --check {patch_path}")
    check = _run(["git", "apply", "--check", patch_path], capture=True)
    if check.returncode != 0:
        print(check.stdout)
        print("Dry-run failed -- not applying.", file=sys.stderr)
        return 1

    pre_head = _git_head()

    print("[2/4] git am (preserves the patch's own author/date/Subject)")
    am = _run(["git", "am", patch_path], capture=True)
    print(am.stdout)
    if am.returncode != 0:
        print("git am failed -- aborting and leaving nothing applied.", file=sys.stderr)
        _run(["git", "am", "--abort"], capture=True)
        return 1

    new_head = _git_head()
    print(f"Applied as commit {new_head}")

    print("[3/4] python3 -m unittest discover -s tests -t .")
    tests = _run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
        capture=True,
    )
    tail = "\n".join(tests.stdout.strip().splitlines()[-15:])
    print(tail)

    if tests.returncode != 0:
        print(
            f"[4/4] Suite failed after applying {os.path.basename(patch_path)} "
            f"-- rolling back to {pre_head} (nothing left committed).",
            file=sys.stderr,
        )
        _run(["git", "reset", "--hard", pre_head], capture=True)
        return 1

    print(f"[4/4] OK: {os.path.basename(patch_path)} applied as {new_head}, suite green.")
    kept = os.path.join(ROOT, os.path.basename(patch_path))
    if not os.path.exists(kept):
        shutil.copyfile(patch_path, kept)
        print(f"Kept a copy at {kept} (its number now counts for `generate`).")
    return 0


def cmd_generate(args):
    extra_dirs = [os.path.abspath(d) for d in args.dirs]
    number = args.number if args.number is not None else next_patch_number(extra_dirs=extra_dirs)
    out_path = patch_filename(number, args.name)
    if os.path.exists(out_path):
        print(f"Refusing to overwrite existing {out_path}", file=sys.stderr)
        return 1

    fmt_cmd = ["git", "format-patch", "--stdout"]
    fmt_cmd += [args.ref] if ".." in args.ref else ["-1", args.ref]

    print(f"git format-patch for '{args.ref}' -> {os.path.basename(out_path)}")
    fmt = subprocess.run(fmt_cmd, cwd=ROOT, text=True, capture_output=True)
    if fmt.returncode != 0 or not fmt.stdout.strip():
        print(fmt.stderr or "git format-patch produced no output.", file=sys.stderr)
        return 1

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(fmt.stdout)
    print(f"Wrote {out_path}")
    if args.number is None:
        print(
            "Numbered from the patch files found on disk; if the cloud has delivered "
            "patches that are not in this repo's root, rerun with --number."
        )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_apply = sub.add_parser(
        "apply", help="Apply a cloud-delivered patch: dry-run, git am, test, rollback on failure."
    )
    p_apply.add_argument("patch", help="Path to the NNNN-short-name.patch file.")
    p_apply.set_defaults(func=cmd_apply)

    p_gen = sub.add_parser(
        "generate", help="Generate a numbered patch from local commit(s) for the cloud."
    )
    p_gen.add_argument(
        "ref", nargs="?", default="HEAD",
        help="Commit to format, or a '<rev>..<rev>' range (default: HEAD).",
    )
    p_gen.add_argument(
        "--name", required=True, help="Short slug for the filename, e.g. 'fix-sentinel-sync'."
    )
    p_gen.add_argument(
        "--number", type=int, default=None,
        help="Use this patch number instead of the next free one found on disk.",
    )
    p_gen.add_argument(
        "--dir", dest="dirs", action="append", default=[],
        help="Also look for NNNN-*.patch files in this directory (repeatable).",
    )
    p_gen.set_defaults(func=cmd_generate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
