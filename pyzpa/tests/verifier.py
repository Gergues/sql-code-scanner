"""Test helper: verify a check against ``-- Noncompliant`` annotations.

Mirrors ZPA's check-verifier idea in a minimal form. A line containing
``-- Noncompliant`` marks that an issue is expected on that line. The verifier
runs a single check and asserts the reported lines match the annotations.
"""

from __future__ import annotations

import re

from pyzpa.analysis.file import PlSqlFile
from pyzpa.analysis.scanner import AstScanner
from pyzpa.api.check import Check

_ANNOTATION = re.compile(r"--\s*Noncompliant\b", re.IGNORECASE)


def expected_lines(source: str) -> set[int]:
    return {
        index
        for index, line in enumerate(source.splitlines(), start=1)
        if _ANNOTATION.search(line)
    }


def verify(check: Check, source: str, path: str = "<test>") -> None:
    """Assert the check reports issues exactly on annotated lines."""
    result = AstScanner([check]).scan_file(PlSqlFile(path=path, content=source))
    assert result.parse_error is None, f"unexpected parse error: {result.parse_error}"

    actual = {issue.location.line for issue in result.issues}
    expected = expected_lines(source)

    missing = expected - actual
    unexpected = actual - expected
    assert not missing and not unexpected, (
        f"line mismatch for {check.rule_key}: "
        f"missing={sorted(missing)} unexpected={sorted(unexpected)}"
    )
