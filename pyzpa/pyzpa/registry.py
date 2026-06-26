"""Discovery and selection of checks.

Checks come from two sources:

* the built-in set in :mod:`pyzpa.checks`;
* third-party packages advertising the ``pyzpa.checks`` entry-point group.

Selection honours ``--checks`` / ``--disable`` CLI options layered on top of each
check's ``active_by_default`` flag.
"""

from __future__ import annotations

from importlib import metadata

from pyzpa.api.check import Check
from pyzpa.checks import BUILTIN_CHECKS

_ENTRY_POINT_GROUP = "pyzpa.checks"


def discover_check_classes() -> list[type[Check]]:
    """Return all known check classes (built-in + entry-points), de-duplicated."""
    classes: list[type[Check]] = list(BUILTIN_CHECKS)
    seen = {c.rule_key for c in classes}

    for ep in _iter_entry_points():
        try:
            obj = ep.load()
        except Exception:  # noqa: BLE001 - a bad plugin must not break the run
            continue
        for cls in _as_check_classes(obj):
            if cls.rule_key not in seen:
                seen.add(cls.rule_key)
                classes.append(cls)
    return classes


def select_checks(
    *,
    only: set[str] | None = None,
    disabled: set[str] | None = None,
) -> list[Check]:
    """Instantiate the checks that should run for this invocation."""
    only = only or set()
    disabled = disabled or set()

    selected: list[Check] = []
    for cls in discover_check_classes():
        key = cls.rule_key
        if only:
            active = key in only
        else:
            active = cls.rule_active_by_default and key not in disabled
        if active:
            selected.append(cls())
    return selected


def _iter_entry_points():
    try:
        eps = metadata.entry_points()
    except Exception:  # noqa: BLE001
        return []
    # importlib.metadata API differs across versions.
    if hasattr(eps, "select"):
        return eps.select(group=_ENTRY_POINT_GROUP)
    return eps.get(_ENTRY_POINT_GROUP, [])  # type: ignore[attr-defined]


def _as_check_classes(obj) -> list[type[Check]]:
    if isinstance(obj, type) and issubclass(obj, Check):
        return [obj]
    if isinstance(obj, (list, tuple)):
        return [c for c in obj if isinstance(c, type) and issubclass(c, Check)]
    return []
