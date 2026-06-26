"""Flag 'SELECT *' usage."""

from __future__ import annotations

from pyzpa.api import Check, NodeType, rule
from pyzpa.ast.nodes import AstNode


@rule(
    key="SelectAllColumns",
    name="'SELECT *' should not be used",
    priority="MINOR",
    tags=("maintainability",),
    description=(
        "Selecting all columns with '*' is fragile against schema changes and "
        "fetches more data than needed. List the required columns explicitly."
    ),
)
class SelectAllColumnsCheck(Check):
    def init(self) -> None:
        self.subscribe_to(NodeType.SELECT_ALL_COLUMNS)

    def visit_node(self, node: AstNode) -> None:
        self.add_issue(node, "Replace 'SELECT *' with the explicit list of columns.")
