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


def init_git_repo(path: Path) -> None:
    path.mkdir(parents=True)
    (path / "README.md").write_text("fixture\n", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Ringer Test",
            "GIT_AUTHOR_EMAIL": "ringer-test@example.invalid",
            "GIT_COMMITTER_NAME": "Ringer Test",
            "GIT_COMMITTER_EMAIL": "ringer-test@example.invalid",
        }
    )
    for args in (
        ["git", "-C", str(path), "init", "--quiet"],
        ["git", "-C", str(path), "add", "README.md"],
        [
            "git",
            "-C",
            str(path),
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "fixture",
        ],
    ):
        subprocess.run(args, check=True, env=env, capture_output=True)


class NoSilentLossTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="ringer-no-silent-loss-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.workdir = self.root / "work"
        self.state_dir = self.root / "state"
        self.ringer_home = self.root / "ringer-home"
        self.config_path = self.root / "config.toml"
        self.manifest_path = self.root / "manifest.json"
        init_git_repo(self.repo)

    def write_config(self, script: str) -> None:
        self.config_path.write_text(
            "\n".join(
                [
                    f"state_dir = {json.dumps(str(self.state_dir))}",
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
                    f"args_template = {json.dumps(['-c', script, '{spec}'])}",
                    "sandbox_args = []",
                    "full_access_args = []",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def write_manifest(self, *, expect_files: list[str] | None = None) -> None:
        task: dict[str, object] = {
            "key": "alpha",
            "engine": "fixture",
            "spec": "Run the deterministic shell fixture and leave its output for verification.",
            "check": "test -f findings.md",
            "verified": "The fixture output exists.",
            "max_attempts": 1,
        }
        if expect_files is not None:
            task["expect_files"] = expect_files
        self.manifest_path.write_text(
            json.dumps(
                {
                    "run_name": "no-silent-loss",
                    "workdir": str(self.workdir),
                    "max_parallel": 1,
                    "worktrees": True,
                    "repo": str(self.repo),
                    "tasks": [task],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "RINGER_HOME": str(self.ringer_home),
                "RINGER_NO_SELF_UPDATE": "1",
                "RINGER_NO_CATALOG_REFRESH": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        return subprocess.run(
            [sys.executable, str(RINGER_PATH), "--config", str(self.config_path), *args],
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=30,
        )

    def test_passing_worktree_names_undeclared_file_before_removal(self) -> None:
        self.write_config("printf 'worker findings\\n' > findings.md")
        self.write_manifest()

        proc = self.run_cli("run", str(self.manifest_path), "--no-dashboard")

        self.assertEqual(0, proc.returncode, proc.stdout)
        self.assertIn("findings.md", proc.stdout)
        self.assertIn("expect_files", proc.stdout)
        self.assertFalse((self.workdir / "alpha").exists())

    def test_reset_worktrees_names_uncommitted_path_before_removal(self) -> None:
        self.write_config("printf 'worker findings\\n' > findings.md")
        self.write_manifest(expect_files=["findings.md"])
        stale_taskdir = self.workdir / "alpha"
        stale_taskdir.parent.mkdir(parents=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
                "worktree",
                "add",
                "--detach",
                str(stale_taskdir),
                "HEAD",
            ],
            check=True,
            capture_output=True,
        )
        (stale_taskdir / "uncommitted-notes.txt").write_text(
            "do not hide this\n", encoding="utf-8"
        )

        proc = self.run_cli(
            "run",
            str(self.manifest_path),
            "--no-dashboard",
            "--reset-worktrees",
        )

        self.assertEqual(0, proc.returncode, proc.stdout)
        self.assertIn("uncommitted-notes.txt", proc.stdout)
        self.assertIn("reset will discard", proc.stdout)
        self.assertFalse(stale_taskdir.exists())

    def test_approve_refuses_dead_orchestrator_without_decision_file(self) -> None:
        self.write_config(":")
        runs_dir = self.state_dir / "runs"
        decisions_dir = self.state_dir / "pilot-decisions"
        decision_file = decisions_dir / "dead-run.json"
        runs_dir.mkdir(parents=True)
        decisions_dir.mkdir(parents=True)
        dead_pid = 99_999_999
        (runs_dir / "dead-run.json").write_text(
            json.dumps(
                {
                    "run_id": "dead-run",
                    "pid": dead_pid,
                    "pilot": {
                        "status": "awaiting",
                        "decision_file": str(decision_file),
                    },
                }
            ),
            encoding="utf-8",
        )
        self.ringer_home.mkdir(parents=True)
        (self.ringer_home / "active-runs.json").write_text(
            json.dumps({"dead-run": {"pid": dead_pid}}),
            encoding="utf-8",
        )

        proc = self.run_cli("approve", "dead-run")

        self.assertNotEqual(0, proc.returncode, proc.stdout)
        self.assertIn("orchestrator exited", proc.stdout)
        self.assertIn("can no longer be delivered", proc.stdout)
        self.assertFalse(decision_file.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
