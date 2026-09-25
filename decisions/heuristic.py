"""Deterministic, offline surface rules, not a calibrated judgment model.

Retry estimates use observed check output, never outcome labels or historical
lookups. Unknown propositions return 0.5; generic rubrics use weak lexical overlap
and otherwise uniform distributions. All numbers below are hand-set rule weights,
not fitted success rates. No files, subprocesses, credentials, or sockets are used.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from typing import Any

from .provider import (
    Answers,
    Choice,
    ChoiceAnswer,
    DecisionProvider,
    Noul,
    NoulAnswer,
    Questions,
    Score,
    ScoreAnswer,
    register_provider,
)

_RETRY = re.compile(r"\b(?:retry|retrying|retries|retried|reattempt|re-attempt)\b")
_SKIP = re.compile(r"\b(?:skip|stop|abort|escalate|abandon|futile|pointless|wasted?|unlikely)\b")
_BLOCKED = re.compile(
    r"read-only file system|no space left on device|disk quota exceeded|"
    r"insufficient[_ ]quota|invalid[ _-]api[ _-]key|"
    r"(?:credentials?|api[ _-]key|access token) (?:has |have |is |are )?expired|"
    r"authentication (?:is )?required|not authenticated|billing (?:limit|quota)"
)
_TRANSIENT = re.compile(
    r"timed? out|timeout|rate[ _-]limit|too many requests|connection reset|"
    r"connection refused|temporar(?:y|ily)|service unavailable|overloaded|\b50[234]\b"
)
_ACTIONABLE = re.compile(
    r"assertionerror|syntaxerror|typeerror|nameerror|indentationerror|"
    r"expected .+ (?:got|received)|missing expected files|was not created"
)
_STOPWORDS = frozenset(
    "a an the and or to of in on for with is are be it this that task check output".split()
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.lower()
    try:
        return json.dumps(value, ensure_ascii=False, default=str).lower()
    except (TypeError, ValueError):
        return str(value).lower()


def _retry_probability(state: Any) -> float:
    if isinstance(state, Mapping):
        output = _text(state.get("first_check_output", state.get("check_output")))
    elif isinstance(state, str):
        output = state.lower()
    else:
        return 0.5
    # A worker generally cannot repair account access, disk capacity, or a
    # read-only filesystem merely by taking another attempt.
    if _BLOCKED.search(output):
        return 0.15
    if _TRANSIENT.search(output):
        return 0.65
    # Concrete feedback may be repairable. A FAIL verdict alone says very little.
    if _ACTIONABLE.search(output):
        return 0.55
    return 0.5


def _retry_direction(instructions: Any) -> int:
    text = _text(instructions)
    if not _RETRY.search(text):
        return 0
    if _SKIP.search(text) or re.search(
        r"\b(?:not|never) (?:\w+ ){0,2}retry\b|\bretry\b.{0,20}\bfail\b", text
    ):
        return -1
    return 1


def _option_direction(label: str, rubric: Any) -> int:
    # An explicit action label takes precedence over explanatory rubric text,
    # which can legitimately mention both alternatives.
    text = label.lower()
    if _SKIP.search(text):
        return -1
    if _RETRY.search(text):
        return 1
    return _retry_direction(rubric)


def _tokens(value: Any) -> set[str]:
    return set(re.findall(r"[a-z][a-z0-9_-]+", _text(value))) - _STOPWORDS


def _rubric_distribution(
    state: Any, criteria: Mapping[str, Any]
) -> dict[str, float]:
    evidence = _tokens(state)
    weights = {}
    for key, description in criteria.items():
        terms = _tokens([key, description])
        # At most a small preference: shared words do not establish correctness.
        overlap = len(evidence & terms) / max(1, len(terms))
        weights[key] = 1.0 + 0.25 * overlap
    total = math.fsum(weights.values())
    return {key: weight / total for key, weight in weights.items()}


def _confidence(probabilities: Mapping[str, float]) -> float:
    """Concentration above uniform, not an empirically calibrated confidence."""
    if len(probabilities) == 1:
        return 1.0
    uniform = 1.0 / len(probabilities)
    return max(0.0, min(1.0, (max(probabilities.values()) - uniform) / (1.0 - uniform)))


class HeuristicProvider(DecisionProvider):
    """Local retry rules and deliberately uncertain general-purpose answers."""

    name = "heuristic"

    def ask(self, state: Any, questions: Questions) -> Answers:
        answers: Answers = {}
        rescue_probability = _retry_probability(state)
        for key, question in questions.items():
            if isinstance(question, Noul):
                direction = _retry_direction(question.instructions)
                probability = (
                    rescue_probability if direction > 0
                    else 1.0 - rescue_probability if direction < 0
                    else 0.5
                )
                answers[key] = NoulAnswer(noul=probability)
            elif isinstance(question, Choice):
                directions = {
                    option: _option_direction(option, rubric)
                    for option, rubric in question.criteria.items()
                }
                if set(directions.values()) == {-1, 1}:
                    counts = {direction: list(directions.values()).count(direction) for direction in (-1, 1)}
                    probabilities = {
                        option: (
                            rescue_probability if direction > 0 else 1.0 - rescue_probability
                        ) / counts[direction]
                        for option, direction in directions.items()
                    }
                else:
                    probabilities = _rubric_distribution(state, question.criteria)
                answers[key] = ChoiceAnswer(
                    choice=max(probabilities, key=probabilities.get),
                    probabilities=probabilities,
                    confidence=_confidence(probabilities),
                )
            elif isinstance(question, Score):
                legend = {str(level): description for level, description in enumerate(question.criteria)}
                probabilities = _rubric_distribution(state, legend)
                answers[key] = ScoreAnswer(
                    score=math.fsum(int(level) * probability for level, probability in probabilities.items()),
                    legend=legend,
                    probabilities=probabilities,
                    confidence=_confidence(probabilities),
                )
            else:
                raise TypeError(f"Unsupported question type: {type(question).__name__}")
        return answers


register_provider("heuristic", HeuristicProvider)

__all__ = ["HeuristicProvider"]
