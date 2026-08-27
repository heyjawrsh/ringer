#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RINGER_PATH = ROOT / "ringer.py"


class RerunCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ringer-rerun-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state_dir = self.root / "state"
        self.runs_dir = self.state_dir / "runs"
        self.runs_dir.mkdir(parents=True)
        self.eval_log = self.state_dir / "runs.jsonl"
        self.config_path = self.root / "config.toml"
        self.config_path.write_text(
            "\n".join(
                [
                    f'state_dir = {json.dumps(str(self.state_dir))}',
                    "",
                    "[eval]",
                    'backend = "jsonl"',
                    f'jsonl_path = {json.dumps(str(self.eval_log))}',
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def task(self, key: str, **overrides: object) -> dict[str, object]:
        task: dict[str, object] = {
            "key": key,
            "spec": (
                f"Create {key}.txt with the requested content, keep the change "
                "strictly scoped to that deliverable, and do not modify unrelated files."
            ),
            "check": (
                f"test -s {key}.txt || "
                f"{{ echo 'FAIL: {key}.txt is missing or empty'; exit 1; }}"
            ),
            "verified": f"{key}.txt exists and is not empty",
            "expect_files": [f"{key}.txt"],
            "task_type": "code-feature",
        }
        task.update(overrides)
        return task

    def write_manifest(
        self,
        tasks: list[dict[str, object]],
        *,
        name: str = "repair-round",
    ) -> tuple[Path, dict[str, object]]:
        manifest: dict[str, object] = {
            "run_name": name,
            "workdir": str(self.root / "work"),
            "repo": str(self.root / "repo"),
            "worktrees": False,
            "max_parallel": 4,
            "integration_check": "python3 -m unittest discover -s tests",
            "integration_timeout_s": 777,
            "x-job-metadata": {"ticket": "RNG-42", "labels": ["repair"]},
            "tasks": tasks,
        }
        path = self.root / "round.json"
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return path, manifest

    def write_state(
        self,
        run_id: str,
        tasks: list[dict[str, object]],
        *,
        run_name: str = "repair-round",
        started_at: str | None = "2026-08-13T12:00:00+00:00",
    ) -> Path:
        state: dict[str, object] = {
            "run_id": run_id,
            "run_name": run_name,
            "tasks": tasks,
        }
        if started_at is not None:
            state["started_at"] = started_at
        path = self.runs_dir / f"{run_id}.json"
        path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        return path

    def run_rerun(
        self,
        manifest: Path,
        *extra: str,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["RINGER_NO_SELF_UPDATE"] = "1"
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(RINGER_PATH),
                "rerun",
                str(manifest),
                "--config",
                str(self.config_path),
                *extra,
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_selects_every_non_passing_task_and_preserves_all_fields(self) -> None:
        passing = self.task("passing")
        failing = self.task(
            "failing",
            expect_files=["build/report.json", "build/detail.txt"],
            task_type="repair-feature",
            known_bad="printf broken > failing.txt",
            owns=["ringer.py", "tests/test_rerun.py"],
            engine_args=["-c", "model_reasoning_effort=high"],
            timeout_s=321,
            redact_spec=True,
            **{"x-repair-owner": "manifest-team"},
        )
        queued = self.task("held-lane", timeout_s=654)
        absent = self.task("never-spawned")
        manifest_path, manifest = self.write_manifest(
            [passing, failing, queued, absent]
        )
        self.write_state(
            "older-run",
            [{"key": task["key"], "status": "pass"} for task in manifest["tasks"]],
            started_at="2026-08-12T12:00:00+00:00",
        )
        self.write_state(
            "latest-run",
            [
                {"key": "passing", "status": "pass"},
                {
                    "key": "failing",
                    "status": "fail",
                    "check_output_tail": "FAIL: wrong report",
                },
                {"key": "held-lane", "status": "queued"},
            ],
            started_at="2026-08-13T12:00:00+00:00",
        )

        result = self.run_rerun(manifest_path)

        self.assertEqual(0, result.returncode, result.stderr)
        output_path = self.root / "round-repair.json"
        self.assertTrue(output_path.is_file())
        repair = json.loads(output_path.read_text(encoding="utf-8"))
        expected = dict(manifest)
        expected["tasks"] = [failing, queued, absent]
        self.assertEqual(expected, repair)
        self.assertEqual(
            ["failing", "held-lane", "never-spawned"],
            [task["key"] for task in repair["tasks"]],
        )
        self.assertIn(f"Wrote repair manifest: {output_path}", result.stdout)
        self.assertIn("failing (fail)", result.stdout)
        self.assertIn("held-lane (queued)", result.stdout)
        self.assertIn("never-spawned (absent)", result.stdout)

    def test_with_context_changes_only_a_failed_tasks_spec(self) -> None:
        failing = self.task("failing")
        queued = self.task("held-lane")
        manifest_path, _manifest = self.write_manifest([failing, queued])
        failure_output = "FAIL: expected report.json\nactual: file was missing"
        self.write_state(
            "context-run",
            [
                {
                    "key": "failing",
                    "status": "fail",
                    "check_output_tail": failure_output,
                },
                {"key": "held-lane", "status": "queued"},
            ],
        )
        output_path = self.root / "context.json"

        result = self.run_rerun(
            manifest_path,
            "--run",
            "context-run",
            "--with-context",
            "-o",
            str(output_path),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        tasks = json.loads(output_path.read_text(encoding="utf-8"))["tasks"]
        failed_spec = tasks[0]["spec"]
        self.assertTrue(failed_spec.startswith(failing["spec"]))
        self.assertIn("PREVIOUS ATTEMPT FAILED", failed_spec)
        self.assertIn(failure_output, failed_spec)
        self.assertEqual(queued["spec"], tasks[1]["spec"])

    def test_selected_task_without_verified_or_failing_check_is_verbatim(self) -> None:
        task = self.task("failing", check="true")
        task.pop("verified")
        manifest_path, _manifest = self.write_manifest([task])
        self.write_state(
            "legacy-run",
            [{"key": "failing", "status": "fail"}],
        )
        output_path = self.root / "legacy-repair.json"

        result = self.run_rerun(
            manifest_path,
            "--run",
            "legacy-run",
            "-o",
            str(output_path),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        repair_task = json.loads(output_path.read_text(encoding="utf-8"))["tasks"][0]
        source_bytes = json.dumps(task, ensure_ascii=False).encode("utf-8")
        repair_bytes = json.dumps(repair_task, ensure_ascii=False).encode("utf-8")
        self.assertEqual(source_bytes, repair_bytes)
        self.assertNotIn("verified", repair_task)
        self.assertEqual("true", repair_task["check"])

    def test_every_task_passed_exits_nonzero_and_writes_nothing(self) -> None:
        tasks = [self.task("alpha"), self.task("bravo")]
        manifest_path, _manifest = self.write_manifest(tasks)
        state_path = self.write_state(
            "clean-run",
            [{"key": task["key"], "status": "pass"} for task in tasks],
        )
        state_before = state_path.read_bytes()
        output_path = self.root / "should-not-exist.json"

        result = self.run_rerun(
            manifest_path,
            "--run",
            "clean-run",
            "-o",
            str(output_path),
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("Every task passed", result.stdout)
        self.assertIn("no repair manifest was written", result.stdout)
        self.assertFalse(output_path.exists())
        self.assertFalse(self.eval_log.exists())
        self.assertEqual(state_before, state_path.read_bytes())

    def test_default_output_is_beside_source_manifest(self) -> None:
        manifest_path, _manifest = self.write_manifest([self.task("failed")])
        self.write_state("failed-run", [{"key": "failed", "status": "error"}])

        result = self.run_rerun(manifest_path, "--run", "failed-run")

        self.assertEqual(0, result.returncode, result.stderr)
        expected = manifest_path.with_name("round-repair.json")
        self.assertTrue(expected.is_file())
        self.assertIn(str(expected), result.stdout)

    def test_refuses_to_overwrite_source_manifest(self) -> None:
        manifest_path, _manifest = self.write_manifest([self.task("failed")])
        self.write_state("failed-run", [{"key": "failed", "status": "fail"}])
        source_before = manifest_path.read_bytes()

        result = self.run_rerun(
            manifest_path,
            "--run",
            "failed-run",
            "-o",
            str(manifest_path),
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("refusing to overwrite source manifest", result.stderr)
        self.assertEqual(source_before, manifest_path.read_bytes())

    def test_missing_matching_run_names_the_manifest_run(self) -> None:
        manifest_path, _manifest = self.write_manifest([self.task("failed")])
        self.write_state(
            "different-run",
            [{"key": "failed", "status": "fail"}],
            run_name="different-job",
        )

        result = self.run_rerun(manifest_path)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("run_name 'repair-round'", result.stderr)
        self.assertFalse((self.root / "round-repair.json").exists())


if __name__ == "__main__":
    unittest.main()
