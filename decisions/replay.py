"""Measure retry judgments against labeled history without leaking outcomes."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from copy import deepcopy
from numbers import Real
from os import PathLike
from pathlib import Path
from typing import Any

from .provider import DecisionProvider, Noul, NoulAnswer

DEFAULT_SKIP_THRESHOLD = 0.25
RETRY_QUESTION_KEY = "retry"
RETRY_QUESTION = Noul(
    instructions=(
        "Will retrying this task once rescue its failed check? Estimate whether "
        "one additional worker attempt, with the original specification and "
        "first-attempt check feedback, will pass the check. Use only the supplied "
        "first-attempt evidence."
    )
)

# Explicit projection, rather than copying the case and removing known labels:
# new outcome/metadata fields in a corpus must never silently become evidence.
_STATE_FIELDS = {
    "first_check_output": "check_output",
    "first_returncode": "returncode",
    "first_verdict": "verdict",
    "task_type": "task_type",
    "worker_engine": "engine",
    "spec": "spec",
}


def _first_attempt_state(case: Mapping[str, Any]) -> dict[str, Any]:
    return deepcopy({key: case.get(key, case.get(alias)) for key, alias in _STATE_FIELDS.items()})


def _read_cases(corpus_path: str | PathLike[str]) -> list[dict[str, Any]]:
    with Path(corpus_path).open(encoding="utf-8") as handle:
        corpus = json.load(handle)
    cases = corpus.get("cases") if isinstance(corpus, dict) else corpus
    if not isinstance(cases, list):
        raise ValueError("corpus must be a list of cases or an object containing 'cases'")
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or not isinstance(case.get("retry_rescued"), bool):
            raise ValueError(f"case {index} must have a boolean retry_rescued label")
    return cases


def _answer_probability(answers: Any) -> float | None:
    if not isinstance(answers, Mapping):
        return None
    answer = answers.get(RETRY_QUESTION_KEY)
    if isinstance(answer, NoulAnswer):
        value = answer.noul
    elif isinstance(answer, Mapping):
        value = answer.get("noul")
    else:
        return None
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        return None
    return float(value)


def score_provider(
    provider: DecisionProvider | None,
    corpus_path: str | PathLike[str],
    *,
    skip_threshold: float = DEFAULT_SKIP_THRESHOLD,
) -> dict[str, int | float]:
    """Replay one retry question per case; all metrics come from the supplied file.

    Skip only when P(rescue) <= skip_threshold (default 0.25). Thresholds must be
    below 0.5, so uncertainty always retries. None, exceptions, missing answers,
    and malformed probabilities also retry and are counted in fallback_retries.

    Accuracy counts rescued attempts retried plus wasted attempts skipped. The
    cost counts distinguish saved attempts from foregone rescues. Empty corpora
    return zero counts and 0.0 rates. Invalid labels fail before any provider call.
    """
    if (
        isinstance(skip_threshold, bool)
        or not isinstance(skip_threshold, Real)
        or not math.isfinite(skip_threshold)
        or not 0.0 <= skip_threshold < 0.5
    ):
        raise ValueError("skip_threshold must be finite and in [0, 0.5)")

    cases = _read_cases(corpus_path)
    rescued = sum(case["retry_rescued"] for case in cases)
    wasted_avoided = rescues_lost = skips = fallbacks = errors = 0
    for case in cases:
        probability = None
        if provider is not None:
            try:
                answers = provider.ask(
                    _first_attempt_state(case), {RETRY_QUESTION_KEY: RETRY_QUESTION}
                )
                probability = _answer_probability(answers)
            except Exception:
                # Authentication, overload, and other vendor failures must not
                # turn into skipped work. Do not catch process interruptions.
                errors += 1
        if probability is None:
            fallbacks += 1
        if probability is not None and probability <= skip_threshold:
            skips += 1
            if case["retry_rescued"]:
                rescues_lost += 1
            else:
                wasted_avoided += 1

    n = len(cases)
    rescues_kept = rescued - rescues_lost
    return {
        "n": n,
        "accuracy": (rescues_kept + wasted_avoided) / n if n else 0.0,
        "always_retry_baseline": rescued / n if n else 0.0,
        "always_skip_baseline": (n - rescued) / n if n else 0.0,
        "wasted_avoided": wasted_avoided,
        "rescues_lost": rescues_lost,
        "rescues_kept": rescues_kept,
        "wasted_retried": n - rescued - wasted_avoided,
        "retries_recommended": n - skips,
        "skips_recommended": skips,
        "fallback_retries": fallbacks,
        "provider_errors": errors,
        "skip_threshold": float(skip_threshold),
    }


__all__ = ["score_provider", "DEFAULT_SKIP_THRESHOLD", "RETRY_QUESTION", "RETRY_QUESTION_KEY"]
