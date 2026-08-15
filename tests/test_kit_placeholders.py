#!/usr/bin/env python3
"""Every kit's README must document exactly the placeholders the kit uses.

A kit is filled in by reading its README. When the README names a placeholder
the kit does not use, or omits one it does, whoever fills it in ships a manifest
with unfilled `{{...}}` holes — which the worker then reads as literal text.
This was found by using `design-directions` for the first time: its README
documented `{{PRODUCT_NAME}}` and `{{DIRECTION}}` while the manifest wanted
`{{PROJECT_NAME}}` and `{{DIRECTION_A/B/C}}`, and never mentioned
`{{SCREEN_SOURCE_FILE}}` or `{{SCREEN_OR_COMPONENT}}` at all.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def placeholders_in(path: Path) -> set[str]:
    try:
        return set(PLACEHOLDER.findall(path.read_text(encoding="utf-8")))
    except (UnicodeDecodeError, OSError):
        return set()


class KitPlaceholderTests(unittest.TestCase):
    def kits(self) -> list[Path]:
        return sorted(p for p in TEMPLATES.iterdir() if p.is_dir() and (p / "README.md").is_file())

    def test_every_kit_documents_exactly_the_placeholders_it_uses(self) -> None:
        self.assertGreaterEqual(len(self.kits()), 15, "kits disappeared from templates/")

        for kit in self.kits():
            with self.subTest(kit=kit.name):
                used: set[str] = set()
                for path in kit.rglob("*"):
                    if path.is_file() and path.name != "README.md":
                        used |= placeholders_in(path)
                documented = placeholders_in(kit / "README.md")

                self.assertEqual(
                    set(),
                    used - documented,
                    f"{kit.name}/README.md does not document placeholder(s) the kit uses: "
                    f"{sorted(used - documented)} — anyone filling this kit from its README "
                    "ships a manifest with unfilled holes",
                )
                self.assertEqual(
                    set(),
                    documented - used,
                    f"{kit.name}/README.md documents placeholder(s) no kit file uses: "
                    f"{sorted(documented - used)} — filling them in has no effect",
                )


if __name__ == "__main__":
    unittest.main()
