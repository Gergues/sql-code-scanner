# ZPA — Codebase Overview

> Note: The codebase is primarily **Kotlin**, not Java — only the `plsql-custom-rules` demo module is Java.

## ZPA — Z PL/SQL Analyzer

**Purpose:** ZPA is a parser and static code analysis tool for **PL/SQL and Oracle SQL**. It detects code quality issues, bugs, and style violations in Oracle database code. It integrates primarily with **SonarQube** (an on-premise code quality platform) as a plugin, and can also be used standalone via the separate `zpa-cli` tool.

## How it works

ZPA lexes and parses PL/SQL source into an **AST (Abstract Syntax Tree)** and builds a **symbol table**, then runs a set of coding rules ("checks") against that tree to report issues, metrics, and highlighting back to SonarQube.

## Module breakdown

| Module | Role |
|--------|------|
| `zpa-core` | The heart of the project — the lexer, parser, and the logic to understand/process PL/SQL code. |
| `zpa-checks` | The built-in coding rules shipped with ZPA. |
| `zpa-checks-testkit` | Test helpers for writing and verifying coding rules (usable for custom rules too). |
| `sonar-zpa-plugin` | The SonarQube plugin itself — all integration code with the SonarQube platform. |
| `zpa-toolkit` | A visual desktop tool (requires JDK 11+) to inspect the AST and symbol table the parser generates. |
| `plsql-custom-rules` | A **Java** demo project showing how to extend ZPA with your own custom rules (available as both Gradle and Maven projects). |

## Key facts

- **Language:** Mostly Kotlin (the custom-rules example is Java); built with Gradle (Kotlin DSL).
- **Public API:** Custom rules must use the package `org.sonar.plugins.plsqlopen.api` — a SonarQube requirement. Classes outside it are internal and may change without notice.
- **Compatibility:** ZPA 4.1.0 targets SonarQube 25.8–26.4; 4.2.0 (in development) targets 26.2–26.5.
- **Installation:** Drop the `sonar-zpa-plugin` JAR into `SONARQUBE_HOME/extensions/plugins`, restart SonarQube, then analyze code with SonarScanner.
- **Testing:** Two integration-test suites — one verifies metrics import into SonarQube, the other validates parser/rule quality against real-world code (requires git submodules).
- **License:** LGPL-3.0. The project accepts bug-fix PRs but not new-feature PRs.

In short, ZPA is the analysis engine that lets SonarQube understand and enforce code quality on Oracle PL/SQL codebases, with an extensibility model for adding custom rules.
