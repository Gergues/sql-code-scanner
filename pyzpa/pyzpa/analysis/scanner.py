"""Orchestrates parsing, walking, and issue collection for a single file."""

from __future__ import annotations

from dataclasses import dataclass, field

from pyzpa.analysis.context import ScanContext
from pyzpa.analysis.file import PlSqlFile
from pyzpa.analysis.metrics import FileMetrics, compute_metrics
from pyzpa.analysis.walker import Walker
from pyzpa.api.check import Check
from pyzpa.api.issue import Issue
from pyzpa.parser.parser import ParseError, PlSqlParser


@dataclass
class ScanResult:
    file: PlSqlFile
    issues: list[Issue] = field(default_factory=list)
    metrics: FileMetrics | None = None
    parse_error: ParseError | None = None

    @property
    def parsed(self) -> bool:
        return self.parse_error is None


class AstScanner:
    """Run a set of checks over PL/SQL files."""

    def __init__(self, checks: list[Check], parser: PlSqlParser | None = None) -> None:
        self._checks = checks
        self._parser = parser or PlSqlParser()

    def scan_file(self, file: PlSqlFile) -> ScanResult:
        parse = self._parser.parse(file.content)

        if not parse.ok or parse.ast is None:
            metrics = compute_metrics(file.content, None, parse.comments)
            return ScanResult(
                file=file, metrics=metrics, parse_error=parse.error
            )

        context = ScanContext(file=file, ast=parse.ast, comments=parse.comments)
        issues: list[Issue] = []

        for check in self._checks:
            check.bind(context)
            check.visit_file()
            for comment in parse.comments:
                check.visit_comment(comment)

        Walker(self._checks).walk(parse.ast)

        for check in self._checks:
            check.leave_file()
            issues.extend(check.issues)

        issues.sort(key=lambda i: (i.location.line, i.location.column, i.rule_key))
        metrics = compute_metrics(file.content, parse.ast, parse.comments)
        return ScanResult(file=file, issues=issues, metrics=metrics)
