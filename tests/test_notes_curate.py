#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ringer import curate_model_notes, parse_model_notes_sections  # noqa: E402


class NotesCurateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.notes_path = self.root / "MODEL-NOTES.md"
        self.notes_path.write_text(
            "# Model notes\n\n"
            "Intro stays untouched.\n\n"
            "## existing\n\n"
            "- 2026-01-01 — canonical.\n",
            encoding="utf-8",
        )
        self.incoming = self.root / "model-notes" / "incoming"
        self.incoming.mkdir(parents=True)

    def write_incoming(self, name: str, text: str) -> Path:
        path = self.incoming / name
        path.write_text(text, encoding="utf-8")
        return path

    def run_curate(self, *, dry_run: bool = False) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = curate_model_notes(self.notes_path, dry_run=dry_run)
        return result, output.getvalue()

    def test_curate_preserves_parsed_sections_and_empties_inbox(self) -> None:
        self.write_incoming(
            "z-session.md",
            "## existing\n\n- 2026-01-03 — z note.\n\n## new model\n\n"
            "- 2026-01-04 — new note.\n",
        )
        self.write_incoming(
            "a-session.md", "## existing\n\n- 2026-01-02 — a note.\n"
        )
        before = parse_model_notes_sections(self.notes_path)

        result, _ = self.run_curate()

        self.assertEqual(0, result)
        self.assertEqual(before, parse_model_notes_sections(self.notes_path))
        self.assertEqual([], list(self.incoming.glob("*.md")))
        self.assertTrue(
            self.notes_path.read_text(encoding="utf-8").startswith(
                "# Model notes\n\nIntro stays untouched.\n\n## existing\n\n"
                "- 2026-01-02 — a note.\n- 2026-01-03 — z note.\n\n"
                "- 2026-01-01 — canonical.\n"
            )
        )

    def test_dry_run_changes_nothing(self) -> None:
        incoming = self.write_incoming(
            "session.md", "## existing\n\n- 2026-01-02 — incoming.\n"
        )
        canonical_before = self.notes_path.read_bytes()
        incoming_before = incoming.read_bytes()

        result, output = self.run_curate(dry_run=True)

        self.assertEqual(0, result)
        self.assertIn("Would curate 1", output)
        self.assertEqual(canonical_before, self.notes_path.read_bytes())
        self.assertEqual(incoming_before, incoming.read_bytes())

    def test_empty_inbox_is_clean_no_op(self) -> None:
        canonical_before = self.notes_path.read_bytes()

        result, output = self.run_curate()

        self.assertEqual(0, result)
        self.assertIn("nothing to curate", output)
        self.assertEqual(canonical_before, self.notes_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
