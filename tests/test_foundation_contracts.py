#!/usr/bin/env python3
from __future__ import annotations

import json
import os
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
    (path / "base.txt").write_text("base\n", encoding="utf-8")
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
        ["git", "-C", str(path), "add", "base.txt"],
        ["git", "-C", str(path), "commit", "--quiet", "-m", "init"],
    ):
        subprocess.run(args, check=True, env=env, capture_output=True)


class FoundationContractTests(unittest.TestCase):
    def _write_config(self, root: Path) -> Path:
        config_path = root / "config.toml"
        engine_command = (
            "case \"$1\" in "
            "foundation) printf 'SHARED_ID = 1\\n' > shared.py ;; "
            "lane) printf 'lane\\n' > lane.txt ;; "
            "bad) printf 'bad\\n' > forbidden.txt ;; "
            "contract) printf 'class SharedThing:\\n    pass\\n' > lane.py ;; "
            "marker:*) touch \"${1#marker:}\" ;; "
            "esac"
        )
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
                    f"  {toml_string(engine_command)},",
                    '  "{spec}",',
                    '  "{spec}",',
                    '  "{model}",',
                    "]",
                    "sandbox_args = []",
                    "full_access_args = []",
                    'model_default = "mock-model"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return config_path

    def _env(self, root: Path) -> dict[str, str]:
        home = root / "home"
        ringer_home = root / "ringer-home"
        home.mkdir()
        ringer_home.mkdir()
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(home),
                "RINGER_HOME": str(ringer_home),
                "XDG_CONFIG_HOME": str(root / "xdg-config"),
                "RINGER_NO_SELF_UPDATE": "1",
                "RINGER_NO_CATALOG_REFRESH": "1",
            }
        )
        return env

    def _run(
        self,
        root: Path,
        manifest: dict[str, Any],
        *,
        timeout: int = 30,
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        config_path = self._write_config(root)
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
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
                "foundation-contract-test",
            ],
            cwd=ROOT,
            env=self._env(root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
        return proc, root / "state"

    def _manifest(
        self,
        root: Path,
        repo: Path,
        tasks: list[dict[str, Any]],
        **extra: Any,
    ) -> dict[str, Any]:
        manifest: dict[str, Any] = {
            "run_name": "foundation-contract-test",
            "workdir": str(root / "work"),
            "max_parallel": 2,
            "worktrees": True,
            "repo": str(repo),
            "tasks": tasks,
        }
        manifest.update(extra)
        return manifest

    @staticmethod
    def _task(key: str, spec: str, check: str = "true", **extra: Any) -> dict[str, Any]:
        task: dict[str, Any] = {
            "key": key,
            "engine": "mock",
            "spec": spec,
            "check": check,
            "max_attempts": 1,
        }
        task.update(extra)
        return task

    def test_foundation_output_is_applied_before_lane_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            repo = root / "repo"
            init_git_repo(repo)
            manifest = self._manifest(
                root,
                repo,
                [
                    self._task("foundation", "foundation", "test -f shared.py"),
                    self._task("lane", "lane", "test -f shared.py && test -f lane.txt"),
                ],
                foundation="foundation",
            )
            proc, _state_dir = self._run(root, manifest)
            combined = proc.stdout + proc.stderr
            self.assertEqual(0, proc.returncode, combined)
            patch = (root / "work" / "foundation.patch").read_text(encoding="utf-8")
            self.assertIn("shared.py", patch)

    def test_empty_foundation_patch_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            repo = root / "repo"
            init_git_repo(repo)
            manifest = self._manifest(
                root,
                repo,
                [
                    self._task("foundation", "no changes"),
                    self._task("lane", "lane", "test -f lane.txt"),
                ],
                foundation="foundation",
            )
            proc, _state_dir = self._run(root, manifest)
            combined = proc.stdout + proc.stderr
            self.assertEqual(0, proc.returncode, combined)
            self.assertIn("Foundation 'foundation' produced no changes", combined)
            self.assertEqual(b"", (root / "work" / "foundation.patch").read_bytes())

    def test_failed_foundation_never_spawns_held_lane_or_integration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            repo = root / "repo"
            init_git_repo(repo)
            marker = root / "lane-ran"
            integration_marker = root / "integration-ran"
            manifest = self._manifest(
                root,
                repo,
                [
                    self._task("foundation", "foundation", "false"),
                    self._task(
                        "lane",
                        f"marker:{marker}",
                    ),
                ],
                foundation="foundation",
                integration_check=f"touch {shlex.quote(str(integration_marker))}",
            )
            proc, state_dir = self._run(root, manifest)
            combined = proc.stdout + proc.stderr
            self.assertNotEqual(0, proc.returncode, combined)
            self.assertIn("Foundation 'foundation' failed", combined)
            self.assertIn("1 held lane(s) were never started", combined)
            self.assertFalse(marker.exists())
            self.assertFalse((root / "work" / "lane").exists())
            self.assertFalse(integration_marker.exists())
            state = json.loads(next((state_dir / "runs").glob("*.json")).read_text())
            held = next(task for task in state["tasks"] if task["key"] == "lane")
            self.assertEqual("queued", held["status"])
            self.assertNotIn("integration", state)

    def test_ownership_violation_fails_and_names_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            repo = root / "repo"
            init_git_repo(repo)
            manifest = self._manifest(
                root,
                repo,
                [self._task("lane", "bad", owns=["allowed/**"])],
            )
            proc, state_dir = self._run(root, manifest)
            combined = proc.stdout + proc.stderr
            self.assertNotEqual(0, proc.returncode, combined)
            self.assertIn("[ringer.py] ownership violation:", combined)
            self.assertIn("forbidden.txt", combined)
            state = json.loads(next((state_dir / "runs").glob("*.json")).read_text())
            lane = state["tasks"][0]
            self.assertIn("[ringer.py] ownership violation:", lane["check_output_tail"])
            self.assertIn("forbidden.txt", lane["check_output_tail"])
            self.assertIn("forbidden.txt", "\n".join(lane["violations"]))

    def test_questions_file_is_exempt_from_ownership(self) -> None:
        """The docs promise the questions file never fails a task. It must not."""
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            repo = root / "repo"
            init_git_repo(repo)
            manifest = self._manifest(
                root,
                repo,
                [self._task("lane", "marker:questions.md", owns=["allowed/**"])],
                questions_file="questions.md",
            )
            proc, state_dir = self._run(root, manifest)
            combined = proc.stdout + proc.stderr

            self.assertEqual(0, proc.returncode, combined)
            self.assertNotIn("ownership violation", combined)
            state = json.loads(next((state_dir / "runs").glob("*.json")).read_text())
            self.assertEqual("pass", state["tasks"][0]["status"])

    def test_unrelated_stray_file_still_violates_when_questions_file_is_set(self) -> None:
        """The exemption is exactly one filename, not a hole in ownership."""
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            repo = root / "repo"
            init_git_repo(repo)
            manifest = self._manifest(
                root,
                repo,
                [self._task("lane", "bad", owns=["allowed/**"])],
                questions_file="questions.md",
            )
            proc, _ = self._run(root, manifest)
            combined = proc.stdout + proc.stderr

            self.assertNotEqual(0, proc.returncode, combined)
            self.assertIn("[ringer.py] ownership violation:", combined)
            self.assertIn("forbidden.txt", combined)

    def test_foundation_paths_are_excluded_from_lane_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            repo = root / "repo"
            init_git_repo(repo)
            manifest = self._manifest(
                root,
                repo,
                [
                    self._task("foundation", "foundation"),
                    self._task("lane", "lane", "test -f shared.py", owns=["lane.txt"]),
                ],
                foundation="foundation",
            )
            proc, _state_dir = self._run(root, manifest)
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_contract_redefinition_fails_and_names_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            repo = root / "repo"
            init_git_repo(repo)
            manifest = self._manifest(
                root,
                repo,
                [self._task("lane", "contract")],
                contracts=["SharedThing"],
            )
            proc, state_dir = self._run(root, manifest)
            self.assertNotEqual(0, proc.returncode, proc.stdout + proc.stderr)
            state = json.loads(next((state_dir / "runs").glob("*.json")).read_text())
            lane = state["tasks"][0]
            message = "\n".join(lane["violations"])
            self.assertIn("[ringer.py] contract violation:", message)
            self.assertIn("SharedThing", message)
            self.assertIn("lane.py:1", message)

    def test_foundation_validation_errors(self) -> None:
        cases = (
            (
                {"foundation": "foundation", "worktrees": False, "repo": None},
                "foundation output cannot be propagated without worktrees",
            ),
            ({"foundation": "missing"}, "foundation must name a manifest task key: missing"),
            (
                {"foundation": "foundation", "pilot": "lane"},
                "foundation and pilot are mutually exclusive",
            ),
        )
        for changes, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temp_root:
                root = Path(temp_root)
                repo = root / "repo"
                init_git_repo(repo)
                manifest = self._manifest(
                    root,
                    repo,
                    [
                        self._task("foundation", "foundation"),
                        self._task("lane", "lane"),
                    ],
                )
                manifest.update(changes)
                proc, _state_dir = self._run(root, manifest)
                self.assertEqual(2, proc.returncode, proc.stdout + proc.stderr)
                self.assertIn(expected, proc.stdout + proc.stderr)

    def test_manifest_without_new_fields_behaves_as_before(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            repo = root / "repo"
            init_git_repo(repo)
            manifest = self._manifest(
                root,
                repo,
                [
                    self._task("one", "lane"),
                    self._task("two", "lane"),
                ],
            )
            proc, state_dir = self._run(root, manifest)
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
            self.assertFalse((root / "work" / "foundation.patch").exists())
            state = json.loads(next((state_dir / "runs").glob("*.json")).read_text())
            self.assertTrue(all(task["status"] == "pass" for task in state["tasks"]))
            self.assertTrue(all("violations" not in task for task in state["tasks"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
