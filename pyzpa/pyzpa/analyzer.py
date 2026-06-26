"""High-level, embeddable analyzer facade.

This is the entry point for using pyzpa as a **library** inside a larger Python
project (no CLI, no subprocess). Construct a :class:`PlSqlAnalyzer` once and reuse
it::

    from pyzpa import PlSqlAnalyzer

    analyzer = PlSqlAnalyzer()                      # all default-active checks
    result = analyzer.analyze_source("BEGIN NULL; END;")
    for issue in result.issues:
        print(issue.rule_key, issue.location.line, issue.message)

    results = analyzer.analyze_paths(["src/plsql"])  # files and/or directories
    if analyzer.has_failures(results):               # honours ``fail_on``
        ...

The analyzer is configured at construction time and is safe to reuse across many
calls. Check selection, file discovery, scanning, formatting, and the
pass/fail threshold are all available without touching the CLI.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from pyzpa.analysis.file import PlSqlFile
from pyzpa.analysis.scanner import AstScanner, ScanResult
from pyzpa.api.check import Check
from pyzpa.api.issue import Severity
from pyzpa.registry import discover_check_classes, select_checks

#: Default file patterns used when an input path is a directory.
DEFAULT_INCLUDE: tuple[str, ...] = (
    "*.sql",
    "*.pks",
    "*.pkb",
    "*.pkg",
    "*.prc",
    "*.fnc",
    "*.trg",
    "*.typ",
)


class PlSqlAnalyzer:
    """Embeddable PL/SQL analyzer.

    Parameters
    ----------
    checks:
        Rule keys to run **exclusively**. When given, ``disabled`` and the
        per-check ``active_by_default`` flag are ignored.
    disabled:
        Rule keys to switch off (layered on top of the default-active set).
    check_instances:
        Pre-built :class:`~pyzpa.api.check.Check` instances to run instead of the
        discovered set. Use this to inject custom checks programmatically.
    fail_on:
        Minimum severity that :meth:`has_failures` treats as a failure. Accepts a
        :class:`~pyzpa.api.issue.Severity` or its name (e.g. ``"MAJOR"``).
    encoding:
        Default text encoding used when reading files from disk.
    """

    def __init__(
        self,
        *,
        checks: Iterable[str] | None = None,
        disabled: Iterable[str] | None = None,
        check_instances: Iterable[Check] | None = None,
        fail_on: Severity | str = Severity.MAJOR,
        encoding: str = "utf-8",
    ) -> None:
        if check_instances is not None:
            self._checks: list[Check] = list(check_instances)
        else:
            self._checks = select_checks(
                only=set(checks) if checks else None,
                disabled=set(disabled) if disabled else None,
            )
        self._scanner = AstScanner(self._checks)
        self._encoding = encoding
        self.fail_on = (
            fail_on if isinstance(fail_on, Severity) else Severity.from_name(fail_on)
        )

    # -- introspection ---------------------------------------------------
    @property
    def checks(self) -> list[Check]:
        """The check instances this analyzer will run."""
        return list(self._checks)

    @staticmethod
    def available_checks() -> list[type[Check]]:
        """All discoverable check classes (built-in + entry-point plugins)."""
        return discover_check_classes()

    # -- analysis --------------------------------------------------------
    def analyze_source(self, source: str, path: str = "<source>") -> ScanResult:
        """Analyze an in-memory PL/SQL string."""
        return self._scanner.scan_file(PlSqlFile(path=path, content=source))

    def analyze_file(
        self, path: str | Path, encoding: str | None = None
    ) -> ScanResult:
        """Analyze a single file on disk."""
        file = PlSqlFile.from_path(path, encoding=encoding or self._encoding)
        return self._scanner.scan_file(file)

    def analyze_files(self, files: Iterable[PlSqlFile]) -> list[ScanResult]:
        """Analyze pre-built :class:`PlSqlFile` objects."""
        return [self._scanner.scan_file(f) for f in files]

    def analyze_paths(
        self,
        paths: Sequence[str | Path],
        *,
        include: Iterable[str] | None = None,
        exclude: Iterable[str] | None = None,
        encoding: str | None = None,
    ) -> list[ScanResult]:
        """Analyze files and/or directories (directories are searched recursively).

        ``include``/``exclude`` are filename glob patterns applied to directory
        contents (``include`` defaults to :data:`DEFAULT_INCLUDE`).
        """
        files = self.collect_files(
            paths, include=include, exclude=exclude, encoding=encoding
        )
        return self.analyze_files(files)

    # -- file discovery --------------------------------------------------
    def collect_files(
        self,
        paths: Sequence[str | Path],
        *,
        include: Iterable[str] | None = None,
        exclude: Iterable[str] | None = None,
        encoding: str | None = None,
    ) -> list[PlSqlFile]:
        """Resolve input paths into a de-duplicated list of :class:`PlSqlFile`."""
        include = tuple(include) if include is not None else DEFAULT_INCLUDE
        exclude = tuple(exclude or ())
        enc = encoding or self._encoding

        files: list[PlSqlFile] = []
        seen: set[str] = set()
        for raw in paths:
            p = Path(raw)
            if p.is_dir():
                for pattern in include:
                    for match in sorted(p.rglob(pattern)):
                        if _excluded(match, exclude):
                            continue
                        _add_unique(files, seen, match, enc)
            else:
                _add_unique(files, seen, p, enc)
        return files

    # -- results helpers -------------------------------------------------
    def has_failures(self, results: Iterable[ScanResult]) -> bool:
        """True if any issue is at or above the configured ``fail_on`` severity."""
        return any(
            issue.severity >= self.fail_on
            for result in results
            for issue in result.issues
        )

    @staticmethod
    def format(results: Iterable[ScanResult], fmt: str = "text") -> str:
        """Render results as ``text``, ``json``, or ``sarif``."""
        from pyzpa.report import WRITERS  # local import avoids an import cycle

        try:
            writer = WRITERS[fmt]
        except KeyError as exc:
            raise ValueError(
                f"unknown format {fmt!r}; choose from {sorted(WRITERS)}"
            ) from exc
        return writer(list(results))


def _add_unique(
    files: list[PlSqlFile], seen: set[str], path: Path, encoding: str
) -> None:
    key = str(path.resolve())
    if key in seen:
        return
    seen.add(key)
    files.append(PlSqlFile.from_path(path, encoding=encoding))


def _excluded(path: Path, patterns: tuple[str, ...]) -> bool:
    return any(path.match(pattern) for pattern in patterns)


#: Short alias for convenience.
Analyzer = PlSqlAnalyzer
