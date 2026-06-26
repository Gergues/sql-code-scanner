# zpa-checks — Architecture

> The library of built-in coding rules shipped with ZPA (~52 checks).

## 1. Responsibility

Provide ZPA's default rule set. Each rule is a small visitor that subscribes to specific grammar nodes and reports issues. This module contributes only rule *logic* and *metadata*; it relies on `zpa-core` for parsing/AST and on the host (`sonar-zpa-plugin` or `zpa-cli`) to actually run and report.

## 2. Layout

- Source: `com.felipebz.zpa.checks` — a flat package; one class per rule named `<Name>Check.kt`.
- Metadata: `src/main/resources/org/sonar/l10n/plsqlopen/rules/plsql/`
  - `<Rule>.html` — human-readable rule description with examples.
  - `plsqlopen.properties` / `plsqlopen_pt_BR.properties` — localized issue messages.

## 3. Anatomy of a check

```kotlin
@Rule(priority = Priority.MAJOR, tags = [Tags.PERFORMANCE])
@ConstantRemediation("30min")
@RuleInfo(scope = RuleInfo.Scope.ALL)
@ActivatedByDefault
class ExampleCheck : AbstractBaseCheck() {
    override fun init() {
        subscribeTo(PlSqlGrammar.SOME_NODE_TYPE)   // pick AST nodes to visit
    }
    override fun visitNode(node: AstNode) {
        addIssue(node, getLocalizedMessage())       // report
    }
}
```

- **Base class:** `AbstractBaseCheck` (extends `PlSqlCheck` from `zpa-core`). Adds `getLocalizedMessage()` which loads text from the resource bundles; `convertCheckClassName()` maps `ComparisonWithNullCheck` → resource key `ComparisonWithNull`.
- **Annotations:** `@Rule` (priority + tags from `Tags.kt`), `@ConstantRemediation` (effort, e.g. `"30min"`), `@RuleInfo` (scope), `@ActivatedByDefault`.
- **Visitor hooks:** `init()` to subscribe; `visitNode()` per matched node; `leaveFile()` for whole-file/scope checks; `visitComment()` for comment-based checks.

## 4. Example rules

| Check | Detects |
|-------|---------|
| `ComparisonWithNullCheck` | `= NULL` instead of `IS NULL` / `IS NOT NULL`. |
| `SelectAllColumnsCheck` | `SELECT *` usage (performance). |
| `UnusedVariableCheck` | Declared-but-unused variables in a scope. |
| `EmptyBlockCheck` | Empty statement blocks. |
| `VariableHidingCheck` | Variable shadowing in nested scopes. |

(~47 more checks in the same package.)

## 5. Metadata & localization

Issue messages use the key format `<RuleName>.message=...` with `{0}` placeholders, e.g.:

```
ComparisonWithNull.message=Fix this comparison or change to "{0}".
```

HTML files provide the long description rendered in SonarQube's rule view. The rule's key, priority, remediation, and default-activation come from the annotations and are loaded by `zpa-core`'s `RulesDefinitionAnnotationLoader`.

## 6. Dependencies

```kotlin
implementation(libs.flr.core)            // AST types
implementation(libs.flr.xpath)           // XPath over the AST
implementation(project(":zpa-core"))     // check framework, grammar, symbols
testImplementation(project(":zpa-checks-testkit"))  // verifier-based tests
```

## 7. Testing

Each check has a paired test that uses `PlSqlCheckVerifier` (from `zpa-checks-testkit`) against a `.sql` fixture annotated with `-- Noncompliant` markers. See [03-zpa-checks-testkit.md](03-zpa-checks-testkit.md).
