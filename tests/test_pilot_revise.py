#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ringer import PilotDecisionError, record_pilot_decision  # noqa: E402


class PilotReviseTests(unittest.TestCase):
    def _seed_awaiting(self, root: Path) -> tuple[Path, Path]:
        state_dir = root / "state"
        (state_dir / "runs").mkdir(parents=True)
        decision_file = root / "pilot.decision"
        (state_dir / "runs" / "run-1.json").write_text(
            json.dumps(
                {
                    "run_id": "run-1",
                    "pilot": {
                        "status": "awaiting",
                        "decision_file": str(decision_file),
                    },
                }
            ),
            encoding="utf-8",
        )
        return state_dir, decision_file

    def test_revise_with_note_is_accepted_and_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state_dir, decision_file = self._seed_awaiting(Path(temp))
            record_pilot_decision(state_dir, "run-1", "revise", note="Fix the title")
            payload = json.loads(decision_file.read_text(encoding="utf-8"))
            self.assertEqual({"decision", "note", "decided_at"}, set(payload))
            self.assertEqual("revise", payload["decision"])
            self.assertEqual("Fix the title", payload["note"])

    def test_revise_refuses_empty_or_whitespace_note(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state_dir, _ = self._seed_awaiting(Path(temp))
            for note in (None, "", "   "):
                with self.subTest(note=note), self.assertRaises(PilotDecisionError):
                    record_pilot_decision(state_dir, "run-1", "revise", note=note)

    def test_revision_state_and_cap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state_dir = root / "state"
            workdir = root / "work"
            config = root / "config.toml"
            config.write_text(
                f'''state_dir = {json.dumps(str(state_dir))}
[eval]
backend = "jsonl"
jsonl_path = {json.dumps(str(root / "runs.jsonl"))}
[artifact]
enabled = false
[engines.mock]
bin = "/bin/sh"
args_template = ["-c", "exit 0", "{{spec}}"]
sandbox_args = []
full_access_args = []
''',
                encoding="utf-8",
            )
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "run_name": "revise-cap-test",
                        "workdir": str(workdir),
                        "pilot": "pilot",
                        "pilot_wait_s": 10,
                        "pilot_max_revisions": 1,
                        "tasks": [
                            {"key": "pilot", "engine": "mock", "spec": "pilot", "check": "true", "max_attempts": 1},
                            {"key": "held", "engine": "mock", "spec": "held", "check": f"touch {root / 'held-ran'}", "max_attempts": 1},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            ringer_home = root / "ringer-home"
            ringer_home.mkdir()
            env.update(
                {
                    "RINGER_HOME": str(ringer_home),
                    "RINGER_NO_SELF_UPDATE": "1",
                    "RINGER_NO_CATALOG_REFRESH": "1",
                }
            )
            proc = subprocess.Popen(
                [sys.executable, "ringer.py", "run", str(manifest), "--config", str(config), "--no-dashboard", "--identity", "test"],
                cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            try:
                state_path = self._wait_awaiting(proc, state_dir)
                state = json.loads(state_path.read_text(encoding="utf-8"))
                run_id = state["run_id"]
                self._revise(run_id, config, env, "first")
                self._wait_revisions(state_path, 1)
                state = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertEqual("awaiting", state["pilot"]["status"])
                self.assertEqual("first", state["pilot"]["last_note"])
                self._revise(run_id, config, env, "over cap")
                stdout, stderr = proc.communicate(timeout=15)
                self.assertNotEqual(0, proc.returncode, stdout + stderr)
                self.assertIn("revision limit 1 reached after 1", stdout + stderr)
                self.assertFalse((root / "held-ran").exists())
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate()

    def _wait_awaiting(self, proc: subprocess.Popen[str], state_dir: Path) -> Path:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            for path in (state_dir / "runs").glob("*.json"):
                state = json.loads(path.read_text(encoding="utf-8"))
                if state.get("pilot", {}).get("status") == "awaiting":
                    return path
            if proc.poll() is not None:
                stdout, stderr = proc.communicate()
                self.fail(f"run exited before review:\n{stdout}\n{stderr}")
            time.sleep(0.05)
        self.fail("pilot did not await review")

    def _wait_revisions(self, state_path: Path, count: int) -> None:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state.get("pilot", {}).get("revisions") == count:
                return
            time.sleep(0.05)
        self.fail("revision did not complete")

    def _revise(self, run_id: str, config: Path, env: dict[str, str], note: str) -> None:
        result = subprocess.run(
            [sys.executable, "ringer.py", "revise", run_id, "--note", note, "--config", str(config)],
            cwd=ROOT, env=env, text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
