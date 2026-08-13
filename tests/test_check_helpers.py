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
    assert_runs,
    assert_section,
    normalize,
)


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


if __name__ == "__main__":
    unittest.main()
