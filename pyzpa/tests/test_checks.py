"""Tests for the built-in checks using fixture files + Noncompliant verifier."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyzpa.checks import (
    ComparisonWithNullCheck,
    EmptyBlockCheck,
    SelectAllColumnsCheck,
    TodoCommentCheck,
)
from tests.verifier import verify

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("check_factory", "fixture"),
    [
        (ComparisonWithNullCheck, "comparison_with_null.sql"),
        (SelectAllColumnsCheck, "select_all_columns.sql"),
        (EmptyBlockCheck, "empty_block.sql"),
        (TodoCommentCheck, "todo_comment.sql"),
    ],
)
def test_check_matches_annotations(check_factory, fixture):
    verify(check_factory(), _read(fixture), path=fixture)
