# pyzpa

**Python-based Z PL/SQL Analyzer** — a minimal, pure-Python static analyzer for
**Oracle PL/SQL**. It parses PL/SQL with [Lark](https://github.com/lark-parser/lark),
runs a small set of coding checks over the resulting AST, and reports findings
through a CLI.

> A large portion of this application's logic was ported from the
> [ZPA project](https://github.com/felipebz/zpa) by Felipe Zorzo.

This is an **MVP**. It deliberately excludes SonarQube integration, syntax
highlighting, copy/paste detection, utPLSQL import, and the desktop toolkit.
See the design notes in
[`code_builder/architecture/08-python-mvp.md`](../code_builder/architecture/08-python-mvp.md).

## Install (editable, for development)

```pwsh
cd pyzpa
python -m pip install -e ".[dev]"
```

## Use as a library

`pyzpa` is importable in-process — no CLI or subprocess required. The
`PlSqlAnalyzer` facade is the entry point:

```python
from pyzpa import PlSqlAnalyzer

analyzer = PlSqlAnalyzer()                       # all default-active checks

# Analyze an in-memory string
result = analyzer.analyze_source("BEGIN\n  IF x = NULL THEN NULL; END IF;\nEND;\n")
for issue in result.issues:
    print(issue.rule_key, issue.location.line, issue.message)

# Analyze files / directories (directories searched recursively)
results = analyzer.analyze_paths(["src/plsql"])
print(analyzer.format(results, "json"))          # text | json | sarif

# Gate a build on severity
if analyzer.has_failures(results):               # honours fail_on
    raise SystemExit("PL/SQL issues found")
```

Configure check selection and the failure threshold at construction time:

```python
from pyzpa import PlSqlAnalyzer, Severity

analyzer = PlSqlAnalyzer(
    checks=["ComparisonWithNull", "SelectAllColumns"],  # run these only
    # disabled=["TodoComment"],                          # or subtract from defaults
    fail_on=Severity.MAJOR,
)
```

Inject custom checks programmatically (no entry-point packaging needed):

```python
from pyzpa import Check, NodeType, PlSqlAnalyzer, rule
from pyzpa.checks import BUILTIN_CHECKS


@rule(key="NoRaiseWithoutArg", name="RAISE should name an exception", priority="MAJOR")
class NoBareRaise(Check):
    def init(self):
        self.subscribe_to(NodeType.RAISE_STATEMENT)

    def visit_node(self, node):
        if not node.children:
            self.add_issue(node, "RAISE should specify an exception.")


analyzer = PlSqlAnalyzer(check_instances=[c() for c in BUILTIN_CHECKS] + [NoBareRaise()])
```

Key exports from the top-level package: `PlSqlAnalyzer` (alias `Analyzer`),
`ScanResult`, `PlSqlFile`, `FileMetrics`, `AstScanner`, and the check-author API
`Check`, `rule`, `Issue`, `IssueLocation`, `Severity`, `NodeType`.

## Use from the command line

```pwsh
# Analyze files / directories
pyzpa scan path\to\code --format text

# List available checks
pyzpa list-checks

# Print the AST for a single file (debugging aid)
pyzpa parse path\to\file.sql --tree
```

### Common options for `scan`

| Option | Description | Default |
|--------|-------------|---------|
| `--format {text,json,sarif}` | Output format | `text` |
| `--output PATH` | Write report to a file instead of stdout | stdout |
| `--checks LIST` | Comma-separated check keys to run | all active-by-default |
| `--disable LIST` | Check keys to disable | none |
| `--include GLOB` | File globs to include | `**/*.sql,**/*.pkb,**/*.pks,**/*.pkg` |
| `--exclude GLOB` | File globs to skip | none |
| `--strict` | Fail a file on parse error (default tolerant) | tolerant |
| `--fail-on LEVEL` | Min severity that yields a non-zero exit code | `major` |

## Layout

```
pyzpa/
├── api/          # stable surface for check authors (Check, Issue, @rule, NodeType)
├── grammar/      # plsql.lark grammar (subset)
├── parser/       # Lark parser + AST builder
├── ast/          # internal AST node
├── analysis/     # scanner, walker, symbols, metrics
├── checks/       # built-in checks
├── report/       # text / json / sarif writers
├── registry.py   # check discovery & selection
├── analyzer.py   # PlSqlAnalyzer facade (library entry point)
└── cli.py        # command-line entry point (thin wrapper over the facade)
```

## Status

MVP scaffold — see the milestone plan in the design note. Current built-in
checks: comparison-with-null, select-all-columns, empty-block, TODO/FIXME
comments.
