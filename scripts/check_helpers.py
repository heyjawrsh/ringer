"""Helpers for checks that are tolerant on format and strict on substance.

Add the ``scripts`` directory to ``sys.path`` and import these helpers from
``check_helpers``. They accept harmless formatting variation while keeping
failures specific enough to guide the next worker attempt.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, NoReturn, Sequence


def normalize(text: str) -> str:
    """Replace unusual whitespace and collapse whitespace runs."""
    return re.sub(r"\s+", " ", text).strip()


def fail(message: str) -> NoReturn:
    """Print one actionable failure line and exit non-zero."""
    print(f"CHECK FAIL: {normalize(message)}")
    raise SystemExit(1)


def _heading_text(line: str) -> tuple[str, bool]:
    """Return a line without supported Markdown heading decoration."""
    value = normalize(line)
    decorated = False

    hash_match = re.match(r"^#{1,6}(?:\s+|$)(.*)$", value)
    if hash_match is not None:
        value = hash_match.group(1).strip()
        value = re.sub(r"\s+#+$", "", value).strip()
        decorated = True

    changed = True
    while changed:
        changed = False
        if len(value) >= 4 and value.startswith("**") and value.endswith("**"):
            value = value[2:-2].strip()
            decorated = True
            changed = True
        if value.endswith(":"):
            value = value[:-1].strip()
            decorated = True
            changed = True

    return normalize(value), decorated


def assert_section(text: str, name: str) -> None:
    """Assert that a tolerantly formatted heading named ``name`` exists."""
    wanted = normalize(name).casefold()
    headings: list[str] = []

    for line in text.splitlines():
        heading, decorated = _heading_text(line)
        if not heading:
            continue
        if heading.casefold() == wanted:
            return
        if decorated:
            headings.append(heading)

    found = ", ".join(repr(heading) for heading in headings) or "none"
    fail(f"missing section {name!r}; headings found: {found}")


def _excerpt(text: str, limit: int = 240) -> str:
    """Return a compact excerpt suitable for a one-line diagnostic."""
    value = normalize(text)
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def assert_contains(text: str, needle: str, *, why: str | None = None) -> None:
    """Assert that normalized ``text`` contains normalized ``needle``."""
    normalized_text = normalize(text)
    normalized_needle = normalize(needle)
    if normalized_needle.casefold() in normalized_text.casefold():
        return

    reason = f" ({why})" if why else ""
    fail(
        f"missing {normalized_needle!r}{reason}; "
        f"document excerpt: {_excerpt(normalized_text)!r}"
    )


def _command_text(cmd: Sequence[str | os.PathLike[str]]) -> str:
    """Render a command safely for a diagnostic."""
    return shlex.join(os.fspath(argument) for argument in cmd)


def _output_tail(output: str, limit: int = 2_000) -> str:
    """Return the useful tail of combined process output."""
    if not output:
        return "<no output>"
    if len(output) <= limit:
        return output
    return "..." + output[-(limit - 3) :]


def assert_runs(
    cmd: Sequence[str | os.PathLike[str]],
    *,
    cwd: str | os.PathLike[str] | None = None,
    timeout: float = 120,
) -> str:
    """Run ``cmd`` and return output, or fail with status and output tail."""
    command = list(cmd)
    if not command:
        fail("command ''; exit status: could not start; output tail: command is empty")
    rendered = _command_text(command)
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.output or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        fail(
            f"command {rendered!r}; exit status: timed out after {timeout} seconds; "
            f"output tail: {_output_tail(output)}"
        )
    except OSError as exc:
        fail(f"command {rendered!r}; exit status: could not start; output tail: {exc}")

    if result.returncode != 0:
        fail(
            f"command {rendered!r}; exit status: {result.returncode}; "
            f"output tail: {_output_tail(result.stdout)}"
        )
    return result.stdout


def assert_json_valid(path: str | os.PathLike[str]) -> Any:
    """Read and return JSON from ``path``, or fail with a useful reason."""
    json_path = Path(path)
    try:
        contents = json_path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"JSON file {json_path}: {exc}")
    except UnicodeError as exc:
        fail(f"JSON file {json_path}: {exc}")

    if not contents.strip():
        fail(f"JSON file {json_path}: file is empty")

    try:
        return json.loads(contents)
    except json.JSONDecodeError as exc:
        fail(f"JSON file {json_path}: {exc}")
