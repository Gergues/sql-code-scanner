# pyzpa — Getting Started & Developer Guide

**Python-based Z PL/SQL Analyzer.** A minimal Python static analyzer for Oracle
PL/SQL. This guide covers environment setup, installation, running the CLI,
testing, and adding new checks.

> A large portion of this application's logic was ported from the
> [ZPA project](https://github.com/felipebz/zpa) by Felipe Zorzo.

> Status: MVP scaffold. Parser is a Lark-based PL/SQL **subset** — enough to drive
> the starter checks, not full Oracle PL/SQL coverage.

---

## 1. Prerequisites

- Python **3.11+**
- Windows PowerShell (`pwsh`) — commands below use it; bash equivalents noted where relevant.

Check your version:

```pwsh
python --version
```

---

## 2. Create and activate a virtual environment

> Note: `python venv create ./venv` is **not** valid. The module is invoked with
> `python -m venv` and the target directory is the only argument.

```pwsh
cd c:\V-Machines\common-disk\sql-code-scanner\pyzpa

# Create the venv
python -m venv .venv

# Activate it (PowerShell)
.\.venv\Scripts\Activate.ps1
```

If activation is blocked by execution policy, allow it for the current session:

```pwsh
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Other shells:

```bash
# cmd.exe
.venv\Scripts\activate.bat
# bash / WSL
source .venv/bin/activate
```

Deactivate any time with `deactivate`.

---

## 3. Install the package

Editable install with development extras (pytest, ruff):

```pwsh
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

This installs the runtime dependency (`lark`) and registers the `pyzpa` console
script defined in [pyproject.toml](../pyproject.toml).

---

## 4. Verify the install

```pwsh
pyzpa --version
pyzpa list-checks
pyzpa parse tests/fixtures/empty_block.sql
pyzpa scan tests/fixtures --format text
```

Run the test suite:

```pwsh
pytest
```

---

## 5. CLI reference

```
pyzpa <command> [options]
```

| Command        | Purpose                                              |
| -------------- | ---------------------------------------------------- |
| `scan`         | Analyse files/directories and report issues.         |
| `list-checks`  | List available checks and default activation state.  |
| `parse`        | Parse one file and print its AST (debugging).        |

### `scan` options

| Option             | Default  | Description                                            |
| ------------------ | -------- | ----------------------------------------------------- |
| `paths` (positional) | —      | One or more files or directories to scan.             |
| `--format`         | `text`   | Output format: `text`, `json`, or `sarif`.            |
| `--output, -o`     | stdout   | Write the report to a file instead of stdout.         |
| `--checks`         | —        | Comma-separated rule keys to run **exclusively**.     |
| `--disable`        | —        | Comma-separated rule keys to disable.                 |
| `--fail-on`        | `MINOR`  | Minimum severity that triggers a non-zero exit.       |
| `--strict`         | off      | Treat parse errors as a failure (exit code 3).        |
| `--encoding`       | `utf-8`  | Source file encoding.                                 |

### Exit codes

| Code | Meaning                                            |
| ---- | -------------------------------------------------- |
| `0`  | Success, no findings at or above `--fail-on`.      |
| `1`  | Findings at or above `--fail-on` were reported.    |
| `2`  | Usage / I/O error.                                 |
| `3`  | Parse error (during `parse`, or `scan --strict`).  |

### Examples

```pwsh
# Scan a folder, fail the build only on MAJOR+ issues
pyzpa scan src\plsql --fail-on MAJOR

# Run a single rule and emit SARIF for CI annotations
pyzpa scan src\plsql --checks SelectAllColumns --format sarif -o pyzpa.sarif

# Everything except the TODO rule, as JSON
pyzpa scan src\plsql --disable TodoComment --format json
```

---

## 6. Project layout

```
pyzpa/
  pyproject.toml          # build config, deps, console script, check entry-point
  README.md
  pyzpa/
    __init__.py           # __version__
    cli.py                # argparse CLI: scan / list-checks / parse
    registry.py           # builtin + entry-point check discovery & selection
    api/                  # public surface for check authors
      check.py            #   Check base class (subscribe + visitor hooks)
      decorators.py       #   @rule metadata decorator
      issue.py            #   Issue, IssueLocation, Severity
      nodes.py            #   NodeType constants + statement/complexity sets
    ast/nodes.py          # generic AstNode tree + navigation helpers
    grammar/plsql.lark    # PL/SQL subset grammar (Earley, propagate_positions)
    parser/               # PlSqlParser, ast_builder, comment extraction
    analysis/             # PlSqlFile, ScanContext, Walker, metrics, AstScanner
    checks/               # built-in checks
    report/               # text / json / sarif writers
  tests/
    verifier.py           # `-- Noncompliant` annotation verifier
    fixtures/*.sql
    test_checks.py, test_parser.py, test_cli.py
```

---

## 7. Built-in checks

| Rule key             | Severity | What it flags                                              |
| -------------------- | -------- | ---------------------------------------------------------- |
| `ComparisonWithNull` | MAJOR    | `=` / `<>` comparisons against `NULL` (use `IS [NOT] NULL`). |
| `SelectAllColumns`   | MINOR    | `SELECT *` usage.                                          |
| `EmptyBlock`         | MAJOR    | Blocks that are empty or contain only `NULL;`.             |
| `TodoComment`        | INFO     | `TODO` / `FIXME` markers in comments.                      |

---

## 8. Adding a new check

1. Create a module under [pyzpa/checks/](../pyzpa/checks/).
2. Subclass `Check`, decorate it with `@rule`, subscribe to node types in `init`,
   and report issues from `visit_node` (or `visit_comment` for comment-based rules).

```python
from pyzpa.api import Check, NodeType, rule
from pyzpa.ast.nodes import AstNode


@rule(
    key="NoDeadLoop",
    name="Loops should be able to terminate",
    priority="MAJOR",
    tags=("suspicious",),
)
class NoDeadLoopCheck(Check):
    def init(self) -> None:
        self.subscribe_to(NodeType.LOOP_STATEMENT)

    def visit_node(self, node: AstNode) -> None:
        # ...your logic...
        self.add_issue(node, "This loop may never terminate.")
```

3. Register it in [pyzpa/checks/__init__.py](../pyzpa/checks/__init__.py) by adding
   the class to `BUILTIN_CHECKS`.
4. Add a fixture in `tests/fixtures/` using `-- Noncompliant` on each expected line,
   and a parametrized entry in [tests/test_checks.py](../tests/test_checks.py).

### Third-party check packages

External packages can ship checks without modifying pyzpa by advertising the
`pyzpa.checks` entry-point group:

```toml
[project.entry-points."pyzpa.checks"]
my_rules = "my_company.rules:CHECKS"   # CHECKS = a list of Check subclasses
```

`registry.discover_check_classes()` loads them automatically.

---

## 9. Testing model

The verifier in [tests/verifier.py](../tests/verifier.py) mirrors ZPA's
check-verifier idea: a line containing `-- Noncompliant` marks where an issue is
expected. `verify(check, source)` asserts the reported lines match the annotations
exactly (no missing, no unexpected).

```pwsh
pytest                      # run everything
pytest tests/test_checks.py # one module
pytest -k Null              # by keyword
```

---

## 10. Known limitations

- The grammar is a deliberate **subset** of PL/SQL; complex/real-world packages may
  produce parse errors. Use `--strict` to surface them, or omit it to skip
  unparseable files.
- No SonarQube integration, syntax highlighting, CPD, or utPLSQL support (out of MVP scope).
- The Earley dynamic lexer can be sensitive to keyword-vs-identifier overlap (e.g.
  `NULL`); if a fixture fails to parse, that is the first place to investigate.
