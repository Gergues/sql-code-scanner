"""Starter example: using pyzpa as a library.

Run it directly:

    python examples/basic_usage.py

It demonstrates the most common entry points of the :class:`pyzpa.PlSqlAnalyzer`
facade: analysing an in-memory string, scanning files/directories, selecting and
disabling checks, gating on severity, rendering reports, and adding a custom check.
"""

from __future__ import annotations

from pyzpa import Check, NodeType, PlSqlAnalyzer, Severity, rule

# A small PL/SQL snippet with a few intentional problems.
SAMPLE_PLSQL = """\
BEGIN
  IF v_status = NULL THEN          -- ComparisonWithNull (MAJOR)
    SELECT * INTO v_row            -- SelectAllColumns (MINOR)
      FROM employees
     WHERE id = 1;
  END IF;

  BEGIN                            -- EmptyBlock (MAJOR)
    NULL;
  END;

  -- TODO: handle the error case   -- TodoComment (INFO)
  do_work();
END;
"""


def analyze_a_string() -> None:
    """Analyze an in-memory string and print each finding."""
    print("=== analyze_source ===")
    analyzer = PlSqlAnalyzer()  # all default-active checks
    result = analyzer.analyze_source(SAMPLE_PLSQL, path="sample.sql")

    if result.parse_error is not None:
        print(f"  parse error: {result.parse_error.message}")
        return

    for issue in result.issues:
        loc = issue.location
        print(
            f"  {loc.line:>3}:{loc.column:<3} "
            f"{issue.severity.name:<8} [{issue.rule_key}] {issue.message}"
        )

    if result.metrics is not None:
        m = result.metrics
        print(
            f"  metrics: {m.lines} lines, {m.statements} statements, "
            f"complexity {m.complexity}"
        )


def select_specific_checks() -> None:
    """Run only a chosen subset of checks."""
    print("\n=== checks=['SelectAllColumns'] ===")
    analyzer = PlSqlAnalyzer(checks=["SelectAllColumns"])
    result = analyzer.analyze_source(SAMPLE_PLSQL)
    print(f"  active checks: {[c.rule_key for c in analyzer.checks]}")
    print(f"  issues found:  {[i.rule_key for i in result.issues]}")


def gate_on_severity() -> None:
    """Use has_failures() to decide pass/fail for a build."""
    print("\n=== fail_on threshold ===")
    results = [PlSqlAnalyzer().analyze_source(SAMPLE_PLSQL)]

    strict = PlSqlAnalyzer(fail_on=Severity.MINOR)
    lenient = PlSqlAnalyzer(fail_on=Severity.BLOCKER)
    print(f"  fail_on=MINOR   -> failing: {strict.has_failures(results)}")
    print(f"  fail_on=BLOCKER -> failing: {lenient.has_failures(results)}")


def render_reports() -> None:
    """Render the same results as text, JSON, and SARIF."""
    print("\n=== report formats ===")
    analyzer = PlSqlAnalyzer()
    results = [analyzer.analyze_source(SAMPLE_PLSQL, path="sample.sql")]
    for fmt in ("text", "json", "sarif"):
        report = analyzer.format(results, fmt)
        print(f"  --- {fmt} ({len(report)} chars) ---")
    # Show the text report in full as the most readable one.
    print(analyzer.format(results, "text"))


def add_a_custom_check() -> None:
    """Inject a project-specific check without packaging it."""
    print("\n=== custom check ===")

    @rule(
        key="BareRaise",
        name="RAISE should name an exception",
        priority="MAJOR",
        tags=("error-handling",),
    )
    class BareRaiseCheck(Check):
        def init(self) -> None:
            self.subscribe_to(NodeType.RAISE_STATEMENT)

        def visit_node(self, node) -> None:
            # A bare ``RAISE;`` has no qualified_name child.
            if not node.children:
                self.add_issue(node, "RAISE should specify an exception name.")

    analyzer = PlSqlAnalyzer(check_instances=[BareRaiseCheck()])
    result = analyzer.analyze_source(
        "BEGIN\n  RAISE;\nEXCEPTION WHEN OTHERS THEN RAISE;\nEND;\n"
    )
    for issue in result.issues:
        print(f"  line {issue.location.line}: [{issue.rule_key}] {issue.message}")


def main() -> None:
    analyze_a_string()
    select_specific_checks()
    gate_on_severity()
    render_reports()
    add_a_custom_check()


if __name__ == "__main__":
    main()


# Expected output:
#
# === analyze_source ===
#     2:5   MAJOR    [ComparisonWithNull] Use 'IS NULL' or 'IS NOT NULL' instead of comparing with NULL.
#     3:11  MINOR    [SelectAllColumns] Replace 'SELECT *' with the explicit list of columns.
#     8:2   MAJOR    [EmptyBlock] This block is empty or only contains 'NULL;'.
#    12:2   INFO     [TodoComment] Complete the task associated with this 'TODO' comment.
#   metrics: 15 lines, 5 statements, complexity 2
#
# === checks=['SelectAllColumns'] ===
#   active checks: ['SelectAllColumns']
#   issues found:  ['SelectAllColumns']
#
# === fail_on threshold ===
#   fail_on=MINOR   -> failing: True
#   fail_on=BLOCKER -> failing: False
#
# === report formats ===
#   --- text (828 chars) ---
#   --- json (1285 chars) ---
#   --- sarif (5250 chars) ---
# Error                               | Timestamp           | Severity | Description
# ------------------------------------+---------------------+----------+---------------------------------------------------------------
# sample.sql:2:5 [ComparisonWithNull] | 2026-06-24T10:10:46 | MAJOR    | Use 'IS NULL' or 'IS NOT NULL' instead of comparing with NULL.
# sample.sql:3:11 [SelectAllColumns]  | 2026-06-24T10:10:46 | MINOR    | Replace 'SELECT *' with the explicit list of columns.
# sample.sql:8:2 [EmptyBlock]         | 2026-06-24T10:10:46 | MAJOR    | This block is empty or only contains 'NULL;'.
# sample.sql:12:2 [TodoComment]       | 2026-06-24T10:10:46 | INFO     | Complete the task associated with this 'TODO' comment.
#
# 4 issue(s) in 1 file(s)
#
# === custom check ===
#   line 2: [BareRaise] RAISE should specify an exception name.
#   line 3: [BareRaise] RAISE should specify an exception name.
