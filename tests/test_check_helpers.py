#!/usr/bin/env python3
"""Tests for reusable check-script helpers."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from check_helpers import (  # noqa: E402
    assert_contains,
    assert_json_valid,
    assert_labeled_blocks,
    assert_runs,
    assert_section,
    assert_verbatim_quotes,
    count_labels,
    extract_quoted_spans,
    normalize,
)


SOURCE_DOC = """
# AI classification architecture

The partial unique index classification_runs_one_live on the constant
expression ((1)) enforces the single-live-run invariant for this schema.
Deleting a target cascades through dimension states to both value tables.
"""

GOOD_REPORT = """
## Summary
Three defects, all in the index prose.

### Finding: the index claim needs its scope stated
- Evidence: "enforces  the single-live-run  invariant for this schema"
**Priority:** P0
Confidence: high

### Finding: cascade wording is ambiguous
- Evidence: `Deleting a target cascades through dimension states to both value tables`
**Priority:** P2
Confidence: medium

### Finding: the constant expression deserves a note
- Evidence:
```
The partial unique index classification_runs_one_live ...
enforces the single-live-run invariant
```
**Priority:** P3
Confidence: low
"""


class CheckHelpersTests(unittest.TestCase):
    def failure_output(self, function: Callable[..., object], *args: object) -> str:
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            function(*args)
        self.assertNotEqual(0, raised.exception.code)
        return output.getvalue()

    def test_normalize_collapses_unusual_whitespace(self) -> None:
        self.assertEqual("alpha beta gamma", normalize("  alpha\u00a0beta\n\t gamma  "))

    def test_assert_section_accepts_formatting_variation(self) -> None:
        assert_section("# Intro\n## **RELEASE\u00a0NOTES:**\nDetails", "release notes")

    def test_assert_section_names_missing_section_and_found_headings(self) -> None:
        output = self.failure_output(assert_section, "# Introduction\n## Results", "Methods")

        self.assertIn("CHECK FAIL:", output)
        self.assertIn("Methods", output)
        self.assertIn("Introduction", output)
        self.assertIn("Results", output)

    def test_assert_contains_passes_and_fails_symmetrically(self) -> None:
        assert_contains("Ready\u00a0for   REVIEW", "ready for review")

        output = self.failure_output(assert_contains, "Ready for review", "approved")
        self.assertIn("approved", output)
        self.assertIn("Ready for review", output)

    def test_assert_runs_succeeds(self) -> None:
        output = assert_runs([sys.executable, "-c", "print('ready')"])

        self.assertEqual("ready\n", output)

    def test_assert_runs_fails_loudly(self) -> None:
        output = self.failure_output(
            assert_runs,
            [sys.executable, "-c", "print('broken'); raise SystemExit(7)"],
        )

        self.assertIn("exit status: 7", output)
        self.assertIn("broken", output)
        self.assertIn(sys.executable, output)

    def test_assert_json_valid_accepts_good_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "good.json"
            expected = {"ready": True, "count": 2}
            path.write_text(json.dumps(expected), encoding="utf-8")

            self.assertEqual(expected, assert_json_valid(path))

    def test_assert_json_valid_reports_parser_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.json"
            path.write_text('{"ready": true,}', encoding="utf-8")

            output = self.failure_output(assert_json_valid, path)

        self.assertIn(str(path), output)
        self.assertIn("Expecting property name enclosed in double quotes", output)
        self.assertRegex(output, r"line 1 column \d+")


class LabeledBlockTests(unittest.TestCase):
    def failure_output(self, function: Callable[..., object], *args: object, **kwargs: object) -> str:
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            function(*args, **kwargs)
        self.assertNotEqual(0, raised.exception.code)
        return output.getvalue()

    def test_count_labels_accepts_every_ordinary_markdown_dress(self) -> None:
        # A real run failed only because a hand-rolled prefix accepted
        # "Finding:", "- Finding:" and "**Finding:**" but not "### Finding:".
        # The model picked the heading and an honest 10-finding review was
        # rejected as having none.
        report = "\n".join(
            [
                "Finding: plain",
                "- Finding: bulleted",
                "* Finding: starred",
                "1. Finding: numbered",
                "**Finding:** bolded",
                "### Finding: heading",
                "> Finding: quoted",
            ]
        )

        self.assertEqual(7, count_labels(report, "Finding"))

    def test_count_labels_ignores_the_word_used_in_prose(self) -> None:
        self.assertEqual(0, count_labels("The finding above is unproven.", "Finding"))

    def test_assert_labeled_blocks_returns_the_block_count(self) -> None:
        blocks = assert_labeled_blocks(
            GOOD_REPORT,
            ("Finding", "Evidence", "Priority", "Confidence"),
            values={"Priority": r"P[0-3]", "Confidence": r"high|medium|low"},
        )

        self.assertEqual(3, blocks)

    def test_assert_labeled_blocks_names_the_label_that_is_short(self) -> None:
        report = "### Finding: one\nEvidence: only here\n### Finding: two\n"

        output = self.failure_output(
            assert_labeled_blocks, report, ("Finding", "Evidence")
        )

        self.assertIn("2 'Finding' block(s) but only 1 'Evidence' label(s)", output)

    def test_assert_labeled_blocks_rejects_an_out_of_range_value(self) -> None:
        report = "Finding: one\nEvidence: here\nPriority: P7\n"

        output = self.failure_output(
            assert_labeled_blocks,
            report,
            ("Finding", "Evidence", "Priority"),
            values={"Priority": r"P[0-3]"},
        )

        self.assertIn("only 0 valid 'Priority' value(s)", output)
        self.assertIn("P[0-3]", output)

    def test_assert_labeled_blocks_enforces_a_minimum(self) -> None:
        output = self.failure_output(
            assert_labeled_blocks, "## Summary\nNothing to report.", ("Finding",)
        )

        self.assertIn("found 0 'Finding' block(s); at least 1 required", output)


class VerbatimQuoteTests(unittest.TestCase):
    def failure_output(self, function: Callable[..., object], *args: object, **kwargs: object) -> str:
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            function(*args, **kwargs)
        self.assertNotEqual(0, raised.exception.code)
        return output.getvalue()

    def test_extract_quoted_spans_skips_short_spans(self) -> None:
        spans = extract_quoted_spans('Use `x` and "ok" and `a span long enough to be evidence`')

        self.assertEqual(["a span long enough to be evidence"], spans)

    def test_accepts_wrapping_spacing_and_ellipsis(self) -> None:
        matched, unmatched = assert_verbatim_quotes(GOOD_REPORT, SOURCE_DOC)

        self.assertEqual(3, len(matched))
        self.assertEqual([], unmatched)

    def test_rejects_plausible_paraphrase(self) -> None:
        # The gate's whole purpose: paraphrase reads true and cites nothing.
        paraphrased = GOOD_REPORT.replace("enforces", "guarantees").replace(
            "cascades through dimension states", "propagates across dimension rows"
        )

        output = self.failure_output(assert_verbatim_quotes, paraphrased, SOURCE_DOC)

        self.assertIn("appear verbatim in the source", output)
        self.assertIn("guarantees the single-live-run invariant", output)

    def test_unmatched_spans_are_reported_not_fatal(self) -> None:
        report = GOOD_REPORT + '\nFix: `add a NOT NULL constraint to the proposal column`\n'

        matched, unmatched = assert_verbatim_quotes(report, SOURCE_DOC)

        self.assertEqual(3, len(matched))
        self.assertEqual(["add a NOT NULL constraint to the proposal column"], unmatched)


if __name__ == "__main__":
    unittest.main()
