#!/usr/bin/env python3
"""Enforce the one-file-per-session model-notes inbox policy."""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = "a4684ed"
INSTRUCTION_SURFACES = (
    Path(".claude/skills/ringer/SKILL.md"),
    Path("CONTRIBUTING.md"),
    Path("docs/model-notes/README.md"),
)

# A positive write verb close to the canonical path is an instruction.  Negative
# wording is deliberately excluded so "never append to ..." remains permitted.
CANONICAL_WRITE_INSTRUCTION_RE = re.compile(
    r"\b(add|append|write|record)\b[^.!?]{0,100}?docs/model-notes\.md",
    re.IGNORECASE | re.DOTALL,
)
NEGATION_RE = re.compile(r"\b(?:do\s+not|don't|never|must\s+not|no)\b", re.IGNORECASE)
COMMIT_MARKER = "--commit--"


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def repo_has_full_history() -> bool:
    try:
        proc = git("rev-parse", "--is-shallow-repository")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return proc.stdout.strip() == "false"


def instructs_writing_canonical_log(text: str) -> bool:
    lowered = text.lower()
    for match in CANONICAL_WRITE_INSTRUCTION_RE.finditer(lowered):
        # Only a negation in the write verb's own clause governs it.  In
        # particular, "do not write X; append to MODEL-NOTES" still violates
        # the policy even though a negation appears nearby.
        clause_start = max(
            lowered.rfind(separator, 0, match.start())
            for separator in (".", "!", "?", ";", "\n")
        )
        before_verb = lowered[clause_start + 1 : match.start()]
        if not NEGATION_RE.search(before_verb):
            return True
    return False


def git_log_records(*args: str) -> dict[str, list[str]]:
    records: dict[str, list[str]] = {}
    commit = ""
    for line in git("log", f"--format={COMMIT_MARKER}%H", *args).stdout.splitlines():
        if line.startswith(COMMIT_MARKER):
            commit = line.removeprefix(COMMIT_MARKER)
            records.setdefault(commit, [])
        elif commit and line.strip():
            records[commit].append(line)
    return records


class ModelNotesInboxPolicyTests(unittest.TestCase):
    def test_instruction_surfaces_direct_new_notes_to_inbox(self) -> None:
        for relative_path in INSTRUCTION_SURFACES:
            with self.subTest(path=str(relative_path)):
                text = (ROOT / relative_path).read_text(encoding="utf-8")
                lowered = text.lower()
                if relative_path == Path("docs/model-notes/README.md"):
                    # From inside docs/model-notes, incoming/ is the same path.
                    inbox_named = bool(
                        re.search(r"\b(?:docs/model-notes/)?incoming/", lowered)
                    )
                else:
                    inbox_named = "docs/model-notes/incoming" in lowered
                self.assertTrue(
                    inbox_named,
                    f"{relative_path} must direct new model observations to "
                    "docs/model-notes/incoming/",
                )
                self.assertFalse(
                    instructs_writing_canonical_log(text),
                    f"{relative_path} instructs readers to write observations "
                    "to docs/MODEL-NOTES.md; direct them to the inbox instead",
                )

    def test_history_does_not_append_directly_to_canonical_log(self) -> None:
        if not repo_has_full_history():
            self.skipTest("git history unavailable or shallow; history audit skipped")

        try:
            git("cat-file", "-e", f"{CUTOFF}^{{commit}}")
        except subprocess.CalledProcessError:
            self.skipTest(f"cutoff commit {CUTOFF} is unavailable; history audit skipped")

        canonical_changes = git_log_records(
            "--numstat", f"{CUTOFF}..HEAD", "--", "docs/MODEL-NOTES.md"
        )
        inbox_deletions = git_log_records(
            "--name-only",
            "--diff-filter=D",
            f"{CUTOFF}..HEAD",
            "--",
            "docs/model-notes/incoming",
        )
        commits_with_additions = {
            commit
            for commit, lines in canonical_changes.items()
            if any(line.split("\t", 1)[0].isdigit() and int(line.split("\t", 1)[0]) > 0
                   for line in lines)
        }
        commits_with_inbox_deletions = {
            commit for commit, paths in inbox_deletions.items() if paths
        }
        offenders = sorted(commits_with_additions - commits_with_inbox_deletions)

        self.assertFalse(
            offenders,
            "commit(s) added lines directly to docs/MODEL-NOTES.md without "
            "curating an inbox file: "
            f"{', '.join(offenders)}. Move the entry to a dated file under "
            "docs/model-notes/incoming/ instead.",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
