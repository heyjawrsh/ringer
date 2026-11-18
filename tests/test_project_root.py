#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ringer import project_root_for, scan_hud_run_states_with_unreadable  # noqa: E402


class ProjectRootTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="ringer-project-root-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        project_root_for.cache_clear()
        self.addCleanup(project_root_for.cache_clear)

    def test_plain_checkout_and_subfolder(self) -> None:
        repo = self.root / "repo"
        (repo / ".git").mkdir(parents=True)
        subfolder = repo / "src" / "nested"
        subfolder.mkdir(parents=True)
        for project in (repo, subfolder):
            with self.subTest(project=project):
                self.assertEqual(str(repo), project_root_for(str(project) + "/"))

    @unittest.skipUnless(shutil.which("git"), "git is unavailable")
    def test_real_git_worktree(self) -> None:
        repo = self.root / "repo"
        worktree = self.root / "worktree"
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "--orphan", "-b", "test", str(worktree)],
            check=True,
            capture_output=True,
        )
        self.assertEqual(str(repo), project_root_for(str(worktree)))
        subfolder = worktree / "src"
        subfolder.mkdir()
        self.assertEqual(str(repo), project_root_for(str(subfolder)))

    def worktree(self, *, commondir: bool) -> tuple[Path, Path]:
        repo = self.root / "repo"
        gitdir = repo / ".git" / "worktrees" / "lane"
        gitdir.mkdir(parents=True)
        worktree = self.root / "lane"
        worktree.mkdir()
        (worktree / ".git").write_text(
            "gitdir: ../repo/.git/worktrees/lane\n", encoding="utf-8"
        )
        if commondir:
            (gitdir / "commondir").write_text("../..\n", encoding="utf-8")
        return repo, worktree

    def test_worktree_with_commondir(self) -> None:
        repo, worktree = self.worktree(commondir=True)
        self.assertEqual(str(repo), project_root_for(str(worktree)))

    def test_worktree_without_commondir(self) -> None:
        repo, worktree = self.worktree(commondir=False)
        self.assertEqual(str(repo), project_root_for(str(worktree)))

    def test_commondir_outside_worktrees_layout(self) -> None:
        repo = self.root / "repo"
        (repo / ".git").mkdir(parents=True)
        gitdir = self.root / "metadata"
        gitdir.mkdir()
        (gitdir / "commondir").write_text(str(repo / ".git"), encoding="utf-8")
        worktree = self.root / "lane"
        worktree.mkdir()
        (worktree / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
        self.assertEqual(str(repo), project_root_for(str(worktree)))

    def test_non_git_folder(self) -> None:
        folder = self.root / "plain"
        folder.mkdir()
        self.assertEqual(str(folder), project_root_for(str(folder / ".." / "plain")))

    def test_home_repository_does_not_absorb_non_git_project(self) -> None:
        (self.root / ".git").mkdir()
        folder = self.root / "Work" / "Playground" / "project" / "lanes"
        folder.mkdir(parents=True)
        with patch.object(Path, "home", return_value=self.root):
            self.assertEqual(str(folder), project_root_for(str(folder)))

    def test_checkout_below_home_repository_still_resolves(self) -> None:
        (self.root / ".git").mkdir()
        repo = self.root / "Work" / "repo"
        (repo / ".git").mkdir(parents=True)
        folder = repo / "src"
        folder.mkdir()
        with patch.object(Path, "home", return_value=self.root):
            self.assertEqual(str(repo), project_root_for(str(folder)))

    def test_explicit_home_project_still_resolves(self) -> None:
        (self.root / ".git").mkdir()
        with patch.object(Path, "home", return_value=self.root):
            self.assertEqual(str(self.root), project_root_for(str(self.root)))

    def test_missing_path_inside_checkout_returns_itself(self) -> None:
        (self.root / ".git").mkdir()
        missing = self.root / "missing"
        self.assertEqual(str(missing), project_root_for(str(missing)))

    def test_none_and_empty(self) -> None:
        self.assertIsNone(project_root_for(None))
        self.assertIsNone(project_root_for(""))

    def test_unreadable_git_metadata_returns_project(self) -> None:
        _, worktree = self.worktree(commondir=True)
        for error in (PermissionError("unreadable"), UnicodeError("invalid text")):
            with self.subTest(error=error), patch.object(Path, "read_text", side_effect=error):
                project_root_for.cache_clear()
                self.assertEqual(str(worktree), project_root_for(str(worktree)))

    def test_malformed_git_metadata_returns_project(self) -> None:
        _, worktree = self.worktree(commondir=True)
        for content in ("not a gitdir\n", "gitdir: \n", "gitdir: ../unknown\n"):
            with self.subTest(content=content):
                (worktree / ".git").write_text(content, encoding="utf-8")
                project_root_for.cache_clear()
                self.assertEqual(str(worktree), project_root_for(str(worktree)))

    def test_result_is_cached(self) -> None:
        _, worktree = self.worktree(commondir=True)
        expected = project_root_for(str(worktree))
        with patch.object(Path, "read_text", side_effect=AssertionError("uncached read")):
            self.assertEqual(expected, project_root_for(str(worktree)))

    def test_scan_adds_root_without_changing_project_or_state_file(self) -> None:
        repo, worktree = self.worktree(commondir=True)
        state_dir = self.root / "state"
        runs_dir = state_dir / "runs"
        runs_dir.mkdir(parents=True)
        state = {"run_id": "test", "project": str(worktree), "finished": True, "tasks": []}
        path = runs_dir / "test.json"
        path.write_text(json.dumps(state), encoding="utf-8")
        before = path.read_bytes()
        before_mtime = path.stat().st_mtime_ns

        runs, unreadable = scan_hud_run_states_with_unreadable(state_dir, active_runs={})

        self.assertEqual(0, unreadable)
        self.assertEqual([{**state, "orchestrator_alive": False, "project_root": str(repo)}], runs)
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(before_mtime, path.stat().st_mtime_ns)

    def test_scan_missing_or_non_string_project(self) -> None:
        runs_dir = self.root / "runs"
        runs_dir.mkdir()
        for project in (None, "", 42, [], {}):
            with self.subTest(project=project):
                state = {"run_id": "test"}
                if project is not None:
                    state["project"] = project
                (runs_dir / "test.json").write_text(json.dumps(state), encoding="utf-8")
                runs, _ = scan_hud_run_states_with_unreadable(self.root, active_runs={})
                self.assertIsNone(runs[0]["project_root"])
                self.assertEqual(state.get("project"), runs[0].get("project"))

    def test_stale_run_repair_does_not_persist_project_root(self) -> None:
        repo, worktree = self.worktree(commondir=True)
        runs_dir = self.root / "runs"
        runs_dir.mkdir()
        path = runs_dir / "test.json"
        path.write_text(
            json.dumps({"run_id": "test", "project": str(worktree), "state": "live"}),
            encoding="utf-8",
        )
        runs, _ = scan_hud_run_states_with_unreadable(self.root, active_runs={})
        self.assertEqual(str(repo), runs[0]["project_root"])
        persisted = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("died", persisted["state"])
        self.assertNotIn("project_root", persisted)


if __name__ == "__main__":
    unittest.main(verbosity=2)
