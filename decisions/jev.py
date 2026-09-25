"""TypeSafe's Jev as a decision provider.

This file is the whole integration. It adds no hook to `provider.py` and
edits nothing that already exists -- a vendor arrives as a module plus a
`register_provider` call, which is the property the seam was built for and
the one a competitor or a later model has to be able to exercise.

The credential is read from the environment, never stored here. Absence of a
credential is an ordinary condition, not an error: the provider raises when
asked, `replay` counts it, and the caller falls back to whatever it did
before. That is the same path a 429 or a 529 takes.

Wire contract (docs/decisions/typesafe-api-contract.md):
    POST https://api.typesafe.ai/v1/systemone
    Authorization: Bearer <key>
    {state, model, questions{id: {type, instructions, criteria?}}}
 -> {model, answers{id: {...}}, usage}

A Noul answer carries `noul` and NO confidence; Choice and Score carry
`probabilities` and a `confidence` derived from them. That asymmetry is the
vendor's, and it is reproduced rather than smoothed over.
"""
from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
from typing import Any

from decisions.provider import (
    Choice,
    ChoiceAnswer,
    DecisionProvider,
    Noul,
    NoulAnswer,
    Score,
    ScoreAnswer,
    register_provider,
)

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
CREDENTIAL_ENV = "TYPESAFE_API_KEY"

# The vendor SDK's own defaults, reproduced so our retries match the
# behaviour their service is tuned for: two retries after the first attempt,
# 0.5s doubling to a 5s ceiling, with jitter subtracting up to 25%.
MAX_RETRIES = 2
BASE_DELAY_S = 0.5
MAX_DELAY_S = 5.0
RETRYABLE_STATUS = {408, 429} | set(range(500, 600))


class JevUnavailable(RuntimeError):
    """The vendor could not answer. Callers fall back; they do not skip work."""


def _question_payload(question: Any) -> dict[str, Any]:
    if isinstance(question, Noul):
        payload: dict[str, Any] = {"type": "noul",
                                   "instructions": question.instructions}
        # Noul's true/false criteria are optional and this seam's Noul may not
        # carry the field at all, so ask rather than assume.
        criteria = getattr(question, "criteria", None)
        if criteria:
            payload["criteria"] = criteria
        return payload
    if isinstance(question, Choice):
        return {"type": "choice", "instructions": question.instructions,
                "criteria": dict(question.criteria)}
    if isinstance(question, Score):
        return {"type": "score", "instructions": question.instructions,
                "criteria": list(question.criteria)}
    raise TypeError(f"unsupported question type: {type(question).__name__}")


def _answer_object(raw: Any) -> Any:
    if not isinstance(raw, dict):
        raise JevUnavailable(f"malformed answer: {raw!r}")
    kind = raw.get("type")
    if kind == "noul":
        # No confidence here, deliberately. See the module docstring.
        return NoulAnswer(noul=float(raw["noul"]))
    if kind == "choice":
        return ChoiceAnswer(
            choice=str(raw["choice"]),
            probabilities={str(k): float(v)
                           for k, v in (raw.get("probabilities") or {}).items()},
            confidence=float(raw["confidence"]))
    if kind == "score":
        return ScoreAnswer(
            score=float(raw["score"]),
            legend={str(k): str(v) for k, v in (raw.get("legend") or {}).items()},
            probabilities={str(k): float(v)
                           for k, v in (raw.get("probabilities") or {}).items()},
            confidence=float(raw["confidence"]))
    raise JevUnavailable(f"unknown answer type: {kind!r}")


class JevProvider(DecisionProvider):
    """Ask Jev, in one round trip, for every question at once."""

    name = "jev"

    def __init__(self, *, model: str = DEFAULT_MODEL, timeout_s: float = 30.0,
                 api_key: str | None = None) -> None:
        self.model = model
        self.timeout_s = timeout_s
        self._api_key = api_key

    def _key(self) -> str:
        key = self._api_key or os.environ.get(CREDENTIAL_ENV, "")
        if not key:
            raise JevUnavailable(
                f"no credential in ${CREDENTIAL_ENV}; the caller falls back")
        return key

    def ask(self, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        if not questions:
            return {}
        body = json.dumps({
            "state": state,
            "model": self.model,
            "questions": {k: _question_payload(q) for k, q in questions.items()},
        }).encode("utf-8")
        request = urllib.request.Request(
            ENDPOINT, data=body,
            headers={"Authorization": f"Bearer {self._key()}",
                     "Content-Type": "application/json"})

        last = ""
        for attempt in range(MAX_RETRIES + 1):
            try:
                with urllib.request.urlopen(request,
                                            timeout=self.timeout_s) as response:
                    payload = json.loads(response.read())
                break
            except urllib.error.HTTPError as exc:
                last = f"HTTP {exc.code}"
                # A 401 or a 422 will not improve by being asked again.
                if exc.code not in RETRYABLE_STATUS or attempt == MAX_RETRIES:
                    raise JevUnavailable(last) from exc
                delay = self._delay(attempt, exc.headers.get("Retry-After"))
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last = f"{type(exc).__name__}: {exc}"
                if attempt == MAX_RETRIES:
                    raise JevUnavailable(last) from exc
                delay = self._delay(attempt, None)
            time.sleep(delay)
        else:  # pragma: no cover - the loop always breaks or raises
            raise JevUnavailable(last or "exhausted retries")

        answers = payload.get("answers")
        if not isinstance(answers, dict):
            raise JevUnavailable("response carried no answers map")
        missing = set(questions) - set(answers)
        if missing:
            # The SDK can omit an answer it does not recognise. Say so rather
            # than returning a partial map the caller will read as complete.
            raise JevUnavailable(f"no answer for {sorted(missing)}")
        return {key: _answer_object(answers[key]) for key in questions}

    @staticmethod
    def _delay(attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(float(retry_after), MAX_DELAY_S)
            except ValueError:
                pass
        delay = min(BASE_DELAY_S * (2 ** attempt), MAX_DELAY_S)
        return delay * (1.0 - random.random() * 0.25)


register_provider("jev", JevProvider)

__all__ = ["JevProvider", "JevUnavailable"]
