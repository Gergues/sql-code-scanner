# sonar-zpa-plugin — Architecture

> The SonarQube plugin that integrates the ZPA engine into a SonarQube server. This is the module packaged and dropped into `SONARQUBE_HOME/extensions/plugins`.

## 1. Responsibility

Adapt the host-agnostic `zpa-core` engine to the SonarQube extension model: declare the PL/SQL language, run analysis as a sensor, map ZPA issues/metrics/highlighting/CPD into SonarQube APIs, expose the rule repository and quality profile, and import external utPLSQL test/coverage reports.

## 2. Package structure (`com.felipebz.zpa`)

| Package / class | Role |
|-----------------|------|
| `PlSqlPlugin` | Plugin entry point (`org.sonar.api.Plugin`); registers all extensions. |
| `PlSql` | Language definition (file suffixes, key). |
| `PlSqlProfile` | Built-in quality profile (default activated rules). |
| `PlSqlSquidSensor` | The sensor — drives analysis over the project's PL/SQL files. |
| `PlSqlRuleRepository` | Registers ZPA rules into SonarQube's rule repository. |
| `squid/PlSqlAstScanner` | Bridges `zpa-core`'s `AstScanner` to a `SensorContext`. |
| `squid/SonarQubePlSqlFile` | Wraps a SonarQube `InputFile` as a `PlSqlFile`. |
| `symbols/SonarQubeSymbolTable` | Saves symbol references as SonarQube symbol highlighting. |
| `symbols/ObjectLocator`, `MappedObject` | Cross-file object resolution (global scope). |
| `metrics/CpdVisitor` | Feeds copy-paste-detection tokens to SonarQube. |
| `highlight/PlSqlHighlighterVisitor` | Syntax highlighting (referenced from the scanner). |
| `rules/SonarQubeRule*Adapter`, `SonarQubeRuleMetadataLoader` | Map ZPA rule keys/params/metadata to SonarQube. |
| `utplsql/*` | Import utPLSQL test-execution and coverage reports. |
| `log/SonarQubeLogger(s)` | Routes `zpa-core` logging to SonarQube's logger. |

## 3. Plugin registration

`PlSqlPlugin.define(context)` wires the ZPA logging factory and registers extensions:

- Configuration properties: file suffixes (`sonar.plsqlopen.file.suffixes`, default `sql,pkg,pks,pkb`), Oracle Forms metadata path, parse error-recovery toggle, concurrent-execution toggle.
- Core extensions: `PlSql`, `PlSqlProfile`, `PlSqlSquidSensor`, `PlSqlRuleRepository`, `ObjectLocator`.
- utPLSQL extensions: test/coverage report-path properties and `UtPlSqlSensor`.

## 4. Analysis bridge — `PlSqlAstScanner`

The sensor constructs a `PlSqlAstScanner` wrapping `zpa-core`'s `AstScanner` (configured with the checks, Forms metadata, error-recovery flag, and file encoding). Per file:

1. Wrap the `InputFile` as a `SonarQubePlSqlFile`; branch on `MAIN` vs `TEST` type.
2. Call `astScanner.scanFile(file, extraVisitors)`, injecting host visitors:
   - `PlSqlHighlighterVisitor` (syntax highlighting),
   - `CpdVisitor` (copy/paste detection) — main files only.
3. Apply `noSonarFilter` for NOSONAR lines.
4. Under a `ReentrantLock` (SonarQube save APIs are not thread-safe):
   - `saveIssues(...)` — convert `PreciseIssue`/`IssueLocation` to `NewIssue`/`NewIssueLocation`.
   - `SonarQubeSymbolTable.save(symbols)` — symbol references.
   - Save measures: `STATEMENTS`, `NCLOC`, `COMMENT_LINES`, `COMPLEXITY`, `FUNCTIONS`.
   - Record executable lines via `FileLinesContext` (`EXECUTABLE_LINES_DATA`).

This is the seam where the engine's `AstScannerResult` becomes SonarQube data.

## 5. Rules & profile

- `PlSqlRuleRepository` + the `rules/SonarQubeRule*` adapters surface ZPA's annotation-defined rules (keys, params, HTML descriptions, remediation) to SonarQube.
- `PlSqlProfile` defines the default "Sonar way"-style profile from `@ActivatedByDefault` rules.

## 6. utPLSQL integration

`UtPlSqlSensor` (with `TestResultImporter`, `CoverageResultImporter`, and the `*Report` models) imports external utPLSQL execution and coverage reports so unit-test results and coverage appear in SonarQube alongside static-analysis findings.

## 7. Dependencies

Depends on `zpa-core` and `zpa-checks`, plus the SonarQube `sonar-plugin-api`. Packaged as a SonarQube plugin JAR whose manifest points to `PlSqlPlugin` as the entry class.
