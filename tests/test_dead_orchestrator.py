#!/usr/bin/env python3
from __future__ import annotations

import http.client
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ringer import PersistentHudServer  # noqa: E402


class DeadOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_env = os.environ.copy()
        self.addCleanup(self.restore_env)
        self.root = Path(self.tmp.name)
        os.environ["RINGER_HOME"] = str(self.root / "ringer-home")
        self.state_dir = self.root / "state"
        self.runs_dir = self.state_dir / "runs"
        self.decisions_dir = self.state_dir / "pilot-decisions"
        self.runs_dir.mkdir(parents=True)
        self.decisions_dir.mkdir(parents=True)
        self.dead_pid = 99999999
        self.seed_run("live-run", os.getpid())
        self.dead_decision_file = self.seed_run("dead-run", self.dead_pid)
        self.seed_active_runs()
        self.server = PersistentHudServer(
            self.state_dir,
            preferred_port=0,
            open_viewer=False,
        )
        self.port = self.server.start()
        self.addCleanup(self.server.stop)

    def restore_env(self) -> None:
        os.environ.clear()
        os.environ.update(self.old_env)

    def seed_run(self, run_id: str, pid: int) -> Path:
        decision_file = self.decisions_dir / f"{run_id}.json"
        state = {
            "run_id": run_id,
            "run_name": f"{run_id} test",
            "state": "live",
            "pid": pid,
            "tasks": [{"key": "pilot-lane", "status": "pass"}],
            "pilot": {
                "task": "pilot-lane",
                "status": "awaiting",
                "since": "2026-08-12T12:00:00+00:00",
                "wait_s": 1800,
                "decision_file": str(decision_file),
            },
        }
        (self.runs_dir / f"{run_id}.json").write_text(
            json.dumps(state, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return decision_file

    def seed_active_runs(self) -> None:
        active = {
            "live-run": {"pid": os.getpid()},
            "dead-run": {"pid": self.dead_pid},
        }
        ringer_home = Path(os.environ["RINGER_HOME"])
        ringer_home.mkdir(parents=True)
        (ringer_home / "active-runs.json").write_text(
            json.dumps(active, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def fetch_runs(self) -> dict[str, dict[str, object]]:
        with urlopen(f"http://127.0.0.1:{self.port}/api/runs", timeout=5) as response:
            self.assertEqual(200, response.status)
            payload = json.loads(response.read().decode("utf-8"))
        return {run["run_id"]: run for run in payload["runs"]}

    def test_active_orchestrator_is_reported_alive(self) -> None:
        runs = self.fetch_runs()

        self.assertIs(runs["live-run"]["orchestrator_alive"], True)

    def test_dead_orchestrator_is_reported_not_alive(self) -> None:
        runs = self.fetch_runs()

        self.assertIs(runs["dead-run"]["orchestrator_alive"], False)

    def test_dead_awaiting_run_refuses_decision(self) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.addCleanup(conn.close)
        body = json.dumps({"run_id": "dead-run", "decision": "approve"})
        conn.request(
            "POST",
            "/api/pilot/decision",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(409, response.status)
        self.assertIn("orchestrator exited", payload["error"])
        self.assertIn("can no longer be delivered", payload["error"])
        self.assertFalse(self.dead_decision_file.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
