#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADVERSARIAL = ROOT / "templates/adversarial-review/checks/check_review_report.py"
REVIEW_SWARM = ROOT / "templates/review-swarm/checks/review-swarm.py"
LABELS = ("Finding", "Evidence", "Impact", "Fix", "Priority", "Confidence")
LABEL_LINE = re.compile(rf"^({'|'.join(LABELS)})\s*:", re.IGNORECASE)
CANONICAL_STYLES = ("plain", "heading_3", "bullet_dash", "number_dot", "bold_stars")
EXTRA_STYLES = (
    "heading_1",
    "heading_2",
    "heading_4",
    "heading_5",
    "heading_6",
    "bullet_star",
    "bullet_plus",
    "number_paren",
    "bold_underscores",
    "blockquote",
    "combined",
)

ADVERSARIAL_REPORT = """# Adversarial review

## Summary
One defect in the session store.

Finding: session cookie is not marked Secure
Evidence: src/auth/session.ts:42 builds the cookie with no Secure attribute on any response.
Impact: an attacker sharing the network can read the session cookie and take over the account.
Fix: set Secure and SameSite=Lax when the cookie is constructed.
Priority: P1
Confidence: high
"""

SWARM_REPORT = """# Review Report

## Summary
One defect in the checkout surface.

## Findings
Finding: order total ignores the discount
Evidence: src/cart/total.ts:88 sums the line items before the discount is applied.
Impact: shoppers are charged the undiscounted total at capture time.
Fix: apply the discount before summing the line items.
Priority: P1
Confidence: high

## Clean
Currency formatting, tax rounding.

## Assumptions
Discounts are exclusive, never stacked.
"""


def dress(text: str, style: str) -> str:
    rendered: list[str] = []
    for line in text.splitlines():
        match = LABEL_LINE.match(line)
        if not match:
            rendered.append(line)
            continue
        label = match.group(1)
        value = line[match.end() :]
        if style == "plain":
            rendered.append(line)
        elif style.startswith("heading_"):
            rendered.append("#" * int(style.removeprefix("heading_")) + " " + line)
        elif style == "bullet_dash":
            rendered.append("- " + line)
        elif style == "bullet_star":
            rendered.append("* " + line)
        elif style == "bullet_plus":
            rendered.append("+ " + line)
        elif style == "number_dot":
            rendered.append("1. " + line)
        elif style == "number_paren":
            rendered.append("1) " + line)
        elif style == "bold_stars":
            rendered.append(f"**{label}:**{value}")
        elif style == "bold_underscores":
            rendered.append(f"__{label}:__{value}")
        elif style == "blockquote":
            rendered.append("> " + line)
        elif style == "combined":
            rendered.append(f"> - **{label}:**{value}")
        else:  # pragma: no cover - test setup guards the style list
            raise AssertionError(style)
    return "\n".join(rendered) + "\n"


def without_label(text: str, label: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not re.match(rf"^{label}\s*:", line, re.IGNORECASE)
    ) + "\n"


def replace_value(text: str, label: str, value: str) -> str:
    return re.sub(rf"(?im)^{label}\s*:.*$", f"{label}: {value}", text)


def without_findings(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not LABEL_LINE.match(line)) + "\n"


class KitLabelToleranceTests(unittest.TestCase):
    def run_check(self, kit: str, report: str) -> subprocess.CompletedProcess[str]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "report.md"
        path.write_text(report, encoding="utf-8")
        if kit == "adversarial-review":
            command = [sys.executable, str(ADVERSARIAL), "--file", str(path)]
        elif kit == "review-swarm":
            command = [
                sys.executable,
                str(REVIEW_SWARM),
                "--report",
                str(path),
                "--surface",
                "checkout",
            ]
        else:  # pragma: no cover - test setup guards the kit list
            raise AssertionError(kit)
        return subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def test_valid_reports_accept_all_label_dresses(self) -> None:
        kits = (
            ("adversarial-review", ADVERSARIAL_REPORT),
            ("review-swarm", SWARM_REPORT),
        )
        for kit, report in kits:
            for style in (*CANONICAL_STYLES, *EXTRA_STYLES):
                with self.subTest(kit=kit, style=style):
                    result = self.run_check(kit, dress(report, style))
                    self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_substantive_defects_fail_in_every_canonical_dress(self) -> None:
        defects = (
            ("missing_fix", lambda text: without_label(text, "Fix")),
            ("missing_impact", lambda text: without_label(text, "Impact")),
            ("bad_priority", lambda text: replace_value(text, "Priority", "P7")),
            ("bad_confidence", lambda text: replace_value(text, "Confidence", "probably")),
            ("no_finding_or_verdict", without_findings),
        )
        kits = (
            ("adversarial-review", ADVERSARIAL_REPORT),
            ("review-swarm", SWARM_REPORT),
        )
        for kit, report in kits:
            for style in CANONICAL_STYLES:
                for defect, mutate in defects:
                    with self.subTest(kit=kit, style=style, defect=defect):
                        result = self.run_check(kit, dress(mutate(report), style))
                        self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
