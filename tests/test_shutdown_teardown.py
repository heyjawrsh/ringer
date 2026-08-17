from __future__ import annotations

import asyncio
import gc
import importlib.util
import signal
import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RINGER_PATH = ROOT / "ringer.py"
SPEC = importlib.util.spec_from_file_location("ringer_shutdown_module", RINGER_PATH)
assert SPEC is not None and SPEC.loader is not None
ringer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ringer
SPEC.loader.exec_module(ringer)


class _RecordingTransport:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FinishedProcess:
    def __init__(self) -> None:
        self.pid = 12345
        self.returncode = 0
        self._transport = _RecordingTransport()
        self.waited = False

    async def wait(self) -> int:
        self.waited = True
        return 0


class ShutdownTransportTests(unittest.TestCase):
    def test_kill_all_workers_waits_and_closes_owned_transports(self) -> None:
        runner = object.__new__(ringer.RingerRunner)
        proc = _FinishedProcess()
        runner.active_processes = {proc.pid: proc}

        asyncio.run(runner.kill_all_workers())

        self.assertTrue(proc.waited)
        self.assertTrue(proc._transport.closed)
        self.assertEqual(runner.active_processes, {})

    def test_cancelled_run_has_no_closed_loop_unraisable_after_forced_gc(self) -> None:
        # One end-to-end attempt is worthless for a roughly 4% GC-timing race.
        # Retain the Process until after asyncio.run closes its loop, then force
        # collection under an unraisable hook so transport leaks are deterministic.
        retained: list[Any] = []
        unraisable: list[Any] = []
        original_hook = sys.unraisablehook

        async def cancelled_run() -> None:
            runner = object.__new__(ringer.RingerRunner)
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                "import time; time.sleep(30)",
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
            runner.active_processes = {proc.pid: proc}
            retained.append(proc)
            task = asyncio.current_task()
            assert task is not None
            asyncio.get_running_loop().call_soon(task.cancel)
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                await runner.kill_all_workers()
                raise

        try:
            sys.unraisablehook = unraisable.append
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(cancelled_run())
            retained.clear()
            gc.collect()
        finally:
            sys.unraisablehook = original_hook
            for proc in retained:
                if proc.returncode is None:
                    try:
                        proc.send_signal(signal.SIGKILL)
                    except ProcessLookupError:
                        pass

        closed_loop_errors = [
            item
            for item in unraisable
            if isinstance(item.exc_value, RuntimeError)
            and "Event loop is closed" in str(item.exc_value)
        ]
        self.assertEqual(closed_loop_errors, [])


if __name__ == "__main__":
    unittest.main()
