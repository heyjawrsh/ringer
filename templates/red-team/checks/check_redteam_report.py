#!/usr/bin/env python3
"""Validate a red-team report with evidence-backed structured findings."""

from __future__ import annotations

import argparse
import pathlib
import re
import sys


REQUIRED_DETAIL_LABELS = ("Evidence", "Repro", "Impact", "Severity", "Silent")
LABEL_LINE = re.compile(
    r"^\s*(?:(?:>\s*)|(?:#{1,6}\s*)|(?:[-+*]\s+)|(?:\d+[.)]\s+))*"
    r"(?:[*_`]{1,3}\s*)?"
    r"(?P<label>Finding|Evidence|Repro|Impact|Severity|Silent)"
    r"\s*(?:[*_`]{1,3})?\s*:\s*(?:[*_`]{1,3}\s*)?"
    r"(?P<value>.*?)\s*(?:[*_`]{1,3})?\s*$",
    re.IGNORECASE,
)
NO_FINDINGS = re.compile(
    r"^\s*(?:(?:>\s*)|(?:#{1,6}\s*)|(?:[-+*]\s+)|(?:\d+[.)]\s+))*"
    r"(?:[*_`]{1,3}\s*)?(?:verdict\s*:\s*)?NO[\s_-]+FINDINGS\b",
    re.IGNORECASE | re.MULTILINE,
)
EXERCISED_LANGUAGE = re.compile(
    r"\b(exercised|tested|ran|checked|covered|audited|forced|attempted|booted|inspected|verified)\b",
    re.IGNORECASE,
)
ARTIFACT_REFERENCE = re.compile(
    r"(?:"
    r"(?:^|[\s(])(?:\.{0,2}/)?[\w.-]+(?:/[\w.@+,:=-]+)+"
    r"|\b[\w.-]+\.(?:txt|log|out|json|jsonl|csv|tsv|xml|html|har|png|jpe?g|gif|webp|pdf)\b"
    r"|\b(?:log excerpt|command output|terminal output|captured (?:artifact|log|output)|"
    r"screenshot(?: path)?|screen recording|stdout|stderr|traceback|HTTP response|response body)\b"
    r")",
    re.IGNORECASE,
)


def parse_label(line: str) -> tuple[str, str] | None:
    match = LABEL_LINE.match(line)
    if not match:
        return None
    return match.group("label").title(), match.group("value").strip()


def field_value(
    lines: list[str],
    markers: list[tuple[int, str, str]],
    marker_index: int,
    block_end: int,
) -> str:
    line_number, _label, inline_value = markers[marker_index]
    next_line = block_end
    if marker_index + 1 < len(markers):
        next_line = min(next_line, markers[marker_index + 1][0])
    continuation = "\n".join(lines[line_number + 1 : next_line]).strip()
    parts = [part for part in (inline_value, continuation) if part]
    return "\n".join(parts).strip(" \t\r\n*_`")


def validate_report(path: pathlib.Path) -> tuple[list[str], int, bool]:
    if not path.is_file():
        return [f"{path} not found or is not a file"], 0, False

    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return [f"{path} is empty"], 0, False

    lines = text.splitlines()
    markers: list[tuple[int, str, str]] = []
    for line_number, line in enumerate(lines):
        parsed = parse_label(line)
        if parsed:
            markers.append((line_number, parsed[0], parsed[1]))

    finding_marker_indexes = [
        index for index, (_line, label, _value) in enumerate(markers) if label == "Finding"
    ]
    finding_count = len(finding_marker_indexes)
    no_findings = bool(NO_FINDINGS.search(text))
    failures: list[str] = []

    if finding_count == 0 and not no_findings:
        failures.append("report must contain at least one Finding: block or an explicit NO FINDINGS verdict")
        return failures, finding_count, no_findings

    if finding_count and no_findings:
        failures.append("report cannot contain both Finding: blocks and a NO FINDINGS verdict")

    if no_findings and finding_count == 0:
        remainder = NO_FINDINGS.sub("", text)
        visible_remainder = re.sub(r"[\s#*_`>-]+", "", remainder)
        if len(visible_remainder) < 12 or not EXERCISED_LANGUAGE.search(remainder):
            failures.append("NO FINDINGS verdict must say what was exercised")
        return failures, finding_count, no_findings

    for finding_number, finding_marker_index in enumerate(finding_marker_indexes, start=1):
        next_finding_marker_index = (
            finding_marker_indexes[finding_number]
            if finding_number < finding_count
            else len(markers)
        )
        block_end = (
            markers[next_finding_marker_index][0]
            if next_finding_marker_index < len(markers)
            else len(lines)
        )
        block_marker_indexes = range(finding_marker_index, next_finding_marker_index)
        fields: dict[str, tuple[int, str]] = {}
        for marker_index in block_marker_indexes:
            _line_number, label, _inline_value = markers[marker_index]
            fields.setdefault(
                label,
                (marker_index, field_value(lines, markers, marker_index, block_end)),
            )

        finding_value = fields["Finding"][1]
        if not finding_value:
            failures.append(f"finding {finding_number}: Finding: label has no value")

        for label in REQUIRED_DETAIL_LABELS:
            if label not in fields:
                failures.append(f"finding {finding_number}: missing {label}: label")
            elif not fields[label][1]:
                failures.append(f"finding {finding_number}: {label}: label has no value")

        if "Severity" in fields and fields["Severity"][1]:
            severity = fields["Severity"][1].strip()
            if severity.upper() not in {"P0", "P1", "P2", "P3"}:
                failures.append(
                    f"finding {finding_number}: offending Severity value {severity!r}; expected P0, P1, P2, or P3"
                )

        if "Silent" in fields and fields["Silent"][1]:
            silent = fields["Silent"][1].strip()
            if silent.lower() not in {"yes", "no"}:
                failures.append(
                    f"finding {finding_number}: offending Silent value {silent!r}; expected yes or no"
                )

        if "Evidence" in fields and fields["Evidence"][1]:
            evidence = fields["Evidence"][1]
            visible_evidence = re.sub(r"\s+", "", evidence)
            if len(visible_evidence) < 12 or not ARTIFACT_REFERENCE.search(evidence):
                failures.append(
                    f"finding {finding_number}: Evidence must point to a captured artifact such as a log excerpt, screenshot path, or command output"
                )

    return failures, finding_count, no_findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default="report.md")
    args = parser.parse_args()

    path = pathlib.Path(args.file)
    failures, finding_count, no_findings = validate_report(path)
    if failures:
        print("FAIL:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    if no_findings:
        print("PASS: explicit no-findings verdict states what was exercised")
    else:
        print(f"PASS: {finding_count} evidence-backed finding block(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
