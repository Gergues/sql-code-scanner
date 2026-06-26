"""SARIF 2.1.0 report writer."""

from __future__ import annotations

import json
from collections.abc import Iterable

from pyzpa import __version__
from pyzpa.analysis.scanner import ScanResult
from pyzpa.api.issue import Severity
from pyzpa.registry import discover_check_classes

_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

# Map our severities onto SARIF result levels.
_LEVEL = {
    Severity.INFO: "note",
    Severity.MINOR: "warning",
    Severity.MAJOR: "warning",
    Severity.CRITICAL: "error",
    Severity.BLOCKER: "error",
}


def write_sarif(results: Iterable[ScanResult]) -> str:
    results = list(results)
    rules, rule_index = _rules()

    sarif_results = []
    for result in results:
        uri = result.file.path.replace("\\", "/")
        for issue in result.issues:
            sarif_results.append(_result_entry(issue, uri, rule_index))

    log = {
        "version": "2.1.0",
        "$schema": _SCHEMA,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "pyzpa",
                        "informationUri": "https://github.com/pyzpa/pyzpa",
                        "version": __version__,
                        "rules": rules,
                    }
                },
                "results": sarif_results,
            }
        ],
    }
    return json.dumps(log, indent=2)


def _rules() -> tuple[list[dict], dict[str, int]]:
    rules: list[dict] = []
    index: dict[str, int] = {}
    for cls in discover_check_classes():
        index[cls.rule_key] = len(rules)
        rules.append(
            {
                "id": cls.rule_key,
                "name": cls.rule_key,
                "shortDescription": {"text": cls.rule_name},
                "fullDescription": {"text": cls.rule_description or cls.rule_name},
                "defaultConfiguration": {
                    "level": _LEVEL.get(cls.rule_priority, "warning")
                },
                "properties": {"tags": list(cls.rule_tags)},
            }
        )
    return rules, index


def _result_entry(issue, uri: str, rule_index: dict[str, int]) -> dict:
    loc = issue.location
    entry = {
        "ruleId": issue.rule_key,
        "level": _LEVEL.get(Severity(issue.severity), "warning"),
        "message": {"text": issue.message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": uri},
                    "region": {
                        "startLine": max(loc.line, 1),
                        "startColumn": loc.column + 1,
                    },
                }
            }
        ],
    }
    if issue.rule_key in rule_index:
        entry["ruleIndex"] = rule_index[issue.rule_key]
    region = entry["locations"][0]["physicalLocation"]["region"]
    if loc.end_line:
        region["endLine"] = loc.end_line
        region["endColumn"] = loc.end_column + 1
    return entry
