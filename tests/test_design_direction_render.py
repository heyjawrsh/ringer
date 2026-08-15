#!/usr/bin/env python3
"""The design-directions render gate must reject placeholders and blank images.

The deliverable of a directions round IS the image. Before this, the kit check
accepted any non-empty file, so `echo x > direction.png` passed the one
assertion the round exists to make. These tests synthesise PNGs with the
standard library so they never need a browser.
"""

from __future__ import annotations

import random
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "templates" / "design-directions" / "checks" / "check_direction.py"

NOTES = (
    "# Direction\n\nThis direction diverges from the supplied reference by trading the "
    "narrative headline for a dense tabular lane matrix with monospace typography.\n"
)


def write_png(path: Path, width: int, height: int, *, uniform: bool) -> None:
    """Write a valid 8-bit RGB PNG, either flat or full of incompressible noise."""
    rows = bytearray()
    noise = random.Random(1979)
    for _ in range(height):
        rows.append(0)  # filter type: None
        if uniform:
            rows.extend(b"\x0b\x0f\x14" * width)
        else:
            rows.extend(noise.randbytes(width * 3))

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + chunk(b"IEND", b"")
    )


class DesignDirectionRenderTests(unittest.TestCase):
    def run_check(self, render: Path, notes: Path, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(CHECK), "--render", str(render), "--notes", str(notes), *extra],
            capture_output=True,
            text=True,
            timeout=120,
        )

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.temp = Path(self._temp.name)
        self.notes = self.temp / "notes.md"
        self.notes.write_text(NOTES, encoding="utf-8")
        self.addCleanup(self._temp.cleanup)

    def test_a_real_render_passes(self) -> None:
        render = self.temp / "direction.png"
        write_png(render, 600, 400, uniform=False)

        result = self.run_check(render, self.notes)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)

    def test_a_text_file_named_png_is_rejected(self) -> None:
        render = self.temp / "direction.png"
        render.write_text("x\n", encoding="utf-8")

        result = self.run_check(render, self.notes)

        self.assertEqual(1, result.returncode)
        self.assertIn("not a PNG file", result.stdout)

    def test_a_blank_render_is_rejected(self) -> None:
        render = self.temp / "direction.png"
        write_png(render, 600, 400, uniform=True)

        result = self.run_check(render, self.notes)

        self.assertEqual(1, result.returncode)
        self.assertIn("looks blank", result.stdout)

    def test_a_render_below_the_size_floor_is_rejected(self) -> None:
        render = self.temp / "direction.png"
        write_png(render, 120, 120, uniform=False)

        result = self.run_check(render, self.notes, "--min-width", "600", "--min-height", "400")

        self.assertEqual(1, result.returncode)
        self.assertIn("120x120", result.stdout)

    def test_notes_are_still_gated(self) -> None:
        render = self.temp / "direction.png"
        write_png(render, 600, 400, uniform=False)
        thin = self.temp / "thin.md"
        thin.write_text("# Direction\n\nIt looks nice.\n", encoding="utf-8")

        result = self.run_check(render, thin)

        self.assertEqual(1, result.returncode)
        self.assertIn("diverges", result.stdout)


if __name__ == "__main__":
    unittest.main()
