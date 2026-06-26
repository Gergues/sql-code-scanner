"""Comment extraction.

Lark ignores comments, so we recover them with a lightweight scan over the raw
source. This keeps comment-based checks (e.g. TODO/FIXME) simple.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING = re.compile(r"'(?:[^']|'')*'")


@dataclass(frozen=True)
class Comment:
    text: str
    line: int
    column: int
    is_block: bool


def extract_comments(source: str) -> list[Comment]:
    """Return comments in *source*, ignoring comment markers inside strings."""
    # Mask string literals so that '--' or '/*' inside them is not mistaken
    # for a comment. Preserve newlines to keep line numbers accurate.
    masked = _STRING.sub(lambda m: _blank(m.group()), source)

    comments: list[Comment] = []
    for match in _BLOCK_COMMENT.finditer(masked):
        line, column = _line_col(source, match.start())
        comments.append(
            Comment(source[match.start() : match.end()], line, column, is_block=True)
        )
    for match in _LINE_COMMENT.finditer(masked):
        line, column = _line_col(source, match.start())
        comments.append(
            Comment(source[match.start() : match.end()], line, column, is_block=False)
        )
    comments.sort(key=lambda c: (c.line, c.column))
    return comments


def _blank(text: str) -> str:
    return "".join("\n" if ch == "\n" else " " for ch in text)


def _line_col(source: str, offset: int) -> tuple[int, int]:
    line = source.count("\n", 0, offset) + 1
    last_newline = source.rfind("\n", 0, offset)
    column = offset - last_newline - 1
    return line, column
