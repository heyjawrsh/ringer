"""Portable regression tests for the policy in docs/decisions/jev-measured.md.

All judgments and replay labels are synthetic inline fixtures, not vendor calls
or cached measurements. These bind policy behavior, not model accuracy.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from decisions import provider as provider_module
from decisions.answer_quality import grade
from decisions.provider import (
    Choice,
    ChoiceAnswer,
    DecisionProvider,
    Noul,
    NoulAnswer,
    Score,
    ScoreAnswer,
    get_provider,
    register_provider,
)
from decisions.replay import score_provider
from decisions.retry_policy import RetryDecision, decide


class InlineProvider(DecisionProvider):
    """A provider defined outside the dispatch module, with supplied answers."""

    name = "inline-test-provider"

    def __init__(self, answers=None):
        self.answers = {} if answers is None else answers

    def ask(self, state, questions):
        return dict(self.answers)


class RaisingProvider(DecisionProvider):
    def __init__(self, exception_type=RuntimeError):
        self.exception_type = exception_type

    def ask(self, state, questions):
        raise self.exception_type("Synthetic provider outage")


def prognosis(choice, confidence):
    probabilities = {
        option: 0.8 if option == choice else 0.1
        for option in ("retry_likely_fails", "retry_likely_passes", "cannot_tell")
    }
    return InlineProvider({"retry": ChoiceAnswer(choice, probabilities, confidence)})


def quality_provider(**overrides):
    probabilities = {
        "addresses_question": 0.90,
        "complete": 0.90,
        "committal": 0.90,
        "unsupported_claims": 0.084,
    }
    probabilities.update(overrides)
    answers = {key: NoulAnswer(value) for key, value in probabilities.items()}
    answers["usefulness"] = ScoreAnswer(
        score=3.5,
        legend={"0": "Unusable", "1": "Weak", "2": "Partial", "3": "Useful", "4": "Complete"},
        probabilities={"0": 0.0, "1": 0.0, "2": 0.0, "3": 0.5, "4": 0.5},
        confidence=0.8,
    )
    return InlineProvider(answers)


class QuestionContractTests(unittest.TestCase):
    def test_noul_answer_has_no_confidence(self):
        answer = NoulAnswer(0.8)
        self.assertFalse(
            hasattr(answer, "confidence"),
            "A Noul's probability must not masquerade as separate confidence.",
        )
        self.assertNotIn(
            "confidence", asdict(answer),
            "Serialized Noul answers must preserve the vendor's no-confidence contract.",
        )

    def test_choice_and_score_answers_carry_confidence(self):
        answers = (
            ChoiceAnswer("yes", {"yes": 0.8, "no": 0.2}, 0.6),
            ScoreAnswer(0.8, {"0": "Low", "1": "High"}, {"0": 0.2, "1": 0.8}, 0.6),
        )
        for answer in answers:
            with self.subTest(answer_type=type(answer).__name__):
                self.assertEqual(
                    asdict(answer).get("confidence"), 0.6,
                    "Choice and Score must retain confidence for caller-owned policy gates.",
                )
                self.assertEqual(
                    answer.confidence, 0.6,
                    "Callers must be able to read confidence directly from Choice and Score.",
                )

    def test_noul_criteria_are_optional(self):
        question = Noul("Is the answer complete?")
        self.assertIsNone(
            question.criteria,
            "Omitting Noul criteria must still construct without inventing a rubric.",
        )

    def test_noul_accepts_only_true_and_false_criteria_keys(self):
        for criteria in (
            {}, {"true": "Finished"}, {"false": "Cut off"},
            {"true": "Finished", "false": "Cut off"},
        ):
            with self.subTest(criteria=criteria):
                self.assertEqual(
                    Noul("Is the answer complete?", criteria).criteria, criteria,
                    "Valid true/false Noul criteria must survive construction intact.",
                )
        for key in ("yes", "no", "True", "unexpected"):
            with self.subTest(invalid_key=key):
                with self.assertRaises(
                    ValueError,
                    msg="Accepting any key besides true/false breaks the Noul API contract.",
                ):
                    Noul("Is the answer complete?", {"true": "Finished", key: "Invalid"})


class ProviderTests(unittest.TestCase):
    def test_provider_defined_here_can_register_and_resolve_by_name(self):
        # Isolate registration so discovery order cannot affect other tests.
        with patch.dict(provider_module._PROVIDERS):
            register_provider("test-file-only", InlineProvider)
            resolved = get_provider("test-file-only")
            self.assertIsInstance(
                resolved, InlineProvider,
                "New providers must plug in by registration without editing dispatch code.",
            )
            self.assertEqual(
                resolved.ask({}, {}), {},
                "Named resolution must return a usable provider instance, not its factory.",
            )

    def test_unknown_provider_raises(self):
        with patch.dict(provider_module._PROVIDERS, {}, clear=True):
            with self.assertRaises(
                KeyError,
                msg="An unregistered name must fail visibly instead of selecting a silent fallback.",
            ):
                get_provider("definitely-unregistered")

    def test_heuristic_answers_all_three_types_without_networking(self):
        questions = {
            "rescue": Noul("Will retrying rescue this task?"),
            "action": Choice("Should we retry?", {"retry": "Try again", "skip": "Stop"}),
            "topic": Choice("Which topic appears?", {"code": "Code", "design": "Design"}),
            "quality": Score("How useful is this output?", ["Unusable", "Useful", "Complete"]),
        }
        expected_types = {
            "rescue": NoulAnswer, "action": ChoiceAnswer,
            "topic": ChoiceAnswer, "quality": ScoreAnswer,
        }
        targets = (
            "socket.socket", "socket.create_connection", "socket.getaddrinfo",
            "urllib.request.urlopen", "http.client.HTTPConnection.connect",
        )
        with ExitStack() as stack:
            network_guards = [
                stack.enter_context(patch(target, side_effect=AssertionError("Network is disabled")))
                for target in targets
            ]
            provider = get_provider("heuristic")
            for output in ("Authentication required", "Connection timed out", "SyntaxError", "Unknown failure"):
                with self.subTest(check_output=output):
                    answers = provider.ask({"first_check_output": output}, questions)
                    self.assertEqual(
                        set(answers), set(questions),
                        "The offline fallback must answer every supplied question without a vendor.",
                    )
                    for key, answer_type in expected_types.items():
                        self.assertIsInstance(
                            answers[key], answer_type,
                            f"The offline fallback must return the matching typed answer for {key}.",
                        )
            for target, guard in zip(targets, network_guards):
                self.assertEqual(
                    guard.call_count, 0,
                    f"The heuristic fallback must work offline; it attempted networking through {target}.",
                )


class RetryPolicyTests(unittest.TestCase):
    state = {"first_check_output": "Synthetic check failed", "first_returncode": 1}

    def test_confident_failure_skips_including_at_the_gate(self):
        for confidence in (0.5, 0.9):
            with self.subTest(confidence=confidence):
                decision = decide(self.state, prognosis("retry_likely_fails", confidence))
                self.assertTrue(
                    decision.skip,
                    "A predicted failure at or above the measured 0.5 gate must save the retry attempt.",
                )

    def test_same_failure_below_gate_preserves_retry(self):
        decision = decide(self.state, prognosis("retry_likely_fails", 0.49))
        self.assertFalse(
            decision.skip,
            "Removing the confidence gate changes 23 saved/4 lost into 70 saved/31 lost rescues.",
        )

    def test_configured_minimum_confidence_controls_skipping(self):
        provider = prognosis("retry_likely_fails", 0.6)
        self.assertTrue(
            decide(self.state, provider, min_confidence=0.6).skip,
            "Confidence equal to the configured minimum must satisfy the inclusive gate.",
        )
        self.assertFalse(
            decide(self.state, provider, min_confidence=0.7).skip,
            "Ignoring the configured minimum cancels retries below the caller's confidence gate.",
        )

    def test_confident_cannot_tell_preserves_retry(self):
        decision = decide(self.state, prognosis("cannot_tell", 1.0))
        self.assertFalse(
            decision.skip,
            "Skipping cannot_tell inverts the vendor's abstention based on only 44 measured cases.",
        )

    def test_confident_pass_preserves_retry(self):
        decision = decide(self.state, prognosis("retry_likely_passes", 1.0))
        self.assertFalse(
            decision.skip,
            "A confident prediction of rescue must never cancel the attempt that can rescue the task.",
        )

    def test_unavailable_or_wrong_type_provider_retries_with_readable_reason(self):
        cases = (
            ("missing", None, r"(?i)no.*provider"),
            ("raises", RaisingProvider(), r"(?i)provider.*unavailable"),
            ("process exception", RaisingProvider(SystemExit), r"(?i)provider.*unavailable"),
            ("wrong type", InlineProvider({"retry": NoulAnswer(0.1)}), r"(?i)not.*ChoiceAnswer"),
        )
        for label, provider, reason_pattern in cases:
            with self.subTest(failure=label):
                decision = decide(self.state, provider)
                self.assertIsInstance(
                    decision, RetryDecision,
                    "Provider failure must produce an auditable retry decision instead of escaping.",
                )
                self.assertFalse(
                    decision.skip,
                    "Missing, failing, or mistyped judgments must preserve the worker's retry.",
                )
                self.assertRegex(
                    decision.reason, reason_pattern,
                    "Fallback retries need a readable reason explaining why judgment was unavailable.",
                )


class ReplayProvider(DecisionProvider):
    def ask(self, state, questions):
        probability = 0.1 if state["first_check_output"] == "blocked" else 0.8
        return {key: NoulAnswer(probability) for key in questions}


class ReplayTests(unittest.TestCase):
    def test_baseline_and_both_costs_come_from_each_supplied_corpus(self):
        # Identical evidence, different outcomes: one rescue versus three.
        corpora = (
            [("blocked", False), ("blocked", True), ("repairable", False), ("repairable", False)],
            [("blocked", False), ("blocked", True), ("repairable", True), ("repairable", True)],
        )
        reports = []
        with tempfile.TemporaryDirectory() as directory:
            for index, corpus in enumerate(corpora):
                path = Path(directory) / f"synthetic-{index}.json"
                cases = [
                    {"first_check_output": output, "first_returncode": 1,
                     "first_verdict": "FAIL", "task_type": "code",
                     "worker_engine": "inline", "spec": "Repair the synthetic check",
                     "retry_rescued": rescued}
                    for output, rescued in corpus
                ]
                path.write_text(json.dumps({"cases": cases}), encoding="utf-8")
                reports.append(score_provider(ReplayProvider(), path))

        self.assertEqual(
            [report["always_retry_baseline"] for report in reports], [0.25, 0.75],
            "Always-retry baseline must be the rescue fraction of the supplied corpus, not a stored benchmark.",
        )
        self.assertNotEqual(
            reports[0]["always_retry_baseline"], reports[1]["always_retry_baseline"],
            "A constant baseline conceals changes in the corpus and invalidates provider comparisons.",
        )
        for report in reports:
            for metric in ("accuracy", "wasted_avoided", "rescues_lost"):
                self.assertIn(
                    metric, report,
                    "Replay must expose saved attempts and forfeited rescues, not accuracy alone.",
                )
            self.assertEqual(
                report["wasted_avoided"], 1,
                "A skipped wasted attempt must be counted on the benefit side of the policy cost.",
            )
            self.assertEqual(
                report["rescues_lost"], 1,
                "A skipped successful rescue must be counted on the harm side, even if accuracy looks good.",
            )


class AnswerQualityTests(unittest.TestCase):
    state = {
        "QUESTION": "What is the project called?",
        "SOURCE": "The project is called Cedar.",
        "ANSWER": "The project is called Cedar.",
    }

    def test_clean_answer_is_graded_without_flags(self):
        result = grade(self.state, quality_provider())
        self.assertTrue(
            result.graded,
            "A clean, fully judged answer must be distinguishable from an unavailable grade.",
        )
        self.assertEqual(
            result.flags, (),
            "A complete, supported, direct answer must not invite spurious review.",
        )

    def test_unsupported_claims_flag_absence_from_source_not_falsehood(self):
        state = dict(self.state, ANSWER="The project is called Cedar and supports 100 users.")
        result = grade(state, quality_provider(unsupported_claims=0.946))
        self.assertTrue(result.graded, "A high unsupported-claims probability must still yield a grade.")
        self.assertEqual(
            len(result.flags), 1,
            "High unsupported claims must independently invite review even when other judgments are clean.",
        )
        text = " ".join(result.flags)
        self.assertRegex(
            text, r"(?i)(unsupported|not supported|absent|missing).*source",
            "Unsupported-claims advice must explain that evidence is absent from the supplied source.",
        )
        self.assertNotRegex(
            text, r"(?i)\b(fabricat\w*|invent\w*|wrong)\b",
            "Absence from a source does not establish falsehood; calling claims fabricated, invented, or wrong overstates the grade.",
        )

    def test_truncation_and_evasion_each_raise_a_flag(self):
        cases = (
            ("truncated", "The project is called", {"complete": 0.22}, r"(?i)truncat|cut off"),
            ("evasive", "It might be called something, but who can say?", {"committal": 0.45}, r"(?i)hedg|committ|evas"),
        )
        for label, answer, overrides, pattern in cases:
            with self.subTest(defect=label):
                result = grade(dict(self.state, ANSWER=answer), quality_provider(**overrides))
                self.assertTrue(result.graded, "Truncation and evasion are graded concerns, not provider outages.")
                self.assertEqual(
                    len(result.flags), 1,
                    f"A {label} answer must independently invite review despite otherwise clean judgments.",
                )
                self.assertRegex(
                    " ".join(result.flags), pattern,
                    f"The {label} flag must tell the reader which answer problem needs attention.",
                )

    def test_missing_or_raising_provider_reports_no_opinion(self):
        for provider in (None, RaisingProvider(), RaisingProvider(SystemExit)):
            with self.subTest(provider=type(provider).__name__):
                result = grade(self.state, provider)
                self.assertFalse(
                    result.graded,
                    "No provider opinion must not masquerade as a completed clean grade.",
                )
                self.assertEqual(
                    result.flags, (),
                    "A failed or absent provider has no evidence on which to flag the answer.",
                )
                self.assertRegex(
                    result.reason, r"(?i)not graded.*provider",
                    "An ungraded result must explain the missing opinion so callers can seek manual review.",
                )


if __name__ == "__main__":
    unittest.main()
