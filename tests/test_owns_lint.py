#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ringer import Manifest, lint_manifest  # noqa: E402


class OwnsLintTests(unittest.TestCase):
    def manifest(
        self,
        spec: str,
        *,
        owns: list[str] | None,
        questions_file: str = "",
    ) -> Manifest:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        task: dict[str, object] = {
            "key": "docs-lane",
            "spec": spec,
            "check": "test -s ringer.py || { echo 'FAIL: ringer.py missing'; exit 1; }",
            "expect_files": ["ringer.py"],
            "verified": "ringer.py exists",
            "known_bad": "rm -f ringer.py",
        }
        if owns is not None:
            task["owns"] = owns
        return Manifest.from_obj(
            {
                "run_name": "owns-lint-test",
                "workdir": str(Path(temp_dir.name) / "work"),
                "max_parallel": 1,
                "worktrees": False,
                "questions_file": questions_file,
                "tasks": [task],
            }
        )

    def ownership_findings(self, manifest: Manifest) -> list[str]:
        return [finding for finding in lint_manifest(manifest) if "owns does not cover" in finding]

    def test_reports_instructed_write_outside_owns(self) -> None:
        findings = self.ownership_findings(
            self.manifest("Implement the change. Write ./notes.md with design notes.", owns=["ringer.py"])
        )
        self.assertEqual(
            ["docs-lane: spec instructs the worker to write notes.md, but owns does not cover it."],
            findings,
        )

    def test_granted_write_is_not_reported(self) -> None:
        manifest = self.manifest("Write ./notes.md with design notes.", owns=["*.md"])
        self.assertEqual([], self.ownership_findings(manifest))

    def test_questions_file_is_exempt(self) -> None:
        manifest = self.manifest(
            "If blocked, write ./questions.md.",
            owns=["ringer.py"],
            questions_file="questions.md",
        )
        self.assertEqual([], self.ownership_findings(manifest))

    def test_task_without_owns_is_not_reported(self) -> None:
        manifest = self.manifest("Write ./notes.md with design notes.", owns=None)
        self.assertEqual([], self.ownership_findings(manifest))

    def test_read_only_path_mention_is_not_reported(self) -> None:
        manifest = self.manifest("Read ./notes.md before changing ringer.py.", owns=["ringer.py"])
        self.assertEqual([], self.ownership_findings(manifest))

    def test_forbidding_phrasings_are_not_write_instructions(self) -> None:
        # A path the spec FORBIDS is not one it requests. "must not" and
        # "should not" were both missed originally and flagged files the spec
        # had explicitly told the worker to leave alone; a rule that cries wolf
        # is one people learn to ignore.
        for phrasing in (
            "You must not edit ./docs/A.md",
            "You should not modify ./docs/A.md",
            "You cannot modify ./docs/A.md",
            "You may not write ./docs/A.md",
            "Never write ./docs/A.md",
            "Do not create ./docs/A.md",
            "Avoid ./docs/A.md",
        ):
            with self.subTest(phrasing=phrasing):
                manifest = self.manifest(phrasing, owns=["ringer.py"])
                self.assertEqual([], self.ownership_findings(manifest))

    def test_negation_must_be_adjacent_to_the_verb(self) -> None:
        # "do not forget to write X" IS an instruction to write X. The guard
        # only suppresses a negation sitting immediately before the verb, so
        # this must still be reported.
        manifest = self.manifest(
            "Do not forget to write ./notes.md when you finish.", owns=["ringer.py"]
        )
        findings = self.ownership_findings(manifest)
        self.assertEqual(1, len(findings), findings)
        self.assertIn("notes.md", findings[0])


if __name__ == "__main__":
    unittest.main()
