<!-- Research produced by the jev-integration run, 2026-09-25. Sources were
     local snapshots of docs.typesafe.ai staged on that date; every quoted
     passage was verified verbatim against them by an automated check. -->

# Research Report

## Summary
- Jev exposes ONE endpoint that evaluates a state against typed questions.
- Three question types: Noul, Choice, Score. Answers return under the caller's own ids.
- Choice and Score answers carry a confidence; Noul answers do not carry a confidence field.

## Answer
The evaluation endpoint is `POST https://api.typesafe.ai/v1/systemone`, authenticated
with an `Authorization: Bearer <API_KEY>` header and `Content-Type: application/json`.

The request body has three required fields: `state` (string, object or array),
`model` (use `jev-latest`), and `questions`, a map whose keys the caller chooses.
Answers come back under those same ids, so the key you choose is the key you read.
The key is not sent to the underlying model.

Noul is a yes/no question and returns `noul`, a number from 0 (no) to 1 (yes).
Choice picks one option from `criteria` and returns `choice`, a `probabilities` map
over every option, and a `confidence`. Score rates against an ordered `criteria`
array and returns `score`, a `legend` mapping each level number to its description,
`probabilities` keyed by level, and a `confidence`.

Noul answers do not carry a confidence. Only Choice and Score do. For a Noul the
degree of certainty has to be read from how far `noul` sits from 0.5.

Errors use standard HTTP status codes: 401 for a bad key, 422 for a malformed
request, 429 when rate limited and 529 when overloaded. Both 429 and 529 should be
retried with exponential backoff rather than immediately.

## Evidence
- Claim: the endpoint and auth header.
  Source: sources/api_.md
  Accessed: 2026-09-25
  Quoted Evidence: "POST https://api.typesafe.ai/v1/systemone"

- Claim: answers are keyed by the caller's ids.
  Source: sources/api_.md
  Accessed: 2026-09-25
  Quoted Evidence: "One answer per question, returned under the same ids you provided."

- Claim: Noul answers carry no confidence.
  Source: sources/confidence.md
  Accessed: 2026-09-25
  Quoted Evidence: "The answer's `confidence` property collapses that shape into a single number from 0 to 1, so you can threshold on it without doing the math yourself. (Noul answers don't carry one.)"

- Claim: retryable error codes.
  Source: sources/api_.md
  Accessed: 2026-09-25
  Quoted Evidence: "You have exceeded your rate limit. Back off and retry after a short delay."

## Uncertain
- Whether `usage.output_tokens` is billed; the pricing page was not staged.
- Whether the 255-option Choice ceiling is enforced per request or per account.

## Assumptions
- `jev-latest` resolves to the flagship model, as the API reference states.
