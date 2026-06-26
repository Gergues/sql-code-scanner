"""pyzpa — single-file edition.
Layout (mirrors the package, top to bottom):
    1.  Issue model           (Severity, IssueLocation, Issue)
    2.  Grammar node types     (NodeType + statement/complexity sets)
    3.  AST node               (AstNode)
    4.  Comments               (Comment, extract_comments)
    5.  Rule decorator + Check (rule, Check)
    6.  Source file + context  (PlSqlFile, ScanContext)
    7.  Metrics                (FileMetrics, compute_metrics)
    8.  Grammar + parser       (PLSQL_GRAMMAR, build_ast, PlSqlParser)
    9.  Walker + scanner       (Walker, ScanResult, AstScanner)
    10. Built-in checks        (ComparisonWithNull, SelectAllColumns, ...)
    11. Registry               (discover_check_classes, select_checks)
    12. Analyzer facade        (PlSqlAnalyzer)
    13. Report writers         (text/json/csv/sarif + WRITERS)
    14. CLI                    (main and subcommands)

Library usage::

    from pyzpa_oneshot import PlSqlAnalyzer

    analyzer = PlSqlAnalyzer()
    result = analyzer.analyze_source("BEGIN NULL; END;")
    for issue in result.issues:
        print(issue.rule_key, issue.location.line, issue.message)

CLI usage::

    python pyzpa_oneshot.py scan path/to/file.sql
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from functools import lru_cache
from importlib import metadata
from pathlib import Path
from typing import Optional

from lark import Lark, Token, Tree
from lark.exceptions import LarkError

__version__ = "0.1.0"


# ---------------------------------------------------------------------------
# 1. Issue model
# ---------------------------------------------------------------------------
class Severity(IntEnum):
    """Ordered severity levels (mirrors ZPA priorities)."""

    INFO = 0
    MINOR = 1
    MAJOR = 2
    CRITICAL = 3
    BLOCKER = 4

    @classmethod
    def from_name(cls, name: str) -> "Severity":
        return cls[name.strip().upper()]


@dataclass(frozen=True)
class IssueLocation:
    """A 1-based source location range."""

    line: int
    column: int = 0
    end_line: int = 0
    end_column: int = 0


@dataclass(frozen=True)
class Issue:
    """A single finding reported by a check."""

    rule_key: str
    message: str
    location: IssueLocation
    severity: Severity
    file_path: str = ""


# ---------------------------------------------------------------------------
# 2. Grammar node-type and token-type constants
# ---------------------------------------------------------------------------
class NodeType:
    # Program units
    ANONYMOUS_BLOCK = "anonymous_block"
    CREATE_PROCEDURE = "create_procedure"
    CREATE_FUNCTION = "create_function"
    NESTED_BLOCK = "nested_block"

    # Declarations
    DECLARE_SECTION = "declare_section"
    VARIABLE_DECLARATION = "variable_declaration"
    PARAMETER = "parameter"
    DATATYPE = "datatype"

    # Statements
    ASSIGNMENT_STATEMENT = "assignment_statement"
    IF_STATEMENT = "if_statement"
    ELSIF_CLAUSE = "elsif_clause"
    ELSE_CLAUSE = "else_clause"
    LOOP_STATEMENT = "loop_statement"
    NULL_STATEMENT = "null_statement"
    RETURN_STATEMENT = "return_statement"
    RAISE_STATEMENT = "raise_statement"
    CALL_STATEMENT = "call_statement"
    SELECT_STATEMENT = "select_statement"
    EXCEPTION_SECTION = "exception_section"
    EXCEPTION_HANDLER = "exception_handler"

    # SELECT internals
    SELECT_ALL_COLUMNS = "select_all_columns"
    SELECT_ITEM = "select_item"
    TABLE_REF = "table_ref"
    WHERE_CLAUSE = "where_clause"

    # Expressions
    EQ_COMPARISON = "eq_comparison"
    NEQ_COMPARISON = "neq_comparison"
    REL_COMPARISON = "rel_comparison"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    FUNCTION_CALL = "function_call"
    QUALIFIED_NAME = "qualified_name"
    NULL_LITERAL = "null_literal"
    NUMBER_LITERAL = "number_literal"
    STRING_LITERAL = "string_literal"

    # Tokens
    NAME = "NAME"


#: Node types that represent executable statements (used by metrics and checks).
STATEMENT_NODE_TYPES = frozenset(
    {
        NodeType.ASSIGNMENT_STATEMENT,
        NodeType.IF_STATEMENT,
        NodeType.LOOP_STATEMENT,
        NodeType.NULL_STATEMENT,
        NodeType.RETURN_STATEMENT,
        NodeType.RAISE_STATEMENT,
        NodeType.CALL_STATEMENT,
        NodeType.SELECT_STATEMENT,
        NodeType.NESTED_BLOCK,
    }
)

#: Node types that add a branch to cyclomatic complexity.
COMPLEXITY_NODE_TYPES = frozenset(
    {
        NodeType.IF_STATEMENT,
        NodeType.ELSIF_CLAUSE,
        NodeType.LOOP_STATEMENT,
        NodeType.EXCEPTION_HANDLER,
    }
)


# ---------------------------------------------------------------------------
# 3. AST node
# ---------------------------------------------------------------------------
@dataclass
class AstNode:
    """Generic tree node (node type + children + position)."""

    node_type: str
    value: Optional[str] = None
    line: int = 0
    column: int = 0
    end_line: int = 0
    end_column: int = 0
    children: list["AstNode"] = field(default_factory=list)
    parent: "AstNode | None" = field(default=None, repr=False)

    # -- construction ----------------------------------------------------
    def add_child(self, child: "AstNode") -> None:
        child.parent = self
        self.children.append(child)

    # -- navigation ------------------------------------------------------
    def children_of_type(self, *node_types: str) -> list["AstNode"]:
        return [c for c in self.children if c.node_type in node_types]

    def first_child_of_type(self, *node_types: str) -> "AstNode | None":
        for c in self.children:
            if c.node_type in node_types:
                return c
        return None

    def has_child_of_type(self, *node_types: str) -> bool:
        return any(c.node_type in node_types for c in self.children)

    def descendants(self):
        for child in self.children:
            yield child
            yield from child.descendants()

    def descendants_of_type(self, *node_types: str):
        for node in self.descendants():
            if node.node_type in node_types:
                yield node

    def walk(self):
        """Yield this node and all descendants (pre-order)."""
        yield self
        for child in self.children:
            yield from child.walk()

    # -- text ------------------------------------------------------------
    def text(self) -> str:
        if self.value is not None:
            return self.value
        return " ".join(c.text() for c in self.children)

    def pretty(self, indent: int = 0) -> str:
        pad = "  " * indent
        label = self.node_type
        if self.value is not None:
            label += f" {self.value!r}"
        label += f"  @{self.line}:{self.column}"
        lines = [pad + label]
        for child in self.children:
            lines.append(child.pretty(indent + 1))
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. Comments
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# 5. Rule decorator + Check base class
# ---------------------------------------------------------------------------
def rule(
    *,
    key: str,
    name: str,
    priority: str = "MAJOR",
    remediation: str = "5min",
    active_by_default: bool = True,
    tags: Iterable[str] | None = None,
    description: str = "",
):
    """Attach rule metadata to a :class:`Check` subclass."""

    def decorator(cls):
        cls.rule_key = key
        cls.rule_name = name
        cls.rule_priority = Severity.from_name(priority)
        cls.rule_remediation = remediation
        cls.rule_active_by_default = active_by_default
        cls.rule_tags = tuple(tags or ())
        cls.rule_description = description
        return cls

    return decorator


class Check:
    """Base class for a coding rule.

    Subclasses are decorated with :func:`rule` to provide metadata such as
    ``rule_key`` and ``rule_priority``.
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


# ---------------------------------------------------------------------------
# 6. Source file + scan context
# ---------------------------------------------------------------------------
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


@dataclass
class ScanContext:
    file: PlSqlFile
    ast: AstNode
    comments: list[Comment]

    @property
    def file_path(self) -> str:
        return self.file.path


# ---------------------------------------------------------------------------
# 7. Metrics
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# 8. Grammar + parser
# ---------------------------------------------------------------------------
#: Minimal Oracle PL/SQL grammar subset (embedded copy of grammar/plsql.lark).
PLSQL_GRAMMAR = r"""
// Minimal Oracle PL/SQL grammar subset for the pyzpa MVP.
// Parsed with Lark's Earley parser (dynamic lexer), positions propagated.
// This is intentionally a SUBSET — enough to drive the starter checks.

start: program_unit*

?program_unit: anonymous_block
             | create_procedure
             | create_function

anonymous_block: declare_section? "BEGIN"i statement* exception_section? "END"i ";"

create_procedure: "CREATE"i ("OR"i "REPLACE"i)? "PROCEDURE"i qualified_name parameter_list? _is_as declaration* "BEGIN"i statement* exception_section? "END"i qualified_name? ";"

create_function: "CREATE"i ("OR"i "REPLACE"i)? "FUNCTION"i qualified_name parameter_list? "RETURN"i datatype _is_as declaration* "BEGIN"i statement* exception_section? "END"i qualified_name? ";"

_is_as: "IS"i | "AS"i

parameter_list: "(" parameter ("," parameter)* ")"
parameter: NAME _mode? datatype (":=" expression)?
_mode: "IN"i "OUT"i | "IN"i | "OUT"i

declare_section: "DECLARE"i declaration*
declaration: variable_declaration
variable_declaration: NAME datatype (":=" expression)? ";"

datatype: qualified_name ("(" NUMBER ("," NUMBER)? ")")?

exception_section: "EXCEPTION"i exception_handler+
exception_handler: "WHEN"i expression "THEN"i statement*

?statement: assignment_statement
          | if_statement
          | loop_statement
          | null_statement
          | return_statement
          | raise_statement
          | select_statement
          | nested_block
          | call_statement

nested_block: "BEGIN"i statement* exception_section? "END"i ";"

assignment_statement: qualified_name ":=" expression ";"
null_statement: "NULL"i ";"
return_statement: "RETURN"i expression? ";"
raise_statement: "RAISE"i qualified_name? ";"

if_statement: "IF"i expression "THEN"i statement* elsif_clause* else_clause? "END"i "IF"i ";"
elsif_clause: "ELSIF"i expression "THEN"i statement*
else_clause: "ELSE"i statement*

loop_statement: _loop_header? "LOOP"i statement* "END"i "LOOP"i ";"
_loop_header: "WHILE"i expression
            | "FOR"i NAME "IN"i expression ".." expression

call_statement: qualified_name ("(" arguments? ")")? ";"
arguments: expression ("," expression)*

select_statement: "SELECT"i select_item ("," select_item)* "INTO"i qualified_name ("," qualified_name)* "FROM"i table_ref ("," table_ref)* where_clause? ";"
select_item: "*"            -> select_all_columns
           | expression
table_ref: qualified_name NAME?
where_clause: "WHERE"i expression

?expression: or_expr
?or_expr: and_expr ("OR"i and_expr)*
?and_expr: not_expr ("AND"i not_expr)*
?not_expr: "NOT"i not_expr
         | comparison
?comparison: sum
           | sum "=" sum                 -> eq_comparison
           | sum ("<>" | "!=") sum        -> neq_comparison
           | sum ("<=" | ">=" | "<" | ">") sum -> rel_comparison
           | sum "IS"i "NULL"i            -> is_null
           | sum "IS"i "NOT"i "NULL"i     -> is_not_null
?sum: product (("+" | "-") product)*
?product: factor (("*" | "/") factor)*
?factor: "(" expression ")"
       | "NULL"i        -> null_literal
       | NUMBER         -> number_literal
       | STRING         -> string_literal
       | function_call
       | qualified_name

function_call: qualified_name "(" arguments? ")"
qualified_name: NAME ("." NAME)*

NAME: /[A-Za-z][A-Za-z0-9_$#]*/
NUMBER: /\d+(\.\d+)?/
STRING: /'([^']|'')*'/

COMMENT_LINE: /--[^\n]*/
COMMENT_BLOCK: /\/\*([^*]|\*(?!\/))*\*\//

%import common.WS
%ignore WS
%ignore COMMENT_LINE
%ignore COMMENT_BLOCK
"""

# Token types we keep as leaf nodes (others, e.g. punctuation, are anonymous
# and filtered out by Lark already since they are string literals).
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
def _lark() -> Lark:
    return Lark(
        PLSQL_GRAMMAR,
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


# ---------------------------------------------------------------------------
# 9. Walker + scanner
# ---------------------------------------------------------------------------
class Walker:
    """Dispatch each AST node to checks subscribed to its node type."""

    def __init__(self, checks: Iterable[Check]) -> None:
        self._by_type: dict[str, list[Check]] = defaultdict(list)
        for check in checks:
            for node_type in check.subscribed_types:
                self._by_type[node_type].append(check)

    def walk(self, root: AstNode) -> None:
        for node in root.walk():
            for check in self._by_type.get(node.node_type, ()):
                check.visit_node(node)


@dataclass
class ScanResult:
    file: PlSqlFile
    issues: list[Issue] = field(default_factory=list)
    metrics: FileMetrics | None = None
    parse_error: ParseError | None = None

    @property
    def parsed(self) -> bool:
        return self.parse_error is None


class AstScanner:
    """Run a set of checks over PL/SQL files."""

    def __init__(self, checks: list[Check], parser: PlSqlParser | None = None) -> None:
        self._checks = checks
        self._parser = parser or PlSqlParser()

    def scan_file(self, file: PlSqlFile) -> ScanResult:
        parse = self._parser.parse(file.content)

        if not parse.ok or parse.ast is None:
            metrics = compute_metrics(file.content, None, parse.comments)
            return ScanResult(file=file, metrics=metrics, parse_error=parse.error)

        context = ScanContext(file=file, ast=parse.ast, comments=parse.comments)
        issues: list[Issue] = []

        for check in self._checks:
            check.bind(context)
            check.visit_file()
            for comment in parse.comments:
                check.visit_comment(comment)

        Walker(self._checks).walk(parse.ast)

        for check in self._checks:
            check.leave_file()
            issues.extend(check.issues)

        issues.sort(key=lambda i: (i.location.line, i.location.column, i.rule_key))
        metrics = compute_metrics(file.content, parse.ast, parse.comments)
        return ScanResult(file=file, issues=issues, metrics=metrics)


# ---------------------------------------------------------------------------
# 10. Built-in checks
# ---------------------------------------------------------------------------
@rule(
    key="ComparisonWithNull",
    name="Comparisons with NULL should use IS NULL or IS NOT NULL",
    priority="MAJOR",
    tags=("bug", "suspicious"),
    description=(
        "Any comparison with NULL using = or <> evaluates to NULL, never TRUE. "
        "Use IS NULL or IS NOT NULL instead."
    ),
)
class ComparisonWithNullCheck(Check):
    def init(self) -> None:
        self.subscribe_to(NodeType.EQ_COMPARISON, NodeType.NEQ_COMPARISON)

    def visit_node(self, node: AstNode) -> None:
        if node.has_child_of_type(NodeType.NULL_LITERAL):
            self.add_issue(
                node, "Use 'IS NULL' or 'IS NOT NULL' instead of comparing with NULL."
            )


@rule(
    key="SelectAllColumns",
    name="'SELECT *' should not be used",
    priority="MINOR",
    tags=("maintainability",),
    description=(
        "Selecting all columns with '*' is fragile against schema changes and "
        "fetches more data than needed. List the required columns explicitly."
    ),
)
class SelectAllColumnsCheck(Check):
    def init(self) -> None:
        self.subscribe_to(NodeType.SELECT_ALL_COLUMNS)

    def visit_node(self, node: AstNode) -> None:
        self.add_issue(node, "Replace 'SELECT *' with the explicit list of columns.")


_NON_EMPTY_STATEMENTS = STATEMENT_NODE_TYPES - {NodeType.NULL_STATEMENT}


@rule(
    key="EmptyBlock",
    name="Blocks should not be empty",
    priority="MAJOR",
    tags=("suspicious",),
    description=(
        "A block whose body is empty or contains only 'NULL;' usually indicates "
        "missing or dead code."
    ),
)
class EmptyBlockCheck(Check):
    def init(self) -> None:
        self.subscribe_to(NodeType.NESTED_BLOCK)

    def visit_node(self, node: AstNode) -> None:
        has_real_statement = node.has_child_of_type(*_NON_EMPTY_STATEMENTS)
        has_handler = node.has_child_of_type(NodeType.EXCEPTION_SECTION)
        if not has_real_statement and not has_handler:
            self.add_issue(node, "This block is empty or only contains 'NULL;'.")


_TODO_MARKER = re.compile(r"\b(TODO|FIXME)\b", re.IGNORECASE)


@rule(
    key="TodoComment",
    name="'TODO' and 'FIXME' tags should be handled",
    priority="INFO",
    tags=("maintainability",),
    description="TODO/FIXME comments flag work that is not yet complete.",
)
class TodoCommentCheck(Check):
    def visit_comment(self, comment: Comment) -> None:
        match = _TODO_MARKER.search(comment.text)
        if match:
            self.add_line_issue(
                comment.line,
                f"Complete the task associated with this '{match.group(1).upper()}' comment.",
                column=comment.column,
            )


#: All checks shipped in-box.
BUILTIN_CHECKS: tuple[type[Check], ...] = (
    ComparisonWithNullCheck,
    SelectAllColumnsCheck,
    EmptyBlockCheck,
    TodoCommentCheck,
)


# ---------------------------------------------------------------------------
# 11. Registry
# ---------------------------------------------------------------------------
_ENTRY_POINT_GROUP = "pyzpa.checks"


def discover_check_classes() -> list[type[Check]]:
    """Return all known check classes (built-in + entry-points), de-duplicated."""
    classes: list[type[Check]] = list(BUILTIN_CHECKS)
    seen = {c.rule_key for c in classes}

    for ep in _iter_entry_points():
        try:
            obj = ep.load()
        except Exception:  # noqa: BLE001 - a bad plugin must not break the run
            continue
        for cls in _as_check_classes(obj):
            if cls.rule_key not in seen:
                seen.add(cls.rule_key)
                classes.append(cls)
    return classes


def select_checks(
    *,
    only: set[str] | None = None,
    disabled: set[str] | None = None,
) -> list[Check]:
    """Instantiate the checks that should run for this invocation."""
    only = only or set()
    disabled = disabled or set()

    selected: list[Check] = []
    for cls in discover_check_classes():
        key = cls.rule_key
        if only:
            active = key in only
        else:
            active = cls.rule_active_by_default and key not in disabled
        if active:
            selected.append(cls())
    return selected


def _iter_entry_points():
    try:
        eps = metadata.entry_points()
    except Exception:  # noqa: BLE001
        return []
    # importlib.metadata API differs across versions.
    if hasattr(eps, "select"):
        return eps.select(group=_ENTRY_POINT_GROUP)
    return eps.get(_ENTRY_POINT_GROUP, [])  # type: ignore[attr-defined]


def _as_check_classes(obj) -> list[type[Check]]:
    if isinstance(obj, type) and issubclass(obj, Check):
        return [obj]
    if isinstance(obj, (list, tuple)):
        return [c for c in obj if isinstance(c, type) and issubclass(c, Check)]
    return []


# ---------------------------------------------------------------------------
# 12. Analyzer facade
# ---------------------------------------------------------------------------
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
        Pre-built :class:`Check` instances to run instead of the discovered set.
    fail_on:
        Minimum severity that :meth:`has_failures` treats as a failure.
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
        """Analyze files and/or directories (directories are searched recursively)."""
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
        """Render results as ``text``, ``json``, ``csv``, or ``sarif``."""
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


# ---------------------------------------------------------------------------
# 13. Report writers
# ---------------------------------------------------------------------------
_TEXT_HEADERS = ("Error", "Timestamp", "Severity", "Description")


def write_text(results: Iterable[ScanResult]) -> str:
    results = list(results)
    timestamp = datetime.now().isoformat(timespec="seconds")

    rows: list[tuple[str, str, str, str]] = []
    total_issues = 0
    files_with_errors = 0

    for result in results:
        if result.parse_error is not None:
            files_with_errors += 1
            err = result.parse_error
            rows.append(
                (
                    f"{result.file.path}:{err.line}:{err.column}",
                    timestamp,
                    "PARSE",
                    err.message,
                )
            )
            continue

        for issue in result.issues:
            total_issues += 1
            loc = issue.location
            rows.append(
                (
                    f"{result.file.path}:{loc.line}:{loc.column} "
                    f"[{issue.rule_key}]",
                    timestamp,
                    Severity(issue.severity).name,
                    issue.message,
                )
            )

    lines = _render_table(rows)
    lines.append("")
    summary = f"{total_issues} issue(s) in {len(results)} file(s)"
    if files_with_errors:
        summary += f", {files_with_errors} file(s) with parse errors"
    lines.append(summary)
    return "\n".join(lines)


def _render_table(rows: list[tuple[str, str, str, str]]) -> list[str]:
    """Render aligned, pipe-delimited columns with a header."""
    widths = [len(h) for h in _TEXT_HEADERS]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def format_row(cells: tuple[str, ...]) -> str:
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    lines = [format_row(_TEXT_HEADERS)]
    lines.append("-+-".join("-" * w for w in widths))
    lines.extend(format_row(row) for row in rows)
    return lines


def write_json(results: Iterable[ScanResult]) -> str:
    payload = {"files": [_json_file_entry(r) for r in results]}
    return json.dumps(payload, indent=2)


def _json_file_entry(result: ScanResult) -> dict:
    entry: dict = {
        "path": result.file.path,
        "parsed": result.parsed,
        "issues": [_json_issue_entry(i) for i in result.issues],
    }
    if result.metrics is not None:
        m = result.metrics
        entry["metrics"] = {
            "lines": m.lines,
            "commentLines": m.comment_lines,
            "statements": m.statements,
            "complexity": m.complexity,
        }
    if result.parse_error is not None:
        err = result.parse_error
        entry["parseError"] = {
            "message": err.message,
            "line": err.line,
            "column": err.column,
        }
    return entry


def _json_issue_entry(issue) -> dict:
    loc = issue.location
    return {
        "ruleKey": issue.rule_key,
        "severity": Severity(issue.severity).name,
        "message": issue.message,
        "line": loc.line,
        "column": loc.column,
        "endLine": loc.end_line,
        "endColumn": loc.end_column,
    }


_CSV_HEADERS = (
    "File",
    "Line",
    "Column",
    "End Line",
    "End Column",
    "Severity",
    "Rule",
    "Message",
)


def write_csv(results: Iterable[ScanResult]) -> str:
    buffer = io.StringIO()
    # Lead with a UTF-8 BOM so Excel opens the file with the correct
    # encoding and renders accented characters on double-click.
    buffer.write("\ufeff")
    # QUOTE_MINIMAL keeps the file compact; the csv module handles
    # embedded commas, quotes and newlines in messages safely.
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_HEADERS)

    for result in results:
        path = result.file.path

        if result.parse_error is not None:
            err = result.parse_error
            writer.writerow(
                [path, err.line, err.column, "", "", "PARSE_ERROR", "", err.message]
            )
            continue

        for issue in result.issues:
            loc = issue.location
            writer.writerow(
                [
                    path,
                    loc.line,
                    loc.column,
                    loc.end_line if loc.end_line is not None else "",
                    loc.end_column if loc.end_column is not None else "",
                    Severity(issue.severity).name,
                    issue.rule_key,
                    issue.message,
                ]
            )

    return buffer.getvalue()


_SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

# Map our severities onto SARIF result levels.
_SARIF_LEVEL = {
    Severity.INFO: "note",
    Severity.MINOR: "warning",
    Severity.MAJOR: "warning",
    Severity.CRITICAL: "error",
    Severity.BLOCKER: "error",
}


def write_sarif(results: Iterable[ScanResult]) -> str:
    results = list(results)
    rules, rule_index = _sarif_rules()

    sarif_results = []
    for result in results:
        uri = result.file.path.replace("\\", "/")
        for issue in result.issues:
            sarif_results.append(_sarif_result_entry(issue, uri, rule_index))

    log = {
        "version": "2.1.0",
        "$schema": _SARIF_SCHEMA,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "pyzpa",
                        "informationUri": "https://github.com/pyzpa/pyzpa",
                        "version": __version__,
                        "rules": rules,
                    }
                },
                "results": sarif_results,
            }
        ],
    }
    return json.dumps(log, indent=2)


def _sarif_rules() -> tuple[list[dict], dict[str, int]]:
    rules: list[dict] = []
    index: dict[str, int] = {}
    for cls in discover_check_classes():
        index[cls.rule_key] = len(rules)
        rules.append(
            {
                "id": cls.rule_key,
                "name": cls.rule_key,
                "shortDescription": {"text": cls.rule_name},
                "fullDescription": {"text": cls.rule_description or cls.rule_name},
                "defaultConfiguration": {
                    "level": _SARIF_LEVEL.get(cls.rule_priority, "warning")
                },
                "properties": {"tags": list(cls.rule_tags)},
            }
        )
    return rules, index


def _sarif_result_entry(issue, uri: str, rule_index: dict[str, int]) -> dict:
    loc = issue.location
    entry = {
        "ruleId": issue.rule_key,
        "level": _SARIF_LEVEL.get(Severity(issue.severity), "warning"),
        "message": {"text": issue.message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": uri},
                    "region": {
                        "startLine": max(loc.line, 1),
                        "startColumn": loc.column + 1,
                    },
                }
            }
        ],
    }
    if issue.rule_key in rule_index:
        entry["ruleIndex"] = rule_index[issue.rule_key]
    region = entry["locations"][0]["physicalLocation"]["region"]
    if loc.end_line:
        region["endLine"] = loc.end_line
        region["endColumn"] = loc.end_column + 1
    return entry


WRITERS = {
    "text": write_text,
    "json": write_json,
    "csv": write_csv,
    "sarif": write_sarif,
}


# ---------------------------------------------------------------------------
# 14. CLI
# ---------------------------------------------------------------------------
EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_PARSE = 3

#: File extension used for each report format when auto-naming output files.
_FORMAT_EXTENSIONS = {
    "text": "txt",
    "json": "json",
    "csv": "csv",
    "sarif": "sarif",
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USAGE
    return args.func(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pyzpa", description="PL/SQL static analyzer.")
    parser.add_argument("--version", action="version", version=f"pyzpa {__version__}")
    sub = parser.add_subparsers(dest="command")

    scan = sub.add_parser("scan", help="Analyse files and report issues.")
    scan.add_argument("paths", nargs="+", help="Files or directories to scan.")
    scan.add_argument(
        "--format",
        choices=("text", "json", "csv", "sarif"),
        default="csv",
        help="Output format (default: csv).",
    )
    scan.add_argument(
        "--output",
        "-o",
        help=(
            "Write the report to this file. Use '-' for stdout. When omitted, "
            "a timestamped file named report_<YYYYMMDDHHMMSS>.<ext> is created."
        ),
    )
    scan.add_argument(
        "--checks",
        help="Comma-separated rule keys to run exclusively.",
    )
    scan.add_argument(
        "--disable",
        help="Comma-separated rule keys to disable.",
    )
    scan.add_argument(
        "--fail-on",
        default="MINOR",
        help="Minimum severity that causes a non-zero exit (default: MINOR).",
    )
    scan.add_argument(
        "--strict",
        action="store_true",
        help="Treat parse errors as a failure (exit code 3).",
    )
    scan.add_argument("--encoding", default="utf-8", help="Source file encoding.")
    scan.set_defaults(func=_cmd_scan)

    listing = sub.add_parser("list-checks", help="List available checks.")
    listing.add_argument(
        "--format", choices=("text", "json"), default="text", help="Output format."
    )
    listing.set_defaults(func=_cmd_list_checks)

    parse_cmd = sub.add_parser("parse", help="Parse one file and print its AST.")
    parse_cmd.add_argument("path", help="File to parse.")
    parse_cmd.add_argument("--encoding", default="utf-8", help="Source file encoding.")
    parse_cmd.set_defaults(func=_cmd_parse)

    return parser


# -- commands ------------------------------------------------------------
def _cmd_scan(args: argparse.Namespace) -> int:
    if not _valid_severity(args.fail_on):
        print(f"pyzpa: unknown severity '{args.fail_on}'", file=sys.stderr)
        return EXIT_USAGE

    analyzer = PlSqlAnalyzer(
        checks=_split_keys(args.checks) or None,
        disabled=_split_keys(args.disable) or None,
        fail_on=args.fail_on,
        encoding=args.encoding,
    )

    try:
        files = analyzer.collect_files(args.paths)
    except OSError as exc:
        print(f"pyzpa: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if not files:
        print("pyzpa: no input files found", file=sys.stderr)
        return EXIT_USAGE

    results = analyzer.analyze_files(files)

    report = analyzer.format(results, args.format)
    _emit(report, args.output, args.format)

    if args.strict and any(r.parse_error is not None for r in results):
        return EXIT_PARSE
    return EXIT_FINDINGS if analyzer.has_failures(results) else EXIT_OK


def _cmd_list_checks(args: argparse.Namespace) -> int:
    classes = sorted(discover_check_classes(), key=lambda c: c.rule_key)
    if args.format == "json":
        payload = [
            {
                "key": c.rule_key,
                "name": c.rule_name,
                "severity": c.rule_priority.name,
                "activeByDefault": c.rule_active_by_default,
                "tags": list(c.rule_tags),
            }
            for c in classes
        ]
        print(json.dumps(payload, indent=2))
        return EXIT_OK

    for c in classes:
        flag = "on " if c.rule_active_by_default else "off"
        print(f"[{flag}] {c.rule_key:<24} {c.rule_priority.name:<9} {c.rule_name}")
    print(f"\n{len(classes)} check(s)")
    return EXIT_OK


def _cmd_parse(args: argparse.Namespace) -> int:
    try:
        file = PlSqlFile.from_path(args.path, encoding=args.encoding)
    except OSError as exc:
        print(f"pyzpa: {exc}", file=sys.stderr)
        return EXIT_USAGE

    result = PlSqlParser().parse(file.content)
    if not result.ok or result.ast is None:
        err = result.error
        loc = f"{err.line}:{err.column}" if err else "?"
        print(
            f"parse error at {loc}: {err.message if err else 'unknown'}",
            file=sys.stderr,
        )
        return EXIT_PARSE

    print(result.ast.pretty())
    return EXIT_OK


# -- helpers -------------------------------------------------------------
def _valid_severity(name: str) -> bool:
    try:
        Severity.from_name(name)
    except KeyError:
        return False
    return True


def _split_keys(value: str | None) -> set[str]:
    if not value:
        return set()
    return {k.strip() for k in value.split(",") if k.strip()}


def _emit(report: str, output: str | None, fmt: str) -> None:
    if output == "-":
        print(report)
        return
    target = Path(output) if output else _default_report_path(fmt)
    target.write_text(report + "\n", encoding="utf-8")
    print(f"pyzpa: report written to {target}")


def _default_report_path(fmt: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    ext = _FORMAT_EXTENSIONS.get(fmt, "txt")
    return Path(f"report_{timestamp}.{ext}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
