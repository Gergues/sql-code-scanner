# zpa-core — Architecture

> The analysis engine. Contains the lexer, parser, grammar, AST, symbol table, type system, metrics, and the public API. All other modules depend on it.

## 1. Responsibility

Turn PL/SQL source text into a richly-typed, semantically-aware AST and run visitor-based analysis over it. `zpa-core` knows *how to read and understand* PL/SQL; it does not know about SonarQube or any specific host.

## 2. Package structure (`com.felipebz.zpa`)

| Package | Responsibility |
|---------|----------------|
| `api/` | Public, stable API (exported as `org.sonar.plugins.plsqlopen.api`). |
| `api/annotations/` | Rule metadata annotations — `Rule`, `Priority`, `RuleInfo`, `RuleProperty`, `RuleTemplate`. |
| `api/checks/` | Check/visitor framework — `PlSqlCheck`, `PlSqlVisitor`. |
| `api/squid/` | Semantic AST API — `SemanticAstNode`, `PlSqlCommentAnalyzer`. |
| `api/symbols/` | Symbol-table contracts — `Symbol`, `Scope`, `SymbolTable`, `PlSqlType`. |
| `api/symbols/datatype/` | 13 datatype classes (Numeric, Character, Date, Boolean, LOB, JSON, Record, Rowtype, …). |
| `lexer/` | Lexical analysis; one channel per token category. |
| `parser/` | `PlSqlParser` construction. |
| `grammar/` + `api/*Grammar.kt` | Grammar rules for PL/SQL syntax (DDL/DML/DCL/TCL/session/SQL*Plus). |
| `sslr/` | Grammar-builder infrastructure and the typed `Tree` hierarchy. |
| `symbols/` | Symbol-table implementation — `SymbolTableImpl`, `SymbolVisitor`, `ScopeImpl`, `DefaultTypeSolver`. |
| `squid/` | AST scanning/orchestration — `AstScanner`, `PlSqlAstWalker`, `PlSqlConfiguration`. |
| `metrics/` | `MetricsVisitor`, `ComplexityVisitor`, `FunctionComplexityVisitor`. |
| `rules/` | Rule definition/loading — `ZpaRule`, `ZpaRuleKey`, `ZpaActiveRule`, `RulesDefinitionAnnotationLoader`. |
| `metadata/` | Oracle Forms metadata support. |
| `utils/` | Logging and helpers. |

## 3. Subsystems

### Lexer
`PlSqlLexer` assembles ordered **channels**, each consuming one token category: `NumericChannel`, `IntegerChannel`, `StringChannel`, `DateChannel`, `IdentifierChannel`, `QuotedIdentifierChannel`, `CommentChannel`, `DiscardWhitespaceChannel`. Handles floating-point/scientific numbers, custom string delimiters, date/timestamp literals, and quoted identifiers.

### Parser & grammar
`PlSqlParser.create(config)` combines `PlSqlGrammar` (200+ rule enums) with the lexer to produce an `AstNode` tree. The grammar is split into focused modules: `DdlGrammar`, `DmlGrammar`, `DclGrammar`, `TclGrammar`, `SessionControlGrammar`, `SqlPlusGrammar`, `ConditionsGrammar`, `AggregateSqlFunctionsGrammar`, `SingleRowSqlFunctionsGrammar`. The `PlSqlGrammarBuilder` maps grammar rules to typed `Tree` classes (e.g. `IfStatement`, `ElsifClause`, `RaiseStatement`).

### Semantic AST
`SemanticAstNode` decorates FLR's `AstNode` with a `Symbol?` reference and a `PlSqlDatatype`, and lazily materializes a strongly-typed `Tree` instance via reflection. This is the bridge between the raw parse tree and semantic analysis.

### Symbol table & type system
- `SymbolVisitor` runs a first pass to identify scope holders (procedures, functions, packages, blocks, triggers, types) and declare `Symbol`s (variables, parameters, cursors, …).
- `SymbolTableImpl` stores symbols and scopes and answers lookups.
- `ScopeImpl` forms a parent/child scope chain; `getSymbolsAcessibleInScope()` walks the chain for resolution.
- `DefaultTypeSolver.solve(node, scope)` infers datatypes for expressions and literals across the 13-type hierarchy rooted at `PlSqlDatatype`.

### Metrics
- `MetricsVisitor` — LOC, comment lines, statement count, NOSONAR handling.
- `ComplexityVisitor` — cyclomatic complexity (IF/LOOP/EXIT/CONTINUE/ELSIF/WHEN + program units).
- `FunctionComplexityVisitor` — per-function complexity.

### Orchestration
`AstScanner.scanFile(plSqlFile, extraVisitors)` is the engine entry point. It parses the file, builds the symbol table, runs metric visitors, executes the registered checks plus any host-injected extra visitors, and returns an `AstScannerResult` (symbols, scopes, issues, LOC, complexity, etc.). `PlSqlAstWalker` performs the single depth-first traversal, dispatching each node to its subscribers (`visitFile → visitNode/leaveNode → leaveFile`).

## 4. Public API (`org.sonar.plugins.plsqlopen.api`)

- `PlSqlFile` — input abstraction (`contents()`, `fileName()`, `path()`, `type()` = MAIN/TEST).
- `PlSqlVisitorContext` — exposes `rootTree()`, `plSqlFile()`, and symbol-table access.
- `checks.PlSqlVisitor` — abstract visitor: `subscribedKinds()`, `init()`, `visitFile()/leaveFile()`, `visitNode()/leaveNode()`, `visitToken()`, `visitComment()`.
- `checks.PlSqlCheck` — base rule class; collects `PreciseIssue`s via `addIssue(node, message)`.

## 5. Dependencies

```kotlin
api(libs.flr.core)        // FLR — lexer/parser/AST runtime (SSLR successor)
implementation(libs.jackson) // JSON binding (e.g. Forms metadata)
testImplementation(libs.flr.testing.harness)
```

`flr-xpath` is also available for AST navigation. Minimum SonarQube API versions are declared in the version catalog.

## 6. Design patterns

| Pattern | Where |
|---------|-------|
| Visitor | `PlSqlVisitor` / `PlSqlCheck` and all subclasses. |
| Tree traversal w/ subscriber map | `PlSqlAstWalker`. |
| Decorator | `SemanticAstNode` wrapping FLR `AstNode`. |
| Scope chain | `ScopeImpl.outer` parent links. |
| Lazy initialization | typed `Tree` materialization in `SemanticAstNode`. |
| Strategy | `DefaultTypeSolver` type inference. |
| Annotation-driven config | `RulesDefinitionAnnotationLoader`. |
