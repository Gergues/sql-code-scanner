"""Spreadsheet-friendly CSV report."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable

from pyzpa.analysis.scanner import ScanResult
from pyzpa.api.issue import Severity

HEADERS = (
    "File",
    "Line",
    "Column",
    "End Line",
    "End Column",
    "Severity",
    "Rule",
    "Message",
)


def write_csv(results: Iterable[ScanResult]) -> str:
    buffer = io.StringIO()
    # Lead with a UTF-8 BOM so Excel opens the file with the correct
    # encoding and renders accented characters on double-click.
    buffer.write("\ufeff")
    # QUOTE_MINIMAL keeps the file compact; the csv module handles
    # embedded commas, quotes and newlines in messages safely.
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADERS)

    for result in results:
        path = result.file.path

        if result.parse_error is not None:
            err = result.parse_error
            writer.writerow(
                [path, err.line, err.column, "", "", "PARSE_ERROR", "", err.message]
            )
            continue

        for issue in result.issues:
            loc = issue.location
            writer.writerow(
                [
                    path,
                    loc.line,
                    loc.column,
                    loc.end_line if loc.end_line is not None else "",
                    loc.end_column if loc.end_column is not None else "",
                    Severity(issue.severity).name,
                    issue.rule_key,
                    issue.message,
                ]
            )

    return buffer.getvalue()
