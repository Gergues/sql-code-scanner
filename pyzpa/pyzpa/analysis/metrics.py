"""Lightweight source metrics."""

from __future__ import annotations

from dataclasses import dataclass

from pyzpa.api.nodes import COMPLEXITY_NODE_TYPES, STATEMENT_NODE_TYPES
from pyzpa.ast.nodes import AstNode
from pyzpa.parser.comments import Comment


@dataclass(frozen=True)
class FileMetrics:
    lines: int
    comment_lines: int
    statements: int
    complexity: int


def compute_metrics(
    source: str, ast: AstNode | None, comments: list[Comment]
) -> FileMetrics:
    lines = source.count("\n") + 1 if source else 0

    comment_lines = 0
    for comment in comments:
        comment_lines += comment.text.count("\n") + 1

    statements = 0
    complexity = 1  # base path
    if ast is not None:
        for node in ast.walk():
            if node.node_type in STATEMENT_NODE_TYPES:
                statements += 1
            if node.node_type in COMPLEXITY_NODE_TYPES:
                complexity += 1

    return FileMetrics(
        lines=lines,
        comment_lines=comment_lines,
        statements=statements,
        complexity=complexity,
    )
