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
sys.path.insert(0, str(ROOT))

from ringer import build_models_api_payload  # noqa: E402


def init_git_repo(path: Path) -> None:
    path.mkdir(parents=True)
    (path / "README.md").write_text("fixture\n", encoding="utf-8")
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
        subprocess.run(args, check=True, env=env, capture_output=True)


class QuietOmissionsTests(unittest.TestCase):
    def test_models_payload_reports_skipped_log_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            log_path = root / "runs.jsonl"
            log_path.write_text(
                json.dumps(
                    {
                        "run_id": "run-1",
                        "task_key": "task",
                        "worker_engine": "codex",
                        "model": "gpt-test",
                        "task_type": "code-feature",
                        "verdict": "PASS",
                        "retry": False,
                    }
                )
                + "\nnot-json\n[]\n",
                encoding="utf-8",
            )

            payload = build_models_api_payload(
                log_path=log_path,
                db_path=root / "models.sqlite3",
                catalog_path=root / "missing-catalog.json",
                registry_path=root / "missing-registry.toml",
                notes_path=root / "missing-notes.md",
            )
            payload = build_models_api_payload(
                log_path=log_path,
                db_path=root / "models.sqlite3",
                catalog_path=root / "missing-catalog.json",
                registry_path=root / "missing-registry.toml",
                notes_path=root / "missing-notes.md",
            )

            self.assertEqual(1, payload["rows_read"])
            self.assertEqual(2, payload["skipped"])

    def set_up_worktree_fixture(self, root: Path) -> tuple[Path, Path, Path, Path]:
        repo = root / "repo"
        workdir = root / "work"
        config_path = root / "config.toml"
        manifest_path = root / "manifest.json"
        init_git_repo(repo)
        config_path.write_text(
            "\n".join(
                [
                    f"state_dir = {json.dumps(str(root / 'state'))}",
                    "",
                    "[eval]",
                    'backend = "jsonl"',
                    f"jsonl_path = {json.dumps(str(root / 'runs.jsonl'))}",
                    "",
                    "[artifact]",
                    "enabled = false",
                    "",
                    "[engines.missing]",
                    'bin = "/nonexistent/engine"',
                    'args_template = ["{spec}"]',
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
                    "run_name": "quiet-omissions",
                    "workdir": str(workdir),
                    "worktrees": True,
                    "repo": str(repo),
                    "tasks": [
                        {
                            "key": "alpha",
                            "engine": "missing",
                            "spec": "Implement the fixture behavior and keep the change scoped.",
                            "check": "true",
                            "verified": "The fixture behavior is implemented.",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return repo, workdir, config_path, manifest_path

    def run_ringer(
        self, root: Path, config_path: Path, manifest_path: Path, *args: str
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(root / "home"),
                "RINGER_HOME": str(root / "ringer-home"),
                "RINGER_NO_SELF_UPDATE": "1",
                "RINGER_NO_CATALOG_REFRESH": "1",
            }
        )
        return subprocess.run(
            [
                sys.executable,
                "ringer.py",
                "run",
                str(manifest_path),
                "--config",
                str(config_path),
                "--no-dashboard",
                *args,
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

    def test_reset_with_plain_directory_does_not_recommend_reset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            repo, workdir, config_path, manifest_path = self.set_up_worktree_fixture(root)
            (workdir / "alpha").mkdir(parents=True)

            proc = self.run_ringer(root, config_path, manifest_path, "--reset-worktrees")

            self.assertNotEqual(0, proc.returncode, proc.stdout)
            self.assertIn("move or delete it, then re-run", proc.stdout)
            self.assertNotIn("Re-run with --reset-worktrees", proc.stdout)
            self.assertTrue(repo.is_dir())

    def test_registered_worktree_without_reset_recommends_reset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            repo, workdir, config_path, manifest_path = self.set_up_worktree_fixture(root)
            taskdir = workdir / "alpha"
            taskdir.parent.mkdir(parents=True)
            subprocess.run(
                ["git", "-C", str(repo), "worktree", "add", "--detach", str(taskdir), "HEAD"],
                check=True,
                capture_output=True,
            )

            proc = self.run_ringer(root, config_path, manifest_path)

            self.assertNotEqual(0, proc.returncode, proc.stdout)
            self.assertIn("Re-run with --reset-worktrees", proc.stdout)


if __name__ == "__main__":
    unittest.main()
