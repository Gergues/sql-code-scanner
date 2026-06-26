"""Internal AST node.

A deliberately generic tree (node type + children + position) so checks navigate
by grammar rule name rather than being coupled to Lark's tree shapes.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field


@dataclass
class AstNode:
    node_type: str
    value: str | None = None
    line: int = 0
    column: int = 0
    end_line: int = 0
    end_column: int = 0
    children: list["AstNode"] = field(default_factory=list)
    parent: "AstNode | None" = field(default=None, repr=False)

    # -- construction ----------------------------------------------------
    def add_child(self, child: "AstNode") -> None:
        child.parent = self
        self.children.append(child)

    # -- navigation ------------------------------------------------------
    def children_of_type(self, *node_types: str) -> list["AstNode"]:
        return [c for c in self.children if c.node_type in node_types]

    def first_child_of_type(self, *node_types: str) -> "AstNode | None":
        for c in self.children:
            if c.node_type in node_types:
                return c
        return None

    def has_child_of_type(self, *node_types: str) -> bool:
        return any(c.node_type in node_types for c in self.children)

    def descendants(self) -> Iterator["AstNode"]:
        for child in self.children:
            yield child
            yield from child.descendants()

    def descendants_of_type(self, *node_types: str) -> Iterator["AstNode"]:
        for node in self.descendants():
            if node.node_type in node_types:
                yield node

    def walk(self) -> Iterator["AstNode"]:
        """Yield this node and all descendants (pre-order)."""
        yield self
        for child in self.children:
            yield from child.walk()

    # -- text ------------------------------------------------------------
    def text(self) -> str:
        if self.value is not None:
            return self.value
        return " ".join(c.text() for c in self.children)

    def pretty(self, indent: int = 0) -> str:
        pad = "  " * indent
        label = self.node_type
        if self.value is not None:
            label += f" {self.value!r}"
        label += f"  @{self.line}:{self.column}"
        lines = [pad + label]
        for child in self.children:
            lines.append(child.pretty(indent + 1))
        return "\n".join(lines)
