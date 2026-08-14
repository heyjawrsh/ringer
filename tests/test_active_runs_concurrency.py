#!/usr/bin/env python3
from __future__ import annotations

import multiprocessing
import os
import queue
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ringer import read_active_runs, register_active_run, unregister_active_run  # noqa: E402


def _active_run_worker(
    ringer_home: str,
    action: str,
    run_id: str,
    ready: Any,
    completed: Any,
    release: Any,
    errors: Any,
) -> None:
    os.environ["RINGER_HOME"] = ringer_home
    try:
        ready.wait(timeout=15)
        if action == "register":
            register_active_run(run_id, "worker", run_id, Path(ringer_home))
        else:
            unregister_active_run(run_id)
    except BaseException as exc:
        errors.put(f"{action} {run_id}: {exc!r}")
    finally:
        try:
            completed.wait(timeout=15)
            release.wait(timeout=15)
        except BaseException as exc:
            errors.put(f"barrier {action} {run_id}: {exc!r}")


class ActiveRunsConcurrencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_env = os.environ.copy()
        self.addCleanup(self.restore_env)
        self.ringer_home = Path(self.tmp.name) / "ringer-home"
        os.environ["RINGER_HOME"] = str(self.ringer_home)

    def restore_env(self) -> None:
        os.environ.clear()
        os.environ.update(self.old_env)

    def run_concurrently(self, operations: list[tuple[str, str]]) -> dict[str, dict[str, Any]]:
        context = multiprocessing.get_context()
        participants = len(operations) + 1
        ready = context.Barrier(participants)
        completed = context.Barrier(participants)
        release = context.Barrier(participants)
        errors = context.Queue()
        processes = [
            context.Process(
                target=_active_run_worker,
                args=(
                    str(self.ringer_home),
                    action,
                    run_id,
                    ready,
                    completed,
                    release,
                    errors,
                ),
            )
            for action, run_id in operations
        ]
        for process in processes:
            process.start()

        runs: dict[str, dict[str, Any]] = {}
        try:
            ready.wait(timeout=15)
            completed.wait(timeout=15)
            runs = read_active_runs()
        finally:
            try:
                release.wait(timeout=15)
            except threading.BrokenBarrierError:
                pass
            for process in processes:
                process.join(timeout=5)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)

        worker_errors: list[str] = []
        while True:
            try:
                worker_errors.append(errors.get_nowait())
            except queue.Empty:
                break
        self.assertEqual([], worker_errors)
        self.assertEqual([0] * len(processes), [process.exitcode for process in processes])
        return runs

    def test_simultaneous_registrations_preserve_every_run(self) -> None:
        run_ids = [f"run-{index:02d}" for index in range(12)]

        runs = self.run_concurrently([("register", run_id) for run_id in run_ids])

        self.assertEqual(run_ids, sorted(runs))

    def test_concurrent_register_and_unregister_preserve_other_updates(self) -> None:
        register_active_run("stable", "parent", "Stable", Path(self.tmp.name))
        removed = [f"remove-{index}" for index in range(4)]
        for run_id in removed:
            register_active_run(run_id, "parent", run_id, Path(self.tmp.name))
        added = [f"added-{index}" for index in range(4)]

        runs = self.run_concurrently(
            [("register", run_id) for run_id in added]
            + [("unregister", run_id) for run_id in removed]
        )

        self.assertEqual(sorted(["stable", *added]), sorted(runs))


if __name__ == "__main__":
    unittest.main(verbosity=2)
