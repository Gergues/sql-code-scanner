"""Flag direct comparisons against NULL (use IS NULL / IS NOT NULL instead)."""

from __future__ import annotations

from pyzpa.api import Check, NodeType, rule
from pyzpa.ast.nodes import AstNode


@rule(
    key="ComparisonWithNull",
    name="Comparisons with NULL should use IS NULL or IS NOT NULL",
    priority="MAJOR",
    tags=("bug", "suspicious"),
    description=(
        "Any comparison with NULL using = or <> evaluates to NULL, never TRUE. "
        "Use IS NULL or IS NOT NULL instead."
    ),
)
class ComparisonWithNullCheck(Check):
    def init(self) -> None:
        self.subscribe_to(NodeType.EQ_COMPARISON, NodeType.NEQ_COMPARISON)

    def visit_node(self, node: AstNode) -> None:
        if node.has_child_of_type(NodeType.NULL_LITERAL):
            self.add_issue(
                node, "Use 'IS NULL' or 'IS NOT NULL' instead of comparing with NULL."
            )
