#!/usr/bin/env python3
from __future__ import annotations

import http.client
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ringer import PersistentHudServer  # noqa: E402


class PilotDecisionEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state_dir = self.root / "state"
        self.runs_dir = self.state_dir / "runs"
        self.decisions_dir = self.state_dir / "pilot-decisions"
        self.runs_dir.mkdir(parents=True)
        self.decisions_dir.mkdir(parents=True)
        self.server = PersistentHudServer(
            self.state_dir,
            preferred_port=0,
            open_viewer=False,
        )
        self.port = self.server.start()
        self.addCleanup(self.server.stop)

    def seed_run(self, run_id: str, *, status: str = "awaiting") -> Path:
        decision_file = self.decisions_dir / f"{run_id}.json"
        state = {
            "run_id": run_id,
            "run_name": "Pilot endpoint test",
            "state": "live",
            "tasks": [{"key": "pilot-lane", "status": "pass"}],
            "pilot": {
                "task": "pilot-lane",
                "status": status,
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

    def request(
        self,
        method: str = "POST",
        *,
        run_id: str = "pilot-run",
        decision: str = "approve",
        origin: str | None = None,
        host: str | None = None,
    ) -> tuple[int, dict[str, object]]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.addCleanup(conn.close)
        headers = {"Content-Type": "application/json"}
        if origin is not None:
            headers["Origin"] = origin
        if host is not None:
            headers["Host"] = host
        body = json.dumps({"run_id": run_id, "decision": decision})
        conn.request(method, "/api/pilot/decision", body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        payload = json.loads(raw.decode("utf-8")) if raw else {}
        return response.status, payload

    def assert_decision_file(self, path: Path, expected: str) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual({"decision", "decided_at"}, set(payload))
        self.assertEqual(expected, payload["decision"])
        decided_at = datetime.fromisoformat(payload["decided_at"])
        self.assertIsNotNone(decided_at.tzinfo)

    def test_approve_writes_decision_file(self) -> None:
        decision_file = self.seed_run("approve-run")

        status, payload = self.request(
            run_id="approve-run",
            decision="approve",
            origin=f"http://127.0.0.1:{self.port}",
        )

        self.assertEqual(200, status)
        self.assertEqual("approve-run", payload["run_id"])
        self.assertEqual("approve", payload["decision"])
        self.assert_decision_file(decision_file, "approve")

    def test_reject_writes_decision_file(self) -> None:
        decision_file = self.seed_run("reject-run")

        status, payload = self.request(run_id="reject-run", decision="reject")

        self.assertEqual(200, status)
        self.assertEqual("reject", payload["decision"])
        self.assert_decision_file(decision_file, "reject")

    def test_run_not_awaiting_returns_conflict(self) -> None:
        decision_file = self.seed_run("approved-run", status="approved")

        status, _payload = self.request(run_id="approved-run", decision="approve")

        self.assertEqual(409, status)
        self.assertFalse(decision_file.exists())

    def test_cross_origin_post_is_forbidden(self) -> None:
        decision_file = self.seed_run("cross-origin-run")

        status, _payload = self.request(
            run_id="cross-origin-run",
            decision="approve",
            origin="https://example.test",
        )

        self.assertEqual(403, status)
        self.assertFalse(decision_file.exists())

    def test_non_loopback_host_is_forbidden(self) -> None:
        decision_file = self.seed_run("foreign-host-run")

        status, _payload = self.request(
            run_id="foreign-host-run",
            decision="approve",
            host="example.test",
        )

        self.assertEqual(403, status)
        self.assertFalse(decision_file.exists())

    def test_get_is_method_not_allowed(self) -> None:
        decision_file = self.seed_run("get-run")

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.addCleanup(conn.close)
        conn.request("GET", "/api/pilot/decision")
        response = conn.getresponse()
        response.read()

        self.assertEqual(405, response.status)
        self.assertFalse(decision_file.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
