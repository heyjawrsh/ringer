#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ringer import Manifest  # noqa: E402


class StrictManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ringer-manifest-strict-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def manifest_obj(self, **overrides: object) -> dict[str, object]:
        manifest: dict[str, object] = {
            "run_name": "strict-manifest-test",
            "workdir": str(self.root / "work"),
            "max_parallel": 2,
            "worktrees": False,
            "tasks": [
                {
                    "key": "alpha",
                    "spec": "Create alpha.txt.",
                    "check": "test -s alpha.txt",
                    "expect_files": ["alpha.txt"],
                }
            ],
        }
        manifest.update(overrides)
        return manifest

    def test_unknown_run_field_is_rejected_and_named(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown field 'max_paralell'"):
            Manifest.from_obj(self.manifest_obj(max_paralell=4))

    def test_unknown_task_field_is_rejected_named_and_located(self) -> None:
        tasks = list(self.manifest_obj()["tasks"])
        tasks.extend(
            [
                {"key": "bravo", "spec": "Work.", "check": "true"},
                {
                    "key": "charlie",
                    "spec": "Work.",
                    "check": "true",
                    "own": ["ringer.py"],
                },
            ]
        )
        with self.assertRaisesRegex(ValueError, r"tasks\[2\]: unknown field 'own'"):
            Manifest.from_obj(self.manifest_obj(tasks=tasks))

    def test_quoted_booleans_are_rejected(self) -> None:
        with self.subTest(field="worktrees"), self.assertRaisesRegex(
            ValueError, "worktrees must be true or false"
        ):
            Manifest.from_obj(self.manifest_obj(worktrees="false"))

        task = {
            "key": "alpha",
            "spec": "Work.",
            "check": "true",
            "full_access": "false",
        }
        with self.subTest(field="full_access"), self.assertRaisesRegex(
            ValueError, "full_access must be true or false"
        ):
            Manifest.from_obj(self.manifest_obj(tasks=[task]))

    def test_worktrees_requires_repo(self) -> None:
        with self.assertRaisesRegex(ValueError, "worktrees true requires repo"):
            Manifest.from_obj(self.manifest_obj(worktrees=True))

    def test_extension_keys_are_accepted_at_both_levels(self) -> None:
        task = {
            "key": "alpha",
            "spec": "Work.",
            "check": "true",
            "x-ticket": "RNG-42",
        }
        manifest = Manifest.from_obj(
            self.manifest_obj(tasks=[task], **{"x-job-metadata": {"owner": "qa"}})
        )

        self.assertEqual("alpha", manifest.tasks[0].key)

    def test_valid_manifest_still_parses(self) -> None:
        manifest = Manifest.from_obj(self.manifest_obj())

        self.assertEqual("strict-manifest-test", manifest.run_name)
        self.assertEqual(2, manifest.max_parallel)
        self.assertFalse(manifest.worktrees)

    def test_every_shipped_template_loads(self) -> None:
        template_paths = sorted((ROOT / "templates").rglob("manifest*.json"))
        self.assertEqual(19, len(template_paths))
        for path in template_paths:
            with self.subTest(template=path.relative_to(ROOT)):
                data = json.loads(path.read_text(encoding="utf-8"))
                Manifest.from_obj(data)


if __name__ == "__main__":
    unittest.main()
