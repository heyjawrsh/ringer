#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ringer import Manifest, TaskSpec, Verifier, lint_manifest, main  # noqa: E402


LONG_SPEC = (
    "Create the requested artifact in the current working directory, keep the change scoped, "
    "and make the check command able to explain any failure clearly."
)

GOOD_CHECK = (
    "test -s output.txt && grep -qw 'ready' output.txt || "
    "{ echo 'FAIL: output.txt missing or does not contain ready'; exit 1; }"
)


class LintManifestTests(unittest.TestCase):
    def manifest(
        self,
        tasks: list[dict[str, object]],
        *,
        worktrees: bool = False,
        max_parallel: int = 1,
    ) -> Manifest:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        obj: dict[str, object] = {
            "run_name": "lint-test",
            "workdir": str(Path(temp_dir.name) / "work"),
            "max_parallel": max_parallel,
            "worktrees": worktrees,
            "tasks": tasks,
        }
        if worktrees:
            obj["repo"] = temp_dir.name
        return Manifest.from_obj(obj)

    def task(
        self,
        key: str = "one",
        *,
        spec: str = LONG_SPEC,
        check: str = GOOD_CHECK,
        expect_files: list[str] | None = None,
        known_bad: str | None = "printf 'broken\\n' > output.txt",
    ) -> dict[str, object]:
        task: dict[str, object] = {
            "key": key,
            "spec": spec,
            "check": check,
            "expect_files": ["output.txt"] if expect_files is None else expect_files,
            "verified": "the output file exists and contains the expected content",
        }
        if known_bad is not None:
            task["known_bad"] = known_bad
        return task

    def assertHasFinding(self, findings: list[str], expected: str) -> None:
        self.assertIn(expected, findings, f"expected lint finding not found: {expected}\nfindings: {findings}")

    def test_task_fields_must_be_strings(self) -> None:
        with self.assertRaisesRegex(ValueError, r"task one: check must be a string"):
            self.manifest([self.task(check=["cmd1", "cmd2"])])  # type: ignore[arg-type]

        with self.assertRaisesRegex(ValueError, r"task one: spec must be a string"):
            self.manifest([self.task(spec=["write it"])])  # type: ignore[arg-type]

        task = self.task()
        task["key"] = 123
        with self.assertRaisesRegex(ValueError, r"task key must be a string"):
            self.manifest([task])

    def test_w1_unverifiable_check(self) -> None:
        manifest = self.manifest([self.task(check="echo ok && echo done")])
        self.assertHasFinding(
            lint_manifest(manifest),
            "one: check cannot fail, so the task cannot be verified.",
        )

        commented_manifest = self.manifest([self.task(check="true # worker left the placeholder check")])
        self.assertHasFinding(
            lint_manifest(commented_manifest),
            "one: check cannot fail, so the task cannot be verified.",
        )

        quoted_hash_manifest = self.manifest(
            [
                self.task(
                    check=(
                        "test -s '#artifact' || "
                        "{ echo 'FAIL: #artifact missing'; exit 1; }"
                    )
                )
            ]
        )
        self.assertNotIn(
            "one: check cannot fail, so the task cannot be verified.",
            lint_manifest(quoted_hash_manifest),
        )

    def test_w2_silent_check(self) -> None:
        manifest = self.manifest([self.task(check="test -f output.txt && [ -s report.md ]")])
        self.assertHasFinding(
            lint_manifest(manifest),
            "one: check may fail without printing why; retry prompt and eval log depend on failure output.",
        )

        diff_manifest = self.manifest([self.task(check="diff -q expected.txt actual.txt")])
        self.assertHasFinding(
            lint_manifest(diff_manifest),
            "one: check may fail without printing why; retry prompt and eval log depend on failure output.",
        )

        diff_with_output = self.manifest(
            [self.task(check="diff -q a b || { echo FAIL; diff a b; exit 1; }")]
        )
        self.assertNotIn(
            "one: check may fail without printing why; retry prompt and eval log depend on failure output.",
            lint_manifest(diff_with_output),
        )

        grep_manifest = self.manifest([self.task(check="grep -q x file")])
        self.assertHasFinding(
            lint_manifest(grep_manifest),
            "one: check may fail without printing why; retry prompt and eval log depend on failure output.",
        )

        probe_chain_manifest = self.manifest([self.task(check="grep -q x file && test -s output.txt")])
        self.assertHasFinding(
            lint_manifest(probe_chain_manifest),
            "one: check may fail without printing why; retry prompt and eval log depend on failure output.",
        )

    def test_w3_worktree_deliverable_loss(self) -> None:
        manifest = self.manifest(
            [self.task(expect_files=["report.md"])],
            worktrees=True,
        )
        self.assertHasFinding(
            lint_manifest(manifest),
            "one: deliverable would be deleted with the worktree; write it outside the worktree or export it in the check.",
        )

    def test_w4_worktree_commit_loss(self) -> None:
        spec = LONG_SPEC + " After the file is correct, run git commit with a concise message."
        manifest = self.manifest(
            [self.task(spec=spec, expect_files=[])],
            worktrees=True,
        )
        self.assertHasFinding(
            lint_manifest(manifest),
            "one: worker commits die with the worktree; have the worker leave changes uncommitted and export the diff in the check.",
        )

        negated_spec = LONG_SPEC + " Do NOT run `git commit`; leave the worktree uncommitted."
        negated_manifest = self.manifest(
            [self.task(spec=negated_spec, expect_files=[])],
            worktrees=True,
        )
        self.assertNotIn(
            "one: worker commits die with the worktree; have the worker leave changes uncommitted and export the diff in the check.",
            lint_manifest(negated_manifest),
        )

    def test_w5_serial_fan_out(self) -> None:
        manifest = self.manifest(
            [
                self.task("one", expect_files=["one.txt"]),
                self.task("two", expect_files=["two.txt"]),
                self.task("three", expect_files=["three.txt"]),
            ],
            max_parallel=1,
        )
        self.assertHasFinding(
            lint_manifest(manifest),
            "manifest: tasks will run serially; set max_parallel.",
        )

    def test_w6_write_collision(self) -> None:
        manifest = self.manifest(
            [
                self.task("one", expect_files=["/tmp/shared-deliverable.txt"]),
                self.task("two", expect_files=["/tmp/shared-deliverable.txt"]),
            ],
            worktrees=False,
        )
        self.assertHasFinding(
            lint_manifest(manifest),
            "manifest: write collision on /tmp/shared-deliverable.txt: listed by one, two.",
        )

    def test_w6_relative_paths_do_not_collide(self) -> None:
        # Relative expect_files resolve inside each task's own directory —
        # many tasks emitting report.md/extraction.json is the NORMAL swarm
        # shape, not a collision (first field use caught this false positive).
        manifest = self.manifest(
            [
                self.task("one", expect_files=["report.md"]),
                self.task("two", expect_files=["report.md"]),
                self.task("three", expect_files=["report.md"]),
            ],
            worktrees=False,
            max_parallel=3,
        )
        self.assertEqual([], lint_manifest(manifest))

    def test_verifier_expands_user_expect_files(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            taskdir = Path(root) / "task"
            home = Path(root) / "home"
            taskdir.mkdir()
            home.mkdir()
            (home / "report.md").write_text("done\n", encoding="utf-8")
            previous_home = os.environ.get("HOME")
            os.environ["HOME"] = str(home)
            try:
                task = TaskSpec(
                    key="one",
                    spec=LONG_SPEC,
                    check="true",
                    expect_files=("~/report.md",),
                )
                result = asyncio.run(Verifier().verify(task, taskdir))
            finally:
                if previous_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = previous_home
        self.assertTrue(result.ok, result.raw_output_excerpt)
        self.assertEqual((), result.missing_files)

    def test_w7_underspecified_spec(self) -> None:
        manifest = self.manifest([self.task(spec="Do it.")])
        self.assertHasFinding(
            lint_manifest(manifest),
            "one: spec is probably underspecified; workers are stateless and cannot ask questions.",
        )

    def test_w8_file_pointer_spec(self) -> None:
        findings = lint_manifest(
            self.manifest(
                [self.task(spec="Read the instructions at /tmp/brief.md and do exactly what it says in there.")]
            )
        )
        self.assertTrue(
            any("pointer to an instruction file" in item for item in findings),
            f"expected pointer-spec finding, got: {findings}",
        )

        # A long spec that references files as source material is fine.
        long_spec = (
            "You are a read-only reviewer. Study the code bundle at /tmp/bundle.txt as your "
            "source material, then write ./review.md with sections VERDICT, BLOCKERS, and "
            "EVIDENCE. For every blocker cite file and line from the bundle. Do not modify "
            "any file other than ./review.md. The review must judge correctness, security, "
            "and migration safety, and each claim needs a quoted line of code as evidence. "
            "If a concern cannot be verified from the bundle alone, list it under an "
            "UNCERTAIN heading instead of asserting it. Keep the verdict to one sentence. "
            "Write plainly; the reader is a busy maintainer deciding whether to merge today."
        )
        findings = lint_manifest(self.manifest([self.task(spec=long_spec, expect_files=["review.md"])]))
        self.assertFalse(
            any("pointer to an instruction file" in item for item in findings),
            f"long contextual spec should not be flagged: {findings}",
        )

    def test_w9_missing_expect_files(self) -> None:
        findings = lint_manifest(self.manifest([self.task(expect_files=[])]))
        self.assertTrue(
            any("no expect_files" in item for item in findings),
            f"expected missing-expect_files finding, got: {findings}",
        )

        # Worktrees mode legitimately exports deliverables outside the
        # taskdir (patch export), so the finding must not fire there.
        findings = lint_manifest(
            self.manifest([self.task(expect_files=[])], worktrees=True)
        )
        self.assertFalse(
            any("no expect_files" in item for item in findings),
            f"worktrees manifest should not be flagged for expect_files: {findings}",
        )

    def test_w10_unanchored_substring_grep(self) -> None:
        manifest = self.manifest(
            [self.task(check="grep todo notes.txt || { echo 'FAIL: todo missing'; exit 1; }")]
        )
        self.assertHasFinding(
            lint_manifest(manifest),
            "one: check greps for an unanchored bare literal; use grep -w, anchor the pattern, or match a longer distinctive phrase.",
        )

        word_manifest = self.manifest(
            [self.task(check="grep -w todo notes.txt || { echo 'FAIL: todo missing'; exit 1; }")]
        )
        self.assertNotIn(
            "one: check greps for an unanchored bare literal; use grep -w, anchor the pattern, or match a longer distinctive phrase.",
            lint_manifest(word_manifest),
        )

    def test_w11_focus_stealing_command(self) -> None:
        manifest = self.manifest(
            [self.task(check="open -a Preview output.png || { echo 'FAIL: preview failed'; exit 1; }")]
        )
        self.assertHasFinding(
            lint_manifest(manifest),
            "one: check or spec opens an application window and can steal focus; use a headless probe and write evidence to a file instead.",
        )

        filename_manifest = self.manifest(
            [self.task(check="test -s open-results.txt || { echo 'FAIL: results missing'; exit 1; }")]
        )
        self.assertNotIn(
            "one: check or spec opens an application window and can steal focus; use a headless probe and write evidence to a file instead.",
            lint_manifest(filename_manifest),
        )

    def test_w12_gitignored_deliverable(self) -> None:
        manifest = self.manifest(
            [self.task(expect_files=["artifacts/report.md"])],
            worktrees=True,
        )
        assert manifest.repo is not None
        (manifest.repo / ".gitignore").write_text("# generated output\n\nartifacts/\n", encoding="utf-8")
        self.assertHasFinding(
            lint_manifest(manifest),
            "one: deliverable artifacts/report.md is gitignored and will be missing from the exported patch; have the check copy the artifact to a path outside the worktree and verify the copy.",
        )

        tracked_manifest = self.manifest(
            [self.task(expect_files=["report.md"])],
            worktrees=True,
        )
        assert tracked_manifest.repo is not None
        (tracked_manifest.repo / ".gitignore").write_text("artifacts/\n", encoding="utf-8")
        self.assertNotIn(
            "one: deliverable report.md is gitignored and will be missing from the exported patch; have the check copy the artifact to a path outside the worktree and verify the copy.",
            lint_manifest(tracked_manifest),
        )

    def test_w13_brittle_exact_phrase(self) -> None:
        finding = (
            "one: check greps for a long exact phrase and asserts the wording rather than the claim; "
            "assert the claim, not the phrasing — match a distinctive keyword case-insensitively, or use a tolerant regex."
        )
        manifest = self.manifest(
            [
                self.task(
                    check=(
                        "grep -q 'every run writes the final report' output.txt || "
                        "{ echo 'FAIL: report claim missing'; exit 1; }"
                    )
                )
            ]
        )
        self.assertHasFinding(lint_manifest(manifest), finding)

        case_insensitive_manifest = self.manifest(
            [
                self.task(
                    check=(
                        "grep -qi 'every run writes the final report' output.txt || "
                        "{ echo 'FAIL: report claim missing'; exit 1; }"
                    )
                )
            ]
        )
        self.assertNotIn(finding, lint_manifest(case_insensitive_manifest))

    def test_w14_exotic_whitespace_in_check(self) -> None:
        finding = (
            "one: check contains exotic whitespace and may reject honest work; "
            "normalize whitespace before comparing, and keep exotic characters out of the pattern."
        )
        manifest = self.manifest(
            [
                self.task(
                    check=(
                        "grep -q 'every\u00a0run' output.txt || "
                        "{ echo 'FAIL: run claim missing'; exit 1; }"
                    )
                )
            ]
        )
        self.assertHasFinding(lint_manifest(manifest), finding)

        ascii_manifest = self.manifest(
            [
                self.task(
                    check=(
                        "grep -q 'every run' output.txt || "
                        "{ echo 'FAIL: run claim missing'; exit 1; }"
                    )
                )
            ]
        )
        self.assertNotIn(finding, lint_manifest(ascii_manifest))

    def test_w15_repo_internals_assumption(self) -> None:
        finding = (
            "one: check inspects a path under .git/ and assumes the checkout's internal shape; "
            "verify the artifact, not the checkout's internals."
        )
        manifest = self.manifest(
            [
                self.task(
                    check=(
                        "test -f .git/config || "
                        "{ echo 'FAIL: git config missing'; exit 1; }"
                    )
                )
            ]
        )
        self.assertHasFinding(lint_manifest(manifest), finding)

        task_path_manifest = self.manifest(
            [
                self.task(
                    check=(
                        "test -f config/settings.toml || "
                        "{ echo 'FAIL: settings missing'; exit 1; }"
                    )
                )
            ]
        )
        self.assertNotIn(finding, lint_manifest(task_path_manifest))

    def test_w16_missing_known_bad(self) -> None:
        finding = (
            "one: no known_bad; run --prove-fail cannot cover this task, so a "
            "broken deliverable may slip through — add a command that fabricates one."
        )
        manifest = self.manifest([self.task(known_bad=None)])
        self.assertHasFinding(lint_manifest(manifest), finding)

        covered_manifest = self.manifest([self.task(known_bad="rm -f output.txt")])
        self.assertNotIn(finding, lint_manifest(covered_manifest))

    def test_missing_known_bad_nudge_reports_like_every_other_finding(self) -> None:
        # The nudge is an ordinary finding: `lint` exits 1 for ANY finding and
        # only prints "clean" when there are none. `run` still treats findings
        # as non-blocking warnings, which is where the teaching happens.
        manifest = self.manifest([self.task(known_bad=None)])
        output = io.StringIO()
        with mock.patch.object(Manifest, "from_path", return_value=manifest):
            with contextlib.redirect_stdout(output):
                exit_code = main(["--no-self-update", "lint", "ringer.json"])

        self.assertEqual(1, exit_code)
        self.assertIn("lint: one: no known_bad", output.getvalue())
        self.assertNotIn("lint: clean", output.getvalue())

    def test_compliant_manifest_is_clean(self) -> None:
        manifest = self.manifest(
            [
                self.task("one", expect_files=["one.txt"]),
                self.task("two", expect_files=["two.txt"]),
                self.task("three", expect_files=["three.txt"]),
            ],
            max_parallel=2,
        )
        self.assertEqual([], lint_manifest(manifest), "compliant manifest should have no lint findings")

    def test_templates_are_clean(self) -> None:
        # Every kit ships one or more manifest skeletons (manifest.json plus
        # optional manifest-round*.json for multi-round kits).
        template_paths = sorted((ROOT / "templates").glob("*/manifest*.json"))
        self.assertTrue(template_paths, "expected templates/*/manifest*.json files to exist")
        for path in template_paths:
            with self.subTest(template=path.name):
                manifest = Manifest.from_path(path)
                findings = lint_manifest(manifest)
                self.assertEqual([], findings, f"{path} should lint clean, got: {findings}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
