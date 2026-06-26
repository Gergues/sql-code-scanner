"""A unit of source under analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlSqlFile:
    path: str
    content: str

    @classmethod
    def from_path(cls, path: str | Path, encoding: str = "utf-8") -> "PlSqlFile":
        p = Path(path)
        return cls(path=str(p), content=p.read_text(encoding=encoding))

    @property
    def name(self) -> str:
        return Path(self.path).name
