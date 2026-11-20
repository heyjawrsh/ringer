"""SubQ Snap as a decision provider, on Subquadratic's own API.

This is the second vendor to arrive through the seam, and it arrives the way
the seam intended: one new module plus a `register_provider` call. Nothing in
`provider.py` changes, and nothing in `jev.py` is touched.

SubQ Snap speaks the same wire format as Jev -- the same question objects, the
same answer objects, the same asymmetry where a Noul answer carries a
probability and no confidence while Choice and Score carry both. So this
adapter follows `jev.py` closely rather than inventing a shape.

Wire contract (https://docs.subq.ai/endpoints/decisions-api/):
    POST https://api.subq.ai/v1/systemone
    Authorization: Bearer <key>
    {model, state, questions{id: {type, instructions, criteria?}}}
 -> {model, answers{id: {...}}, usage}

The credential is never stored here and never printed. It comes from
$SUBQ_API_KEY, or, when that is unset and $SUBQ_OP_REF is, from
`op read $SUBQ_OP_REF` (the 1Password CLI), resolved lazily on the first ask
and cached for the life of the provider.

Pricing for this model is input-only: you pay for what you send, and output
tokens are free.
"""
from __future__ import annotations

import json
import os
import random
import subprocess
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

ENDPOINT = "https://api.subq.ai/v1/systemone"
DEFAULT_MODEL = "subq-snap-1.2"
CREDENTIAL_ENV = "SUBQ_API_KEY"
OP_REF_ENV = "SUBQ_OP_REF"

# Same retry shape as Jev's adapter: two retries after the first attempt,
# 0.5s doubling to a 5s ceiling, with jitter subtracting up to 25%.
MAX_RETRIES = 2
BASE_DELAY_S = 0.5
MAX_DELAY_S = 5.0
RETRYABLE_STATUS = {408, 429} | set(range(500, 600))


class SubQUnavailable(RuntimeError):
    """The vendor could not answer. Callers fall back; they do not skip work."""


def _question_payload(question: Any) -> dict[str, Any]:
    if isinstance(question, Noul):
        payload: dict[str, Any] = {"type": "noul",
                                   "instructions": question.instructions}
        criteria = getattr(question, "criteria", None)
        if criteria:
            payload["criteria"] = criteria
        return payload
    if isinstance(question, Choice):
        # Option names map to a description or null; the nulls are kept.
        return {"type": "choice", "instructions": question.instructions,
                "criteria": dict(question.criteria)}
    if isinstance(question, Score):
        return {"type": "score", "instructions": question.instructions,
                "criteria": list(question.criteria)}
    raise TypeError(f"unsupported question type: {type(question).__name__}")


def _normalised(raw: Any) -> dict[str, float]:
    """Rescale rounded probabilities to sum to exactly 1.

    The wire format rounds for display, so a distribution can arrive summing
    to 0.99. Only rounding is absorbed (0.98-1.02); anything further off is a
    malformed response and fails rather than being silently rescaled.
    """
    values = {str(k): float(v) for k, v in (raw or {}).items()}
    if not values:
        raise SubQUnavailable("answer carried no probabilities")
    total = sum(values.values())
    if not 0.98 <= total <= 1.02:
        raise SubQUnavailable(f"probabilities sum to {total:.4f}, not ~1")
    return {k: v / total for k, v in values.items()}


def _answer_object(raw: Any) -> Any:
    if not isinstance(raw, dict):
        raise SubQUnavailable(f"malformed answer: {raw!r}")
    kind = raw.get("type")
    if kind == "noul":
        # No confidence here, deliberately: the vendor does not send one.
        return NoulAnswer(noul=float(raw["noul"]))
    if kind == "choice":
        return ChoiceAnswer(
            choice=str(raw["choice"]),
            probabilities=_normalised(raw.get("probabilities")),
            confidence=float(raw["confidence"]))
    if kind == "score":
        return ScoreAnswer(
            score=float(raw["score"]),
            legend={str(k): str(v) for k, v in (raw.get("legend") or {}).items()},
            probabilities=_normalised(raw.get("probabilities")),
            confidence=float(raw["confidence"]))
    raise SubQUnavailable(f"unknown answer type: {kind!r}")


def _detail_message(exc: urllib.error.HTTPError) -> str:
    """Pull the vendor's detail.message out of an error body, if it is there."""
    try:
        body = exc.read()
    except Exception:  # noqa: BLE001 - an unreadable body is not a new failure
        return ""
    if not body:
        return ""
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        return text.strip()
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str):
            return message
    if isinstance(detail, str):
        return detail
    return ""


class SubQProvider(DecisionProvider):
    """Ask SubQ Snap, in one round trip, for every question at once."""

    name = "subq"

    def __init__(self, *, model: str = DEFAULT_MODEL, timeout_s: float = 30.0,
                 api_key: str | None = None) -> None:
        self.model = model
        self.timeout_s = timeout_s
        self._api_key = api_key
        self._credential: str | None = None
        self._credential_resolved = False

    def _key(self) -> str:
        """Resolve the credential once, then reuse it for this provider.

        A failed resolution is not cached: the next ask tries again, so a
        missing `op` or an unset variable fixed mid-run still recovers.
        """
        if self._credential_resolved:
            return self._credential
        if self._api_key:
            key = self._api_key
        else:
            key = os.environ.get(CREDENTIAL_ENV, "")
            if not key:
                key = self._from_op()
        self._credential = key
        self._credential_resolved = True
        return key

    def _from_op(self) -> str:
        ref = os.environ.get(OP_REF_ENV, "")
        if not ref:
            raise SubQUnavailable(
                f"no credential: set ${CREDENTIAL_ENV} or ${OP_REF_ENV}; "
                "the caller falls back")
        try:
            result = subprocess.run(["op", "read", ref], capture_output=True,
                                    text=True, timeout=30)
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
            raise SubQUnavailable(
                f"could not read ${OP_REF_ENV} with the op CLI: "
                f"{type(exc).__name__}") from exc
        if result.returncode != 0:
            # Relay op's own "[ERROR] ..." line ("authorization timeout" when
            # 1Password is locked) and nothing else, so stray stderr can never
            # carry the secret into an exception.
            reason = [line[len("[ERROR] "):] for line in (result.stderr or "").splitlines()
                      if line.startswith("[ERROR] ")]
            raise SubQUnavailable(
                f"could not read ${OP_REF_ENV}: op exited {result.returncode}"
                + (f": {reason[-1][:200]}" if reason else ""))
        key = result.stdout.strip()
        if not key:
            raise SubQUnavailable(f"${OP_REF_ENV} resolved to an empty value")
        return key

    def ask(self, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        if not questions:
            return {}
        key = self._key()
        body = json.dumps({
            "model": self.model,
            "state": state,
            "questions": {k: _question_payload(q) for k, q in questions.items()},
        }).encode("utf-8")
        request = urllib.request.Request(
            ENDPOINT, data=body,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"})

        last = ""
        payload: Any = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                with urllib.request.urlopen(request,
                                            timeout=self.timeout_s) as response:
                    payload = json.loads(response.read())
                break
            except urllib.error.HTTPError as exc:
                detail = _detail_message(exc)
                last = f"HTTP {exc.code}" + (f": {detail}" if detail else "")
                if exc.code == 402:
                    last += " (the SubQ account is out of credits)"
                # A 400, 401, 402, 403 or 422 will not improve by being retried.
                if exc.code not in RETRYABLE_STATUS or attempt == MAX_RETRIES:
                    raise SubQUnavailable(last) from exc
                delay = self._delay(attempt, exc.headers.get("Retry-After"))
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last = f"{type(exc).__name__}: {exc}"
                if attempt == MAX_RETRIES:
                    raise SubQUnavailable(last) from exc
                delay = self._delay(attempt, None)
            time.sleep(delay)
        else:  # pragma: no cover - the loop always breaks or raises
            raise SubQUnavailable(last or "exhausted retries")

        answers = payload.get("answers") if isinstance(payload, dict) else None
        if not isinstance(answers, dict):
            raise SubQUnavailable("response carried no answers map")
        missing = set(questions) - set(answers)
        if missing:
            raise SubQUnavailable(f"no answer for {sorted(missing)}")
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


register_provider("subq", SubQProvider)

__all__ = ["SubQProvider", "SubQUnavailable"]
