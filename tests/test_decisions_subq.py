"""Offline regression tests for decisions/subq.py -- SubQ Snap as a provider.

Everything here is mocked: no network, no real `op`. urllib is patched at the
module attribute the adapter calls, time.sleep is patched so retries are
instant, and the 1Password CLI is a temporary stub script on PATH.
"""

from __future__ import annotations

import io
import json
import os
import stat
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from decisions.provider import Choice, Noul, NoulAnswer, Score, get_provider
from decisions.subq import (
    CREDENTIAL_ENV,
    DEFAULT_MODEL,
    ENDPOINT,
    OP_REF_ENV,
    SubQProvider,
    SubQUnavailable,
)


class FakeResponse:
    """The subset of an http.client response the adapter reads."""

    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def http_error(code, body=None, headers=None):
    raw = b"" if body is None else json.dumps(body).encode("utf-8")
    return urllib.error.HTTPError(
        ENDPOINT, code, f"HTTP {code}", headers or {}, io.BytesIO(raw))


def answers_payload(answers):
    return {"model": DEFAULT_MODEL, "answers": answers,
            "usage": {"input_tokens": 10, "output_tokens": 0}}


NOUL_ANSWER = {"type": "noul", "noul": 0.8}
CHOICE_ANSWER = {"type": "choice", "choice": "a",
                 "probabilities": {"a": 0.6, "b": 0.39},
                 "confidence": 0.6}
SCORE_ANSWER = {"type": "score", "score": 0.5,
                "legend": {"0": "Low", "1": "High"},
                "probabilities": {"0": 0.33, "1": 0.66},
                "confidence": 0.55}

ALL_ANSWERS = {"n": NOUL_ANSWER, "c": CHOICE_ANSWER, "s": SCORE_ANSWER}

QUESTIONS = {
    "n": Noul("Is it done?"),
    "c": Choice("Pick one", {"a": "First", "b": None}),
    "s": Score("How good?", ["Low", "High"]),
}


class NoCredentialMixin:
    def setUp(self):
        super().setUp()
        patcher = patch.dict(os.environ, {CREDENTIAL_ENV: "", OP_REF_ENV: ""})
        patcher.start()
        self.addCleanup(patcher.stop)


class RequestShapeTests(NoCredentialMixin, unittest.TestCase):
    def test_request_url_headers_and_body(self):
        captured = {}

        def fake_urlopen(request, timeout=None):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse(answers_payload(ALL_ANSWERS))

        provider = SubQProvider(api_key="k-123", timeout_s=12.0)
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            provider.ask({"text": "hello"}, QUESTIONS)

        request = captured["request"]
        self.assertEqual(request.full_url, ENDPOINT)
        self.assertEqual(captured["timeout"], 12.0)
        self.assertEqual(request.get_header("Authorization"), "Bearer k-123")
        self.assertEqual(request.get_header("Content-type"), "application/json")

        body = json.loads(request.data)
        self.assertEqual(body["model"], DEFAULT_MODEL)
        self.assertEqual(body["state"], {"text": "hello"})
        self.assertEqual(body["questions"],
                         {"n": {"type": "noul", "instructions": "Is it done?"},
                          "c": {"type": "choice", "instructions": "Pick one",
                                "criteria": {"a": "First", "b": None}},
                          "s": {"type": "score", "instructions": "How good?",
                                "criteria": ["Low", "High"]}})

    def test_empty_questions_make_no_request(self):
        provider = SubQProvider(api_key="k-123")
        with patch("urllib.request.urlopen") as urlopen:
            self.assertEqual(provider.ask("state", {}), {})
        urlopen.assert_not_called()

    def test_registered_under_subq(self):
        with patch.dict(os.environ, {CREDENTIAL_ENV: "k-123"}):
            provider = get_provider("subq")
        self.assertIsInstance(provider, SubQProvider)


class AnswerMappingTests(NoCredentialMixin, unittest.TestCase):
    def test_typed_answers_with_rounded_probabilities(self):
        provider = SubQProvider(api_key="k-123")
        with patch("urllib.request.urlopen",
                   return_value=FakeResponse(answers_payload(ALL_ANSWERS))):
            answers = provider.ask("state", QUESTIONS)

        self.assertIsInstance(answers["n"], NoulAnswer)
        self.assertAlmostEqual(answers["n"].noul, 0.8)
        self.assertFalse(hasattr(answers["n"], "confidence"))

        choice = answers["c"]
        self.assertEqual(choice.choice, "a")
        self.assertAlmostEqual(sum(choice.probabilities.values()), 1.0)
        self.assertAlmostEqual(choice.probabilities["a"], 0.6 / 0.99)

        score = answers["s"]
        self.assertAlmostEqual(sum(score.probabilities.values()), 1.0)
        self.assertEqual(set(score.legend), {"0", "1"})

    def test_missing_answer_is_named(self):
        provider = SubQProvider(api_key="k-123")
        partial = answers_payload({"n": NOUL_ANSWER})
        with patch("urllib.request.urlopen",
                   return_value=FakeResponse(partial)):
            with self.assertRaises(SubQUnavailable) as caught:
                provider.ask("state", QUESTIONS)
        self.assertIn("c", str(caught.exception))
        self.assertIn("s", str(caught.exception))


class RetryTests(NoCredentialMixin, unittest.TestCase):
    def test_529_then_200_is_retried(self):
        provider = SubQProvider(api_key="k-123")
        outcomes = [http_error(529, {"detail": {"message": "overloaded"}}),
                    FakeResponse(answers_payload({"n": NOUL_ANSWER}))]
        with patch("urllib.request.urlopen", side_effect=outcomes), \
                patch("decisions.subq.time.sleep") as sleep:
            answers = provider.ask("state", {"n": QUESTIONS["n"]})
        self.assertAlmostEqual(answers["n"].noul, 0.8)
        sleep.assert_called_once()

    def test_402_is_not_retried_and_mentions_credits(self):
        provider = SubQProvider(api_key="k-123")
        error = http_error(402, {"detail": {"message": "payment required"}})
        with patch("urllib.request.urlopen", side_effect=error) as urlopen, \
                patch("decisions.subq.time.sleep") as sleep:
            with self.assertRaises(SubQUnavailable) as caught:
                provider.ask("state", {"n": QUESTIONS["n"]})
        message = str(caught.exception)
        self.assertIn("402", message)
        self.assertIn("payment required", message)
        self.assertIn("credits", message)
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

    def test_400_is_not_retried(self):
        provider = SubQProvider(api_key="k-123")
        error = http_error(400, {"detail": {"message": "input too large"}})
        with patch("urllib.request.urlopen", side_effect=error) as urlopen:
            with self.assertRaises(SubQUnavailable) as caught:
                provider.ask("state", {"n": QUESTIONS["n"]})
        self.assertIn("400", str(caught.exception))
        self.assertIn("input too large", str(caught.exception))
        self.assertEqual(urlopen.call_count, 1)

    def test_non_json_error_body_is_tolerated(self):
        provider = SubQProvider(api_key="k-123")
        error = urllib.error.HTTPError(
            ENDPOINT, 401, "Unauthorized", {}, io.BytesIO(b"not json"))
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(SubQUnavailable) as caught:
                provider.ask("state", {"n": QUESTIONS["n"]})
        self.assertIn("401", str(caught.exception))
        self.assertIn("not json", str(caught.exception))


class CredentialTests(NoCredentialMixin, unittest.TestCase):
    def test_no_credential_names_both_env_vars(self):
        provider = SubQProvider()
        with self.assertRaises(SubQUnavailable) as caught:
            provider.ask("state", {"n": QUESTIONS["n"]})
        message = str(caught.exception)
        self.assertIn(CREDENTIAL_ENV, message)
        self.assertIn(OP_REF_ENV, message)

    def _stub_op(self, directory):
        log = Path(directory) / "op.log"
        script = Path(directory) / "op"
        script.write_text(
            "#!/bin/sh\n"
            f'echo "$@" >> "{log}"\n'
            'echo "op-secret"\n')
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        return log

    def test_op_ref_is_read_once_across_two_asks(self):
        provider = SubQProvider()
        response = FakeResponse(answers_payload({"n": NOUL_ANSWER}))
        with tempfile.TemporaryDirectory() as directory:
            log = self._stub_op(directory)
            env = {CREDENTIAL_ENV: "", OP_REF_ENV: "op://vault/item/field",
                   "PATH": directory + os.pathsep + os.environ.get("PATH", "")}
            with patch.dict(os.environ, env), \
                    patch("urllib.request.urlopen", return_value=response) as urlopen:
                provider.ask("state", {"n": QUESTIONS["n"]})
                provider.ask("state", {"n": QUESTIONS["n"]})
            lines = log.read_text().splitlines() if log.exists() else []
        self.assertEqual(lines, ["read op://vault/item/field"])
        self.assertEqual(urlopen.call_args_list[0].args[0].get_header(
            "Authorization"), "Bearer op-secret")

    def test_env_key_wins_over_op(self):
        provider = SubQProvider()
        response = FakeResponse(answers_payload({"n": NOUL_ANSWER}))
        with tempfile.TemporaryDirectory() as directory:
            log = self._stub_op(directory)
            env = {CREDENTIAL_ENV: "env-secret",
                   OP_REF_ENV: "op://vault/item/field",
                   "PATH": directory + os.pathsep + os.environ.get("PATH", "")}
            with patch.dict(os.environ, env), \
                    patch("urllib.request.urlopen", return_value=response) as urlopen:
                provider.ask("state", {"n": QUESTIONS["n"]})
            self.assertFalse(log.exists())
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer env-secret")

    def test_missing_op_cli_is_unavailable(self):
        provider = SubQProvider()
        env = {CREDENTIAL_ENV: "", OP_REF_ENV: "op://vault/item/field",
               "PATH": ""}
        with patch.dict(os.environ, env), \
                patch("urllib.request.urlopen") as urlopen:
            with self.assertRaises(SubQUnavailable) as caught:
                provider.ask("state", {"n": QUESTIONS["n"]})
        self.assertIn(OP_REF_ENV, str(caught.exception))
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
