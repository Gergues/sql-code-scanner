"""CLI integration tests."""

from __future__ import annotations

from pathlib import Path

from pyzpa.cli import EXIT_FINDINGS, EXIT_OK, main


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_scan_reports_findings(tmp_path, capsys):
    src = _write(tmp_path, "a.sql", "BEGIN\n  IF x = NULL THEN NULL; END IF;\nEND;\n")
    out_file = tmp_path / "out.csv"
    code = main(["scan", str(src), "--output", str(out_file)])
    out = capsys.readouterr().out
    assert code == EXIT_FINDINGS
    assert f"report written to {out_file}" in out
    assert "ComparisonWithNull" in out_file.read_text(encoding="utf-8")


def test_scan_stdout(tmp_path, capsys):
    src = _write(tmp_path, "a.sql", "BEGIN\n  IF x = NULL THEN NULL; END IF;\nEND;\n")
    code = main(["scan", str(src), "--output", "-"])
    out = capsys.readouterr().out
    assert code == EXIT_FINDINGS
    assert "ComparisonWithNull" in out


def test_scan_default_timestamped_file(tmp_path, monkeypatch, capsys):
    src = _write(tmp_path, "a.sql", "BEGIN\n  IF x = NULL THEN NULL; END IF;\nEND;\n")
    monkeypatch.chdir(tmp_path)
    code = main(["scan", str(src)])
    out = capsys.readouterr().out
    assert code == EXIT_FINDINGS
    reports = list(tmp_path.glob("report_*.csv"))
    assert len(reports) == 1
    assert reports[0].name in out
    assert "ComparisonWithNull" in reports[0].read_text(encoding="utf-8")


def test_scan_clean_file(tmp_path, capsys):
    src = _write(tmp_path, "b.sql", "BEGIN\n  do_work();\nEND;\n")
    code = main(["scan", str(src), "--output", str(tmp_path / "clean.csv")])
    assert code == EXIT_OK


def test_list_checks(capsys):
    code = main(["list-checks"])
    out = capsys.readouterr().out
    assert code == EXIT_OK
    assert "ComparisonWithNull" in out


def test_parse_command(tmp_path, capsys):
    src = _write(tmp_path, "c.sql", "BEGIN NULL; END;\n")
    code = main(["parse", str(src)])
    out = capsys.readouterr().out
    assert code == EXIT_OK
    assert "anonymous_block" in out
