"""Convert a Lark parse tree into our generic :class:`AstNode` tree."""

from __future__ import annotations

from lark import Token, Tree

from pyzpa.ast.nodes import AstNode

# Token types we keep as leaf nodes (others, e.g. punctuation, are anonymous and
# filtered out by Lark already since they are string literals).
_LEAF_TOKENS = {"NAME", "NUMBER", "STRING"}


def build_ast(tree: Tree) -> AstNode:
    """Build an :class:`AstNode` from a Lark ``Tree`` with propagated positions."""
    node = _convert_tree(tree)
    assert node is not None
    return node


def _convert_tree(tree: Tree) -> AstNode:
    node = AstNode(node_type=tree.data if isinstance(tree.data, str) else str(tree.data))
    _apply_meta(node, tree)

    for child in tree.children:
        converted = _convert_child(child)
        if converted is not None:
            node.add_child(converted)

    _fill_position_from_children(node)
    return node


def _convert_child(child) -> AstNode | None:
    if isinstance(child, Tree):
        return _convert_tree(child)
    if isinstance(child, Token):
        if child.type not in _LEAF_TOKENS:
            return None
        leaf = AstNode(node_type=child.type, value=str(child))
        leaf.line = child.line or 0
        leaf.column = (child.column or 1) - 1
        leaf.end_line = child.end_line or leaf.line
        leaf.end_column = (child.end_column or 1) - 1
        return leaf
    return None


def _apply_meta(node: AstNode, tree: Tree) -> None:
    meta = getattr(tree, "meta", None)
    if meta is None or getattr(meta, "empty", True):
        return
    node.line = getattr(meta, "line", 0) or 0
    node.column = max(getattr(meta, "column", 1) - 1, 0)
    node.end_line = getattr(meta, "end_line", node.line) or node.line
    node.end_column = max(getattr(meta, "end_column", 1) - 1, 0)


def _fill_position_from_children(node: AstNode) -> None:
    """If meta gave no position, derive it from the span of children."""
    if node.line:
        return
    positioned = [c for c in node.children if c.line]
    if not positioned:
        return
    first = positioned[0]
    last = positioned[-1]
    node.line = first.line
    node.column = first.column
    node.end_line = last.end_line or last.line
    node.end_column = last.end_column or last.column
