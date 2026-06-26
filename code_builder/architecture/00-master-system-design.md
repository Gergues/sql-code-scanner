# ZPA — Master Architecture & System Design

> Master document. Each component has a dedicated architecture document in this folder:
> - [01-zpa-core.md](01-zpa-core.md)
> - [02-zpa-checks.md](02-zpa-checks.md)
> - [03-zpa-checks-testkit.md](03-zpa-checks-testkit.md)
> - [04-sonar-zpa-plugin.md](04-sonar-zpa-plugin.md)
> - [05-zpa-toolkit.md](05-zpa-toolkit.md)
> - [06-plsql-custom-rules.md](06-plsql-custom-rules.md)

## 1. What ZPA is

**ZPA (Z PL/SQL Analyzer)** is a parser and static-code-analysis engine for **Oracle PL/SQL and SQL**. It lexes and parses source code into an **Abstract Syntax Tree (AST)**, builds a **symbol table** with scope and datatype information, computes **code metrics**, and runs a library of **coding rules (checks)** that report quality issues.

The engine is consumed in three ways:
- As a **SonarQube plugin** (`sonar-zpa-plugin`) for on-premise code-quality dashboards.
- As a **standalone CLI** (`zpa-cli`, separate repository).
- As a **desktop AST viewer** (`zpa-toolkit`) for inspecting parser output.

- **Languages:** Primarily **Kotlin**; the `plsql-custom-rules` example module is **Java**.
- **Build:** Gradle (Kotlin DSL) with a `build-logic` convention plugin; the custom-rules demo also ships a Maven `pom.xml`.
- **License:** LGPL-3.0.
- **Parser framework:** **FLR** (Fluent Lexical Runtime) — a modern successor to SonarSource's SSLR.

## 2. Component map

| Component | Type | Responsibility |
|-----------|------|----------------|
| `zpa-core` | Library (engine) | Lexer, parser, grammar, AST, symbol table, type system, metrics, rule infrastructure, public API. |
| `zpa-checks` | Library (rules) | ~52 built-in coding rules built on the core check framework. |
| `zpa-checks-testkit` | Test library | `PlSqlCheckVerifier` + annotation-based SQL fixtures for testing rules. |
| `sonar-zpa-plugin` | SonarQube plugin | Bridges the engine to SonarQube: language, sensor, rules repo, quality profile, metrics, utPLSQL import. |
| `zpa-toolkit` | Desktop app (Swing) | Visual AST / source explorer built on the FLR toolkit. |
| `plsql-custom-rules` | Example plugin | Demonstrates third-party custom rules (Gradle + Maven). |

## 3. Layered architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Consumers                                                         │
│  ┌───────────────────┐  ┌────────────┐  ┌──────────────────────┐  │
│  │ sonar-zpa-plugin  │  │ zpa-cli    │  │ zpa-toolkit (Swing)  │  │
│  │ (SonarQube)       │  │ (external) │  │                      │  │
│  └─────────┬─────────┘  └─────┬──────┘  └──────────┬───────────┘  │
└────────────┼──────────────────┼────────────────────┼──────────────┘
             │                  │                     │
             ▼                  ▼                     ▼
┌──────────────────────────────────────────────────────────────────┐
│  Rules layer                                                       │
│  ┌──────────────┐   ┌───────────────────┐   ┌──────────────────┐  │
│  │ zpa-checks   │   │ plsql-custom-rules│   │ zpa-checks-testkit│ │
│  │ (built-in)   │   │ (3rd-party)       │   │ (test harness)    │ │
│  └──────┬───────┘   └─────────┬─────────┘   └────────┬──────────┘ │
└─────────┼─────────────────────┼──────────────────────┼────────────┘
          │     all extend PlSqlCheck (public API)      │
          ▼                     ▼                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  zpa-core (engine)                                                 │
│  Lexer → Parser → Grammar/AST → Symbol table → Type solver →       │
│  Metrics → AstScanner orchestration                                │
│  Public API: org.sonar.plugins.plsqlopen.api                       │
└────────────────────────────┬───────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  FLR (Fluent Lexical Runtime) — lexer/parser/AST primitives        │
└──────────────────────────────────────────────────────────────────┘
```

## 4. End-to-end analysis flow

```
PL/SQL source (text)
   │
   ▼  PlSqlLexer (channels: comments, numbers, strings, identifiers, …)
Tokens
   │
   ▼  PlSqlParser + PlSqlGrammar (DDL/DML/DCL/TCL/session/SQL*Plus rules)
Raw AST (FLR AstNode)
   │
   ▼  SemanticAstNode wrapping (adds Symbol + PlSqlDatatype, lazy typed Tree)
Semantic AST
   │
   ▼  AstScanner.scanFile()  — orchestrates a multi-pass walk:
   │      1. SymbolVisitor      → builds scopes + symbol table, resolves datatypes
   │      2. MetricsVisitor     → LOC, comments, statements, NOSONAR
   │      3. ComplexityVisitor  → cyclomatic complexity (+ per-function)
   │      4. Checks (PlSqlCheck) → emit PreciseIssue objects
   │      5. Extra visitors injected by host (highlighting, CPD, …)
AstScannerResult (symbols, scopes, issues, metrics)
   │
   ▼  Consumer renders results (SonarQube measures/issues, CLI report, toolkit tree)
```

Key design point: **everything that inspects code is a visitor**. Built-in rules, custom rules, symbol-table construction, and metrics all subclass the same `PlSqlVisitor`/`PlSqlCheck` base and `subscribeTo(...)` the grammar node types they care about. The `PlSqlAstWalker` dispatches nodes to subscribers in a single depth-first traversal.

## 5. The public API contract

The package **`org.sonar.plugins.plsqlopen.api`** is the only stable, externally-consumable surface (a SonarQube requirement). It exposes:

- `PlSqlFile`, `PlSqlVisitorContext` — input + analysis context.
- `checks.PlSqlCheck` / `checks.PlSqlVisitor` — base classes for rules.
- `PlSqlGrammar`, `DmlGrammar`, `DdlGrammar`, etc. — node types to subscribe to.
- `annotations.*` — `@Rule`, `@Priority`, `@ConstantRemediation`, `@ActivatedByDefault`, `@RuleProperty`, `@RuleTemplate`.
- `symbols.*` — `Symbol`, `Scope`, `SymbolTable`, datatype hierarchy.

Anything outside this package is internal and may change without notice.

> Note: in the engine source the package root is `com.felipebz.zpa.api`, which is shaded/relocated to the `org.sonar.plugins.plsqlopen.api` namespace that external consumers (custom rules) import.

## 6. Cross-cutting concerns

- **Error recovery:** parsing can run strict (fail fast) or tolerant (continue past errors), controlled by `PlSqlConfiguration` / the `sonar.zpa.errorRecoveryEnabled` property.
- **Concurrency:** the SonarQube sensor can analyze files concurrently; result-saving is guarded by a `ReentrantLock` because some SonarQube save APIs are not thread-safe.
- **Localization:** rule messages are externalized in resource bundles (`plsqlopen.properties`, `plsqlopen_pt_BR.properties`).
- **Rule metadata:** defined via annotations on each check and HTML description files, loaded by `RulesDefinitionAnnotationLoader`.

## 7. Compatibility

| ZPA version | SonarQube (min/max) |
|-------------|---------------------|
| 4.1.0 | 25.8 / 26.4 |
| 4.2.0 (in development) | 26.2 / 26.5 |

## 8. Repository layout (engine modules)

```
zpa/
├── zpa-core/            # engine
├── zpa-checks/          # built-in rules
├── zpa-checks-testkit/  # rule test harness
├── sonar-zpa-plugin/    # SonarQube integration
├── zpa-toolkit/         # Swing AST viewer
├── plsql-custom-rules/  # example custom-rule plugin (Java, Gradle + Maven)
├── build-logic/         # Gradle convention plugins
└── gradle/libs.versions.toml  # version catalog
```
