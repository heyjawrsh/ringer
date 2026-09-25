"""Provider-independent questions, answers, and named provider factories.

Only the standard library is required. Providers implement ``ask`` and register
a zero-argument factory; callers own question keys and decisions about certainty.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from numbers import Real
from typing import Any, Literal

Description = str | dict[str, Any] | list[Any]


@dataclass(frozen=True, slots=True)
class Noul:
    """Ask whether a proposition is true."""

    instructions: Description
    type: Literal["noul"] = field(default="noul", init=False)


@dataclass(frozen=True, slots=True)
class Choice:
    """Select one of the named options using its rubric."""

    instructions: Description
    criteria: Mapping[str, Description | None]
    type: Literal["choice"] = field(default="choice", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.criteria, Mapping) or not self.criteria:
            raise ValueError("Choice criteria must be a nonempty option map")
        if any(not isinstance(key, str) for key in self.criteria):
            raise ValueError("Choice option names must be strings")
        object.__setattr__(self, "criteria", dict(self.criteria))


@dataclass(frozen=True, slots=True)
class Score:
    """Rate against ordered levels, numbered from zero."""

    instructions: Description
    criteria: list[Description]
    type: Literal["score"] = field(default="score", init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.criteria, Sequence)
            or isinstance(self.criteria, (str, bytes))
            or not self.criteria
        ):
            raise ValueError("Score criteria must be a nonempty ordered list")
        object.__setattr__(self, "criteria", list(self.criteria))


def _probability(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a number between 0 and 1")
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be finite and between 0 and 1")
    return value


def _distribution(values: Mapping[str, float]) -> dict[str, float]:
    if not isinstance(values, Mapping) or not values:
        raise ValueError("probabilities must be a nonempty map")
    if any(not isinstance(key, str) for key in values):
        raise ValueError("probability keys must be strings")
    result = {key: _probability(value, key) for key, value in values.items()}
    if not math.isclose(math.fsum(result.values()), 1.0, abs_tol=1e-6):
        raise ValueError("probabilities must sum to 1")
    return result


@dataclass(frozen=True, slots=True)
class NoulAnswer:
    """Probability of yes. There is deliberately no confidence field."""

    noul: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "noul", _probability(self.noul, "noul"))


@dataclass(frozen=True, slots=True)
class ChoiceAnswer:
    """A selected option and a distribution over every supplied option."""

    choice: str
    probabilities: Mapping[str, float]
    confidence: float

    def __post_init__(self) -> None:
        probabilities = _distribution(self.probabilities)
        if self.choice not in probabilities:
            raise ValueError("choice must appear in probabilities")
        object.__setattr__(self, "probabilities", probabilities)
        object.__setattr__(self, "confidence", _probability(self.confidence, "confidence"))


@dataclass(frozen=True, slots=True)
class ScoreAnswer:
    """Expected level with descriptions and probabilities keyed by level number."""

    score: float
    legend: Mapping[str, Description]
    probabilities: Mapping[str, float]
    confidence: float

    def __post_init__(self) -> None:
        probabilities = _distribution(self.probabilities)
        if not isinstance(self.legend, Mapping) or set(self.legend) != {
            str(level) for level in range(len(self.legend))
        }:
            raise ValueError("legend keys must be consecutive level strings starting at '0'")
        if set(self.legend) != set(probabilities):
            raise ValueError("legend and probabilities must describe the same levels")
        if (
            isinstance(self.score, bool)
            or not isinstance(self.score, Real)
            or not math.isfinite(self.score)
            or not 0.0 <= self.score <= len(self.legend) - 1
        ):
            raise ValueError("score must be finite and within the rubric's levels")
        object.__setattr__(self, "score", float(self.score))
        object.__setattr__(self, "legend", dict(self.legend))
        object.__setattr__(self, "probabilities", probabilities)
        object.__setattr__(self, "confidence", _probability(self.confidence, "confidence"))


Question = Noul | Choice | Score
Answer = NoulAnswer | ChoiceAnswer | ScoreAnswer
Questions = Mapping[str, Question]
Answers = dict[str, Answer]


class DecisionProvider(ABC):
    """Judge state without producing or executing a worker artifact.

    Implementations return exactly one matching answer per question, under the
    original caller key. Unavailable vendors may raise; the caller owns fallback.
    """

    @abstractmethod
    def ask(self, state: Any, questions: Questions) -> Answers:
        """Evaluate independent questions over the same state."""
        raise NotImplementedError


ProviderFactory = Callable[[], DecisionProvider]
_PROVIDERS: dict[str, ProviderFactory] = {}


def register_provider(name: str, factory: ProviderFactory) -> None:
    """Register (or explicitly replace) a factory without editing dispatch code."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("provider name must be a nonempty string")
    if not callable(factory):
        raise TypeError("provider factory must be callable")
    _PROVIDERS[name] = factory


def get_provider(name: str) -> DecisionProvider:
    """Create a registered provider; unknown names raise KeyError."""
    try:
        factory = _PROVIDERS[name]
    except KeyError:
        raise KeyError(f"Unknown decision provider: {name!r}") from None
    return factory()


__all__ = [
    "Noul", "Choice", "Score", "Question", "Questions", "Description",
    "NoulAnswer", "ChoiceAnswer", "ScoreAnswer", "Answer", "Answers",
    "DecisionProvider", "ProviderFactory", "register_provider", "get_provider",
]
