#!/usr/bin/env python3
"""Bump the po400 version in every manifest at once (stdlib only).

Usage:
    python3 scripts/bump_version.py patch            # Phase 1: once per release cycle (pre-flight RC)
    python3 scripts/bump_version.py minor|major      # Phase 2: final step after the release is verified
    python3 scripts/bump_version.py set 0.1.0        # Reconcile to an explicit version
    python3 scripts/bump_version.py show             # Print the versions found in each manifest

See RELEASE_PLAN.md §1 for when each bump is allowed.
"""

import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# (relative path, regex with one group capturing the version)
MANIFESTS = [
    ("pyproject.toml", re.compile(r'^(version\s*=\s*")(\d+\.\d+\.\d+)(")', re.MULTILINE)),
    ("po400/__init__.py", re.compile(r'^(__version__\s*=\s*")(\d+\.\d+\.\d+)(")', re.MULTILINE)),
]

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def read_versions(root: str = ROOT) -> dict:
    versions = {}
    for rel, rx in MANIFESTS:
        with open(os.path.join(root, rel), encoding="utf-8") as f:
            m = rx.search(f.read())
        if not m:
            raise ValueError(f"No version found in {rel}")
        versions[rel] = m.group(2)
    return versions


def next_version(current: str, part: str) -> str:
    major, minor, patch = (int(x) for x in current.split("."))
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "major":
        return f"{major + 1}.0.0"
    raise ValueError(f"Unknown bump part: {part}")


def write_version(new: str, root: str = ROOT) -> None:
    for rel, rx in MANIFESTS:
        path = os.path.join(root, rel)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        text, n = rx.subn(lambda m: f"{m.group(1)}{new}{m.group(3)}", text, count=1)
        if n != 1:
            raise ValueError(f"Could not update version in {rel}")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def main(argv=None, root: str = ROOT) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("patch", "minor", "major", "set", "show"):
        print(__doc__.strip(), file=sys.stderr)
        return 2

    versions = read_versions(root)
    if argv[0] == "show":
        for rel, v in versions.items():
            print(f"{rel}: {v}")
        return 0 if len(set(versions.values())) == 1 else 1

    if argv[0] == "set":
        if len(argv) != 2 or not SEMVER_RE.match(argv[1]):
            print("Usage: bump_version.py set X.Y.Z", file=sys.stderr)
            return 2
        new = argv[1]
    else:
        if len(set(versions.values())) != 1:
            print(f"Manifests disagree ({versions}); reconcile first with: bump_version.py set X.Y.Z", file=sys.stderr)
            return 1
        new = next_version(next(iter(versions.values())), argv[0])

    write_version(new, root)
    print(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
