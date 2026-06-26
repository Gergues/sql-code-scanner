"""pyzpa — Python-based Z PL/SQL Analyzer for Oracle PL/SQL.

A large portion of this application's logic was ported from the ZPA project by
Felipe Zorzo (https://github.com/felipebz/zpa).

Library usage::

    from pyzpa import PlSqlAnalyzer

    analyzer = PlSqlAnalyzer()
    result = analyzer.analyze_source("BEGIN NULL; END;")
    for issue in result.issues:
        print(issue.rule_key, issue.location.line, issue.message)
"""

__version__ = "0.1.0"

# Public library surface. Defined after ``__version__`` so modules that read it
# during import (e.g. the SARIF writer) resolve cleanly.
from pyzpa.analysis.file import PlSqlFile
from pyzpa.analysis.metrics import FileMetrics
from pyzpa.analysis.scanner import AstScanner, ScanResult
from pyzpa.analyzer import DEFAULT_INCLUDE, Analyzer, PlSqlAnalyzer
from pyzpa.api import Check, Issue, IssueLocation, NodeType, Severity, rule

__all__ = [
    "__version__",
    # facade
    "PlSqlAnalyzer",
    "Analyzer",
    "DEFAULT_INCLUDE",
    # results
    "ScanResult",
    "FileMetrics",
    "PlSqlFile",
    "AstScanner",
    # check-author API
    "Check",
    "rule",
    "Issue",
    "IssueLocation",
    "Severity",
    "NodeType",
]
