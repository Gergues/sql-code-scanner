"""Tests for the high-level PlSqlAnalyzer library facade."""

from __future__ import annotations

from pyzpa import PlSqlAnalyzer, ScanResult, Severity


def test_analyze_source_returns_issues():
    analyzer = PlSqlAnalyzer()
    result = analyzer.analyze_source("BEGIN\n  IF x = NULL THEN NULL; END IF;\nEND;\n")
    assert isinstance(result, ScanResult)
    assert any(i.rule_key == "ComparisonWithNull" for i in result.issues)


def test_only_selected_check_runs():
    analyzer = PlSqlAnalyzer(checks=["SelectAllColumns"])
    keys = {c.rule_key for c in analyzer.checks}
    assert keys == {"SelectAllColumns"}

    result = analyzer.analyze_source("BEGIN\n  IF x = NULL THEN NULL; END IF;\nEND;\n")
    assert result.issues == []  # ComparisonWithNull not selected


def test_disabled_check_is_skipped():
    analyzer = PlSqlAnalyzer(disabled=["ComparisonWithNull"])
    keys = {c.rule_key for c in analyzer.checks}
    assert "ComparisonWithNull" not in keys


def test_has_failures_respects_fail_on():
    src = "BEGIN\n  SELECT * INTO v FROM t;\nEND;\n"  # SelectAllColumns = MINOR

    strict = PlSqlAnalyzer(fail_on=Severity.MINOR)
    lenient = PlSqlAnalyzer(fail_on="MAJOR")

    results = strict.analyze_source(src)
    assert strict.has_failures([results]) is True
    assert lenient.has_failures([results]) is False


def test_analyze_paths_and_format(tmp_path):
    (tmp_path / "a.sql").write_text("BEGIN\n  SELECT * INTO v FROM t;\nEND;\n", "utf-8")
    (tmp_path / "skip.txt").write_text("not sql", "utf-8")

    analyzer = PlSqlAnalyzer()
    results = analyzer.analyze_paths([tmp_path])
    assert len(results) == 1

    text = analyzer.format(results, "text")
    assert "SelectAllColumns" in text

    import json

    payload = json.loads(analyzer.format(results, "json"))
    assert payload["files"][0]["issues"]


def test_available_checks_lists_builtins():
    keys = {c.rule_key for c in PlSqlAnalyzer.available_checks()}
    assert {"ComparisonWithNull", "SelectAllColumns", "EmptyBlock", "TodoComment"} <= keys
