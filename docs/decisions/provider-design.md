<!-- Research produced by the jev-integration run, 2026-09-25. Sources were
     local snapshots of docs.typesafe.ai staged on that date; every quoted
     passage was verified verbatim against them by an automated check. -->

# Research Report

## Summary

- Add an optional judgment provider alongside artifact-producing workers; executable checks retain authority.
- Low confidence, missing models, and provider failures must preserve Ringer's existing retry behavior.
- Separate provider-call retries from task retries; keep thresholds and policy independent of vendors.

## Answer

### Role and replaceability

Jev provides focused semantic judgments over supplied state. It does not generate text, code, reasoning explanations, or conversation; it does not call tools or edit files. It therefore must not be registered as an ordinary artifact-producing worker. Existing workers should produce artifacts; Ringer should execute checks; a judgment cannot convert a failed check into success.

Proposed seam: assess filtered failure evidence using explicit alternatives such as retry-may-help, blocked, and insufficient-evidence. Supply relevant diagnostics, task requirements, and available remedial actions; avoid asking for an open-ended repair plan. Return one of assessment, abstention, or provider failure. Preserve answer semantics, probabilities, optional confidence, model/question versions, state identity, request ID, and usage. Normalize errors into cause, retryability, and optional server-requested delay. Ringer owns policy, execution, counters, and deadlines.

The SDK returns answers keyed by question, with model/usage metadata. Choice selects a label and exposes probabilities/confidence; Score is a probability-weighted rubric value. Noul is the probability of yes, has no separate confidence, and is uncertain near 0.5. Do not coerce these into interchangeable certainty scores or invent missing confidence. A vendor without compatible uncertainty semantics must abstain from automated suppression. Validate required answers: the SDK can skip unknown answer kinds. A replacement vendor needs an adapter and fresh calibration, not a redesigned task lifecycle. Merely changing the SDK's base URL requires a TypeSafe-compatible API.

### Two separate retry decisions

The SDK's default RetryPolicy permits **two retries after the initial attempt**, hence at most three attempts. It retries **HTTP 408, 429, every 500–599 status, connection errors, and timeouts**. Other statuses, including 400/401/403/404/422, are outside that default set. Additional exception types and a predicate can add retry triggers.

Backoff starts at **0.5 seconds**, doubles per attempt, and caps at **5 seconds**, with jitter randomly subtracting up to **25%** of the delay. Retry-After and retry-after-ms headers are honored by default. The **30-second total retry budget** includes the initial attempt and delays; a retry whose delay reaches or exceeds the remaining budget is skipped and the last error is raised. Zero max_retries disables retries; a None budget removes that limit. Policy is configurable per client or call.

Exceptions distinguish HTTP failures with status/body/headers/request metadata, connection failures without a response, timeouts, and malformed successful responses. Rate-limit errors expose retry_after_ms. Invalid API keys can fail during client construction before any request.

Design inference: another attempt is worthwhile when a failure is plausibly transient and the attempt fits a finite budget. Keep this deterministic transport policy inside the adapter, with one retry owner to avoid multiplying attempts. A nonretryable provider authentication/validation failure is **not** a recommendation to stop retrying the Ringer task. After provider exhaustion or failure, use the existing task retry branch.

### Confidence as control flow

Confidence summarizes probability-distribution concentration; calibration describes groups of predictions, not a guarantee that an individual answer is correct. The application owns the action. Keep questions and thresholds centrally reviewable.

The routing example allows a recoverable balance display at **0.6**, but requires **above 0.85** for automatically approving a transfer; intermediate certainty requires confirmation. These are illustrative, not universal thresholds. For Ringer, displaying an advisory label can tolerate a lower threshold than suppressing a potentially successful retry. Suppression should require a separately validated, stricter threshold; critical tasks should retain deterministic or human authority over abandonment. Tune by action, question, primitive, model version, and observed cost of false suppression.

**When confidence is low, abstain and invoke exactly Ringer's existing retry behavior, preserving its counters, timing, and limits.** Do not stop, silently succeed, await mandatory human review, or repeatedly query until confidence rises. Apply the same fallback to missing configuration, provider unavailability, invalid/missing answers, and stale assessments. Medium confidence may produce a review flag without blocking that retry. Only an enabled, validated suppression policy may override the default. Suppression leaves the task failed or blocked, preserves evidence, and permits explicit resumption; it never implies completion.

Begin with shadow assessments while all existing retries run. Measure false suppression against actual retry outcomes, review confidently wrong cases, and retain a disable switch. Check state freshness before applying a result; keep all executable acceptance checks authoritative.

### Weaknesses and threshold implications

The jev-1.13 jaggedness page names **literal reading; Math and Numbers; date/time comparison; indirection; irrelevant large state; adversarial content; contradictory instructions/criteria; structural invariants; and generation**. Counting, numeric representations, and exact interpolation from Score are unreliable. Date ordering/arithmetic belong in code. Double negatives and multiple reasoning hops reduce reliability; unrelated context reduces accuracy. Injected instructions or persuasive framing in state can steer answers. Equivalent-looking Noul/Choice questions and separately asked negations need not agree mathematically.

Use direct, aligned criteria, filtered evidence, and deterministic arithmetic/invariants. Treat task logs as untrusted data. A high threshold cannot repair an unsuitable question or prove resistance to adversarial input. Evaluate these failure classes explicitly; never transfer a threshold unchanged between Noul and Choice. The guardrails cookbook's screening example is not proof of injection immunity.

## Evidence

All sources below are staged files in /Users/jawrsh/.ringer/jobs/jev-integration/sources/, fetched from docs.typesafe.ai.

Claim: Jev cannot perform the artifact worker's generative/tool role.

Source: introduction_coding-agents.md

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> It does not generate text, write code, or hold a conversation.

> Coding agents rely on an LLM that streams text, calls tools, and edits files based on natural-language instructions. Jev does none of that.

Claim: SDK retries are additional attempts with bounded exponential delays and jitter.

Source: sdk_python_api_retries.md

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> Maximum retries after the initial attempt; `0` disables retries.

> First backoff delay in seconds, doubled each attempt up to `backoff_max`; zero disables backoff.

> Fraction of each backoff delay randomly subtracted, between 0 and 1.

> Total retry budget in seconds per SDK call, including the initial attempt and delays; `None` disables the limit.

> Whether to honor `Retry-After` and `retry-after-ms` response headers.

> Whether to retry `TypeSafeAPIConnectionError`, raised when the request cannot reach or read from the server.

> Whether to retry `TypeSafeAPITimeoutError`, raised when the request exceeds its timeout.

> Stops before a retry whose delay would reach or exceed the budget, re-raising the last error.

Claim: Provider errors preserve diagnostics; HTTP success can still be invalid.

Source: sdk_python_api_exceptions.md

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> An unsuccessful HTTP response with its body and request metadata.

> A successful HTTP response whose body was missing or structurally invalid required data.

Claim: Noul uncertainty is not a separate confidence field.

Source: sdk_python_api_types_responses.md

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> Probability of a yes answer or a true statement, from 0 to 1. Values near 1 favor yes or true, values near 0 favor no or false, and values near 0.5 indicate uncertainty.

> Probability of each choice in criteria, keyed by choice name, from 0 to 1. Shows how likely the alternatives are; values sum to approximately 1.

> Expected score: the probability-weighted average of the rubric levels. May fall between integer levels.

Claim: Unknown answer types can leave required judgments absent.

Source: sdk_python_usage.md

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> The SDK logs a warning and skips unrecognized answer kinds.

Claim: Low confidence calls for abstention; stakes determine thresholds.

Source: confidence.md

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> **Low confidence:** Do not act. Route to a human, request clarification, or fall back to a different system. The model is telling you it does not have enough information or the question is not a good fit.

> A confidence threshold is not one number. Different actions within the same system should be gated at different levels depending on the consequences of getting it wrong.

> The answer's `confidence` property collapses that shape into a single number from 0 to 1, so you can threshold on it without doing the math yourself. (Noul answers don't carry one.)

Claim: The bank example uses different thresholds for different consequences.

Source: patterns_confidence-routing.md

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> Checking a balance at 0.6 is fine because the worst case is the user having to listen to the balance read-out. But approving a transfer requires very high confidence (>0.85), otherwise the system should ask the user to confirm.

Claim: Calibration is not individual correctness.

Source: concepts_system-one.md

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> Calibration is measured across groups of predictions; it does not guarantee that an individual answer is correct.

> System One models do not write replies, produce code, or generate explanations of their reasoning.

Claim: Action policy belongs to application code.

Source: cookbooks_llm_guardrails.md

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> TypeSafe supplies the assessment; your application owns the decision.

Claim: Adversarial state can influence judgments; primitive thresholds are not interchangeable.

Source: model-jaggedness_jev-1.13.md

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> State is data, and `jev-1.13` does not treat it as hostile by default.

> Content written to adversarially steer the model, whether that is an injected instruction, a deliberately misleading framing, or text that argues for its own classification, can move the answer.

> Don't carry a threshold tuned on a Noul over to a Choice, and don't hold the model to arithmetic identities between separate questions.

Claim: Reviewable question and threshold definitions are vendor guidance.

Source: agent-skill.md

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> Put the constants (questions and thresholds) in a single place so they're easy to review.

## Uncertain

Production suppression thresholds, Ringer-specific calibration/error rates, and replacement-vendor equivalence are unestablished. The supplied pages do not settle retry-header precedence or malformed-header behavior. The guardrails examples use jev-1.12; they do not establish jev-1.13 performance or adversarial safety. No runtime experiments or repository inspection were performed.

## Assumptions

Ringer currently always retries failed tasks, as supplied in the brief; preserve whatever limits already govern that behavior. Architecture recommendations above are proposals. Access was limited to the explicitly staged sources and the requested output within the otherwise restricted jobs directory.
