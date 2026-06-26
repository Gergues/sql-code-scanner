"""Flag empty blocks (a block whose body does nothing)."""

from __future__ import annotations

from pyzpa.api import Check, NodeType, rule
from pyzpa.api.nodes import STATEMENT_NODE_TYPES
from pyzpa.ast.nodes import AstNode

_NON_EMPTY_STATEMENTS = STATEMENT_NODE_TYPES - {NodeType.NULL_STATEMENT}


@rule(
    key="EmptyBlock",
    name="Blocks should not be empty",
    priority="MAJOR",
    tags=("suspicious",),
    description=(
        "A block whose body is empty or contains only 'NULL;' usually indicates "
        "missing or dead code."
    ),
)
class EmptyBlockCheck(Check):
    def init(self) -> None:
        self.subscribe_to(NodeType.NESTED_BLOCK)

    def visit_node(self, node: AstNode) -> None:
        has_real_statement = node.has_child_of_type(*_NON_EMPTY_STATEMENTS)
        has_handler = node.has_child_of_type(NodeType.EXCEPTION_SECTION)
        if not has_real_statement and not has_handler:
            self.add_issue(node, "This block is empty or only contains 'NULL;'.")
