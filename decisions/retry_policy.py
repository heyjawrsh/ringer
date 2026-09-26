"""Conservative retry suppression using the measured Choice confidence gate.

At confidence >= 0.5, the 343-case replay saved 23 wasted attempts while
forfeiting 4 rescues. A lost rescue costs more than a wasted attempt, so
uncertainty and provider failures must preserve the retry. See
``docs/decisions/jev-measured.md`` for the measurement.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .provider import Choice, ChoiceAnswer, DecisionProvider

DEFAULT_MIN_CONFIDENCE = 0.5
RETRY_QUESTION_KEY = "retry"

# The state field names the thresholds were MEASURED with. These are not
# cosmetic: the state is handed to the provider as a JSON object and its keys
# are part of what the model reads, so a runtime state shaped differently
# from the measured one is a different question, and the numbers in
# docs/decisions/jev-measured.md stop describing it.
#
# They live here, with one builder, because the measurement path
# (decisions/replay.py) and the runtime path (ringer.py) reached the provider
# by different routes and had already drifted apart on four of six names.
STATE_KEYS = (
    "first_check_output",
    "first_returncode",
    "first_verdict",
    "task_type",
    "worker_engine",
    "spec",
)


def build_state(*, check_output: Any, returncode: Any, verdict: Any,
                task_type: Any, engine: Any, spec: Any) -> dict[str, Any]:
    """Build the exact state the retry thresholds were calibrated against."""
    return {
        "first_check_output": check_output,
        "first_returncode": returncode,
        "first_verdict": verdict,
        "task_type": task_type,
        "worker_engine": engine,
        "spec": spec,
    }

RETRY_QUESTION = Choice(
    instructions=(
        "Will retrying this task once rescue its failed check? Estimate whether "
        "one additional worker attempt, with the original specification and "
        "first-attempt check feedback, will pass the check. Use only the supplied "
        "first-attempt evidence."
    ),
    criteria={
        "retry_likely_passes": (
            "One more worker attempt can plausibly fix the failure and pass "
            "the check using the specification and first-attempt feedback."
        ),
        "retry_likely_fails": (
            "Another worker attempt is likely to encounter the same blocker "
            "and fail the check again."
        ),
        "cannot_tell": (
            "The supplied evidence does not support a judgment about whether "
            "another worker attempt would pass or fail the check."
        ),
    },
)


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """An auditable policy outcome; ``skip=False`` preserves the retry."""

    skip: bool
    reason: str
    choice: str | None = None
    confidence: float | None = None
    provider: str | None = None


def _confidence(value: Any) -> float | None:
    """Read a confidence without turning malformed data into permission to skip."""
    try:
        if isinstance(value, bool):
            return None
        number = float(value)
        if math.isfinite(number) and 0.0 <= number <= 1.0:
            return number
    except BaseException:
        # Even a broken conversion must preserve the worker's retry.
        pass
    return None


def decide(
    state: Any,
    provider: DecisionProvider | None,
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> RetryDecision:
    """Skip only a confidently predicted failure; otherwise retry with a reason.

    ``cannot_tell`` always retries, regardless of confidence. Its small measured
    bucket is not sufficient evidence to turn an abstention into cancelled work.
    """
    if provider is None:
        return RetryDecision(False, "Retrying: no decision provider is configured.")

    provider_name = None
    choice = None
    confidence = None
    try:
        name = getattr(provider, "name", None)
        provider_name = name if isinstance(name, str) else type(provider).__name__
        answers = provider.ask(state, {RETRY_QUESTION_KEY: RETRY_QUESTION})
        if not isinstance(answers, Mapping):
            return RetryDecision(
                False, "Retrying: the provider did not return an answer map.",
                provider=provider_name,
            )
        answer = answers.get(RETRY_QUESTION_KEY)
        if answer is None:
            return RetryDecision(
                False, "Retrying: the provider omitted the retry answer.",
                provider=provider_name,
            )
        if not isinstance(answer, ChoiceAnswer):
            return RetryDecision(
                False, "Retrying: the retry answer is not a ChoiceAnswer.",
                provider=provider_name,
            )
        if not isinstance(answer.choice, str):
            return RetryDecision(
                False, "Retrying: the chosen option is not a string.",
                provider=provider_name,
            )
        choice = answer.choice
        confidence = _confidence(answer.confidence)
        if confidence is None:
            return RetryDecision(
                False, "Retrying: confidence is not a finite number between 0 and 1.",
                choice=choice, provider=provider_name,
            )
        gate = _confidence(min_confidence)
        if gate is None:
            reason = "Retrying: the confidence gate is not a finite number between 0 and 1."
        elif choice == "cannot_tell":
            reason = "Retrying: cannot_tell means insufficient evidence, at any confidence."
        elif choice != "retry_likely_fails":
            reason = f"Retrying: {choice!r} does not recommend skipping the retry."
        elif confidence >= gate:
            return RetryDecision(
                True,
                f"Skipping retry: {provider_name} chose retry_likely_fails with "
                f"confidence {confidence!r} >= gate {gate!r}.",
                choice=choice, confidence=confidence, provider=provider_name,
            )
        else:
            reason = (
                "Retrying: retry_likely_fails has confidence "
                f"{confidence!r} below gate {gate!r}."
            )
        return RetryDecision(
            False, reason, choice=choice, confidence=confidence, provider=provider_name,
        )
    except BaseException as exc:
        # The policy contract requires retrying after anything a provider raises,
        # including exceptions outside Exception. Avoid exposing error payloads.
        return RetryDecision(
            False,
            f"Retrying: the provider judgment is unavailable ({type(exc).__name__}).",
            choice=choice, confidence=confidence, provider=provider_name,
        )


__all__ = [
    "DEFAULT_MIN_CONFIDENCE", "RETRY_QUESTION_KEY", "RETRY_QUESTION",
    "RetryDecision", "decide",
]
