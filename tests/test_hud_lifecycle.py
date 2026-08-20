#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import multiprocessing
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ringer  # noqa: E402
from ringer import PersistentHudServer  # noqa: E402
from tests.test_hud_single_tab import config as base_config  # noqa: E402


def run_hud_process(config: ringer.AppConfig, port: int) -> None:
    raise SystemExit(ringer.run_persistent_hud(config, port=port, open_viewer=False))


class HudLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="ringer-hud-lifecycle-")
        self.addCleanup(self.tmp.cleanup)
        self.config = base_config(Path(self.tmp.name))

    def capture(self, function: object, *args: object, **kwargs: object) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = function(*args, **kwargs)  # type: ignore[operator]
        return result, output.getvalue()

    def start_ringside(self) -> tuple[PersistentHudServer, int]:
        server = PersistentHudServer(self.config.state_dir, preferred_port=0, open_viewer=False)
        port = server.start()
        self.addCleanup(server.stop)
        return server, port

    def ephemeral_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            return int(probe.getsockname()[1])

    def test_probe_rejects_unrelated_200_and_accepts_ringside(self) -> None:
        class UnrelatedHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                body = json.dumps({"server": {"ringer_version": "impostor"}}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        unrelated = ThreadingHTTPServer(("127.0.0.1", 0), UnrelatedHandler)
        thread = threading.Thread(target=unrelated.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(unrelated.server_close)
        self.addCleanup(unrelated.shutdown)
        unrelated_port = int(unrelated.server_address[1])
        self.assertFalse(ringer.hud_is_alive(unrelated_port))

        _server, ringside_port = self.start_ringside()
        self.assertTrue(ringer.hud_is_alive(ringside_port))
        self.assertEqual(ringer.RINGSIDE_SERVICE, ringer.hud_identity(ringside_port)["service"])

    def test_status_not_running_is_successful(self) -> None:
        probe = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
        port = int(probe.server_address[1])
        probe.server_close()
        result, output = self.capture(ringer.status_persistent_hud, self.config, port=port)
        self.assertEqual(0, result)
        self.assertIn("Ringside", output)
        self.assertIn("not running", output)

    def test_status_reports_started_ephemeral_instance(self) -> None:
        _server, port = self.start_ringside()
        result, output = self.capture(ringer.status_persistent_hud, self.config, port=port)
        self.assertEqual(0, result)
        self.assertIn("Ringside is running", output)
        self.assertIn("version=", output)
        self.assertIn(f"pid={ringer.os.getpid()}", output)

    def test_stop_is_graceful_and_second_stop_is_noop(self) -> None:
        _server, port = self.start_ringside()
        result, output = self.capture(ringer.stop_persistent_hud, self.config, port=port)
        self.assertEqual(0, result)
        self.assertIn("Ringside stopped", output)
        result, output = self.capture(ringer.stop_persistent_hud, self.config, port=port)
        self.assertEqual(0, result)
        self.assertIn("nothing to stop", output)

    def test_stop_ends_the_foreground_hud_process(self) -> None:
        port = self.ephemeral_port()
        process = multiprocessing.Process(
            target=run_hud_process,
            args=(self.config, port),
        )
        process.start()
        self.addCleanup(process.join, 2)
        self.addCleanup(process.terminate)

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not ringer.hud_is_alive(port):
            if not process.is_alive():
                self.fail(f"foreground Ringside exited early with {process.exitcode}")
            time.sleep(0.05)
        self.assertTrue(ringer.hud_is_alive(port))
        identity = ringer.hud_identity(port)
        self.assertIsNotNone(identity)
        self.assertEqual(process.pid, identity["pid"])

        result, output = self.capture(ringer.stop_persistent_hud, self.config, port=port)
        self.assertEqual(0, result)
        self.assertIn("Ringside stopped", output)
        process.join(5)
        self.assertFalse(process.is_alive(), f"stopped Ringside process {process.pid} leaked")
        self.assertEqual(0, process.exitcode)
        with self.assertRaises(ProcessLookupError):
            os.kill(process.pid, 0)

    def test_mismatched_recorded_pid_is_not_acted_on(self) -> None:
        server, port = self.start_ringside()
        record_path = ringer.hud_instance_record_path(self.config.state_dir, port)
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["pid"] = record["pid"] + 1
        ringer.atomic_write_json(record_path, record)
        result, output = self.capture(ringer.stop_persistent_hud, self.config, port=port)
        self.assertEqual(1, result)
        self.assertIn("not stopped", output)
        self.assertTrue(ringer.hud_is_alive(port))
        server.stop()

    def test_detached_spawn_closes_stdin_starts_session_and_waits_for_health(self) -> None:
        port = 43123
        process = mock.Mock()
        with mock.patch.object(ringer.subprocess, "Popen", return_value=process) as popen, mock.patch.object(
            ringer, "hud_is_alive", side_effect=[False, True]
        ), mock.patch.object(ringer.time, "sleep"):
            alive, error = ringer.spawn_detached_hud(self.config, port=port)

        self.assertTrue(alive)
        self.assertIsNone(error)
        command = popen.call_args.args[0]
        self.assertEqual(["--no-open", "--port", str(port)], command[-3:])
        self.assertIs(ringer.subprocess.DEVNULL, popen.call_args.kwargs["stdin"])
        self.assertTrue(popen.call_args.kwargs["start_new_session"])

    def test_restart_returns_failure_when_detached_replacement_is_not_live(self) -> None:
        port = 43124
        with mock.patch.object(ringer, "stop_persistent_hud", return_value=0), mock.patch.object(
            ringer, "spawn_detached_hud", return_value=(False, None)
        ):
            result, output = self.capture(ringer.restart_persistent_hud, self.config, port=port)

        self.assertEqual(1, result)
        self.assertIn("restart failed", output)
        self.assertIn("no live instance", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
