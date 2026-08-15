#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from ringer import Manifest


ROOT = Path(__file__).resolve().parents[1]
RINGER_PATH = ROOT / "ringer.py"


class UnattendedRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ringer-unattended-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workdir = self.root / "work"
        self.manifest_path = self.root / "manifest.json"
        self.config_path = self.root / "config.toml"
        self.config_path.write_text(
            "\n".join(
                [
                    f"state_dir = {json.dumps(str(self.root / 'state'))}",
                    "",
                    "[artifact]",
                    "enabled = false",
                    "",
                    "[eval]",
                    'backend = "jsonl"',
                    f"jsonl_path = {json.dumps(str(self.root / 'runs.jsonl'))}",
                    "",
                    "[engines.fixture]",
                    'bin = "/bin/sh"',
                    f"args_template = {json.dumps(['-c', '{spec}'])}",
                    "sandbox_args = []",
                    "full_access_args = []",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    @staticmethod
    def task(key: str, spec: str, check: str) -> dict[str, Any]:
        return {
            "key": key,
            "engine": "fixture",
            "spec": spec,
            "check": check,
            "max_attempts": 1,
        }

    def run_manifest(
        self,
        tasks: list[dict[str, Any]],
        **run_fields: Any,
    ) -> subprocess.CompletedProcess[str]:
        manifest = {
            "run_name": "unattended-test",
            "workdir": str(self.workdir),
            "max_parallel": 1,
            "worktrees": False,
            "tasks": tasks,
            **run_fields,
        }
        self.manifest_path.write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(self.root / "home"),
                "RINGER_HOME": str(self.root / "ringer-home"),
                "XDG_CONFIG_HOME": str(self.root / "xdg-config"),
                "RINGER_NO_SELF_UPDATE": "1",
                "RINGER_NO_CATALOG_REFRESH": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        return subprocess.run(
            [
                sys.executable,
                str(RINGER_PATH),
                "--config",
                str(self.config_path),
                "run",
                str(self.manifest_path),
                "--no-dashboard",
                "--identity",
                "unattended-test",
            ],
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=15,
        )

    def test_wall_clock_budget_stops_new_tasks_and_reports_them(self) -> None:
        tasks = [
            self.task("slow", "sleep 1.1; touch done", "test -f done"),
            self.task("held-one", "touch done", "test -f done"),
            self.task("held-two", "touch done", "test -f done"),
        ]

        proc = self.run_manifest(tasks, budget_wall_clock_s=1)

        self.assertEqual(0, proc.returncode, proc.stdout)
        self.assertIn("Stop condition fired: budget_wall_clock_s", proc.stdout)
        self.assertIn("2 task(s) will not be started", proc.stdout)
        report = (self.workdir / "RUN_REPORT.md").read_text(encoding="utf-8")
        self.assertIn("wall-clock budget", report)
        self.assertIn("`slow`: passed", report)
        self.assertIn("`held-one`: not started", report)
        self.assertIn("`held-two`: not started", report)
        self.assertIn("Not started: 2", report)

    def test_failure_breaker_stops_after_consecutive_failed_attempts(self) -> None:
        tasks = [
            self.task("f0", "true", "echo first failure; false"),
            self.task("f1", "true", "echo second failure; false"),
            self.task("f2", "touch done", "test -f done"),
            self.task("f3", "touch done", "test -f done"),
        ]

        proc = self.run_manifest(tasks, failure_breaker=2)

        self.assertNotEqual(0, proc.returncode, proc.stdout)
        self.assertIn("Stop condition fired: failure_breaker", proc.stdout)
        self.assertIn("2 task(s) will not be started", proc.stdout)
        self.assertEqual(2, len(re.findall(r"^f\d", proc.stdout, re.MULTILINE)))
        self.assertIn("not started: f2, f3", proc.stdout)
        report = (self.workdir / "RUN_REPORT.md").read_text(encoding="utf-8")
        self.assertIn("failure breaker", report)
        self.assertIn("`f0`: failed", report)
        self.assertIn("`f1`: failed", report)
        self.assertIn("`f2`: not started", report)
        self.assertIn("`f3`: not started", report)
        self.assertIn("Failed: 2", report)

    def test_questions_are_harvested_without_failing_task(self) -> None:
        task = self.task(
            "writer",
            "printf 'Which format should the final export use?\\n' > questions.md; "
            "touch done",
            "test -f done",
        )

        proc = self.run_manifest([task], questions_file="questions.md")

        self.assertEqual(0, proc.returncode, proc.stdout)
        report = (self.workdir / "RUN_REPORT.md").read_text(encoding="utf-8")
        self.assertIn("finished normally", report)
        self.assertIn("`writer`: passed", report)
        self.assertIn("### `writer`", report)
        self.assertIn("Which format should the final export use?", report)

    def test_plain_manifest_writes_no_run_report(self) -> None:
        task = self.task("plain", "touch done", "test -f done")

        proc = self.run_manifest([task])

        self.assertEqual(0, proc.returncode, proc.stdout)
        self.assertFalse((self.workdir / "RUN_REPORT.md").exists())

    def test_run_level_fields_reject_wrong_types_and_nonpositive_limits(self) -> None:
        base = {
            "run_name": "validation-test",
            "workdir": str(self.workdir),
            "max_parallel": 1,
            "tasks": [self.task("plain", "true", "echo failure; false")],
        }
        invalid = {
            "budget_wall_clock_s": "1",
            "failure_breaker": True,
            "questions_file": ["questions.md"],
        }
        for field, value in invalid.items():
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, rf"^{field} must be"
            ):
                Manifest.from_obj({**base, field: value})
        for field in ("budget_wall_clock_s", "failure_breaker"):
            with self.subTest(field=field, value=0), self.assertRaisesRegex(
                ValueError, rf"^{field} must be positive$"
            ):
                Manifest.from_obj({**base, field: 0})


if __name__ == "__main__":
    unittest.main(verbosity=2)
