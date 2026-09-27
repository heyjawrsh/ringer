"""Advisory quality judgments for answers drawn from a source packet.

State uses the measured field names ``QUESTION``, ``SOURCE``, and ``ANSWER``.
Four independent Nouls and one usefulness Score are asked in a single request,
following https://docs.typesafe.ai/cookbooks/llm_guardrails. Flags invite review;
they never change an executed check or a verdict. Unsupported means absent from
the source packet, even when a claim could be true outside that packet.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from numbers import Real
from typing import Any

from .provider import DecisionProvider, Noul, NoulAnswer, Score, ScoreAnswer


QUESTIONS = {
    "addresses_question": Noul(
        instructions=(
            "Does `ANSWER` address the actual question in `QUESTION`, rather "
            "than answering a different question or offering generic filler?"
        ),
    ),
    "complete": Noul(
        instructions=(
            "Is `ANSWER` complete, with its thoughts and ending finished, "
            "rather than truncated or cut off mid-thought? Judge whether the "
            "text is finished independently of whether it addresses `QUESTION`."
        ),
    ),
    "committal": Noul(
        instructions=(
            "Does `ANSWER` commit to a substantive conclusion or position "
            "in response to `QUESTION`, rather than hedge until it says "
            "nothing? Scoped uncertainty or a clear conclusion that `SOURCE` "
            "cannot resolve `QUESTION` still counts as a position."
        ),
    ),
    "unsupported_claims": Noul(
        instructions=(
            "Does `ANSWER` state any specific facts, such as numbers, limits, "
            "field names, endpoints, or guarantees, that do not appear "
            "anywhere in `SOURCE`? Judge absence from this source packet, "
            "even if the claim could be true or a reasonable synthesis. "
            "A paraphrase of a fact present in `SOURCE` is supported."
        ),
    ),
    "usefulness": Score(
        instructions=(
            "How useful is `ANSWER` to the person who asked `QUESTION`, "
            "given the source packet in `SOURCE`?"
        ),
        criteria=[
            "Provides no usable answer: irrelevant, empty, or generic filler.",
            "Touches the topic but leaves the person's actual question unanswered.",
            "Provides a partial answer that needs substantial follow-up to use.",
            "Provides a direct, useful answer with only minor gaps to resolve.",
            "Provides an immediately usable answer covering the requested details "
            "and making the limits of the available evidence clear.",
        ],
    ),
}

# Thresholds sit inside the supplied measurement gaps, not at either endpoint.
# The unsupported-specifics gap was also measured on source-verbatim answers;
# legitimate synthesis beyond the packet (~0.80) should still invite checking.
MIN_ADDRESSES_QUESTION = 0.50  # real 0.90; off-topic 0.01, filler 0.12
MIN_COMPLETE = 0.50          # real 0.82; truncated 0.22
MIN_COMMITTAL = 0.65         # real 0.84; over-hedged 0.45
MAX_UNSUPPORTED_CLAIMS = 0.50  # clean 0.084; one unsupported specific 0.946
MIN_USEFULNESS = 2.0         # real 3.17; filler 0.23, off-topic 0.01 (0-4)

_NOUL_KEYS = (
    "addresses_question", "complete", "committal", "unsupported_claims",
)


@dataclass(frozen=True, slots=True)
class AnswerQuality:
    """An opinion, or an explicit reason no complete opinion was obtained.

    Empty flags are meaningful only when ``graded`` is true. ``confidence``
    belongs to the usefulness Score; each Noul already expresses probability.
    """

    graded: bool
    flags: tuple[str, ...]
    reason: str
    usefulness: float | None = None
    confidence: float | None = None
    addresses_question: float | None = None
    complete: float | None = None
    committal: float | None = None
    unsupported_claims: float | None = None


def _ungraded(reason: str) -> AnswerQuality:
    return AnswerQuality(
        graded=False,
        flags=(),
        reason=f"Answer quality was not graded: {reason} Review the answer manually.",
    )


def _number(value: Any, maximum: float) -> float | None:
    """Reject malformed values rather than silently treating them as clean."""
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    number = float(value)
    if math.isfinite(number) and 0.0 <= number <= maximum:
        return number
    return None


def grade(state: Any, provider: DecisionProvider | None) -> AnswerQuality:
    """Ask the whole battery once; return advice without raising on any failure.

    The caller supplies ``QUESTION``, ``SOURCE``, and ``ANSWER`` in state.
    Require every typed answer before reporting a grade, so a partial response
    cannot masquerade as a clean answer. Score confidence is retained for the
    reader and does not suppress any independently measured concern.
    """
    try:
        if provider is None:
            return _ungraded("no decision provider is configured.")

        answers = provider.ask(state, QUESTIONS)
        if not isinstance(answers, Mapping):
            return _ungraded("the provider did not return an answer map.")

        nouls = {}
        for key in _NOUL_KEYS:
            answer = answers.get(key)
            if answer is None:
                return _ungraded(f"the provider omitted the {key} answer.")
            if not isinstance(answer, NoulAnswer):
                return _ungraded(f"the {key} answer is not a NoulAnswer.")
            value = _number(answer.noul, 1.0)
            if value is None:
                return _ungraded(f"the {key} probability is not finite and within 0-1.")
            nouls[key] = value

        usefulness = answers.get("usefulness")
        if usefulness is None:
            return _ungraded("the provider omitted the usefulness answer.")
        if not isinstance(usefulness, ScoreAnswer):
            return _ungraded("the usefulness answer is not a ScoreAnswer.")
        levels = {str(level) for level in range(5)}
        if set(usefulness.legend) != levels or set(usefulness.probabilities) != levels:
            return _ungraded("the usefulness answer does not use the 0-4 scale.")
        score = _number(usefulness.score, 4.0)
        confidence = _number(usefulness.confidence, 1.0)
        if score is None:
            return _ungraded("the usefulness score is not finite and within 0-4.")
        if confidence is None:
            return _ungraded("the usefulness confidence is not finite and within 0-1.")

        flags = []
        if nouls["addresses_question"] < MIN_ADDRESSES_QUESTION:
            flags.append(
                "May answer a different question; compare it with your question "
                "and ask for a direct answer."
            )
        if nouls["complete"] < MIN_COMPLETE:
            flags.append(
                "May be truncated or cut off mid-thought; ask for the missing remainder."
            )
        if nouls["committal"] < MIN_COMMITTAL:
            flags.append(
                "May hedge without committing to a position; ask for a clear "
                "conclusion and its supporting evidence."
            )
        if nouls["unsupported_claims"] > MAX_UNSUPPORTED_CLAIMS:
            flags.append(
                "States specifics not supported by your source, worth checking "
                "against the packet or an additional source."
            )
        if score < MIN_USEFULNESS:
            flags.append(
                "May offer little useful information; ask for concrete findings "
                "that answer your question."
            )
        return AnswerQuality(
            graded=True,
            flags=tuple(flags),
            reason="Advisory grade obtained from all five judgments.",
            usefulness=score,
            confidence=confidence,
            **nouls,
        )
    except BaseException:
        # Even SystemExit, KeyboardInterrupt, or a broken answer accessor must
        # leave the answer ungraded. Do not stringify provider error payloads.
        return _ungraded("the provider judgment could not be obtained or read.")


__all__ = ["QUESTIONS", "AnswerQuality", "grade"]
