#!/usr/bin/env python3
"""`run` checks every worktree taskdir before engines or run state start."""
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


def init_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text("hello worktrees\n", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
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
            "init",
        ],
    ):
        subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            check=True,
            env=env,
            capture_output=True,
        )


class WorktreePreflightTests(unittest.TestCase):
    def set_up_fixture(self, root: Path) -> tuple[Path, Path, Path, Path, Path]:
        home = root / "home"
        ringer_home = root / "ringer-home"
        state_dir = root / "state"
        workdir = root / "work"
        repo = root / "repo"
        config_path = root / "config.toml"
        manifest_path = root / "manifest.json"
        model_log = root / "runs.jsonl"

        home.mkdir()
        ringer_home.mkdir()
        init_git_repo(repo)
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
                    "enabled = true",
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
                    "run_name": "worktree-preflight-test",
                    "workdir": str(workdir),
                    "max_parallel": 2,
                    "worktrees": True,
                    "repo": str(repo),
                    "tasks": [
                        {
                            "key": "alpha",
                            "engine": "missing",
                            "spec": (
                                "Implement the alpha fixture behavior while leaving the "
                                "working tree ready for deterministic verification."
                            ),
                            "check": "test -f alpha.txt || { echo missing alpha; exit 1; }",
                            "verified": "The alpha fixture file exists.",
                            "task_type": "code-feature",
                        },
                        {
                            "key": "beta",
                            "engine": "missing",
                            "spec": (
                                "Implement the beta fixture behavior while leaving the "
                                "working tree ready for deterministic verification."
                            ),
                            "check": "test -f beta.txt || { echo missing beta; exit 1; }",
                            "verified": "The beta fixture file exists.",
                            "task_type": "code-feature",
                        },
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return config_path, manifest_path, model_log, workdir, repo

    def run_ringer(
        self,
        root: Path,
        config_path: Path,
        manifest_path: Path,
        *mode_args: str,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOME"] = str(root / "home")
        env["RINGER_HOME"] = str(root / "ringer-home")
        env["XDG_CONFIG_HOME"] = str(root / "xdg-config")
        env["RINGER_NO_SELF_UPDATE"] = "1"
        env["RINGER_NO_CATALOG_REFRESH"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [
                sys.executable,
                "ringer.py",
                "run",
                str(manifest_path),
                "--config",
                str(config_path),
                "--no-dashboard",
                *mode_args,
            ],
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=30,
        )

    def add_stale_worktree(self, repo: Path, taskdir: Path) -> None:
        taskdir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "worktree",
                "add",
                "--detach",
                str(taskdir),
                "HEAD",
            ],
            stdin=subprocess.DEVNULL,
            check=True,
            capture_output=True,
        )

    def worktree_list(self, repo: Path) -> str:
        return subprocess.run(
            ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
            stdin=subprocess.DEVNULL,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    def test_fresh_tasks_are_reported_before_engine_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root).resolve()
            config_path, manifest_path, model_log, workdir, repo = self.set_up_fixture(root)
            base_sha = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                stdin=subprocess.DEVNULL,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            proc = self.run_ringer(root, config_path, manifest_path)
            output = proc.stdout

            self.assertNotEqual(0, proc.returncode, output)
            self.assertIn(f"Worktree pre-flight: repo={repo} base={base_sha}", output)
            self.assertRegex(output, re.compile(r"^alpha\s+fresh\s+", re.MULTILINE))
            self.assertRegex(output, re.compile(r"^beta\s+fresh\s+", re.MULTILINE))
            self.assertIn("engine 'missing' binary not found", output)
            self.assertLess(
                output.index("Worktree pre-flight:"),
                output.index("engine 'missing' binary not found"),
            )
            self.assertFalse(model_log.exists(), "engine preflight wrote model-log rows")
            self.assertFalse((root / "state").exists(), "engine preflight wrote run state")
            self.assertFalse(workdir.exists(), "fresh pre-flight created the workdir")

    def test_stale_registered_worktree_aborts_without_reset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root).resolve()
            config_path, manifest_path, model_log, workdir, repo = self.set_up_fixture(root)
            taskdir = workdir / "alpha"
            self.add_stale_worktree(repo, taskdir)

            proc = self.run_ringer(root, config_path, manifest_path)
            output = proc.stdout

            self.assertNotEqual(0, proc.returncode, output)
            self.assertRegex(output, re.compile(r"^alpha\s+stale worktree\s+", re.MULTILINE))
            self.assertIn("--reset-worktrees", output)
            self.assertIn("git -C", output)
            self.assertTrue(taskdir.is_dir(), "pre-flight removed a stale worktree without opt-in")
            self.assertIn(f"worktree {taskdir}", self.worktree_list(repo))
            self.assertNotIn("engine 'missing' binary not found", output)
            self.assertFalse(model_log.exists(), "stale pre-flight wrote model-log rows")
            self.assertFalse((root / "state").exists(), "stale pre-flight wrote run state")
            self.assertFalse((workdir / "logs").exists(), "stale pre-flight created task logs")

    def test_reset_removes_registered_worktree_then_proceeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root).resolve()
            config_path, manifest_path, _, workdir, repo = self.set_up_fixture(root)
            taskdir = workdir / "alpha"
            self.add_stale_worktree(repo, taskdir)

            stale_proc = self.run_ringer(root, config_path, manifest_path)
            self.assertNotEqual(0, stale_proc.returncode, stale_proc.stdout)
            self.assertTrue(taskdir.is_dir(), "stale abort removed the worktree")

            proc = self.run_ringer(
                root,
                config_path,
                manifest_path,
                "--reset-worktrees",
            )
            output = proc.stdout

            self.assertNotEqual(0, proc.returncode, output)
            self.assertRegex(output, re.compile(r"^alpha\s+reset\s+", re.MULTILINE))
            self.assertRegex(output, re.compile(r"^beta\s+fresh\s+", re.MULTILINE))
            self.assertIn("engine 'missing' binary not found", output)
            self.assertFalse(taskdir.exists(), "reset left the stale worktree directory")
            self.assertNotIn(f"worktree {taskdir}", self.worktree_list(repo))

    def test_reset_never_deletes_stale_plain_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root).resolve()
            config_path, manifest_path, _, workdir, repo = self.set_up_fixture(root)
            taskdir = workdir / "alpha"
            taskdir.mkdir(parents=True)
            sentinel = taskdir / "post-mortem.txt"
            sentinel.write_text("keep me\n", encoding="utf-8")

            proc = self.run_ringer(
                root,
                config_path,
                manifest_path,
                "--reset-worktrees",
            )
            output = proc.stdout

            self.assertNotEqual(0, proc.returncode, output)
            self.assertRegex(output, re.compile(r"^alpha\s+stale dir\s+", re.MULTILINE))
            self.assertIn("move or delete it, then re-run", output)
            self.assertIn("--reset-worktrees", output)
            self.assertNotIn("engine 'missing' binary not found", output)
            self.assertEqual("keep me\n", sentinel.read_text(encoding="utf-8"))
            self.assertNotIn(f"worktree {taskdir}", self.worktree_list(repo))

    def test_dry_run_ignores_stale_registered_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root).resolve()
            config_path, manifest_path, _, workdir, repo = self.set_up_fixture(root)
            taskdir = workdir / "alpha"
            self.add_stale_worktree(repo, taskdir)

            proc = self.run_ringer(root, config_path, manifest_path, "--dry-run")
            output = proc.stdout

            self.assertEqual(0, proc.returncode, output)
            self.assertIn("DRY RUN: no codex workers will be spawned.", output)
            self.assertNotIn("Worktree pre-flight:", output)
            self.assertNotIn("stale worktree", output)
            self.assertTrue(taskdir.is_dir())
            self.assertIn(f"worktree {taskdir}", self.worktree_list(repo))


if __name__ == "__main__":
    unittest.main()
