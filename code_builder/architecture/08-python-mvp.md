# pyzpa — Python MVP Specification

> MVP spec for a minimal Python port of the ZPA engine. Scope is deliberately narrow: parse Oracle PL/SQL with **Lark**, run a small set of checks, and report findings via a **CLI**. SonarQube integration, highlighting, CPD, utPLSQL import, and the desktop toolkit are **out of scope**.
>
> Related design notes: [00-master-system-design.md](00-master-system-design.md), [01-zpa-core.md](01-zpa-core.md), [07-python-port-feasibility.md](07-python-port-feasibility.md). Target output location: `/pyzpa`.

## 1. Goal

Deliver a standalone, pure-Python static analyzer for Oracle PL/SQL that:

1. Parses PL/SQL source into an AST using **Lark** (PyPI) instead of FLR/SSLR.
2. Runs a small, extensible set of **checks** over the AST.
3. Is driven by a **CLI** for input selection, output format, and which checks/modules run.

The MVP proves the pipeline end-to-end on a useful rule subset. It is not feature-parity with the Kotlin engine.

## 2. In scope vs. out of scope

| In scope (MVP) | Out of scope (later / never) |
|----------------|------------------------------|
| Lark-based lexer+parser for a PL/SQL subset | Full Oracle PL/SQL grammar coverage |
| AST + lightweight visitor framework | Reflection-based typed-tree (`SemanticAstNode`) |
| Symbol table — minimal (declarations + scopes) | Full type solver across 13 datatypes |
| ~6–10 starter checks | All ~52 built-in rules |
| Cyclomatic complexity + basic metrics (LOC, statements) | Per-function metric exports to a host |
| CLI: input, output format, check selection | SonarQube plugin, highlighting, CPD, utPLSQL |
| Text + JSON + SARIF output | Generic Issue Import wiring into a server |
| Rule metadata via decorators | HTML rule docs pipeline |

## 3. Technology choices

- **Language/runtime:** Python ≥ 3.11.
- **Parser:** `lark` (PyPI). Use the **Earley** parser initially for grammar flexibility on the ambiguous PL/SQL dialect; revisit **LALR** later for speed once the grammar stabilizes.
- **CLI:** `argparse` (stdlib) for zero extra deps, or `typer`/`click` if richer UX is wanted. MVP default: `argparse`.
- **Packaging:** `pyproject.toml` (PEP 621), entry-point script `pyzpa`.
- **Testing:** `pytest`, reusing a `-- Noncompliant` verifier pattern adapted from `zpa-checks-testkit`.
- **Lint/format:** `ruff` + `ruff format` (optional but recommended).

## 4. Parsing approach with Lark

- Grammar lives in `pyzpa/grammar/plsql.lark` (EBNF). Start from a **subset** sufficient for the starter checks: anonymous blocks, `CREATE PROCEDURE/FUNCTION/PACKAGE`, `DECLARE` sections, `IF/LOOP/WHILE/FOR`, assignments, `SELECT/INSERT/UPDATE/DELETE`, expressions, comparisons, `NULL`.
- Case-insensitive keywords; preserve comments as Lark tokens (needed for NOSONAR-style handling later, optional in MVP).
- Use a Lark `Transformer`/`Visitor` to convert the parse tree into a stable internal AST (`pyzpa/ast/nodes.py`) so checks aren't coupled to Lark tree shapes.
- **Error handling:** configurable `--error-recovery` (tolerant) vs strict (fail file). MVP may start strict and add `on_error` recovery later.

> Tradeoff: Lark Earley handles grammar ambiguity well but is slower than the JVM engine. Acceptable for an MVP; performance is a later concern (LALR, caching, or native parser).

## 5. Module layout (`/pyzpa`)

```
pyzpa/
├── pyproject.toml              # PEP 621 metadata; [project.scripts] pyzpa = "pyzpa.cli:main"
├── README.md
├── pyzpa/
│   ├── __init__.py
│   ├── cli.py                  # argument parsing, orchestration, exit codes
│   ├── api/                    # stable surface for check authors
│   │   ├── __init__.py
│   │   ├── check.py            # Check base class (subscribe_to, visit_node, add_issue)
│   │   ├── issue.py            # Issue, IssueLocation, Severity
│   │   ├── decorators.py       # @rule(key, name, priority, remediation, active_by_default, tags)
│   │   └── nodes.py            # NodeType constants (grammar rule names) checks subscribe to
│   ├── grammar/
│   │   └── plsql.lark          # Lark grammar (subset)
│   ├── parser/
│   │   ├── parser.py           # build Lark parser; parse(text) -> ParseTree
│   │   └── ast_builder.py      # Lark Transformer -> internal AST
│   ├── ast/
│   │   └── nodes.py            # AstNode + typed node dataclasses
│   ├── analysis/
│   │   ├── scanner.py          # AstScanner.scan_file(file) -> ScanResult
│   │   ├── walker.py           # depth-first dispatch to subscribed checks
│   │   ├── symbols.py          # minimal symbol table (Symbol, Scope)
│   │   └── metrics.py          # LOC, statements, cyclomatic complexity
│   ├── checks/
│   │   ├── __init__.py         # registry of built-in checks
│   │   ├── comparison_with_null.py
│   │   ├── select_all_columns.py
│   │   ├── empty_block.py
│   │   ├── unused_variable.py
│   │   └── ...                 # ~6–10 starter checks
│   ├── report/
│   │   ├── text_writer.py      # human-readable console output
│   │   ├── json_writer.py      # machine-readable findings
│   │   └── sarif_writer.py     # SARIF 2.1.0
│   └── registry.py             # discover/select checks (built-in + entry-points)
└── tests/
    ├── verifier.py             # PlSqlCheckVerifier equivalent (-- Noncompliant)
    ├── fixtures/*.sql
    └── test_*.py
```

## 6. CLI specification

Console entry point: `pyzpa`.

```
pyzpa scan [PATHS...] [options]
```

| Option | Description | Default |
|--------|-------------|---------|
| `PATHS...` | Files or directories to analyze | required |
| `--include GLOB` | Glob(s) of files to include | `**/*.sql,**/*.pkb,**/*.pks,**/*.pkg` |
| `--exclude GLOB` | Glob(s) to skip | none |
| `--format {text,json,sarif}` | Output format | `text` |
| `--output PATH` | Write report to file (else stdout) | stdout |
| `--checks LIST` | Comma-separated check keys to run | all active-by-default |
| `--disable LIST` | Check keys to disable | none |
| `--list-checks` | Print available checks and exit | — |
| `--error-recovery / --strict` | Tolerant vs fail-fast parsing | tolerant |
| `--encoding NAME` | Source charset | `utf-8` |
| `--fail-on {none,info,minor,major,critical,blocker}` | Min severity that yields non-zero exit | `major` |
| `-v, --verbose` | Verbose logging | off |

**Auxiliary commands (MVP-minimal):**
- `pyzpa scan` — analyze and report (primary).
- `pyzpa list-checks` — enumerate checks with key, name, severity, default state.
- `pyzpa parse FILE [--tree]` — debugging aid: print the AST for one file.

**Exit codes:** `0` = no findings at/above `--fail-on`; `1` = findings at/above threshold; `2` = usage/IO error; `3` = parse error in strict mode.

## 7. Check authoring model

Checks mirror the Kotlin pattern (subscribe to node types, visit, emit issues) but use Python decorators for metadata:

```python
from pyzpa.api.check import Check
from pyzpa.api.decorators import rule
from pyzpa.api.nodes import NodeType

@rule(
    key="ComparisonWithNull",
    name="Comparison with NULL using = / !=",
    priority="MAJOR",
    remediation="5min",
    active_by_default=True,
    tags=["bug"],
)
class ComparisonWithNullCheck(Check):
    def init(self):
        self.subscribe_to(NodeType.RELATIONAL_EXPRESSION)

    def visit_node(self, node):
        if node.uses_equality_with_null():
            self.add_issue(node, 'Use "IS NULL" / "IS NOT NULL" instead.')
```

- **Discovery:** built-in checks registered in `pyzpa/checks/__init__.py`; third-party checks discoverable later via entry-points group `pyzpa.checks` (post-MVP hook, design now).
- **Selection:** `registry.py` resolves `--checks` / `--disable` / active-by-default into the active set passed to the scanner.

## 8. Analysis pipeline (MVP)

```
paths → file discovery (include/exclude globs)
      → for each file:
          parser.parse(text)            # Lark
          ast_builder.transform(tree)   # → internal AST
          scanner.scan_file:
              symbols.build(ast)        # minimal scopes + declarations
              metrics.compute(ast)      # LOC, statements, complexity
              walker.walk(ast, checks)  # dispatch → add_issue
      → aggregate ScanResult[]
      → report.<format>.write(results) → stdout/file
      → exit code from --fail-on
```

## 9. Starter check set (target ~6–10)

| Key | Detects | Needs symbols? |
|-----|---------|----------------|
| `ComparisonWithNull` | `= NULL` / `!= NULL` instead of `IS [NOT] NULL` | no |
| `SelectAllColumns` | `SELECT *` | no |
| `EmptyBlock` | empty `BEGIN ... END` | no |
| `UnusedVariable` | declared, never referenced | yes |
| `VariableHiding` | inner scope shadows outer name | yes |
| `DeadCodeAfterReturn` | statements after unconditional `RETURN`/`RAISE` | no |
| `ToDoComment` | `TODO`/`FIXME` markers | no (comment) |
| `IdenticalBranches` | `IF` branches with identical bodies | no |

(Start with the no-symbol checks; add symbol-dependent ones as the symbol table matures.)

## 10. Testing strategy

- Port the `zpa-checks-testkit` verifier idea: `.sql` fixtures with `-- Noncompliant` annotations (and optional `{{message}}` / `[[sc=..;ec=..]]`).
- `tests/verifier.py` parses annotations, runs one check, diffs expected vs actual issues, asserts.
- One fixture + test per starter check; plus parser smoke tests in `pyzpa parse`.

## 11. Milestones

1. **M1 — Skeleton:** package, CLI shell, `list-checks`, Lark grammar subset parsing anonymous blocks + procedures; `pyzpa parse` prints AST.
2. **M2 — Engine:** internal AST, walker, `Check` base, decorator metadata, 3 no-symbol checks, text reporter, verifier + tests.
3. **M3 — Output & selection:** JSON + SARIF reporters, `--checks/--disable/--fail-on`, exit codes.
4. **M4 — Symbols:** minimal symbol table + scopes; add `UnusedVariable`, `VariableHiding`; metrics (LOC, statements, complexity).
5. **M5 — Hardening:** error recovery, broader grammar coverage, entry-point discovery hook, docs.

## 12. Explicit non-goals (MVP)

- No SonarQube plugin, server integration, or Generic Issue Import wiring.
- No syntax highlighting, CPD, or utPLSQL import.
- No desktop toolkit.
- No full type inference or complete Oracle dialect coverage.
- No performance guarantees beyond "usable on a typical schema's scripts."
