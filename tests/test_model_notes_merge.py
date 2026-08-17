#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ringer import parse_model_notes_sections  # noqa: E402


class ModelNotesMergeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.notes_path = self.root / "MODEL-NOTES.md"
        self.notes_path.write_text(
            "## existing\n\n- 2026-01-01 — canonical.\n", encoding="utf-8"
        )

    def write_incoming(self, name: str, text: str) -> Path:
        incoming = self.root / "model-notes" / "incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        path = incoming / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_merges_into_existing_heading(self) -> None:
        self.write_incoming("session.md", "## existing\n\n- 2026-01-02 — incoming.\n")

        sections = parse_model_notes_sections(self.notes_path)

        # Incoming notes lead: this log reads newest-first and the scoreboard's
        # Notes column shows only the leading bullet, so an appended entry would
        # merge and still be invisible where people read it.
        self.assertEqual(
            ["2026-01-02 — incoming.", "2026-01-01 — canonical."],
            sections["existing"],
        )

    def test_merge_creates_new_heading(self) -> None:
        self.write_incoming("session.md", "## new model\n\n- 2026-01-02 — first note.\n")

        sections = parse_model_notes_sections(self.notes_path)

        self.assertEqual(["2026-01-02 — first note."], sections["new model"])

    def test_no_incoming_directory_behaves_as_before(self) -> None:
        self.assertEqual(
            {"existing": ["2026-01-01 — canonical."]},
            parse_model_notes_sections(self.notes_path),
        )

    def test_unreadable_incoming_file_is_skipped(self) -> None:
        broken = self.write_incoming("a-broken.md", "## broken\n\n- 2026-01-02 — hidden.\n")
        self.write_incoming("b-readable.md", "## readable\n\n- 2026-01-03 — visible.\n")
        original_read_text = Path.read_text

        def read_text(path: Path, *args: object, **kwargs: object) -> str:
            if path == broken:
                raise PermissionError("unreadable")
            return original_read_text(path, *args, **kwargs)

        with mock.patch.object(Path, "read_text", autospec=True, side_effect=read_text):
            sections = parse_model_notes_sections(self.notes_path)

        self.assertNotIn("broken", sections)
        self.assertEqual(["2026-01-03 — visible."], sections["readable"])

    def test_incoming_files_are_merged_in_name_order(self) -> None:
        self.write_incoming("z-session.md", "## existing\n\n- 2026-01-03 — z note.\n")
        self.write_incoming("a-session.md", "## existing\n\n- 2026-01-02 — a note.\n")

        sections = parse_model_notes_sections(self.notes_path)

        # Incoming lead the canonical entries, and keep name order among
        # themselves so two sessions never race for position.
        self.assertEqual(
            [
                "2026-01-02 — a note.",
                "2026-01-03 — z note.",
                "2026-01-01 — canonical.",
            ],
            sections["existing"],
        )


if __name__ == "__main__":
    unittest.main()
