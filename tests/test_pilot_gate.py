#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def toml_string(value: object) -> str:
    return json.dumps(str(value))


class PilotGateTests(unittest.TestCase):
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

    def _write_manifest(
        self,
        root: Path,
        *,
        pilot: str | None = "pilot-lane",
        pilot_check: str = "true",
        pilot_wait_s: int = 10,
        integration_check: str | None = None,
    ) -> tuple[Path, Path, Path]:
        workdir = root / "work"
        held_marker = root / "held-ran"
        pilot_marker = root / "pilot-ran"
        manifest: dict[str, Any] = {
            "run_name": "pilot-gate-test",
            "workdir": str(workdir),
            "max_parallel": 2,
            "tasks": [
                {
                    "key": "pilot-lane",
                    "engine": "mock",
                    "spec": "Run the designated pilot lane.",
                    "check": (
                        f"touch {shlex.quote(str(pilot_marker))}; {pilot_check}"
                    ),
                    "max_attempts": 1,
                },
                {
                    "key": "held-lane",
                    "engine": "mock",
                    "spec": "Run only after pilot approval.",
                    "check": f"touch {shlex.quote(str(held_marker))}",
                    "max_attempts": 1,
                },
            ],
        }
        if pilot is not None:
            manifest["pilot"] = pilot
            manifest["pilot_wait_s"] = pilot_wait_s
        if integration_check is not None:
            manifest["integration_check"] = integration_check
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest_path, pilot_marker, held_marker

    def _command(self, manifest_path: Path, config_path: Path) -> list[str]:
        return [
            sys.executable,
            "ringer.py",
            "run",
            str(manifest_path),
            "--config",
            str(config_path),
            "--no-dashboard",
            "--identity",
            "pilot-gate-test",
        ]

    def _wait_for_awaiting(
        self,
        proc: subprocess.Popen[str],
        state_dir: Path,
        timeout_s: float = 12,
    ) -> tuple[Path, dict[str, Any]]:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            for state_path in (state_dir / "runs").glob("*.json"):
                try:
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if state.get("pilot", {}).get("status") == "awaiting":
                    return state_path, state
            if proc.poll() is not None:
                stdout, stderr = proc.communicate()
                self.fail(
                    "run exited before awaiting pilot review:\n"
                    f"stdout:\n{stdout}\nstderr:\n{stderr}"
                )
            time.sleep(0.1)
        self.fail("timed out waiting for pilot state")

    def _decision(
        self,
        root: Path,
        config_path: Path,
        env: dict[str, str],
        decision: str,
        run_id: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "ringer.py",
                decision,
                run_id,
                "--config",
                str(config_path),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )

    def test_approve_releases_held_lanes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            config_path = self._write_config(root)
            env = self._env(root)
            manifest_path, pilot_marker, held_marker = self._write_manifest(root)
            proc = subprocess.Popen(
                self._command(manifest_path, config_path),
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                state_path, awaiting = self._wait_for_awaiting(proc, root / "state")
                self.assertTrue(pilot_marker.exists())
                self.assertFalse(held_marker.exists())
                held = next(task for task in awaiting["tasks"] if task["key"] == "held-lane")
                self.assertEqual("queued", held["status"])
                self.assertFalse((root / "work" / "held-lane").exists())
                run_id = awaiting["run_id"]
                decision = self._decision(root, config_path, env, "approve", run_id)
                self.assertEqual(0, decision.returncode, decision.stdout + decision.stderr)
                self.assertIn(f"Pilot approve recorded for run {run_id}.", decision.stdout)
                stdout, stderr = proc.communicate(timeout=15)
                combined = stdout + stderr
                self.assertEqual(0, proc.returncode, combined)
                self.assertTrue(held_marker.exists())
                self.assertIn(f"./ringer.py approve {run_id}", combined)
                self.assertIn(f"./ringer.py reject {run_id}", combined)
                state = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertEqual("approved", state["pilot"]["status"])
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate()

    def test_reject_keeps_held_lanes_from_starting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            config_path = self._write_config(root)
            env = self._env(root)
            manifest_path, _pilot_marker, held_marker = self._write_manifest(root)
            proc = subprocess.Popen(
                self._command(manifest_path, config_path),
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                state_path, awaiting = self._wait_for_awaiting(proc, root / "state")
                decision = self._decision(
                    root, config_path, env, "reject", awaiting["run_id"]
                )
                self.assertEqual(0, decision.returncode, decision.stdout + decision.stderr)
                stdout, stderr = proc.communicate(timeout=15)
                combined = stdout + stderr
                self.assertNotEqual(0, proc.returncode, combined)
                self.assertIn("Pilot run rejected", combined)
                self.assertFalse(held_marker.exists())
                self.assertFalse((root / "work" / "held-lane").exists())
                state = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertEqual("rejected", state["pilot"]["status"])
                held = next(task for task in state["tasks"] if task["key"] == "held-lane")
                self.assertEqual("queued", held["status"])
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate()

    def test_pilot_failure_never_starts_held_lanes_or_integration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            config_path = self._write_config(root)
            env = self._env(root)
            integration_marker = root / "integration-ran"
            manifest_path, _pilot_marker, held_marker = self._write_manifest(
                root,
                pilot_check="false",
                integration_check=f"touch {shlex.quote(str(integration_marker))}",
            )
            proc = subprocess.run(
                self._command(manifest_path, config_path),
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=20,
            )
            combined = proc.stdout + proc.stderr
            self.assertNotEqual(0, proc.returncode, combined)
            self.assertIn("Pilot 'pilot-lane' failed", combined)
            self.assertIn("1 held lane(s) were never started", combined)
            self.assertFalse(held_marker.exists())
            self.assertFalse((root / "work" / "held-lane").exists())
            self.assertFalse(integration_marker.exists())
            state_path = next((root / "state" / "runs").glob("*.json"))
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertNotIn("integration", state)

    def test_pilot_review_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            config_path = self._write_config(root)
            env = self._env(root)
            manifest_path, _pilot_marker, held_marker = self._write_manifest(
                root, pilot_wait_s=1
            )
            proc = subprocess.run(
                self._command(manifest_path, config_path),
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=15,
            )
            combined = proc.stdout + proc.stderr
            self.assertNotEqual(0, proc.returncode, combined)
            self.assertIn("Pilot review timed out after 1s", combined)
            self.assertFalse(held_marker.exists())
            state_path = next((root / "state" / "runs").glob("*.json"))
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual("timeout", state["pilot"]["status"])

    def test_unknown_pilot_task_fails_manifest_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            config_path = self._write_config(root)
            env = self._env(root)
            manifest_path, _pilot_marker, _held_marker = self._write_manifest(
                root, pilot="missing-lane"
            )
            proc = subprocess.run(
                self._command(manifest_path, config_path),
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=10,
            )
            self.assertNotEqual(0, proc.returncode)
            self.assertIn(
                "pilot must name a manifest task key: missing-lane",
                proc.stdout + proc.stderr,
            )

    def test_approve_unknown_run_id_errors_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            config_path = self._write_config(root)
            env = self._env(root)
            proc = self._decision(root, config_path, env, "approve", "unknown-run")
            self.assertNotEqual(0, proc.returncode)
            self.assertIn("unknown run_id: unknown-run", proc.stdout + proc.stderr)

    def test_manifest_without_pilot_runs_all_lanes_normally(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            config_path = self._write_config(root)
            env = self._env(root)
            integration_marker = root / "integration-ran"
            manifest_path, pilot_marker, held_marker = self._write_manifest(
                root,
                pilot=None,
                integration_check=f"touch {shlex.quote(str(integration_marker))}",
            )
            proc = subprocess.run(
                self._command(manifest_path, config_path),
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=20,
            )
            combined = proc.stdout + proc.stderr
            self.assertEqual(0, proc.returncode, combined)
            self.assertTrue(pilot_marker.exists())
            self.assertTrue(held_marker.exists())
            self.assertTrue(integration_marker.exists())
            state_path = next((root / "state" / "runs").glob("*.json"))
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertNotIn("pilot", state)


if __name__ == "__main__":
    unittest.main(verbosity=2)
