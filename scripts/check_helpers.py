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


# A label written by a model may be plain, quoted, bulleted, numbered, bolded,
# or promoted to a Markdown heading. Checks that hand-roll this prefix tend to
# accept the forms their own fixture happened to use and reject the rest.
LABEL_PREFIX = (
    r"^[ \t]*(?:>[ \t]*)?(?:#{1,6}[ \t]*)?(?:[-*+][ \t]*)?"
    r"(?:\d+[.)][ \t]*)?(?:\*\*|__)?"
)


def label_pattern(label: str) -> re.Pattern[str]:
    """Return a pattern matching ``label:`` in any ordinary Markdown dress."""
    return re.compile(
        LABEL_PREFIX + rf"{re.escape(label)}(?:\*\*|__)?[ \t]*:",
        re.I | re.M,
    )


def count_labels(text: str, label: str) -> int:
    """Count tolerantly formatted ``label:`` lines in ``text``."""
    return len(label_pattern(label).findall(text))


def assert_labeled_blocks(
    text: str,
    labels: Sequence[str],
    *,
    min_blocks: int = 1,
    values: dict[str, str] | None = None,
) -> int:
    """Assert ``text`` holds parallel ``label:`` blocks and return how many.

    The first label anchors the count: if a report carries three ``Finding:``
    lines it must carry three of every other label too. ``values`` maps a label
    to a regex its value must match (e.g. ``{"Priority": r"P[0-3]"}``), which
    is checked once per block.
    """
    if not labels:
        fail("assert_labeled_blocks needs at least one label (check misconfigured)")

    anchor = labels[0]
    blocks = count_labels(text, anchor)
    if blocks < min_blocks:
        fail(
            f"found {blocks} {anchor!r} block(s); at least {min_blocks} required. "
            f"Every block needs all of: {', '.join(labels)}"
        )

    for label in labels[1:]:
        found = count_labels(text, label)
        if found < blocks:
            fail(
                f"{blocks} {anchor!r} block(s) but only {found} {label!r} label(s). "
                f"Every block needs all of: {', '.join(labels)}"
            )

    for label, pattern in (values or {}).items():
        matcher = re.compile(
            LABEL_PREFIX + rf"{re.escape(label)}(?:\*\*|__)?[ \t]*:[ \t]*\**[ \t]*(?:{pattern})\b",
            re.I | re.M,
        )
        found = len(matcher.findall(text))
        if found < blocks:
            fail(
                f"{blocks} block(s) but only {found} valid {label!r} value(s); "
                f"{label} must match {pattern}"
            )

    return blocks


_FENCED_QUOTE_RE = re.compile(r"```[a-zA-Z0-9_+-]*\n(.*?)```", re.S)
_INLINE_QUOTE_RE = re.compile(r"`([^`\n]+)`")
_DOUBLE_QUOTE_RE = re.compile(r"[\"“]([^\"“”\n]+)[\"”]")


def extract_quoted_spans(text: str, *, min_chars: int = 30) -> list[str]:
    """Return fenced, backticked and double-quoted spans of real length."""
    spans: list[str] = []
    for pattern in (_FENCED_QUOTE_RE, _INLINE_QUOTE_RE, _DOUBLE_QUOTE_RE):
        for match in pattern.finditer(text):
            span = match.group(1).strip()
            if len(normalize(span)) >= min_chars:
                spans.append(span)
    return spans


def _span_is_verbatim(span: str, source_norm: str, min_part_chars: int) -> bool:
    """True when the span, or every ellipsis-separated part, is in the source."""
    parts = [part for part in re.split(r"\.\.\.|…", span) if normalize(part)]
    if not parts:
        return False
    for part in parts:
        needle = normalize(part)
        if len(needle) < min_part_chars or needle.casefold() not in source_norm:
            return False
    return True


def assert_verbatim_quotes(
    text: str,
    source_text: str,
    *,
    min_quotes: int = 3,
    min_chars: int = 30,
    min_part_chars: int = 20,
) -> tuple[list[str], list[str]]:
    """Assert quoted evidence really appears in ``source_text``.

    This is the anti-hallucination gate for prose deliverables: a review can
    invent a plausible quotation far more easily than it can invent one that
    survives a verbatim lookup. Whitespace and letter case are normalized and
    an ellipsis inside a quote is matched piecewise, so honest citation styles
    still pass.
    Returns ``(matched, unmatched)`` — unmatched spans are not a failure on
    their own, since reports also quote proposed fixes and new code.
    """
    source_norm = normalize(source_text).casefold()
    spans = extract_quoted_spans(text, min_chars=min_chars)
    matched = [s for s in spans if _span_is_verbatim(s, source_norm, min_part_chars)]
    unmatched = [s for s in spans if s not in matched]

    if len(matched) < min_quotes:
        detail = ""
        if unmatched:
            shown = "; ".join(_excerpt(span, 120) for span in unmatched[:3])
            detail = f" Spans that were not source text: {shown}"
        fail(
            f"only {len(matched)} of {len(spans)} quoted span(s) appear verbatim in "
            f"the source; at least {min_quotes} required. Evidence must quote the "
            f"document under review, not paraphrase it or cite text that is not "
            f"there.{detail}"
        )
    return matched, unmatched


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
