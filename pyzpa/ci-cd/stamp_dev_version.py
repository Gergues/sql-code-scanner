#!/usr/bin/env python3
"""Stamp a PEP 440 ``.devN`` suffix onto the project version in ``pyproject.toml``.

Used by the periodic (nightly) pipeline so every scheduled run produces a unique,
installable version on TestPyPI without a manual version bump. The edit is meant
to run on an ephemeral CI checkout — it rewrites ``pyproject.toml`` in place.

Usage::

    python ci-cd/stamp_dev_version.py            # appends .dev<UTC timestamp>
    python ci-cd/stamp_dev_version.py --print    # only print the new version

The base version is read from the existing ``version = "X.Y.Z"`` line. If that
line already carries a ``.devN`` / ``.postN`` / ``aN`` / ``bN`` / ``rcN`` suffix
it is stripped before the new dev suffix is applied.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

VERSION_RE = re.compile(r'^(?P<prefix>\s*version\s*=\s*")(?P<version>[^"]+)(?P<suffix>")', re.M)
# Trailing pre/post/dev release segment we want to drop before re-stamping.
PRE_POST_DEV_RE = re.compile(r"(?:\.post\d+|\.dev\d+|[._-]?(?:a|b|rc)\d+)+$")


def base_version(version: str) -> str:
    return PRE_POST_DEV_RE.sub("", version.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "pyproject.toml",
        help="Path to pyproject.toml (default: package root).",
    )
    parser.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="Print the computed dev version without writing the file.",
    )
    args = parser.parse_args(argv)

    text = args.pyproject.read_text(encoding="utf-8")
    match = VERSION_RE.search(text)
    if not match:
        print(f"error: no 'version = \"...\"' line found in {args.pyproject}", file=sys.stderr)
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    new_version = f"{base_version(match.group('version'))}.dev{stamp}"

    if args.print_only:
        print(new_version)
        return 0

    new_text = VERSION_RE.sub(
        lambda m: f"{m.group('prefix')}{new_version}{m.group('suffix')}", text, count=1
    )
    args.pyproject.write_text(new_text, encoding="utf-8")
    print(new_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
