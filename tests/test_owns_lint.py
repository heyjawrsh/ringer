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


if __name__ == "__main__":
    unittest.main()
