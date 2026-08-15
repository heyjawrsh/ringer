#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


MAX_WORDS = 1200
REQUIRED_HEADINGS = ("Summary", "Findings", "Clean", "Assumptions")
FINDING_FIELDS = ("Evidence", "Impact", "Fix", "Priority", "Confidence")
OPEN_PLACEHOLDER = "{" * 2
CLOSE_PLACEHOLDER = "}" * 2
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
ALL_LABELS = ("Finding", *FINDING_FIELDS)
LEVEL_TWO_LABEL_PATTERN = re.compile(
    r"^([ \t]*)##(?=[ \t]*(?:[-*+][ \t]*)?(?:\d+[.)][ \t]*)?"
    rf"(?:\*\*|__)?(?:{'|'.join(ALL_LABELS)})(?:\*\*|__)?[ \t]*:)",
    re.IGNORECASE | re.MULTILINE,
)


def fail(name: str, detail: str) -> str:
    return f"FAIL [{name}]: {detail}"


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def has_heading(text: str, heading: str) -> bool:
    return bool(re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.IGNORECASE | re.MULTILINE))


def section(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def validate_report(path: Path, surface: str) -> list[str]:
    failures: list[str] = []
    if not path.is_file():
        return [fail("missing_report", f"{path} does not exist")]
    if path.stat().st_size == 0:
        return [fail("empty_report", f"{path} is empty")]

    text = path.read_text(encoding="utf-8", errors="replace")
    if word_count(text) > MAX_WORDS:
        failures.append(fail("too_long", f"report has more than {MAX_WORDS} words"))
    if not re.search(r"^#\s+Review Report\s*$", text, re.IGNORECASE | re.MULTILINE):
        failures.append(fail("missing_title", "report must start with '# Review Report'"))
    for heading in REQUIRED_HEADINGS:
        if not has_heading(text, heading):
            failures.append(fail("missing_section", f"missing '## {heading}'"))

    summary = section(text, "Summary")
    summary_lines = [line for line in summary.splitlines() if line.strip()]
    if len(summary_lines) > 3:
        failures.append(fail("summary_too_long", "Summary must be no more than 3 non-empty lines"))

    # A level-two label is valid Markdown dress, but must not be mistaken for
    # the next report section while extracting the Findings body.
    findings_text = LEVEL_TWO_LABEL_PATTERN.sub(r"\1###", text)
    findings = section(findings_text, "Findings")
    if not findings:
        failures.append(fail("missing_findings_body", "Findings section has no content"))
    else:
        finding_matches = list(FINDING_PATTERN.finditer(findings))
        blocks = [
            findings[match.start() : finding_matches[index + 1].start()]
            if index + 1 < len(finding_matches)
            else findings[match.start() :]
            for index, match in enumerate(finding_matches)
        ]
        for index, block in enumerate(blocks, start=1):
            for field in FINDING_FIELDS:
                if not label_pattern(field).search(block):
                    failures.append(fail("finding_missing_field", f"finding {index} is missing {field}:"))
            if label_pattern("Evidence").search(block) and not re.search(r"\b[\w./-]+:\d+\b", block):
                failures.append(fail("finding_missing_line", f"finding {index} evidence should cite file:line"))
            if not label_value_pattern("Priority", r"P[0-3]").search(block):
                failures.append(fail("finding_bad_priority", f"finding {index} priority must be P0, P1, P2, or P3"))
            if not label_value_pattern("Confidence", r"high|medium|low").search(block):
                failures.append(fail("finding_bad_confidence", f"finding {index} confidence must be high, medium, or low"))
        if not blocks and "no findings" not in findings.lower():
            failures.append(
                fail(
                    "findings_not_explicit",
                    "Findings must contain at least one 'Finding:' block or say 'No findings'",
                )
            )

    clean = section(text, "Clean")
    if clean and len([line for line in clean.splitlines() if line.strip()]) < 1:
        failures.append(fail("clean_not_explicit", "Clean section must name reviewed dimensions with no findings"))
    if OPEN_PLACEHOLDER in surface or CLOSE_PLACEHOLDER in surface:
        failures.append(fail("placeholder_unfilled", "surface placeholder was not filled in the check command"))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a review-swarm report contract.")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--surface", required=True)
    args = parser.parse_args()

    failures = validate_report(args.report, args.surface)
    if failures:
        for item in failures:
            print(item)
        return 1
    print(f"PASS [review_contract]: {args.report} is structured and evidence-ready for {args.surface}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
