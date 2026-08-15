#!/usr/bin/env python3
"""Validate an adversarial review report with structured findings."""

from __future__ import annotations

import argparse
import pathlib
import re
import sys


REQUIRED_LABELS = ["Finding", "Evidence", "Impact", "Fix", "Priority", "Confidence"]
LABEL_PREFIX = (
    r"^[ \t]*(?:>[ \t]*)?(?:#{1,6}[ \t]*)?(?:[-*+][ \t]*)?"
    r"(?:\d+[.)][ \t]*)?(?:\*\*|__)?"
)
VALUE_DECORATION = r"[ \t]*(?:(?:\*{1,2}|_{1,2})[ \t]*)*"


def label_pattern(label: str) -> re.Pattern[str]:
    """Match a line-start label in ordinary Markdown dress."""
    return re.compile(
        LABEL_PREFIX + rf"{re.escape(label)}(?:\*\*|__)?[ \t]*:",
        re.IGNORECASE | re.MULTILINE,
    )


def label_value_pattern(label: str, value: str) -> re.Pattern[str]:
    """Match a labeled value, allowing emphasis to close after the colon."""
    return re.compile(
        label_pattern(label).pattern + VALUE_DECORATION + rf"(?:{value})\b",
        re.IGNORECASE | re.MULTILINE,
    )


FINDING_PATTERN = label_pattern("Finding")
GENERIC_LABEL_PATTERN = re.compile(
    LABEL_PREFIX + r"[A-Za-z][A-Za-z ]*(?:\*\*|__)?[ \t]*:",
    re.IGNORECASE | re.MULTILINE,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="report.md")
    args = parser.parse_args()

    path = pathlib.Path(args.file)
    if not path.exists():
        print(f"FAIL: {path} not found")
        return 1
    text = path.read_text(encoding="utf-8", errors="replace")
    fails: list[str] = []

    if not re.search(r"(?im)^#+\s*summary\b", text):
        fails.append("missing ## Summary section")

    finding_matches = list(FINDING_PATTERN.finditer(text))
    finding_blocks = [
        text[match.start() : finding_matches[index + 1].start()]
        if index + 1 < len(finding_matches)
        else text[match.start() :]
        for index, match in enumerate(finding_matches)
    ]
    finding_count = len(finding_blocks)
    no_findings = bool(re.search(r"(?i)\bNO FINDINGS\b", text))

    if finding_count == 0 and not no_findings:
        fails.append("report must contain NO FINDINGS or at least one Finding: block")

    for index, block_text in enumerate(finding_blocks, start=1):
        for label in REQUIRED_LABELS:
            if not label_pattern(label).search(block_text):
                fails.append(f"finding {index}: missing {label}: label")
        priority = label_value_pattern("Priority", r"P[0-3]").search(block_text)
        if not priority:
            fails.append(f"finding {index}: Priority must be P0, P1, P2, or P3")
        confidence = label_value_pattern("Confidence", r"high|medium|low").search(block_text)
        if not confidence:
            fails.append(f"finding {index}: Confidence must be high, medium, or low")
        evidence = label_pattern("Evidence").search(block_text)
        if evidence:
            next_label = GENERIC_LABEL_PATTERN.search(block_text, evidence.end())
            value_end = next_label.start() if next_label else len(block_text)
            evidence_value = block_text[evidence.end() : value_end]
            evidence_value = re.sub(r"^" + VALUE_DECORATION, "", evidence_value)
            evidence_value = re.sub(r"(?:\*{1,2}|_{1,2})[ \t]*$", "", evidence_value.strip())
            if len(evidence_value.strip()) < 20:
                fails.append(
                    f"finding {index}: Evidence is too thin; cite a file, route, log, or reproduction detail"
                )

    if re.search(r"(?i)\b(i\s+(fixed|patched|committed|pushed|modified)|patched\s+the|committed\s+the|pushed\s+the)\b", text):
        fails.append("reviewer appears to claim it changed files; reviewers must not fix")

    if fails:
        print("FAIL:")
        for fail in fails:
            print(f" - {fail}")
        return 1
    if no_findings and finding_count == 0:
        print("PASS: explicit no-findings report with summary")
    else:
        print(f"PASS: {finding_count} structured finding block(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
