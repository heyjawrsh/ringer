<!-- Research produced by the jev-integration run, 2026-09-25. Sources were
     local snapshots of docs.typesafe.ai staged on that date; every quoted
     passage was verified verbatim against them by an automated check. -->

# Research Report

## Summary

- The endpoint accepts authenticated JSON containing state, model, and typed questions.
- Noul has no separate confidence; Choice and Score have distributions and confidence. Score also returns a legend.
- Retry 429/529 with backoff; correct authentication or validation failures first.

## Answer

**HTTP request.** Send `POST https://api.typesafe.ai/v1/systemone` with `Authorization: Bearer <API_KEY>` and `Content-Type: application/json`. The JSON body requires `state` (string, object, or array), `model` (string selecting the model, e.g. `jev-latest`), and `questions` (object mapping caller-chosen string IDs to question objects).

A question ID is its key in `questions`, not a field inside the question. The answer appears at `answers[id]`. IDs are not sent to the model; instructions must contain the complete question. Questions share one state, are evaluated independently, and may mix types.

**Question fields.** Each question requires `type` and `instructions`. Instructions may be a string, object, or array. Below, `Description` means that same union.

| Type | Criteria shape and meaning |
| --- | --- |
| `"noul"` | Optional `criteria` object with `"true"` and `"false"` descriptions, each a `Description`, defining yes and no. Instructions ask a yes/no question or state a proposition. |
| `"choice"` | Required `criteria` object mapping option-name strings to `Description` or `null`. Descriptions define alternatives; `null` means no extra explanation. Maximum 255 options. Instructions ask which option fits. |
| `"score"` | Required `criteria` array of `Description` values, ordered low to high. At least two levels are recommended; the API accepts up to 10. Instructions identify the dimension being rated. |

Criteria are asymmetric: optional yes/no definitions for Noul, required named alternatives for Choice, required positional levels for Score. Only Choice explicitly permits `null` descriptions. Choice option names reach the model, unlike question IDs. Score array positions establish zero-based level numbers.

**Response envelope.** Required top-level fields are `model` (string identifying the versioned model that answered), `answers` (object keyed by original question IDs), and `usage` (object documenting integer `input_tokens` and `output_tokens`). A requested alias can differ from the returned model string.

**Complete answer fields.** Each field below is required in the HTTP reference. The answer's `type` matches its question.

| Variant | All fields and meanings |
| --- | --- |
| Noul | `type: "noul"`; `noul: number` in [0,1], the probability of yes. No separate `confidence`, `probabilities`, or `legend`. |
| Choice | `type: "choice"`; `choice: string`, the highest-probability option key; `probabilities: object<string, number>`, every option mapped to its probability; `confidence: number` in [0,1], derived from the distribution. No `legend`. |
| Score | `type: "score"`; `score: number`, the probability-weighted level position; `legend: object`, stringified level indices mapped to descriptions; `probabilities: object<string, number>`, those indices mapped to probabilities; `confidence: number` in [0,1], derived from the distribution. See Uncertain for legend value typing. |

Choice/Score probabilities sum to 1. With N Score levels, `score = sum(i * probabilities[String(i)])`, spanning 0 through N−1, including fractions. It is not an integer winner or necessarily in [0,1]. Both Score maps use HTTP string keys such as `"0"`; Python SDK integer keys are a conversion. Noul near zero means strong no; near 0.5 means uncertainty. Confidence summarizes concentration, not simply the winning option's probability.

**Errors.** Error responses have HTTP status codes and descriptive JSON bodies.

| Status | Meaning | Handling |
| --- | --- | --- |
| 401 Unauthorized | Missing/invalid API key | Correct credentials/header. |
| 422 Unprocessable Entity | Body validation failed; body identifies offending field | Correct the request. |
| 429 Too Many Requests | Rate limit exceeded | Retry with exponential backoff. |
| 529 Overloaded | Temporary TypeSafe overload | Retry with exponential backoff. |

Default SDK policies retry 429/529 automatically and honor a supplied `retry-after` header. Direct HTTP callers should preserve that behavior.

## Evidence

Claim: Use POST with bearer authentication and JSON.

Source: [api.md](/Users/jawrsh/.ringer/jobs/jev-integration/sources/api.md)

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> POST https://api.typesafe.ai/v1/systemone
> Authorization: Bearer <API_KEY>
> Content-Type: application/json

Claim: The three body fields are required; caller IDs identify answers but do not influence inference.

Source: [api.md](/Users/jawrsh/.ringer/jobs/jev-integration/sources/api.md)

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> <ParamField body="state" type="string | object | array" required>

> <ParamField body="model" type="string" required>

> <ParamField body="questions" type="map<string, Question>" required>

> A key you choose. The matching [Answer](#answer-types) is returned under this same id. The key is not sent to the underlying model and is not used in inference.

Claim: Instructions support structured values; criteria differ by question type.

Source: [api.md](/Users/jawrsh/.ringer/jobs/jev-integration/sources/api.md)

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> The `instructions` property can be a string, an object, or an array.

> <ParamField body="criteria" type="object">
>   Optional descriptions of what a yes and a no mean.
> 
>   <Expandable title="properties">
>     <ParamField body="true" type="string | object | array">
>       What a yes (value near 1) means.
>     </ParamField>
> 
>     <ParamField body="false" type="string | object | array">
>       What a no (value near 0) means.
>     </ParamField>
>   </Expandable>
> </ParamField>

> <ParamField body="criteria" type="map<string, string | object | array | null>" required>
>   A map of option to rubric description; use null when an option needs no extra detail. You can have a maximum of 255 options per Choice.

> <ParamField body="criteria" type="array<string | object | array>" required>
>   An ordered array of level descriptions. A Score should have at least two levels; the API accepts up to 10.
> </ParamField>

Claim: Questions independently share one state.

Source: [primitives.md](/Users/jawrsh/.ringer/jobs/jev-integration/sources/primitives.md)

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> You can ask one question or send several together. Every question in a request sees the same state, is evaluated independently, and returns a typed answer under the ID you chose.

Claim: Choice option names reach the model, unlike question IDs.

Source: [primitives_choice.md](/Users/jawrsh/.ringer/jobs/jev-integration/sources/primitives_choice.md)

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> The model never sees the question id. The option names and their descriptions are both sent to the model, so write descriptions that separate the options from each other.

Claim: The response includes model, answers, and usage; every answer has a matching type.

Source: [api.md](/Users/jawrsh/.ringer/jobs/jev-integration/sources/api.md)

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> <ResponseField name="model" type="string" required>

> <ResponseField name="answers" type="map<string, Answer>" required>

> <ResponseField name="usage" type="object" required>
>   Token usage for the request.
> 
>   <Expandable title="properties">
>     <ResponseField name="input_tokens" type="integer" />
> 
>     <ResponseField name="output_tokens" type="integer" />
>   </Expandable>
> </ResponseField>

> Every answer carries a `type` matching its question. Choice and Score answers also carry a `confidence` between 0 to 1, derived from the answer's probability distribution.

Claim: Noul gives the probability of yes without separate confidence.

Source: [primitives_noul.md](/Users/jawrsh/.ringer/jobs/jev-integration/sources/primitives_noul.md)

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> A Noul answer is a single number representing the probability that the answer is yes where 0 means no and 1 means yes.

> A value near 0.5 means the model gives yes and no similar probability.

> There is no separate `confidence` value for a Noul, unlike a [Choice](/primitives/choice) or a [Score](/primitives/score).

Claim: Choice returns the winner, a full distribution, and confidence.

Source: [primitives_choice.md](/Users/jawrsh/.ringer/jobs/jev-integration/sources/primitives_choice.md)

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> Besides `type`, each Choice answer has three values:
> 
> * `choice`: The option with the highest probability.
> * `probabilities`: The full probability distribution across every option. The sum of all values is 1.
> * [`confidence`](/confidence): A number from 0 to 1 computed from how `probabilities` is spread. A flat shape, with probability spread across several options, means low confidence. A single peak on one option means high confidence.

Claim: Score returns five fields, a weighted mean, and string HTTP keys.

Source: [primitives_score.md](/Users/jawrsh/.ringer/jobs/jev-integration/sources/primitives_score.md)

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> Each Score answer has five values:
> 
> * `type`: The type of TypeSafe question.
> * `probabilities`: The probability of each level, keyed by level number as a string. The sum of all values is 1.
> * `score`: The position on the level number line, from 0 to the top level number, which is 2 here. It's each level number multiplied by its probability, added up: 0 x 0.0 + 1 x 0.57 + 2 x 0.43 = 1.43.
> * `legend`: Each level number mapped back to its description.
> * [`confidence`](/confidence): A number from 0 to 1 computed from how `probabilities` is spread. A single peak on one level means high confidence. Probability spread over several levels means low confidence.

> The SDK keys `probabilities` and `legend` by integer level rather than by string.

Claim: Errors have JSON bodies; load failures warrant delayed retries.

Source: [api.md](/Users/jawrsh/.ringer/jobs/jev-integration/sources/api.md)

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> Errors use standard HTTP status codes with a JSON body describing what went wrong.

> | `401 Unauthorized`         | Missing or invalid API key. Check the `Authorization` header.                                                                            |
> | `422 Unprocessable Entity` | The request body failed validation — for example a missing required field or a malformed question. The body details the offending field. |
> | `429 Too Many Requests`    | You have exceeded your rate limit. Back off and retry after a short delay.                                                               |
> | `529 Overloaded`           | TypeSafe is temporarily overloaded. Retry after a short delay.                                                                           |

> When you receive a `429 Too Many Requests` or `529 Overloaded` response, retry the request with exponential backoff instead of retrying immediately.

Claim: Responses identify the resolved version; SDKs honor retry-after.

Source: [models.md](/Users/jawrsh/.ringer/jobs/jev-integration/sources/models.md)

Accessed: 2026-09-25 (staged snapshot).

Quoted Evidence:

> The response's `model` field reports the versioned ID that answered, so you can log which model produced each result.

> Our [client SDKs](/sdk) retry with backoff by default and honor the `retry-after` header when the response carries one.

## Uncertain

- **Legend mismatch:** `api.md` declares `map<string, string>`, but `primitives_score.md` demonstrates object-valued descriptions returned in `legend`. String-only decoding cannot represent that example. Exact serialization for every structured description, especially arrays, is not established consistently; preserve JSON values until confirmed.
- Exact error-body schema, Choice tie-breaking, and production confidence formula are unspecified. The confidence page's interactive formula is an approximation.
- Enforcement of Score's suggested two-level minimum, minimum Choice cardinality, and whether both Noul criteria properties must be supplied together are unclear.

## Assumptions

- The requested `api_.md` is absent; staged `api.md` is treated as the intended reference. Source links identify the supplied 2026-09-25 snapshots. No live API calls or web search were used.
- Treating unchanged 401/422 failures as nonretryable is an inference from documented causes. Retry counts, timeouts, and backoff parameters remain caller policy.
