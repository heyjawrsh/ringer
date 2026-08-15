#!/usr/bin/env python3
"""Validate a rendered design direction and its reference-divergence notes."""

from __future__ import annotations

import argparse
import pathlib
import re
import struct
import sys


DIVERGENCE_LANGUAGE = re.compile(
    r"\b(?:"
    r"diverg(?:e|es|ed|ing|ence|ences|ent)"
    r"|differ(?:s|ed|ing|ence|ences|ent)"
    r"|depart(?:s|ed|ing|ure|ures)"
    r"|deviat(?:e|es|ed|ing|ion|ions)"
    r"|contrast(?:s|ed|ing)?"
    r"|(?:does|do|did)\s+not\s+match"
    r"|unlike"
    r")\b",
    re.IGNORECASE,
)
REFERENCE_LANGUAGE = re.compile(r"\b(?:supplied\s+)?reference\b", re.IGNORECASE)
MARKDOWN_HEADING = re.compile(r"^\s*(?:>{1,3}\s*)?(?P<marks>#{1,6})\s+")
MARKDOWN_DECORATION = re.compile(r"(?:[*_`~#>]+|^\s*(?:[-+]\s+|\d+[.)]\s+))", re.MULTILINE)
GENERIC_COMPARISON_WORDS = re.compile(
    r"\b(?:where|how|this|the|a|an|our|my|direction|design|result|supplied|reference|from|to|"
    r"diverg(?:e|es|ed|ing|ence|ences|ent)|differ(?:s|ed|ing|ence|ences|ent)|"
    r"depart(?:s|ed|ing|ure|ures)|deviat(?:e|es|ed|ing|ion|ions)|"
    r"contrast(?:s|ed|ing)?|does|do|did|not|match(?:es|ed|ing)?|unlike|"
    r"it|its|is|are|was|were|by|in|on|at|of|with|because|below|above|"
    r"detail|details|note|notes|somewhat|slightly|visually|more|less)\b",
    re.IGNORECASE,
)


def plain_text(value: str) -> str:
    value = MARKDOWN_DECORATION.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip(" :-—–|\t\r\n")


def has_substantive_detail(value: str) -> bool:
    remainder = GENERIC_COMPARISON_WORDS.sub(" ", plain_text(value))
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", remainder)
    visible = re.sub(r"\W+", "", remainder)
    return len(words) >= 1 and len(visible) >= 4


def divergence_is_stated(text: str) -> bool:
    lines = text.splitlines()
    reference_is_named = bool(REFERENCE_LANGUAGE.search(text))

    for index, line in enumerate(lines):
        has_divergence = bool(DIVERGENCE_LANGUAGE.search(line))
        has_reference = bool(REFERENCE_LANGUAGE.search(line))
        if not has_divergence or not (has_reference or reference_is_named):
            continue

        if has_reference and has_substantive_detail(line):
            return True

        marker_heading = MARKDOWN_HEADING.match(line)
        marker_level = len(marker_heading.group("marks")) if marker_heading else None
        following: list[str] = []
        for candidate in lines[index + 1 :]:
            candidate_heading = MARKDOWN_HEADING.match(candidate)
            if candidate_heading and (
                marker_level is None or len(candidate_heading.group("marks")) <= marker_level
            ):
                break
            if candidate.strip():
                following.append(candidate)
            if len(following) >= 4:
                break
        if following and has_substantive_detail("\n".join(following)):
            return True

    return False


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# A blank 1440x900 page renders to roughly 0.005 compressed bytes per pixel; a
# built screen lands near 0.1. Anything under this floor is a flat image.
MIN_IMAGE_BYTES_PER_PIXEL = 0.01


def describe_png(path: pathlib.Path) -> tuple[int, int, int] | None:
    """Return (width, height, compressed image bytes), or None if not a PNG."""
    raw = path.read_bytes()
    if not raw.startswith(PNG_SIGNATURE):
        return None

    position = len(PNG_SIGNATURE)
    width = height = image_bytes = 0
    while position + 8 <= len(raw):
        (length,) = struct.unpack(">I", raw[position : position + 4])
        kind = raw[position + 4 : position + 8]
        if kind == b"IHDR":
            width, height = struct.unpack(">II", raw[position + 8 : position + 16])
        elif kind == b"IDAT":
            image_bytes += length
        elif kind == b"IEND":
            break
        position += 12 + length
    return width, height, image_bytes


def render_failures(path: pathlib.Path, min_width: int, min_height: int) -> list[str]:
    """Check the render is a real image of a built screen, not a placeholder.

    The deliverable of a directions round IS the image, so "the file exists and
    is non-empty" is not a check — `echo x > direction.png` satisfies it.
    """
    described = describe_png(path)
    if described is None:
        return [
            f"render is not a PNG file: {path}. It must be a real screenshot or exported "
            "image of the built surface, not a placeholder or a text file named .png"
        ]

    width, height, image_bytes = described
    failures: list[str] = []
    if not width or not height:
        return [f"render has no readable PNG header, so it is not a usable image: {path}"]
    if width < min_width or height < min_height:
        failures.append(
            f"render is {width}x{height}, below the required {min_width}x{min_height}: {path}"
        )
    density = image_bytes / (width * height)
    if density < MIN_IMAGE_BYTES_PER_PIXEL:
        failures.append(
            f"render looks blank: {width}x{height} compressing to {image_bytes} bytes of "
            f"image data ({density:.4f} per pixel, floor {MIN_IMAGE_BYTES_PER_PIXEL}). A "
            f"render of a built screen is not a flat image: {path}"
        )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--render",
        default="direction.png",
        help="Path to the rendered screenshot or exported image",
    )
    parser.add_argument(
        "--notes",
        default="notes.md",
        help="Path to notes comparing the direction with the supplied reference",
    )
    parser.add_argument(
        "--min-width", type=int, default=200, help="minimum render width in pixels"
    )
    parser.add_argument(
        "--min-height", type=int, default=200, help="minimum render height in pixels"
    )
    args = parser.parse_args()

    failures: list[str] = []
    render_path = pathlib.Path(args.render)
    notes_path = pathlib.Path(args.notes)

    if not render_path.is_file():
        failures.append(f"render is missing or not a file: {render_path}")
    elif render_path.stat().st_size == 0:
        failures.append(f"render is zero bytes: {render_path}")
    else:
        failures.extend(render_failures(render_path, args.min_width, args.min_height))

    notes_text = ""
    if not notes_path.is_file():
        failures.append(f"notes are missing or not a file: {notes_path}")
    else:
        notes_text = notes_path.read_text(encoding="utf-8", errors="replace")
        if not notes_text.strip():
            failures.append(f"notes are empty: {notes_path}")
        elif not divergence_is_stated(notes_text):
            failures.append(
                "notes do not substantively state where the direction diverges, differs, "
                f"or departs from the supplied reference: {notes_path}"
            )

    if failures:
        print("FAIL:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("PASS: render exists and notes state a substantive divergence from the reference")
    return 0


if __name__ == "__main__":
    sys.exit(main())
