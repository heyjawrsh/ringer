from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RINGER_PATH = ROOT / "ringer.py"
SPEC = importlib.util.spec_from_file_location("ringer_check_timeout_module", RINGER_PATH)
assert SPEC is not None and SPEC.loader is not None
ringer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ringer
SPEC.loader.exec_module(ringer)


def task_obj(**overrides: object) -> dict[str, object]:
    task: dict[str, object] = {
        "key": "check-timeout",
        "spec": "Exercise the check timeout.",
        "check": "true",
    }
    task.update(overrides)
    return task


class CheckTimeoutTests(unittest.TestCase):
    def test_default_is_existing_check_timeout(self) -> None:
        task = ringer.TaskSpec.from_obj(task_obj())

        self.assertEqual(task.check_timeout_s, ringer.CHECK_TIMEOUT_S)
        self.assertEqual(task.check_timeout_s, 60)

    def test_generous_timeout_allows_slow_check_to_finish(self) -> None:
        task = ringer.TaskSpec.from_obj(
            task_obj(check="sleep 1; printf finished", check_timeout_s=3)
        )
        with tempfile.TemporaryDirectory(prefix="ringer-check-timeout-") as tmp:
            result = asyncio.run(ringer.Verifier().verify(task, Path(tmp)))

        self.assertTrue(result.ok)
        self.assertFalse(result.check_timed_out)
        self.assertIn("finished", result.raw_output_excerpt)

    def test_short_timeout_kills_check_and_reports_applied_value(self) -> None:
        task = ringer.TaskSpec.from_obj(
            task_obj(check="sleep 2", check_timeout_s=1)
        )
        with tempfile.TemporaryDirectory(prefix="ringer-check-timeout-") as tmp:
            result = asyncio.run(ringer.Verifier().verify(task, Path(tmp)))

        self.assertFalse(result.ok)
        self.assertTrue(result.check_timed_out)
        self.assertIn("check timed out after 1s", result.raw_output_excerpt)

    def test_rejects_non_integer_timeout(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "check_timeout_s must be an integer, got str"
        ):
            ringer.TaskSpec.from_obj(task_obj(check_timeout_s="5"))

    def test_rejects_zero_or_negative_timeout(self) -> None:
        for value in (0, -1):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "check_timeout_s must be positive"
            ):
                ringer.TaskSpec.from_obj(task_obj(check_timeout_s=value))

    def test_rejects_boolean_timeout(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "check_timeout_s must be an integer, got bool"
        ):
            ringer.TaskSpec.from_obj(task_obj(check_timeout_s=True))


if __name__ == "__main__":
    unittest.main()
