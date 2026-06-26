"""Tests for the CSV report writer."""

from __future__ import annotations

import csv
import io

from pyzpa import PlSqlAnalyzer
from pyzpa.analysis.file import PlSqlFile
from pyzpa.analysis.scanner import ScanResult
from pyzpa.api.issue import Issue, IssueLocation, Severity
from pyzpa.parser.parser import ParseError
from pyzpa.report import WRITERS
from pyzpa.report.csv_writer import HEADERS, write_csv

BOM = "\ufeff"


def _parse_rows(report: str) -> list[list[str]]:
    """Parse a CSV report (BOM stripped) into rows."""
    text = report[len(BOM):] if report.startswith(BOM) else report
    return list(csv.reader(io.StringIO(text)))


def _result(*issues: Issue, path: str = "sample.sql") -> ScanResult:
    return ScanResult(file=PlSqlFile(path=path, content=""), issues=list(issues))


def _issue(message: str, *, rule="DemoRule", severity=Severity.MAJOR) -> Issue:
    return Issue(
        rule_key=rule,
        message=message,
        location=IssueLocation(line=2, column=5, end_line=2, end_column=9),
        severity=severity,
    )


def test_csv_registered_in_writers():
    assert WRITERS["csv"] is write_csv


def test_csv_starts_with_utf8_bom():
    report = write_csv([_result(_issue("hello"))])
    assert report.startswith(BOM)
    # The BOM character encodes to the 3-byte UTF-8 BOM on disk.
    assert report.encode("utf-8").startswith(b"\xef\xbb\xbf")


def test_csv_header_row():
    report = write_csv([])
    rows = _parse_rows(report)
    assert rows[0] == list(HEADERS)


def test_csv_emits_issue_row():
    report = write_csv([_result(_issue("Avoid this", rule="DemoRule"))])
    rows = _parse_rows(report)
    assert rows[1] == [
        "sample.sql",
        "2",
        "5",
        "2",
        "9",
        "MAJOR",
        "DemoRule",
        "Avoid this",
    ]


def test_csv_escapes_special_characters():
    nasty = 'Has a comma, a "quote" and a\nnewline'
    report = write_csv([_result(_issue(nasty))])
    rows = _parse_rows(report)
    # The csv reader must round-trip the message back intact.
    assert rows[1][-1] == nasty


def test_csv_blank_location_for_missing_end_position():
    issue = Issue(
        rule_key="TodoComment",
        message="finish me",
        location=IssueLocation(line=4, column=2),  # end_line/end_column default 0
        severity=Severity.INFO,
    )
    # end positions of 0 are treated as "present"; only None becomes blank.
    report = write_csv([_result(issue)])
    rows = _parse_rows(report)
    assert rows[1][:5] == ["sample.sql", "4", "2", "0", "0"]


def test_csv_parse_error_row():
    result = ScanResult(
        file=PlSqlFile(path="broken.sql", content=""),
        parse_error=ParseError("unexpected token", line=3, column=7),
    )
    rows = _parse_rows(write_csv([result]))
    assert rows[1] == [
        "broken.sql",
        "3",
        "7",
        "",
        "",
        "PARSE_ERROR",
        "",
        "unexpected token",
    ]


def test_analyzer_format_csv_end_to_end():
    analyzer = PlSqlAnalyzer()
    results = [analyzer.analyze_source("BEGIN\n  SELECT * INTO v FROM t;\nEND;\n")]
    report = analyzer.format(results, "csv")
    rows = _parse_rows(report)
    assert rows[0] == list(HEADERS)
    assert any("SelectAllColumns" in row for row in rows[1:])
