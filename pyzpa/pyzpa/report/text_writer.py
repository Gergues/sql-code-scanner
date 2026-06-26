"""Human-readable text report."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from pyzpa.analysis.scanner import ScanResult
from pyzpa.api.issue import Severity

_HEADERS = ("Error", "Timestamp", "Severity", "Description")


def write_text(results: Iterable[ScanResult]) -> str:
    results = list(results)
    timestamp = datetime.now().isoformat(timespec="seconds")

    rows: list[tuple[str, str, str, str]] = []
    total_issues = 0
    files_with_errors = 0

    for result in results:
        if result.parse_error is not None:
            files_with_errors += 1
            err = result.parse_error
            rows.append(
                (
                    f"{result.file.path}:{err.line}:{err.column}",
                    timestamp,
                    "PARSE",
                    err.message,
                )
            )
            continue

        for issue in result.issues:
            total_issues += 1
            loc = issue.location
            rows.append(
                (
                    f"{result.file.path}:{loc.line}:{loc.column} "
                    f"[{issue.rule_key}]",
                    timestamp,
                    Severity(issue.severity).name,
                    issue.message,
                )
            )

    lines = _render_table(rows)
    lines.append("")
    summary = f"{total_issues} issue(s) in {len(results)} file(s)"
    if files_with_errors:
        summary += f", {files_with_errors} file(s) with parse errors"
    lines.append(summary)
    return "\n".join(lines)


def _render_table(rows: list[tuple[str, str, str, str]]) -> list[str]:
    """Render aligned, pipe-delimited columns with a header."""
    widths = [len(h) for h in _HEADERS]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def format_row(cells: tuple[str, ...]) -> str:
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    lines = [format_row(_HEADERS)]
    lines.append("-+-".join("-" * w for w in widths))
    lines.extend(format_row(row) for row in rows)
    return lines
