# Python Port — Feasibility & Target Layout (Design Note)

> Advisory design note. Assesses porting the Kotlin ZPA engine to Python and sketches a target Python module layout that mirrors the current components. See the component docs ([01-zpa-core.md](01-zpa-core.md) … [06-plsql-custom-rules.md](06-plsql-custom-rules.md)) for the source-of-truth design being mirrored.

## 1. Verdict

Porting is **feasible but is a re-implementation, not a translation**. The design is clean and layered, so the analysis logic (symbol table, type solver, metrics, checks) ports well. The effort and risk concentrate in two things that **cannot be copied**:

1. The **FLR-bound lexer/parser/grammar** in `zpa-core` (no Python equivalent of FLR/SSLR).
2. The **SonarQube plugin host** (`sonar-zpa-plugin`) — SonarQube only loads JVM plugins, so a Python build cannot be an in-process SonarQube plugin.

Roughly ~80% of real effort sits in re-expressing the grammar and replacing the SonarQube integration with a different output (SARIF / SonarQube Generic Issue Import).

## 2. Difficulty by component

| Component | Difficulty | Strategy |
|-----------|------------|----------|
| `zpa-core` lexer | Medium | Channel model maps cleanly to Python; regex-driven, portable. |
| `zpa-core` parser/grammar | **Very high** | Bound to FLR — the central effort. Re-express on ANTLR4 (Python target) or `lark`. |
| Semantic AST (`SemanticAstNode`) | High | Reflection-based typed-tree needs a Pythonic redesign (registry + `__getattr__`/`functools.cached_property`). |
| Symbol table / scope / type solver | Medium | Pure algorithms; port once an AST exists. |
| Metrics visitors | Low–medium | Straightforward traversal. |
| `zpa-checks` (~52 rules) | Medium (bulk) | Each rule is small/mechanical; `@Rule` metadata → decorators/class attrs. |
| `zpa-checks-testkit` | Low | `-- Noncompliant` verifier is self-contained; `.sql` fixtures reusable as-is. |
| `sonar-zpa-plugin` | **Not portable** | Replace with CLI + SARIF / SonarQube Generic Issue Import; no in-process SonarQube hosting. |
| `zpa-toolkit` | Low priority | Rebuild on a Python UI only if needed. |
| `plsql-custom-rules` | Medium | Replace SonarQube plugin extension model with Python entry-points/plugin discovery. |

## 3. Key porting decisions

- **Parser toolkit (highest-leverage choice).**
  - **ANTLR4, Python target** — *recommended*. Reuse a mature, multi-target runtime and an existing community Oracle PL/SQL grammar as a starting point; port only the analysis layer. C-accelerated runtime helps performance.
  - **`lark`** — pure-Python, ergonomic, good for a from-scratch grammar; slower on very large inputs.
  - **Hand-written recursive descent** — maximum control/fidelity to current behavior, highest cost.
- **`SemanticAstNode` reflection** → a node-type→class registry plus lazy typed wrappers (`functools.cached_property`), avoiding JVM reflection.
- **Annotation-driven rules** → Python decorators (`@rule(...)`) writing metadata onto the class, discovered via a registry or entry-points.
- **Output contract** → emit **SARIF 2.1.0** and/or **SonarQube Generic Issue Import** JSON instead of calling SonarQube save APIs. Keep highlighting/CPD/measures only if a consuming host needs them.
- **Performance** → expect a pure-Python parser to be markedly slower than the JVM; mitigate with ANTLR's accelerated runtime or a native (Rust/C) parsing extension for the hot path.

## 4. What ports cleanly vs. what fights you

**In favor:** small, well-defined public API surface to reproduce; visitor pattern + scope chain + type solver are language-agnostic; rules are isolated and decorator-friendly; fixtures and rule HTML/properties are reusable data.

**Against:** no FLR/SSLR in Python; `SemanticAstNode` reflection redesign; loss of the SonarQube host value (issues/highlighting/CPD/measures/utPLSQL); Python parsing performance.

## 5. Recommended strategy (if Python is required)

ANTLR4 (Python target) + a reused Oracle PL/SQL grammar → port symbol table / type solver / metrics / checks → emit **SARIF / SonarQube Generic Issue Import**.

If the goal is merely *"use ZPA from Python"* rather than *"rewrite ZPA in Python"*, **wrap `zpa-cli`** (subprocess + consume its report) or bridge via JPype/Py4J/GraalVM — dramatically cheaper and preserves full fidelity and the SonarQube path.

## 6. Target Python module layout (mirrors current components)

```
zpa-py/
├── pyproject.toml                  # build, deps (antlr4-python3-runtime), entry-points for rule plugins
├── README.md
│
├── zpa_core/                       # ← mirrors zpa-core
│   ├── __init__.py
│   ├── api/                        # public, stable surface (the contract to keep)
│   │   ├── plsql_file.py           # PlSqlFile (contents/path/type MAIN|TEST)
│   │   ├── context.py              # PlSqlVisitorContext (root_tree, symbol_table)
│   │   ├── grammar.py              # node-type constants: PlSqlGrammar, DmlGrammar, DdlGrammar, …
│   │   ├── annotations.py          # @rule, Priority, ConstantRemediation, ActivatedByDefault, RuleProperty
│   │   ├── checks.py               # PlSqlVisitor, PlSqlCheck (subscribe_to, visit_node, add_issue)
│   │   └── symbols/
│   │       ├── symbol.py           # Symbol, SymbolKind
│   │       ├── scope.py            # Scope (parent chain, accessible-in-scope lookup)
│   │       ├── symbol_table.py
│   │       └── datatype/           # PlSqlDatatype + ~13 concrete types
│   ├── lexer/
│   │   ├── lexer.py                # channel orchestration
│   │   └── channels.py             # numeric/string/date/identifier/comment/whitespace
│   ├── parser/
│   │   ├── plsql_parser.py         # wraps the ANTLR/lark-generated parser
│   │   └── generated/              # ANTLR-generated PL/SQL parser (if ANTLR route)
│   ├── ast/
│   │   ├── semantic_node.py        # SemanticAstNode (symbol + datatype + lazy typed tree)
│   │   ├── tree.py                 # Tree base + registry
│   │   └── nodes/                  # IfStatement, ElsifClause, RaiseStatement, …
│   ├── symbols/
│   │   ├── symbol_visitor.py       # first-pass scope/symbol builder
│   │   ├── scope_impl.py
│   │   └── type_solver.py          # DefaultTypeSolver.solve(node, scope)
│   ├── metrics/
│   │   ├── metrics_visitor.py      # LOC/comments/statements/NOSONAR
│   │   ├── complexity_visitor.py
│   │   └── function_complexity_visitor.py
│   ├── scan/
│   │   ├── ast_scanner.py          # AstScanner.scan_file(file, extra_visitors) -> ScanResult
│   │   ├── ast_walker.py           # depth-first dispatch to subscribers
│   │   ├── configuration.py        # charset, error_recovery
│   │   └── result.py               # ScanResult (symbols, issues, metrics)
│   └── rules/
│       ├── rule.py                 # ZpaRule, ZpaRuleKey, ZpaActiveRule
│       └── annotation_loader.py    # build rule metadata from decorators
│
├── zpa_checks/                     # ← mirrors zpa-checks
│   ├── __init__.py
│   ├── base_check.py               # AbstractBaseCheck (localized messages)
│   ├── checks/                     # comparison_with_null.py, select_all_columns.py, …
│   └── resources/
│       └── l10n/rules/plsql/       # <Rule>.html, plsqlopen.properties (reusable from Kotlin)
│
├── zpa_checks_testkit/             # ← mirrors zpa-checks-testkit
│   ├── verifier.py                 # PlSqlCheckVerifier.verify(path, check)
│   ├── test_issue.py
│   └── annotations.py              # parse -- Noncompliant / @±N / [[...]] / ^
│
├── zpa_report/                     # ← replaces sonar-zpa-plugin (output layer)
│   ├── cli.py                      # entry point: scan files -> report
│   ├── sarif_writer.py             # SARIF 2.1.0
│   ├── sonar_generic_writer.py     # SonarQube Generic Issue Import JSON
│   └── utplsql/                    # optional: import utPLSQL test/coverage reports
│
├── zpa_toolkit/                    # ← mirrors zpa-toolkit (optional)
│   └── viewer.py                   # AST viewer (e.g. Textual/Qt) — only if needed
│
└── plsql_custom_rules_example/     # ← mirrors plsql-custom-rules
    ├── pyproject.toml              # registers rules via entry-points group, e.g. "zpa.rules"
    └── company_rules/
        ├── definition.py           # CustomPlSqlRulesDefinition equivalent (repo key/name, check classes)
        └── forbidden_dml_check.py  # example: subscribe_to(DmlGrammar.DML_TABLE_EXPRESSION_CLAUSE)
```

### Mapping notes

- **`zpa_report/` replaces `sonar-zpa-plugin/`.** The Kotlin plugin's value (issues, highlighting, CPD, measures, utPLSQL) is delivered *through* SonarQube's Java API; in Python that becomes report writers (SARIF / Generic Issue Import) plus an optional utPLSQL importer. Highlighting/CPD are only meaningful if a consuming host renders them.
- **Custom-rule discovery** moves from `extensions.idx` + SonarQube `Plugin` to Python **entry-points** (e.g. an `[project.entry-points."zpa.rules"]` group) resolved by `zpa_report`/`zpa_core` at startup.
- **Public API stability:** keep everything third parties import under `zpa_core.api` (mirroring `org.sonar.plugins.plsqlopen.api`); treat the rest as internal.
