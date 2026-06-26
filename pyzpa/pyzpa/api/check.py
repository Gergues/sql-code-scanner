"""Base class for all checks.

A check subscribes to one or more AST node types in :meth:`init`, then receives
matching nodes in :meth:`visit_node`. Comment-based checks override
:meth:`visit_comment`. Issues are recorded with :meth:`add_issue` /
:meth:`add_line_issue`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyzpa.api.issue import Issue, IssueLocation, Severity

if TYPE_CHECKING:
    from pyzpa.analysis.context import ScanContext
    from pyzpa.ast.nodes import AstNode
    from pyzpa.parser.comments import Comment


class Check:
    """Base class for a coding rule.

    Subclasses are decorated with :func:`pyzpa.api.decorators.rule` to provide
    metadata such as ``rule_key`` and ``rule_priority``.
    """

    # Populated by the @rule decorator; defaults keep undecorated checks usable.
    rule_key: str = "UnnamedRule"
    rule_name: str = "Unnamed rule"
    rule_priority: Severity = Severity.MAJOR
    rule_remediation: str = "5min"
    rule_active_by_default: bool = True
    rule_tags: tuple[str, ...] = ()
    rule_description: str = ""

    def __init__(self) -> None:
        self._subscribed: set[str] = set()
        self._issues: list[Issue] = []
        self._context: ScanContext | None = None
        self.init()

    # -- lifecycle -------------------------------------------------------
    def init(self) -> None:
        """Override to call :meth:`subscribe_to`."""

    def subscribe_to(self, *node_types: str) -> None:
        self._subscribed.update(node_types)

    @property
    def subscribed_types(self) -> set[str]:
        return self._subscribed

    def bind(self, context: "ScanContext") -> None:
        """Bind the per-file context before scanning starts."""
        self._context = context
        self._issues = []

    @property
    def context(self) -> "ScanContext":
        assert self._context is not None, "Check is not bound to a context"
        return self._context

    # -- visitor hooks (override as needed) ------------------------------
    def visit_file(self) -> None: ...

    def visit_node(self, node: "AstNode") -> None: ...

    def visit_comment(self, comment: "Comment") -> None: ...

    def leave_file(self) -> None: ...

    # -- issue reporting -------------------------------------------------
    def add_issue(self, node: "AstNode", message: str) -> Issue:
        location = IssueLocation(
            line=node.line,
            column=node.column,
            end_line=node.end_line,
            end_column=node.end_column,
        )
        return self._record(location, message)

    def add_line_issue(self, line: int, message: str, column: int = 0) -> Issue:
        return self._record(IssueLocation(line=line, column=column), message)

    def _record(self, location: IssueLocation, message: str) -> Issue:
        issue = Issue(
            rule_key=self.rule_key,
            message=message,
            location=location,
            severity=self.rule_priority,
            file_path=self.context.file_path,
        )
        self._issues.append(issue)
        return issue

    @property
    def issues(self) -> list[Issue]:
        return self._issues
