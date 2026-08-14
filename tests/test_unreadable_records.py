#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ringer  # noqa: E402
from ringer import PersistentHudServer  # noqa: E402


class UnreadableRecordsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_env = os.environ.copy()
        self.addCleanup(self.restore_env)
        self.root = Path(self.tmp.name)
        os.environ["HOME"] = str(self.root / "home")
        os.environ["RINGER_HOME"] = str(self.root / "ringer-home")
        os.environ["RINGER_NO_SELF_UPDATE"] = "1"
        self.state_dir = self.root / "state"
        self.runs_dir = self.state_dir / "runs"
        self.artifacts_dir = self.state_dir / "artifacts"
        self.runs_dir.mkdir(parents=True)
        self.artifacts_dir.mkdir(parents=True)
        Path(os.environ["RINGER_HOME"]).mkdir(parents=True)
        (Path(os.environ["RINGER_HOME"]) / "active-runs.json").write_text(
            "{}\n",
            encoding="utf-8",
        )
        self.ringside_stub = self.root / "ringside.html"
        self.ringside_stub.write_text("<!doctype html><main>stub</main>\n", encoding="utf-8")
        patcher = mock.patch.object(ringer, "RINGSIDE_HTML_PATH", self.ringside_stub)
        patcher.start()
        self.addCleanup(patcher.stop)

    def restore_env(self) -> None:
        os.environ.clear()
        os.environ.update(self.old_env)

    def write_run(self, run_id: str, mtime: float) -> None:
        path = self.runs_dir / f"{run_id}.json"
        path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "run_name": run_id,
                    "state": "finished",
                    "finished": True,
                    "started_at": f"2026-07-05T12:{int(mtime):02d}:00+00:00",
                    "tasks": [],
                }
            ),
            encoding="utf-8",
        )
        os.utime(path, (mtime, mtime))

    def write_corrupt_run(self, name: str, mtime: float) -> None:
        path = self.runs_dir / f"{name}.json"
        path.write_text("{not json\n", encoding="utf-8")
        os.utime(path, (mtime, mtime))

    def start_server(self) -> tuple[PersistentHudServer, str]:
        server = PersistentHudServer(self.state_dir, preferred_port=0, open_viewer=False)
        port = server.start()
        self.addCleanup(server.stop)
        return server, f"http://127.0.0.1:{port}"

    def get_json(self, base: str, path: str) -> dict[str, object]:
        with urlopen(f"{base}{path}", timeout=5) as response:
            self.assertEqual(200, response.status)
            return json.loads(response.read().decode("utf-8"))

    def test_corrupt_run_files_are_counted(self) -> None:
        self.write_run("valid-run", 1.0)
        self.write_corrupt_run("corrupt-run", 2.0)
        _server, base = self.start_server()

        payload = self.get_json(base, "/api/runs")

        self.assertEqual(1, payload["unreadable"])
        self.assertEqual(["valid-run"], [run["run_id"] for run in payload["runs"]])

    def test_newest_corrupt_files_do_not_consume_valid_run_slots(self) -> None:
        for index in range(12):
            self.write_run(f"valid-{index:02d}", float(index + 1))
        for index in range(4):
            self.write_corrupt_run(f"corrupt-{index:02d}", float(13 + index))
        _server, base = self.start_server()

        payload = self.get_json(base, "/api/runs")

        self.assertEqual(4, payload["unreadable"])
        self.assertEqual(12, len(payload["runs"]))
        self.assertEqual(
            [f"valid-{index:02d}" for index in reversed(range(12))],
            [run["run_id"] for run in payload["runs"]],
        )

    def test_corrupt_artifact_library_is_reported_unreadable(self) -> None:
        library_path = self.artifacts_dir / "library.json"
        library_path.write_text("{not json\n", encoding="utf-8")
        _server, base = self.start_server()

        payload = self.get_json(base, "/api/library")

        self.assertEqual({"artifacts": {}, "unreadable": 1}, payload)
        self.assertEqual("{not json\n", library_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
