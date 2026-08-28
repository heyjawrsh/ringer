#!/usr/bin/env python3
"""The `preflight` CLI binds all four no-worker proof stages into one verdict."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def toml_string(value: object) -> str:
    return json.dumps(str(value))


class PreflightCommandTests(unittest.TestCase):
    def sound_task(self, *, key: str = "sound-artifact") -> dict[str, object]:
        return {
            "key": key,
            "engine": "missing",
            "spec": (
                "Create artifact.txt in the task directory with exactly one line containing "
                "ready, keep the change scoped to that deliverable, and preserve the manifest."
            ),
            "known_bad": "printf 'broken\\n' > artifact.txt",
            "known_good": "printf 'ready\\n' > artifact.txt",
            "check": (
                "grep -q '^ready$' artifact.txt || "
                "{ echo 'FAIL: artifact.txt is missing or does not contain ready'; exit 1; }"
            ),
            "expect_files": ["artifact.txt"],
            "verified": "artifact.txt exists and contains exactly the required ready line",
        }

    def prepare_fixture(
        self, root: Path, tasks: list[dict[str, object]]
    ) -> dict[str, object]:
        home = root / "home"
        ringer_home = root / "ringer-home"
        state_dir = root / "state"
        workdir = root / "work"
        config_path = root / "config.toml"
        manifest_path = root / "manifest.json"
        model_log = root / "runs.jsonl"

        home.mkdir()
        ringer_home.mkdir()
        config_path.write_text(
            "\n".join(
                [
                    f"state_dir = {toml_string(state_dir)}",
                    "",
                    "[eval]",
                    'backend = "jsonl"',
                    f"jsonl_path = {toml_string(model_log)}",
                    "",
                    "[artifact]",
                    "enabled = false",
                    "",
                    "[engines.missing]",
                    'bin = "/nonexistent/engine-binary"',
                    "args_template = [",
                    '  "{spec}",',
                    "]",
                    "sandbox_args = []",
                    "full_access_args = []",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        manifest_path.write_text(
            json.dumps(
                {
                    "run_name": "preflight-command-test",
                    "workdir": str(workdir),
                    "max_parallel": 1,
                    "worktrees": False,
                    "tasks": tasks,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(home),
                "RINGER_HOME": str(ringer_home),
                "XDG_CONFIG_HOME": str(root / "xdg-config"),
                "RINGER_NO_SELF_UPDATE": "1",
            }
        )
        return {
            "config": config_path,
            "env": env,
            "manifest": manifest_path,
            "model_log": model_log,
            "state_dir": state_dir,
            "workdir": workdir,
        }

    def run_ringer(
        self, fixture: dict[str, object], *args: str
    ) -> subprocess.CompletedProcess[str]:
        config_path = fixture["config"]
        env = fixture["env"]
        self.assertIsInstance(config_path, Path)
        self.assertIsInstance(env, dict)
        return subprocess.run(
            [
                sys.executable,
                "ringer.py",
                *args,
                "--config",
                str(config_path),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )

    def test_preflight_clean_manifest_passes_and_receipt_is_invalidated_by_edit(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            fixture = self.prepare_fixture(Path(temp_root), [self.sound_task()])
            manifest_path = fixture["manifest"]
            state_dir = fixture["state_dir"]
            model_log = fixture["model_log"]
            workdir = fixture["workdir"]
            assert isinstance(manifest_path, Path)
            assert isinstance(state_dir, Path)
            assert isinstance(model_log, Path)
            assert isinstance(workdir, Path)

            proc = self.run_ringer(fixture, "preflight", str(manifest_path))
            output = proc.stdout + proc.stderr

            self.assertEqual(0, proc.returncode, output)
            self.assertIn("Preflight verdict: PASS.", output)
            stage_positions = [
                output.index(f"Stage {number}/4: {stage}")
                for number, stage in enumerate(
                    ("lint", "baseline", "prove-fail", "prove-pass"), start=1
                )
            ]
            self.assertEqual(sorted(stage_positions), stage_positions, output)
            self.assertRegex(
                output,
                re.compile(
                    r"^sound-artifact[ \t]+covered: known_bad[ \t]+"
                    r"covered: known_good[ \t]+YES[ \t]*$",
                    re.MULTILINE,
                ),
                output,
            )
            receipts = list((state_dir / "preflight" / "receipts").glob("*.json"))
            self.assertEqual(1, len(receipts), output)
            receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
            self.assertEqual(
                ["lint", "baseline", "prove-fail", "prove-pass"], receipt["stages"]
            )
            self.assertEqual(["sound-artifact"], receipt["tasks"])
            self.assertFalse(model_log.exists(), "preflight spawned a worker")
            self.assertFalse(
                (workdir / "sound-artifact").exists(),
                "preflight leaked a task directory into the manifest workdir",
            )

            manifest_path.write_text(
                manifest_path.read_text(encoding="utf-8") + "\n", encoding="utf-8"
            )
            after_edit = self.run_ringer(
                fixture,
                "run",
                str(manifest_path),
                "--no-dashboard",
                "--baseline",
            )
            edited_output = after_edit.stdout + after_edit.stderr

            self.assertEqual(0, after_edit.returncode, edited_output)
            self.assertIn("preflighted at a different version", edited_output)
            self.assertIn("the current content is not attested", edited_output)

    def test_preflight_check_that_cannot_run_exits_nonzero_and_names_baseline(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            task = self.sound_task(key="crashed-check")
            task["check"] = (
                "definitely_missing_preflight_check || "
                "{ echo 'required verifier command is unavailable'; exit 127; }"
            )
            fixture = self.prepare_fixture(Path(temp_root), [task])
            manifest_path = fixture["manifest"]
            assert isinstance(manifest_path, Path)

            proc = self.run_ringer(fixture, "preflight", str(manifest_path))
            output = proc.stdout + proc.stderr

            self.assertNotEqual(0, proc.returncode, output)
            self.assertRegex(
                output,
                re.compile(r"^crashed-check\s+baseline: CRASHED", re.MULTILINE),
                output,
            )
            self.assertIn("Preflight verdict: FAIL at baseline.", output)
            self.assertIn("No receipt was written.", output)

    def test_preflight_coverage_gap_is_reported_against_the_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            task = self.sound_task(key="missing-pass-proof")
            del task["known_good"]
            fixture = self.prepare_fixture(Path(temp_root), [task])
            manifest_path = fixture["manifest"]
            assert isinstance(manifest_path, Path)

            proc = self.run_ringer(fixture, "preflight", str(manifest_path))
            output = proc.stdout + proc.stderr

            self.assertNotEqual(0, proc.returncode, output)
            self.assertRegex(
                output,
                re.compile(
                    r"^missing-pass-proof[ \t]+covered: known_bad[ \t]+"
                    r"GAP: no known_good[ \t]+NO[ \t]*$",
                    re.MULTILINE,
                ),
                output,
            )
            self.assertIn("Preflight verdict: FAIL at lint.", output)

    def test_preflight_run_reports_missing_receipt_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            fixture = self.prepare_fixture(Path(temp_root), [self.sound_task()])
            manifest_path = fixture["manifest"]
            state_dir = fixture["state_dir"]
            model_log = fixture["model_log"]
            assert isinstance(manifest_path, Path)
            assert isinstance(state_dir, Path)
            assert isinstance(model_log, Path)

            proc = self.run_ringer(
                fixture,
                "run",
                str(manifest_path),
                "--no-dashboard",
                "--baseline",
            )
            output = proc.stdout + proc.stderr

            self.assertEqual(0, proc.returncode, output)
            self.assertIn("this manifest has never been preflighted", output)
            self.assertIn("baseline: 0 pass, 1 fail, 0 error of 1 check(s)", output)
            self.assertFalse((state_dir / "preflight").exists())
            self.assertFalse(model_log.exists(), "receipt notice spawned a worker")


if __name__ == "__main__":
    unittest.main(verbosity=2)
