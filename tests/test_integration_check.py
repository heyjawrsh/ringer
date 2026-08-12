#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def toml_string(value: object) -> str:
    return json.dumps(str(value))


def init_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "visible.txt").write_text("visible at HEAD\n", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
        }
    )
    for args in (
        ["git", "-C", str(path), "init", "--quiet"],
        ["git", "-C", str(path), "add", "visible.txt"],
        ["git", "-C", str(path), "commit", "--quiet", "-m", "init"],
    ):
        subprocess.run(args, check=True, env=env, capture_output=True)


class IntegrationCheckTests(unittest.TestCase):
    def _write_config(self, root: Path) -> Path:
        config_path = root / "config.toml"
        config_path.write_text(
            "\n".join(
                [
                    f"state_dir = {toml_string(root / 'state')}",
                    "",
                    "[eval]",
                    'backend = "jsonl"',
                    f"jsonl_path = {toml_string(root / 'runs.jsonl')}",
                    "",
                    "[artifact]",
                    "enabled = false",
                    "",
                    "[engines.mock]",
                    'bin = "/bin/sh"',
                    "args_template = [",
                    '  "-c",',
                    '  "exit 0",',
                    '  "{spec}",',
                    "]",
                    "sandbox_args = []",
                    "full_access_args = []",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return config_path

    def _run(
        self,
        root: Path,
        *,
        integration_check: str | None,
        task_check: str = "true",
        worktrees: bool = False,
        repo: Path | None = None,
        integration_timeout_s: int | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
        home = root / "home"
        ringer_home = root / "ringer-home"
        workdir = root / "work"
        manifest_path = root / "manifest.json"
        home.mkdir()
        ringer_home.mkdir()
        config_path = self._write_config(root)
        manifest: dict[str, Any] = {
            "run_name": "integration-test",
            "workdir": str(workdir),
            "max_parallel": 2,
            "worktrees": worktrees,
            "repo": str(repo) if repo is not None else None,
            "tasks": [
                {
                    "key": "lane-one",
                    "engine": "mock",
                    "spec": "The mock engine exits successfully without making changes.",
                    "check": task_check,
                    "max_attempts": 1,
                },
                {
                    "key": "lane-two",
                    "engine": "mock",
                    "spec": "The mock engine exits successfully without making changes.",
                    "check": "true",
                    "max_attempts": 1,
                },
            ],
        }
        if integration_check is not None:
            manifest["integration_check"] = integration_check
        if integration_timeout_s is not None:
            manifest["integration_timeout_s"] = integration_timeout_s
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        env = os.environ.copy()
        env["HOME"] = str(home)
        env["RINGER_HOME"] = str(ringer_home)
        env["XDG_CONFIG_HOME"] = str(root / "xdg-config")
        env["RINGER_NO_SELF_UPDATE"] = "1"
        proc = subprocess.run(
            [
                sys.executable,
                "ringer.py",
                "run",
                str(manifest_path),
                "--config",
                str(config_path),
                "--no-dashboard",
                "--identity",
                "integration-test",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
        return proc, workdir, root / "state"

    def test_passing_integration_check_logs_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            proc, workdir, _state_dir = self._run(
                root,
                integration_check="printf 'integration-output\\n'",
            )
            combined_output = proc.stdout + proc.stderr
            self.assertEqual(0, proc.returncode, combined_output)
            self.assertIn("integration: pass", combined_output)
            log_path = workdir / "logs" / "integration.log"
            self.assertTrue(log_path.is_file())
            log = log_path.read_text(encoding="utf-8")
            self.assertIn("integration-output\n", log)
            self.assertIn("[ringer.py] integration exited rc=0", log)

    def test_failing_integration_check_sets_exit_and_run_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            proc, workdir, state_dir = self._run(
                root,
                integration_check="printf 'merged build broke\\n'; exit 7",
            )
            combined_output = proc.stdout + proc.stderr
            self.assertNotEqual(0, proc.returncode, combined_output)
            self.assertIn("integration: FAIL (rc=7)", combined_output)
            self.assertIn("merged build broke", combined_output)
            state_path = next((state_dir / "runs").glob("*.json"))
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual("fail", state["integration"]["status"])
            self.assertEqual(7, state["integration"]["returncode"])
            self.assertEqual(
                str((workdir / "logs" / "integration.log").resolve()),
                state["integration"]["log_path"],
            )

    def test_task_failure_skips_integration_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            marker = root / "integration-ran"
            proc, workdir, _state_dir = self._run(
                root,
                integration_check=f"touch {shlex.quote(str(marker))}",
                task_check="printf 'task failed\\n'; false",
            )
            combined_output = proc.stdout + proc.stderr
            self.assertEqual(1, proc.returncode, combined_output)
            self.assertIn("integration: skipped (1 task(s) failed)", combined_output)
            self.assertFalse(marker.exists(), "skipped integration command executed")
            self.assertFalse((workdir / "logs" / "integration.log").exists())

    def test_integration_timeout_fails_once_and_is_logged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            proc, workdir, state_dir = self._run(
                root,
                integration_check="printf 'before-timeout\\n'; sleep 5",
                integration_timeout_s=1,
            )
            combined_output = proc.stdout + proc.stderr
            self.assertEqual(1, proc.returncode, combined_output)
            self.assertIn("integration: FAIL (timed out after 1s)", combined_output)
            log = (workdir / "logs" / "integration.log").read_text(encoding="utf-8")
            self.assertIn("before-timeout", log)
            self.assertIn("[ringer.py] integration timed out after 1s", log)
            state_path = next((state_dir / "runs").glob("*.json"))
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual("timeout", state["integration"]["status"])

    def test_manifest_without_integration_field_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            proc, workdir, state_dir = self._run(root, integration_check=None)
            combined_output = proc.stdout + proc.stderr
            self.assertEqual(0, proc.returncode, combined_output)
            self.assertNotIn("integration:", combined_output)
            self.assertFalse((workdir / "logs" / "integration.log").exists())
            state_path = next((state_dir / "runs").glob("*.json"))
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertNotIn("integration", state)

    def test_worktree_integration_uses_fresh_detached_checkout_and_removes_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            repo = root / "repo"
            init_git_repo(repo)
            command = (
                "test -f visible.txt && "
                "test -z \"$(git symbolic-ref -q HEAD)\" && "
                "printf 'repo-visible\\n' && "
                "printf 'cwd=%s\\n' \"$PWD\" && "
                f"test \"$PWD\" != {shlex.quote(str(repo))}"
            )
            proc, workdir, _state_dir = self._run(
                root,
                integration_check=command,
                worktrees=True,
                repo=repo,
            )
            combined_output = proc.stdout + proc.stderr
            self.assertEqual(0, proc.returncode, combined_output)
            self.assertIn("integration: pass", combined_output)
            log = (workdir / "logs" / "integration.log").read_text(encoding="utf-8")
            self.assertIn("repo-visible", log)
            match = re.search(r"^cwd=(.+)$", log, flags=re.MULTILINE)
            self.assertIsNotNone(match, log)
            assert match is not None
            integration_cwd = Path(match.group(1))
            self.assertNotEqual(repo.resolve(), integration_cwd.resolve())
            self.assertFalse(integration_cwd.exists(), "integration worktree leaked")
            worktree_list = subprocess.run(
                ["git", "-C", str(repo), "worktree", "list"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(
                1,
                len(worktree_list.splitlines()),
                f"integration worktree registration leaked:\n{worktree_list}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
