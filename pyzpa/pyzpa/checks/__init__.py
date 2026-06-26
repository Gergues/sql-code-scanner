"""Built-in checks bundled with pyzpa."""

from __future__ import annotations

from pyzpa.api.check import Check
from pyzpa.checks.comparison_with_null import ComparisonWithNullCheck
from pyzpa.checks.empty_block import EmptyBlockCheck
from pyzpa.checks.select_all_columns import SelectAllColumnsCheck
from pyzpa.checks.todo_comment import TodoCommentCheck

#: All checks shipped in-box.
BUILTIN_CHECKS: tuple[type[Check], ...] = (
    ComparisonWithNullCheck,
    SelectAllColumnsCheck,
    EmptyBlockCheck,
    TodoCommentCheck,
)

__all__ = [
    "BUILTIN_CHECKS",
    "ComparisonWithNullCheck",
    "SelectAllColumnsCheck",
    "EmptyBlockCheck",
    "TodoCommentCheck",
]
