"""Flag TODO / FIXME markers in comments."""

from __future__ import annotations

import re

from pyzpa.api import Check, rule
from pyzpa.parser.comments import Comment

_MARKER = re.compile(r"\b(TODO|FIXME)\b", re.IGNORECASE)


@rule(
    key="TodoComment",
    name="'TODO' and 'FIXME' tags should be handled",
    priority="INFO",
    tags=("maintainability",),
    description="TODO/FIXME comments flag work that is not yet complete.",
)
class TodoCommentCheck(Check):
    def visit_comment(self, comment: Comment) -> None:
        match = _MARKER.search(comment.text)
        if match:
            self.add_line_issue(
                comment.line,
                f"Complete the task associated with this '{match.group(1).upper()}' comment.",
                column=comment.column,
            )
