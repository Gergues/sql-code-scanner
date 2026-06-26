"""Per-file context shared with checks during a scan."""

from __future__ import annotations

from dataclasses import dataclass

from pyzpa.analysis.file import PlSqlFile
from pyzpa.ast.nodes import AstNode
from pyzpa.parser.comments import Comment


@dataclass
class ScanContext:
    file: PlSqlFile
    ast: AstNode
    comments: list[Comment]

    @property
    def file_path(self) -> str:
        return self.file.path
