#!/usr/bin/env python3
"""Fail when private local agent configuration becomes Git-tracked."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_ROOTS = {".claude", ".agents", ".codex", ".cursor"}
FORBIDDEN_PREFIXES = tuple(f"{root}/" for root in sorted(FORBIDDEN_ROOTS))
FORBIDDEN_FILES = {
    "AGENTS.md",
    "AGENTS.override.md",
    "CLAUDE.md",
    "CLAUDE.local.md",
}


def main() -> int:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    tracked = result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
    violations = sorted(
        path
        for path in tracked
        if path
        and (
            path in FORBIDDEN_ROOTS
            or path in FORBIDDEN_FILES
            or any(path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)
        )
    )
    if violations:
        print("ERROR: private local agent configuration is Git-tracked:")
        for path in violations:
            print(f"  {path}")
        print("Remove these paths from the index before committing.")
        return 1
    print("private agent path guard passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
