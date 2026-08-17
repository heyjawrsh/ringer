#!/usr/bin/env python3
"""The artifact library must survive concurrent writers.

`update_artifact_library_live` reads the whole library, mutates it, and replaces
it. The replace is atomic, so the file is never corrupt - but without a lock
held ACROSS the read and the write, two processes that read the same version
each write a valid file and the later one silently discards the earlier one's
entry. Runs disappear from the library with nothing in any log to say so.

This is a multi-process test on purpose: the hazard is between processes, and
`fcntl` locks are per-process, so threads would not exercise the real thing.
It is deliberately contended rather than artificially interleaved - a rendezvous
inside the critical section would deadlock the very implementation it is meant
to verify.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WRITERS = 8

WORKER = """
import sys
sys.path.insert(0, {root!r})
from pathlib import Path
import ringer

state_dir = Path(sys.argv[1])
index = sys.argv[2]
ringer.update_artifact_library_live(
    state_dir,
    run_name="run-" + index,
    run_id="run-" + index + "-id",
    identity="tester",
    state="pass",
)
"""


class ArtifactLibraryConcurrencyTests(unittest.TestCase):
    def test_concurrent_writers_all_survive(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state_dir = Path(temp) / "state"
            (state_dir / "artifacts").mkdir(parents=True)
            script = Path(temp) / "worker.py"
            script.write_text(WORKER.format(root=str(ROOT)), encoding="utf-8")

            # Launch them all before waiting on any, so their read-modify-write
            # windows genuinely overlap.
            procs = [
                subprocess.Popen(
                    [sys.executable, str(script), str(state_dir), str(index)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                for index in range(WRITERS)
            ]
            for proc in procs:
                _out, err = proc.communicate(timeout=60)
                self.assertEqual(
                    0, proc.returncode, err.decode("utf-8", errors="replace")
                )

            library = json.loads(
                (state_dir / "artifacts" / "library.json").read_text(encoding="utf-8")
            )
            present = set(library.get("artifacts", {}))
            expected = {f"run-{index}" for index in range(WRITERS)}
            missing = sorted(expected - present)
            self.assertEqual(
                [],
                missing,
                f"{len(missing)} of {WRITERS} concurrent library writes were lost: "
                f"{missing}. The read-modify-write in update_artifact_library_live "
                "needs an exclusive lock held across BOTH the read and the write, "
                "with a re-read after the lock is acquired.",
            )


if __name__ == "__main__":
    unittest.main()
