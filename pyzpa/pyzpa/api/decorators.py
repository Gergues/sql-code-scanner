"""Decorator used to attach rule metadata to a Check subclass."""

from __future__ import annotations

from collections.abc import Iterable

from pyzpa.api.issue import Severity


def rule(
    *,
    key: str,
    name: str,
    priority: str = "MAJOR",
    remediation: str = "5min",
    active_by_default: bool = True,
    tags: Iterable[str] | None = None,
    description: str = "",
):
    """Attach rule metadata to a :class:`~pyzpa.api.check.Check` subclass.

    Example::

        @rule(key="ComparisonWithNull", name="...", priority="MAJOR")
        class ComparisonWithNullCheck(Check):
            ...
    """

    def decorator(cls):
        cls.rule_key = key
        cls.rule_name = name
        cls.rule_priority = Severity.from_name(priority)
        cls.rule_remediation = remediation
        cls.rule_active_by_default = active_by_default
        cls.rule_tags = tuple(tags or ())
        cls.rule_description = description
        return cls

    return decorator
