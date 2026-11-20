# SubQ Snap, measured on the same two corpora as Jev

Measured 2026-11-20 against `subq-snap-1.2`, through `decisions/subq.py`.
Same 343 retry cases, same 28 answer cases, same questions word for word, same
labels — so the only thing that differs between the two vendors' numbers is the
model. Every number below is printed by `measure/eval_snap.py`; none is
hand-computed.

## What was asked

**Corpus 1, retry decisions** — `/Users/jawrsh/.ringer/jobs/jev-integration/retry_corpus.json`,
343 cases where a check failed and a retry ran, 166 rescued (48.4%). The label
`retry_rescued` was never sent; each case carried only first-attempt evidence
(check output, return code, verdict, task type, engine, spec).

Snap answers a question differently depending on which other questions ride in
the same request, so each case went out as **two** requests:

| request | carries | matches |
|---|---|---|
| 1 | only `retry`, the Noul *will retrying this task once rescue its failed check?* | Jev's first pass |
| 2 | only `prognosis`, the Choice over `retry_likely_passes` / `retry_likely_fails` / `cannot_tell` and `recoverability`, the 0–4 Score | Jev's second pass |

The Noul was never sent alongside the other two. `input_tokens` is the sum over
both requests.

**Corpus 2, ask answers** — `answer_quality_corpus.json`, 28 cases: real
answers degraded six ways each, graded through `decisions.answer_quality.grade`
(four Nouls plus the usefulness Score, one request per case).

343 retry cases, 0 vendor errors, 420418 input tokens, $0.0168 at $0.04/M
(output is free). 28/28 answer cases graded.

## Side by side with Jev

| measure | Jev | Snap | Snap 95% CI |
|---|---|---|---|
| Noul AUC — "will retrying rescue this?" | 0.609 | **0.685** | [0.628, 0.740] |
| Choice, P(passes) | 0.708 | 0.692 | [0.633, 0.747] |
| Choice, P(passes) − P(fails) | 0.715 | 0.695 | [0.637, 0.750] |
| Score, 0–4 recoverability | 0.679 | 0.680 | [0.622, 0.738] |
| Usefulness AUC, real vs degraded | 0.969 | 0.875 | [0.627, 1.000] |

On the Noul, Snap's point estimate is higher by 0.076 — but Jev's interval was
[0.548, 0.667] and Snap's is [0.628, 0.740], and they overlap. The honest
reading is that Snap's Noul looks stronger and this corpus cannot settle it.
On the Choice and the Score the two vendors are indistinguishable: 0.695 vs
0.715, 0.680 vs 0.679, all inside each other's intervals.

Snap's Noul nearly closes the gap that Jev's Noul left to its Choice
(0.685 vs 0.695 within Snap) — for Jev the redesign was worth 0.106
(0.609 → 0.715), for Snap it is worth 0.010. Either Snap's yes/no question is
already well-calibrated, or the Choice adds nothing for it. One corpus cannot
tell those apart.

## What the Choice said, against a 48.4% base rate

| bucket | n | actually rescued |
|---|---|---|
| `retry_likely_passes` | 250 | 55.6% |
| `retry_likely_fails` | 74 | 25.7% |
| `cannot_tell` | 19 | 42.1% |

Snap is far less willing to say `cannot_tell` than Jev (19 cases vs 44) and
splits more cases into `retry_likely_passes` (250 vs 198). Its `cannot_tell`
bucket sits at 42.1%, below the base rate — that abstention carries no
information here, whereas Jev's did (25.0%).

## Skip-gate

Skipping only `retry_likely_fails`, gated on the Choice's confidence:

| gate | skipped | saved | lost | ratio |
|---|---|---|---|---|
| none | 74 | 55 | 19 | 2.89 |
| confidence ≥ 0.3 | 66 | 51 | 15 | 3.40 |
| confidence ≥ 0.5 | 42 | 35 | 7 | 5.00 |
| confidence ≥ 0.7 | 18 | 18 | 0 | inf |

Compare Jev's ungated 2.26 and ≥0.3 3.18. Snap's ratios are modestly better at
every gate, on the same trade: a saved worker attempt against a rescue given
up. The ≥0.7 row is 18 cases with zero losses — a ratio of infinity is a
statement about 18 cases, not a guarantee.

## Answer grading

Usefulness AUC real vs degraded **0.875**, 95% CI [0.627, 1.000], against
Jev's 0.969.

That is a lower point estimate, and the comparison is **not strictly like for
like**: Jev's 0.969 was quoted on its own corpus, and this run used the
28-case corpus of four real answers, each degraded six ways. Different real
answers, different n, same method. Snap's interval runs
from 0.627 to 1.000 — it overlaps Jev's number, so this corpus does not
establish that Snap ranks answers worse, only that it did here.

Per-dimension means by variant:

| variant | usefulness | addresses | complete | committal | unsupported |
|---|---|---|---|---|---|
| real | 3.215 | 0.971 | 0.994 | 0.988 | 0.595 |
| off topic | 0.074 | 0.005 | 0.973 | 0.637 | 0.927 |
| generic filler | 0.190 | 0.021 | 0.918 | 0.012 | 0.013 |
| truncated | 2.274 | 0.810 | 0.098 | 0.850 | 0.460 |
| over-hedged | 2.956 | 0.986 | 0.996 | 0.965 | 0.627 |
| fabricated specifics | 2.673 | 0.982 | 0.996 | 0.996 | 0.994 |
| contradicted | 2.574 | 0.912 | 0.980 | 0.973 | 0.861 |

The dedicated dimensions still catch their failure modes: off-topic collapses
`addresses` to 0.005, filler collapses it to 0.021, truncation drops `complete`
to 0.098, fabrication raises `unsupported` to 0.994. The weakness is
`over-hedged`: Snap scores it 2.956 on usefulness, barely under its real
answers' 3.215, and its `committal` mean is 0.965 — essentially the same as
real answers at 0.988. Jev caught hedging at 0.45 on `committal`. Snap does
not.

## Read this honestly

- **One corpus, one machine, one model version.** 343 retry cases is enough
  for an AUC interval of roughly ±0.06 and not enough to separate two vendors
  whose point estimates differ by 0.02.
- **The Noul improvement is a point estimate, not a result.** Snap 0.685 vs
  Jev 0.609 looks like a win; the intervals overlap and I will not call it one.
- **Snap's `cannot_tell` is not informative here** (42.1% rescued, 19 cases,
  base rate 48.4%). Treating its abstention as evidence of a hard case would be
  wrong on this data.
- **The answer-grading comparison is across two different corpora.** 0.875 vs
  0.969 is not a like-for-like verdict. Rebuild both on one corpus before
  ranking the vendors on it.
- **The thresholds in `answer_quality.py` were calibrated on Jev.** Snap's real
  answers average 0.595 on `unsupported_claims`, above the 0.50 flag threshold —
  so Snap would flag clean real answers for unsupported specifics. The
  over-hedged miss is the mirror image: the 0.65 `committal` threshold never
  fires for Snap because it never drops below ~0.85. Those thresholds do not
  transfer without re-measuring.
- **The skip-gate ratios rest on small counts.** 74 skipped at no gate, 18 at
  ≥0.7. The ratio's floor is sound; its ceiling is not estimable.
- **Cost is input-only.** 420418 tokens across 686 requests, $0.0168. Output
  tokens are free on this model, so the price of a longer answer does not
  appear here.

## Switching it on

Snap drops into the same `[decisions]` section Jev uses. Off by default:

```toml
[decisions]
skip_retries   = true
provider       = "subq"
min_confidence = 0.5            # 42 skips on this corpus, 35 saved, 7 lost
modules        = ["decisions.subq"]
```

The key comes from `SUBQ_API_KEY`, or from `op read $SUBQ_OP_REF` when only
the 1Password reference is set. Unset both, or let the vendor go down, and
Ringer retries exactly as before.

## Reproducing

```sh
SUBQ_API_KEY=... python3 ~/.ringer/jobs/subq/measure/eval_snap.py
```

Run from a Ringer checkout. Answers are cached per case beside the script in
`snap_retry_answers.json` and `snap_quality_answers.json`, so a re-run costs
nothing (no key needed) and re-prints every number above.
