"""The PL/SQL parser facade built on Lark."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources

from lark import Lark
from lark.exceptions import LarkError

from pyzpa.ast.nodes import AstNode
from pyzpa.parser.ast_builder import build_ast
from pyzpa.parser.comments import Comment, extract_comments


class ParseError(Exception):
    """Raised (or collected) when source cannot be parsed."""

    def __init__(self, message: str, line: int = 0, column: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column


@dataclass
class ParseResult:
    ast: AstNode | None
    comments: list[Comment] = field(default_factory=list)
    error: ParseError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.ast is not None


@lru_cache(maxsize=1)
def _grammar_source() -> str:
    return (
        resources.files("pyzpa.grammar").joinpath("plsql.lark").read_text(encoding="utf-8")
    )


@lru_cache(maxsize=1)
def _lark() -> Lark:
    return Lark(
        _grammar_source(),
        parser="earley",
        lexer="dynamic",
        propagate_positions=True,
        maybe_placeholders=False,
        start="start",
    )


class PlSqlParser:
    """Parse PL/SQL text into an :class:`AstNode` tree plus comments."""

    def parse(self, source: str) -> ParseResult:
        comments = extract_comments(source)
        try:
            tree = _lark().parse(source)
        except LarkError as exc:
            line = getattr(exc, "line", 0) or 0
            column = getattr(exc, "column", 0) or 0
            error = ParseError(str(exc).strip().splitlines()[0], line, column)
            return ParseResult(ast=None, comments=comments, error=error)

        ast = build_ast(tree)
        return ParseResult(ast=ast, comments=comments, error=None)
