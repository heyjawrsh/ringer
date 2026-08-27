#!/usr/bin/env python3
"""Crashed checks are distinct from honest assertion failures in no-worker gates."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ringer_crashed_check_test", ROOT / "ringer.py")
assert SPEC is not None and SPEC.loader is not None
RINGER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RINGER
SPEC.loader.exec_module(RINGER)


def toml_string(value: object) -> str:
    return json.dumps(str(value))


class CheckCrashedUnitTests(unittest.TestCase):
    def test_live_verdict_distinguishes_crash_from_honest_rejection(self) -> None:
        worker = RINGER.WorkerResult(returncode=0, timed_out=False, tokens=None)
        crashed = RINGER.VerifyResult(
            ok=False,
            check_returncode=127,
            check_timed_out=False,
            raw_output_excerpt="/bin/sh: missing-check: not found\n",
        )
        rejected = RINGER.VerifyResult(
            ok=False,
            check_returncode=1,
            check_timed_out=False,
            raw_output_excerpt="FAIL: expected clean content\n",
        )

        self.assertEqual("CRASHED", RINGER.verdict_for(worker, crashed))
        self.assertEqual("FAIL", RINGER.verdict_for(worker, rejected))
        self.assertNotIn(RINGER.verdict_for(worker, crashed), {"FAIL", "TIMEOUT"})

    def test_live_verdict_preserves_pass_timeout_and_worker_error(self) -> None:
        worker = RINGER.WorkerResult(returncode=0, timed_out=False, tokens=None)
        passed = RINGER.VerifyResult(
            ok=True,
            check_returncode=0,
            check_timed_out=False,
            raw_output_excerpt="",
        )
        timed_out = RINGER.VerifyResult(
            ok=False,
            check_returncode=None,
            check_timed_out=True,
            raw_output_excerpt="",
        )
        errored_worker = RINGER.WorkerResult(
            returncode=None,
            timed_out=False,
            tokens=None,
            error="worker could not start",
        )

        self.assertEqual("PASS", RINGER.verdict_for(worker, passed))
        self.assertEqual("TIMEOUT", RINGER.verdict_for(worker, timed_out))
        self.assertEqual("ERROR", RINGER.verdict_for(errored_worker, passed))

    def test_unhandled_exception_is_a_crash(self) -> None:
        output = (
            "Traceback (most recent call last):\n"
            '  File "check.py", line 1, in <module>\n'
            "TypeError: check exploded\n"
        )

        self.assertTrue(RINGER.check_crashed(1, output))
        self.assertTrue(
            RINGER.check_crashed(2, "/bin/sh: 1: Syntax error: unexpected end of file\n")
        )

    def test_missing_command_or_interpreter_is_a_crash(self) -> None:
        self.assertTrue(RINGER.check_crashed(127, "/bin/sh: missing: not found\n"))
        self.assertTrue(
            RINGER.check_crashed(
                2,
                "python3: can't open file '/tmp/missing.py': "
                "[Errno 2] No such file or directory\n",
            )
        )

    def test_silent_nonzero_exit_is_a_crash(self) -> None:
        self.assertTrue(RINGER.check_crashed(1, ""))
        self.assertTrue(
            RINGER.check_crashed(
                1, "[ringer] check failed silently (exit 1, no output)."
            )
        )

    def test_intentional_diagnostics_override_traceback(self) -> None:
        suite_failure = (
            "Traceback (most recent call last):\n"
            "AssertionError: mismatch\n"
            "Ran 1 test in 0.001s\n\n"
            "FAILED (failures=1)\n"
        )

        self.assertFalse(RINGER.check_crashed(1, "FAIL: expected clean content\n"))
        self.assertFalse(RINGER.check_crashed(1, suite_failure))


class CrashedCheckModeTests(unittest.TestCase):
    def run_mode(
        self, root: Path, tasks: list[dict[str, object]], mode: str
    ) -> subprocess.CompletedProcess[str]:
        home = root / "home"
        ringer_home = root / "ringer-home"
        state_dir = root / "state"
        config_path = root / "config.toml"
        manifest_path = root / "manifest.json"
        home.mkdir()
        ringer_home.mkdir()

        config_path.write_text(
            "\n".join(
                [
                    f"state_dir = {toml_string(state_dir)}",
                    "",
                    "[artifact]",
                    "enabled = false",
                    "",
                    "[engines.missing]",
                    'bin = "/nonexistent/engine-binary"',
                    'args_template = ["{spec}"]',
                    "sandbox_args = []",
                    "full_access_args = []",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        manifest_path.write_text(
            json.dumps(
                {
                    "run_name": "crashed-check-test",
                    "workdir": str(root / "work"),
                    "worktrees": False,
                    "tasks": tasks,
                }
            ),
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["HOME"] = str(home)
        env["RINGER_HOME"] = str(ringer_home)
        env["XDG_CONFIG_HOME"] = str(root / "xdg-config")
        env["RINGER_NO_SELF_UPDATE"] = "1"
        return subprocess.run(
            [
                sys.executable,
                "ringer.py",
                "run",
                str(manifest_path),
                "--config",
                str(config_path),
                "--no-dashboard",
                mode,
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )

    def test_prove_fail_distinguishes_crashes_from_honest_failures(self) -> None:
        python_crash = f"{shlex.quote(sys.executable)} -c " + shlex.quote(
            "raise TypeError('check exploded')"
        )
        suite_output = (
            "Traceback (most recent call last):\n"
            '  File "test_case.py", line 1, in test_value\n'
            "AssertionError: mismatch\n"
            "Ran 1 test in 0.001s\n\n"
            "FAILED (failures=1)\n"
        )
        with tempfile.TemporaryDirectory() as temp_root:
            proc = self.run_mode(
                Path(temp_root),
                [
                    {
                        "key": "unhandled-exception",
                        "engine": "missing",
                        "spec": "The check crashes.",
                        "known_bad": "true",
                        "check": python_crash,
                    },
                    {
                        "key": "missing-command",
                        "engine": "missing",
                        "spec": "The check command is missing.",
                        "known_bad": "true",
                        "check": "ringer-command-that-does-not-exist",
                    },
                    {
                        "key": "honest-failure",
                        "engine": "missing",
                        "spec": "The check rejects known-bad work intentionally.",
                        "known_bad": "true",
                        "check": "printf 'FAIL: expected clean content\\n'; exit 1",
                    },
                    {
                        "key": "suite-failure",
                        "engine": "missing",
                        "spec": "A test suite rejects known-bad work.",
                        "known_bad": "true",
                        "check": f"printf %s {shlex.quote(suite_output)}; exit 1",
                    },
                ],
                "--prove-fail",
            )
        output = proc.stdout + proc.stderr

        self.assertNotEqual(0, proc.returncode, output)
        self.assertRegex(
            output,
            re.compile(
                r"^unhandled-exception\s+prove-fail: CRASHED \(rc=1\)",
                re.MULTILINE,
            ),
        )
        self.assertRegex(
            output,
            re.compile(r"^missing-command\s+prove-fail: CRASHED \(rc=127\)", re.MULTILINE),
        )
        self.assertRegex(
            output,
            re.compile(r"^honest-failure\s+prove-fail: proved \(rc=1\)", re.MULTILINE),
        )
        self.assertRegex(
            output,
            re.compile(r"^suite-failure\s+prove-fail: proved \(rc=1\)", re.MULTILINE),
        )
        self.assertNotRegex(output, r"^honest-failure\s+prove-fail: CRASHED")
        self.assertNotRegex(output, r"^suite-failure\s+prove-fail: CRASHED")
        self.assertIn("The check itself failed to run, so this gate proves nothing.", output)
        self.assertIn(
            "prove-fail: 2 proved, 0 broken, 0 inconclusive, 2 error, "
            "0 skipped, covered 4 of 4 task(s).",
            output,
        )

    def test_prove_pass_reports_crashed_check_as_an_error_not_broken(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            proc = self.run_mode(
                Path(temp_root),
                [
                    {
                        "key": "crashed-good-check",
                        "engine": "missing",
                        "spec": "The known-good check crashes.",
                        "known_good": "true",
                        "check": "ringer-command-that-does-not-exist",
                    }
                ],
                "--prove-pass",
            )
        output = proc.stdout + proc.stderr

        self.assertNotEqual(0, proc.returncode, output)
        self.assertRegex(
            output,
            re.compile(
                r"^crashed-good-check\s+prove-pass: CRASHED \(rc=127\)",
                re.MULTILINE,
            ),
        )
        self.assertNotIn("prove-pass: BROKEN", output)
        self.assertIn(
            "prove-pass: 0 proved, 0 broken, 1 error, 0 skipped, "
            "covered 1 of 1 task(s).",
            output,
        )

    def test_baseline_reports_crashed_check_and_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            proc = self.run_mode(
                Path(temp_root),
                [
                    {
                        "key": "crashed-baseline",
                        "engine": "missing",
                        "spec": "The baseline check crashes.",
                        "check": "ringer-command-that-does-not-exist",
                    }
                ],
                "--baseline",
            )
        output = proc.stdout + proc.stderr

        self.assertNotEqual(0, proc.returncode, output)
        self.assertRegex(
            output,
            re.compile(
                r"^crashed-baseline\s+baseline: CRASHED \(rc=127\)",
                re.MULTILINE,
            ),
        )
        self.assertIn("baseline: 0 pass, 0 fail, 1 error of 1 check(s).", output)
        self.assertIn("1 check(s) could not run", output)
        self.assertIn("A crashed check proves nothing", output)
        self.assertIn("will not retry it or count it against the model", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
