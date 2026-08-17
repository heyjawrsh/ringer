#!/usr/bin/env python3
from __future__ import annotations

import multiprocessing
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ringer import (  # noqa: E402
    append_artifact_library_version,
    read_artifact_library,
    update_artifact_library_live,
)


WRITER_COUNT = 8


def _update_live(state_dir: str, index: int, barrier: Any) -> None:
    barrier.wait()
    update_artifact_library_live(
        Path(state_dir),
        run_name=f"Concurrent Run {index}",
        run_id=f"run-{index}",
        identity=f"agent-{index}",
        state="live",
    )


def _append_version(state_dir: str, index: int, barrier: Any) -> None:
    barrier.wait()
    root = Path(state_dir)
    append_artifact_library_version(
        root,
        run_name="Shared Run",
        run_id=f"run-{index}",
        identity=f"agent-{index}",
        outcome="pass",
        version_path=root / "artifacts" / "versions" / f"run-{index}.html",
        report_path=None,
        tasks_pass=1,
        tasks_fail=0,
    )


class ArtifactLibraryLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_dir = Path(self.tmp.name) / "state"

    def run_concurrently(self, target: Callable[..., None]) -> None:
        context = multiprocessing.get_context("spawn")
        barrier = context.Barrier(WRITER_COUNT)
        processes = [
            context.Process(target=target, args=(str(self.state_dir), index, barrier))
            for index in range(WRITER_COUNT)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(20)
        for process in processes:
            self.assertFalse(process.is_alive())
            self.assertEqual(0, process.exitcode)

    def test_concurrent_live_updates_all_survive(self) -> None:
        self.run_concurrently(_update_live)

        artifacts = read_artifact_library(self.state_dir)["artifacts"]
        self.assertEqual(
            {f"Concurrent Run {index}" for index in range(WRITER_COUNT)},
            set(artifacts),
        )
        self.assertEqual(
            {f"run-{index}" for index in range(WRITER_COUNT)},
            {entry["current_run_id"] for entry in artifacts.values()},
        )

    def test_concurrent_version_appends_all_survive(self) -> None:
        self.run_concurrently(_append_version)

        entry = read_artifact_library(self.state_dir)["artifacts"]["Shared Run"]
        self.assertEqual(WRITER_COUNT, len(entry["versions"]))
        self.assertEqual(
            {f"run-{index}" for index in range(WRITER_COUNT)},
            {version["run_id"] for version in entry["versions"]},
        )


if __name__ == "__main__":
    unittest.main()
