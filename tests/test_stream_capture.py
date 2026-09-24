#!/usr/bin/env python3
"""Offline CLI regression: source bytes, final usage and model report survive PTY capture."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "ringer.py"
SOURCE = Path(os.environ.get("RINGER_STREAM_SOURCE", DEFAULT_SOURCE)).resolve()
PAYLOAD = ("“quoted” 🧠 café — 中文 日本語 한국어\n" * 20000).encode("utf-8")
FINAL = b'{"type":"result","status":"complete"}\ntokens used: 12,345\nreported model: claude-opus-5\n'
EXPECTED = b"STREAM_BEGIN\n" + PAYLOAD + FINAL + b"STREAM_END\n"


def toml_string(value: object) -> str:
    return json.dumps(str(value))


class StreamCaptureCliTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "The worker path uses a real POSIX PTY")
    def test_unicode_large_log_and_final_metadata_through_real_cli(self) -> None:
        # No credentials, network, installed configuration, or shared run history.
        with tempfile.TemporaryDirectory(prefix="ringer-stream-cli-") as directory:
            root = Path(directory)
            state = root / "state"
            work = root / "work"
            payload = root / "payload.bin"
            payload.write_bytes(EXPECTED)
            worker = root / "worker.py"
            worker.write_text(
                "import os\nfrom pathlib import Path\n"
                f"raw = Path({str(payload)!r}).read_bytes()\n"
                "assert os.isatty(1), 'expected real PTY path'\n"
                "os.write(1, b'\\x1b[32m')\n"
                "for offset in range(0, len(raw), 257):\n"
                "    block = raw[offset:offset + 257]\n"
                "    while block:\n"
                "        block = block[os.write(1, block):]\n"
                "os.write(1, b'\\x1b[0m')\n"
                "Path('done.txt').write_text('complete\\n')\n",
                encoding="utf-8",
            )
            config = root / "config.toml"
            config.write_text(
                "\n".join([
                    f"state_dir = {toml_string(state)}",
                    "[eval]", 'backend = "jsonl"',
                    f"jsonl_path = {toml_string(root / 'eval.jsonl')}",
                    "[artifact]", "enabled = false",
                    "[update]", "auto = false",
                    "[steering]", f"dir = {toml_string(root / 'steering')}",
                    "inject_candidates = false",
                    "[engines.mock]", f"bin = {toml_string(sys.executable)}",
                    f"args_template = [{toml_string(worker)}]",
                    "sandbox_args = []", "full_access_args = []",
                    r"model_report_regex = 'reported model: ([^\r\n]+)'",
                ]) + "\n",
                encoding="utf-8",
            )
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "run_name": "stream-capture-regression",
                "workdir": str(work),
                "max_parallel": 1,
                "worktrees": False,
                "tasks": [{
                    "key": "unicode",
                    "engine": "mock",
                    "spec": "Deterministic offline stream fixture; no model is invoked.",
                    "check": "test -s done.txt",
                    "expect_files": ["done.txt"],
                    "max_attempts": 1,
                    "timeout_s": 20,
                }],
            }), encoding="utf-8")
            env = os.environ.copy()
            env["RINGER_HOME"] = str(root / "ringer-home")
            env["RINGER_NO_CATALOG_REFRESH"] = "1"
            env["RINGER_STEERING_DIR"] = str(root / "steering")
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            command = [
                sys.executable, "-B", str(SOURCE),
                "--config", str(config), "--no-self-update",
                "run", str(manifest), "--no-dashboard",
                "--identity", "offline-stream-regression",
            ]
            result = subprocess.run(
                command, cwd=root, env=env,
                capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            log = (work / "unicode" / "worker.log").read_bytes()
            start = log.index(b"STREAM_BEGIN\n")
            end = log.find(b"STREAM_END\n", start)
            self.assertGreaterEqual(end, start, "final stream marker was lost")
            captured = log[start:end + len(b"STREAM_END\n")]
            self.assertEqual(
                hashlib.sha256(EXPECTED).hexdigest(),
                hashlib.sha256(captured).hexdigest(),
                f"expected {len(EXPECTED)} source bytes, captured {len(captured)}",
            )
            self.assertGreater(len(captured), 1_000_000)
            self.assertNotIn(b"\x1b", captured)
            runs = list((state / "runs").glob("*.json"))
            self.assertEqual(len(runs), 1, runs)
            record = json.loads(runs[0].read_text())
            task = record["tasks"][0]
            self.assertEqual(task["tokens"], 12345)
            self.assertEqual(task["attempt_records"][0]["model"], "claude-opus-5")
            self.assertEqual(task["attempt_records"][0]["worker_returncode"], 0)
            self.assertEqual((work / "unicode" / "done.txt").read_text(), "complete\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
