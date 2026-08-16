#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ringer import weakened_assertion_violations  # noqa: E402


class ProtectAssertionsTests(unittest.TestCase):
    def test_removed_assertion_is_quoted_with_its_path(self) -> None:
        violations = weakened_assertion_violations(
            "tests/test_x.py",
            "@@ -1 +0,0 @@\n-        self.assertEqual(1, actual)\n",
        )

        self.assertEqual(1, len(violations))
        self.assertIn("tests/test_x.py", violations[0])
        self.assertIn("self.assertEqual(1, actual)", violations[0])

    def test_only_added_assertions_are_clean(self) -> None:
        violations = weakened_assertion_violations(
            "tests/test_x.py",
            "@@ -1,0 +2 @@\n+        self.assertEqual(1, actual)\n",
        )

        self.assertEqual([], violations)

    def _init_repo(self, repo: Path) -> None:
        (repo / "tests").mkdir(parents=True)
        (repo / "src").mkdir()
        (repo / "tests" / "test_existing.py").write_text(
            "def test_value():\n    assert value == 1\n",
            encoding="utf-8",
        )
        (repo / "src" / "existing.py").write_text(
            "def check():\n    assert value == 1\n",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env.update(
            {
                "GIT_AUTHOR_NAME": "test",
                "GIT_AUTHOR_EMAIL": "test@example.com",
                "GIT_COMMITTER_NAME": "test",
                "GIT_COMMITTER_EMAIL": "test@example.com",
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_SYSTEM": "/dev/null",
            }
        )
        for args in (
            ("init", "--quiet"),
            ("add", "."),
            ("commit", "--quiet", "-m", "base"),
        ):
            subprocess.run(["git", "-C", str(repo), *args], check=True, env=env)

    def _run(self, action: str, protect: list[str]) -> subprocess.CompletedProcess[str]:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        repo = root / "repo"
        self._init_repo(repo)
        worker = (
            "from pathlib import Path; import sys; action=sys.argv[1]; "
            "p=Path('tests/test_new.py') if action == 'new' else "
            "Path('src/existing.py') if action == 'outside' else "
            "Path('tests/test_existing.py'); "
            "p.write_text('def test_new():\\n    assert True\\n') if action == 'new' "
            "else p.write_text(p.read_text().replace('    assert value == 1\\n', ''))"
        )
        config = root / "config.toml"
        config.write_text(
            "\n".join(
                [
                    f"state_dir = {json.dumps(str(root / 'state'))}",
                    "[artifact]",
                    "enabled = false",
                    "[engines.mock]",
                    f"bin = {json.dumps(sys.executable)}",
                    "args_template = [",
                    '  "-c",',
                    f"  {json.dumps(worker)},",
                    '  "{spec}",',
                    "]",
                    "sandbox_args = []",
                    "full_access_args = []",
                    'model_default = "mock-model"',
                ]
            ),
            encoding="utf-8",
        )
        manifest: dict[str, Any] = {
            "run_name": "protect-test",
            "workdir": str(root / "work"),
            "max_parallel": 1,
            "worktrees": True,
            "repo": str(repo),
            "protect_assertions": protect,
            "tasks": [
                {
                    "key": "lane",
                    "engine": "mock",
                    "spec": action,
                    "check": "true",
                    "max_attempts": 1,
                }
            ],
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        env = os.environ.copy()
        env.update(
            {
                "RINGER_NO_SELF_UPDATE": "1",
                "RINGER_NO_CATALOG_REFRESH": "1",
                "RINGER_HOME": str(root / "ringer-home"),
                "XDG_CONFIG_HOME": str(root / "xdg"),
            }
        )
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "ringer.py"),
                "run",
                str(manifest_path),
                "--config",
                str(config),
                "--no-dashboard",
                "--identity",
                "protect-test",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=30,
            check=False,
        )

    def test_brand_new_protected_file_is_clean(self) -> None:
        proc = self._run("new", ["tests/**"])
        self.assertEqual(0, proc.returncode, proc.stdout)

    def test_modified_protected_file_fails_with_actionable_message(self) -> None:
        proc = self._run("remove", ["tests/**"])
        self.assertNotEqual(0, proc.returncode, proc.stdout)
        self.assertIn("tests/test_existing.py", proc.stdout)
        self.assertIn("assert value == 1", proc.stdout)

    def test_unmatched_modified_file_is_clean(self) -> None:
        proc = self._run("outside", ["tests/**"])
        self.assertEqual(0, proc.returncode, proc.stdout)

    def test_empty_setting_disables_guard(self) -> None:
        proc = self._run("remove", [])
        self.assertEqual(0, proc.returncode, proc.stdout)


if __name__ == "__main__":
    unittest.main()
