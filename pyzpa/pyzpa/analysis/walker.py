"""Depth-first AST walker that dispatches nodes to subscribed checks."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from pyzpa.api.check import Check
from pyzpa.ast.nodes import AstNode


class Walker:
    """Dispatch each AST node to checks subscribed to its node type."""

    def __init__(self, checks: Iterable[Check]) -> None:
        self._by_type: dict[str, list[Check]] = defaultdict(list)
        for check in checks:
            for node_type in check.subscribed_types:
                self._by_type[node_type].append(check)

    def walk(self, root: AstNode) -> None:
        for node in root.walk():
            for check in self._by_type.get(node.node_type, ()):  # type: ignore[arg-type]
                check.visit_node(node)
