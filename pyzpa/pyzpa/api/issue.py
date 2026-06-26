"""Issue model produced by checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Severity(IntEnum):
    """Ordered severity levels (mirrors ZPA priorities)."""

    INFO = 0
    MINOR = 1
    MAJOR = 2
    CRITICAL = 3
    BLOCKER = 4

    @classmethod
    def from_name(cls, name: str) -> "Severity":
        return cls[name.strip().upper()]


@dataclass(frozen=True)
class IssueLocation:
    """A 1-based source location range."""

    line: int
    column: int = 0
    end_line: int = 0
    end_column: int = 0


@dataclass(frozen=True)
class Issue:
    """A single finding reported by a check."""

    rule_key: str
    message: str
    location: IssueLocation
    severity: Severity
    file_path: str = ""
