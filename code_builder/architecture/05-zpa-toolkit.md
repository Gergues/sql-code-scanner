# zpa-toolkit — Architecture

> A standalone desktop application for visually inspecting the AST (and source) produced by the ZPA parser. Useful when developing grammar or rules.

## 1. Responsibility

Give developers a GUI to parse a PL/SQL snippet/file and explore the resulting abstract syntax tree, with configurable charset and error-recovery settings. It is a debugging/inspection tool, not part of the analysis pipeline.

## 2. Structure

- `com.felipebz.zpa.toolkit.ZpaToolkit` — `main()` entry point. Instantiates the FLR `Toolkit` with a ZPA configuration model and runs it.
- `com.felipebz.zpa.toolkit.ZpaConfigurationModel` — extends FLR's `AbstractConfigurationModel`; supplies the parser and configurable properties.
- `com.felipebz.flr.toolkit.*` and `com.felipebz.flr.internal.toolkit.*` — the vendored FLR Swing toolkit (view, presenter, source-code model/styler, configuration panel). This is a Model-View-Presenter UI built on Java Swing.

## 3. Entry point

```kotlin
fun main() {
    val toolkit = Toolkit("ZPA Toolkit", ZpaConfigurationModel())
    toolkit.run()
}
```

## 4. Configuration model

`ZpaConfigurationModel` exposes two `ConfigurationProperty` values and builds the parser from them:

- **Charset** (`sonar.sourceEncoding`, default `UTF-8`) — validated by `Validators.charsetValidator()`.
- **Error recovery** (`sonar.zpa.errorRecoveryEnabled`, default `true`) — validated by `Validators.booleanValidator()`.

```kotlin
override fun doGetParser(): Parser<Grammar> = PlSqlParser.create(configuration)
```

where `configuration` is a `PlSqlConfiguration(charset, errorRecovery)`. The FLR toolkit framework calls `doGetParser()` to parse the input and renders the resulting AST in its tree view, synchronizing selection with source highlighting via the MVP components (`ToolkitPresenter`, `ToolkitViewImpl`, `SourceCodeModel`, `SourceCodeStyler`).

## 5. UI framework

Pure **Java Swing** (e.g. `NoWrapJTextPane`, `JTextPane`-based source view) wrapped by the FLR toolkit's MVP layer. Requires **JDK 11+** to run.

## 6. Dependencies

Depends on `zpa-core` (for `PlSqlParser` / `PlSqlConfiguration`) and the FLR toolkit. Distributed as a runnable artifact on the releases page.
