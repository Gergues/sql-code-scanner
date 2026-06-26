"""Command-line interface for pyzpa.

Subcommands:
    scan         Analyse files and report issues (default reporting workflow).
    list-checks  Show available checks and whether they are active by default.
    parse        Parse a single file and print the AST (debugging aid).

Exit codes:
    0  success, no findings at or above --fail-on
    1  findings at or above --fail-on were reported
    2  usage / I/O error
    3  parse error while running 'parse', or parse errors with --strict
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from pyzpa import __version__
from pyzpa.analysis.file import PlSqlFile
from pyzpa.analyzer import PlSqlAnalyzer
from pyzpa.api.issue import Severity
from pyzpa.parser.parser import PlSqlParser
from pyzpa.registry import discover_check_classes

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_PARSE = 3

#: File extension used for each report format when auto-naming output files.
_FORMAT_EXTENSIONS = {
    "text": "txt",
    "json": "json",
    "csv": "csv",
    "sarif": "sarif",
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USAGE
    return args.func(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pyzpa", description="PL/SQL static analyzer.")
    parser.add_argument("--version", action="version", version=f"pyzpa {__version__}")
    sub = parser.add_subparsers(dest="command")

    scan = sub.add_parser("scan", help="Analyse files and report issues.")
    scan.add_argument("paths", nargs="+", help="Files or directories to scan.")
    scan.add_argument(
        "--format",
        choices=("text", "json", "csv", "sarif"),
        default="csv",
        help="Output format (default: csv).",
    )
    scan.add_argument(
        "--output",
        "-o",
        help=(
            "Write the report to this file. Use '-' for stdout. When omitted, "
            "a timestamped file named report_<YYYYMMDDHHMMSS>.<ext> is created."
        ),
    )
    scan.add_argument(
        "--checks",
        help="Comma-separated rule keys to run exclusively.",
    )
    scan.add_argument(
        "--disable",
        help="Comma-separated rule keys to disable.",
    )
    scan.add_argument(
        "--fail-on",
        default="MINOR",
        help="Minimum severity that causes a non-zero exit (default: MINOR).",
    )
    scan.add_argument(
        "--strict",
        action="store_true",
        help="Treat parse errors as a failure (exit code 3).",
    )
    scan.add_argument("--encoding", default="utf-8", help="Source file encoding.")
    scan.set_defaults(func=_cmd_scan)

    listing = sub.add_parser("list-checks", help="List available checks.")
    listing.add_argument(
        "--format", choices=("text", "json"), default="text", help="Output format."
    )
    listing.set_defaults(func=_cmd_list_checks)

    parse_cmd = sub.add_parser("parse", help="Parse one file and print its AST.")
    parse_cmd.add_argument("path", help="File to parse.")
    parse_cmd.add_argument("--encoding", default="utf-8", help="Source file encoding.")
    parse_cmd.set_defaults(func=_cmd_parse)

    return parser


# -- commands ------------------------------------------------------------
def _cmd_scan(args: argparse.Namespace) -> int:
    analyzer = PlSqlAnalyzer(
        checks=_split_keys(args.checks) or None,
        disabled=_split_keys(args.disable) or None,
        fail_on=args.fail_on if _valid_severity(args.fail_on) else Severity.MAJOR,
        encoding=args.encoding,
    )
    if not _valid_severity(args.fail_on):
        print(f"pyzpa: unknown severity '{args.fail_on}'", file=sys.stderr)
        return EXIT_USAGE

    try:
        files = analyzer.collect_files(args.paths)
    except OSError as exc:
        print(f"pyzpa: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if not files:
        print("pyzpa: no input files found", file=sys.stderr)
        return EXIT_USAGE

    results = analyzer.analyze_files(files)

    report = analyzer.format(results, args.format)
    _emit(report, args.output, args.format)

    if args.strict and any(r.parse_error is not None for r in results):
        return EXIT_PARSE
    return EXIT_FINDINGS if analyzer.has_failures(results) else EXIT_OK


def _cmd_list_checks(args: argparse.Namespace) -> int:
    classes = sorted(discover_check_classes(), key=lambda c: c.rule_key)
    if args.format == "json":
        import json

        payload = [
            {
                "key": c.rule_key,
                "name": c.rule_name,
                "severity": c.rule_priority.name,
                "activeByDefault": c.rule_active_by_default,
                "tags": list(c.rule_tags),
            }
            for c in classes
        ]
        print(json.dumps(payload, indent=2))
        return EXIT_OK

    for c in classes:
        flag = "on " if c.rule_active_by_default else "off"
        print(f"[{flag}] {c.rule_key:<24} {c.rule_priority.name:<9} {c.rule_name}")
    print(f"\n{len(classes)} check(s)")
    return EXIT_OK


def _cmd_parse(args: argparse.Namespace) -> int:
    try:
        file = PlSqlFile.from_path(args.path, encoding=args.encoding)
    except OSError as exc:
        print(f"pyzpa: {exc}", file=sys.stderr)
        return EXIT_USAGE

    result = PlSqlParser().parse(file.content)
    if not result.ok or result.ast is None:
        err = result.error
        loc = f"{err.line}:{err.column}" if err else "?"
        print(f"parse error at {loc}: {err.message if err else 'unknown'}", file=sys.stderr)
        return EXIT_PARSE

    print(result.ast.pretty())
    return EXIT_OK


# -- helpers -------------------------------------------------------------
def _valid_severity(name: str) -> bool:
    try:
        Severity.from_name(name)
    except KeyError:
        return False
    return True


def _split_keys(value: str | None) -> set[str]:
    if not value:
        return set()
    return {k.strip() for k in value.split(",") if k.strip()}


def _emit(report: str, output: str | None, fmt: str) -> None:
    if output == "-":
        print(report)
        return
    target = Path(output) if output else _default_report_path(fmt)
    target.write_text(report + "\n", encoding="utf-8")
    print(f"pyzpa: report written to {target}")


def _default_report_path(fmt: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    ext = _FORMAT_EXTENSIONS.get(fmt, "txt")
    return Path(f"report_{timestamp}.{ext}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
