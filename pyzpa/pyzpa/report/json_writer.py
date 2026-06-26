"""Machine-readable JSON report."""

from __future__ import annotations

import json
from collections.abc import Iterable

from pyzpa.analysis.scanner import ScanResult
from pyzpa.api.issue import Severity


def write_json(results: Iterable[ScanResult]) -> str:
    payload = {"files": [_file_entry(r) for r in results]}
    return json.dumps(payload, indent=2)


def _file_entry(result: ScanResult) -> dict:
    entry: dict = {
        "path": result.file.path,
        "parsed": result.parsed,
        "issues": [_issue_entry(i) for i in result.issues],
    }
    if result.metrics is not None:
        m = result.metrics
        entry["metrics"] = {
            "lines": m.lines,
            "commentLines": m.comment_lines,
            "statements": m.statements,
            "complexity": m.complexity,
        }
    if result.parse_error is not None:
        err = result.parse_error
        entry["parseError"] = {
            "message": err.message,
            "line": err.line,
            "column": err.column,
        }
    return entry


def _issue_entry(issue) -> dict:
    loc = issue.location
    return {
        "ruleKey": issue.rule_key,
        "severity": Severity(issue.severity).name,
        "message": issue.message,
        "line": loc.line,
        "column": loc.column,
        "endLine": loc.end_line,
        "endColumn": loc.end_column,
    }
