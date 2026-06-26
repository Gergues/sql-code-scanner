# plsql-custom-rules — Architecture

> A demonstration plugin showing how third parties extend ZPA with their own PL/SQL rules. Shipped as both a Gradle and a Maven project. This is the **Java** module of the repository.

## 1. Responsibility

Serve as a copyable template for building a custom SonarQube plugin that adds organization-specific PL/SQL rules on top of ZPA, and as a compatibility target for `zpa-cli`.

## 2. Structure (`com.company.plsql`)

| Class / file | Role |
|--------------|------|
| `PlSqlCustomRulesPlugin` | SonarQube `Plugin` entry point; registers the rules definition. |
| `PlSqlCustomRulesDefinition` | Extends `org.sonar.plugins.plsqlopen.api.CustomPlSqlRulesDefinition`; declares the repository and its check classes. |
| `ForbiddenDmlCheck` | Example rule. |
| `src/main/resources/META-INF/extensions.idx` | Index file listing the `CustomPlSqlRulesDefinition` subclass for `zpa-cli` discovery. |

## 3. Defining the rule repository

```java
public class PlSqlCustomRulesDefinition extends CustomPlSqlRulesDefinition {
    @Override public String repositoryName() { return "Company"; }
    @Override public String repositoryKey()  { return "my-rules"; }
    @Override public Class[] checkClasses()  { return new Class[]{ ForbiddenDmlCheck.class }; }
}
```

`repositoryKey`/`repositoryName` identify the rule repository in SonarQube; `checkClasses()` lists every rule to register.

## 4. Anatomy of a custom check

```java
@Rule(name = "Avoid DML on table USER",
      description = "You should use the functions from the USER_WRAPPER package.",
      key = "ForbiddenDmlCheck", priority = Priority.MAJOR)
@ConstantRemediation("10min")
@ActivatedByDefault
public class ForbiddenDmlCheck extends PlSqlCheck {
    @Override public void init() {
        subscribeTo(DmlGrammar.DML_TABLE_EXPRESSION_CLAUSE);
    }
    @Override public void visitNode(AstNode node) {
        AstNode table = node.getFirstChildOrNull(DmlGrammar.TABLE_REFERENCE);
        if (table != null && table.getTokenOriginalValue().equalsIgnoreCase("user")) {
            addIssue(table, "Replace this query by a function of the USER_WRAPPER package.");
        }
    }
}
```

It imports only the public API (`org.sonar.plugins.plsqlopen.api.*`): `PlSqlCheck`, `DmlGrammar`, the annotations, and `sslr.AstNode`. The pattern is identical to built-in rules — subscribe to grammar nodes in `init()`, inspect and report in `visitNode()`.

## 5. `extensions.idx`

```
com.company.plsql.PlSqlCustomRulesDefinition
```

This index lets `zpa-cli` discover the rules definition without a full SonarQube server. To stay compatible with `zpa-cli`, this file must match your `CustomPlSqlRulesDefinition` subclass.

## 6. Build setup (Gradle and Maven)

Two parallel build descriptors produce the same plugin:

- **Maven (`pom.xml`)** — uses `sonar-packaging-maven-plugin`; the manifest `pluginClass` must point at the `Plugin` subclass (`PlSqlCustomRulesPlugin`). `groupId`/`artifactId`/`version`/`name`/`description` are freely customizable.
- **Gradle (`build.gradle.kts`)** — `group`/`version`/`description` customizable; the `jar` task's manifest attributes (including the plugin class) may need updating if classes are renamed.

### Dependencies

- `sonar-plugin-api` — minimum SonarQube version supported (provided at runtime).
- `sonar-zpa-plugin` — the ZPA engine + public API the rules build on.
- `zpa-checks-testkit` — optional, for verifier-based rule tests.

## 7. Packaging & deployment

The build produces a SonarQube plugin JAR. Deploy it into `SONARQUBE_HOME/extensions/plugins` **alongside** `sonar-zpa-plugin`; ZPA's API is provided by the base plugin, so the custom plugin only contributes the new rules.
