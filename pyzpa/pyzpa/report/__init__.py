"""Report writers for scan results."""

from __future__ import annotations

from pyzpa.report.csv_writer import write_csv
from pyzpa.report.json_writer import write_json
from pyzpa.report.sarif_writer import write_sarif
from pyzpa.report.text_writer import write_text

WRITERS = {
    "text": write_text,
    "json": write_json,
    "csv": write_csv,
    "sarif": write_sarif,
}

__all__ = ["WRITERS", "write_text", "write_json", "write_csv", "write_sarif"]
