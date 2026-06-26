# zpa-checks-testkit — Architecture

> A lightweight test harness for writing rule tests with annotated SQL fixtures. Usable by both the built-in `zpa-checks` and third-party custom rules.

## 1. Responsibility

Let rule authors express expected issues *inside* a sample SQL file as comments, then automatically parse the file, run a check against it, and assert that produced issues match the annotations — with no per-test boilerplate.

## 2. Key classes

- `com.felipebz.zpa.checks.verifier.PlSqlCheckVerifier` — the orchestrator (itself a `PlSqlCheck`). Entry point: `PlSqlCheckVerifier.verify(filePath, checkInstance)`.
- `com.felipebz.zpa.checks.verifier.TestIssue` — holds the expected-issue metadata parsed from annotations.

## 3. Usage

```kotlin
class ComparisonWithNullCheckTest : BaseCheckTest() {
    @Test
    fun test() {
        PlSqlCheckVerifier.verify(
            getPath("comparison_with_null.sql"),
            ComparisonWithNullCheck()
        )
    }
}
```

Flow: parse the SQL file → run the check → collect actual issues → parse the `-- Noncompliant` annotations into expected issues → diff → throw `AssertionError` on any mismatch.

## 4. Annotation syntax (in the SQL fixture)

| Annotation | Meaning |
|------------|---------|
| `-- Noncompliant` | An issue is expected on this line. |
| `-- Noncompliant@+N` / `@-N` | Issue is N lines ahead / behind. |
| `{{message}}` | Expected issue message. |
| `[[sc=9;ec=10]]` | Expected start/end column. |
| `[[el=+1;effortToFix=3]]` | End-line offset and effort-to-fix. |
| `[[secondary=3,4]]` | Expected secondary location lines. |
| `^` (caret line) | Precise location marker under the annotated line. |

Example:

```sql
create procedure a is             -- Noncompliant {{message}}
  i integer;                      -- Noncompliant {{message1}}
begin
    -- Noncompliant@+1 {{message2}}
    null;
    null; -- Noncompliant {{message4}} [[sc=9;ec=10;secondary=3,4]]
    func(foo,  -- Noncompliant [[sc=5;el=+1;ec=11;effortToFix=3]]
      bar);
end;
```

## 5. Dependencies

```kotlin
compileOnly(project(":zpa-core"))
```

Intentionally minimal: it compiles against `zpa-core` but adds no runtime dependencies of its own, so custom-rule projects can pull it in as a test dependency cheaply.

## 6. Role in the system

The same fixture format documents the precise location and secondary-location features of `zpa-core`'s issue model, so the testkit doubles as executable specification for rule behavior. The repository's own resources (e.g. `check_verifier_*.sql`) test the verifier itself, including negative cases like incorrect attributes, comments, shifts, and secondary locations.
