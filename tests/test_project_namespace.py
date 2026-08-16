#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ringer import (  # noqa: E402
    ArtifactConfig,
    ArtifactRenderer,
    EngineConfig,
    Manifest,
    PersistentHudServer,
    StateWriter,
    TaskRuntime,
    TaskSpec,
    artifact_live_path,
    read_artifact_library,
    running_ringer_version,
    scan_run_states,
)


class ProjectNamespaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ringer-project-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state_dir = self.root / "state"
        self.engine = EngineConfig(
            name="mock",
            bin=sys.executable,
            args_template=("-c", "pass"),
            full_access_args=(),
            sandbox_args=(),
        )
        self.artifact = ArtifactConfig(
            enabled=True,
            out_template=str(self.state_dir / "artifacts" / "{run_id}.html"),
            report_template=str(self.state_dir / "artifacts" / "{run_id}-report.html"),
            index_out=self.state_dir / "artifacts" / "index.html",
        )

    def manifest(self, **extra: object) -> Manifest:
        obj: dict[str, object] = {
            "run_name": "build",
            "workdir": str(self.root / "work"),
            "tasks": [{"key": "one", "spec": "work", "check": "true"}],
        }
        obj.update(extra)
        return Manifest.from_obj(obj)

    def runtime(self, suffix: str) -> TaskRuntime:
        taskdir = self.root / f"task-{suffix}"
        taskdir.mkdir()
        log_path = taskdir / "worker.log"
        log_path.write_text(suffix, encoding="utf-8")
        return TaskRuntime(
            task=TaskSpec(key="one", spec=suffix, check="true", engine="mock"),
            taskdir=taskdir,
            log_path=log_path,
            status="running",
        )

    def writer(self, project: Path, suffix: str) -> StateWriter:
        return StateWriter(
            f"run-{suffix}",
            "build",
            "test",
            self.state_dir,
            {"mock": self.engine},
            datetime(2026, 8, 16, tzinfo=timezone.utc),
            [self.runtime(suffix)],
            threading.RLock(),
            artifact=self.artifact,
            project=project,
        )

    def test_project_derives_from_repo_and_falls_back_to_workdir(self) -> None:
        repo = self.root / "repo"
        self.assertEqual(repo.resolve(), self.manifest(repo=str(repo)).project)
        self.assertEqual((self.root / "work").resolve(), self.manifest().project)

    def test_same_run_name_in_two_projects_has_distinct_live_artifacts(self) -> None:
        first = self.writer(self.root / "a" / "repo", "first")
        second = self.writer(self.root / "b" / "repo", "second")
        first.flush()
        first_html = first.live_path.read_text(encoding="utf-8")
        second.flush()

        self.assertNotEqual(first.live_path, second.live_path)
        self.assertEqual(first_html, first.live_path.read_text(encoding="utf-8"))
        self.assertTrue(second.live_path.is_file())
        entries = list(read_artifact_library(self.state_dir)["artifacts"].values())
        self.assertEqual(2, len(entries))
        self.assertEqual(2, len({entry["project"] for entry in entries}))

    def test_legacy_flat_artifact_and_library_still_resolve(self) -> None:
        legacy = artifact_live_path(self.state_dir, "build")
        legacy.parent.mkdir(parents=True)
        legacy.write_text("legacy", encoding="utf-8")
        library_path = self.state_dir / "artifacts" / "library.json"
        library_path.write_text(
            json.dumps({"artifacts": {"build": {"live_path": str(legacy), "versions": []}}}),
            encoding="utf-8",
        )

        loaded = read_artifact_library(self.state_dir)
        resolved = Path(loaded["artifacts"]["build"]["live_path"])
        self.assertEqual("legacy", resolved.read_text(encoding="utf-8"))

    def test_historical_state_without_new_fields_loads_and_renders(self) -> None:
        runs = self.state_dir / "runs"
        runs.mkdir(parents=True)
        old_state = {
            "run_id": "old",
            "run_name": "build",
            "state": "finished",
            "finished": True,
            "started_at": "2026-01-01T00:00:00+00:00",
            "tasks": [],
            "totals": {"pass": 0, "fail": 0, "tokens": 0},
        }
        (runs / "old.json").write_text(json.dumps(old_state), encoding="utf-8")

        loaded = scan_run_states(self.state_dir)
        self.assertEqual("old", loaded[0]["run_id"])
        html = ArtifactRenderer(self.root / "old.html").render_final_report_html(old_state)
        self.assertIn("build", html)

    def test_ringer_version_is_persisted_and_returned_by_api(self) -> None:
        writer = self.writer(self.root / "repo", "version")
        state = writer.flush()
        self.assertEqual(running_ringer_version(), state["ringer_version"])

        server = PersistentHudServer(self.state_dir, preferred_port=0, open_viewer=False)
        port = server.start()
        self.addCleanup(server.stop)
        with urlopen(f"http://127.0.0.1:{port}/api/runs", timeout=5) as response:
            payload = json.loads(response.read())
        self.assertEqual(running_ringer_version(), payload["server"]["ringer_version"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
