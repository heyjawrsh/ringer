# Jev, measured against Ringer's own retry history

Measured 2026-09-25 against `jev-1.13.0`. Every number here comes from
replaying real decisions, not from a benchmark the vendor chose.

## What was asked

Ringer retries a failed task once, **unconditionally**. Pairing each first
attempt with its retry across 522 runs in `~/.ringer/runs.jsonl` gives 343
cases where a check failed and a retry ran:

| outcome | n |
|---|---|
| the retry rescued it | 166 |
| the retry was wasted | 177 |

So unconditional retry — what Ringer does today — is right **48.4%** of the
time and spends 177 worker attempts that changed nothing. Always skipping
scores 51.6%. The first attempt's verdict alone is a coin flip: `FAIL` splits
160 wasted / 157 rescued.

Each case was sent to Jev as a single Noul: *will retrying this task once
rescue its failed check?* The state carried only first-attempt evidence —
check output, return code, verdict, task type, engine, spec. The label
(`retry_rescued`) was never sent.

343 calls, **0 errors**, 136s at 2.5/s, well under a cent of input tokens.

## The offline baseline first

The heuristic provider that ships in `decisions/heuristic.py` scores
**exactly** the always-retry baseline. On all 343 cases its surface patterns
never match, so it defaults to "retry" every time. There is no cheap regex
signal in check output. That is worth stating plainly, because it is the
result that makes the vendor comparison meaningful rather than rhetorical.

## What Jev scored

**AUC 0.609**, 95% CI **[0.548, 0.667]** (2000 bootstrap resamples). The
interval excludes 0.50, so the ranking carries real information.

The gain survives out-of-sample threshold selection — the threshold is picked
on one random half and scored on the other, 400 times:

| | |
|---|---|
| mean gain over always-retry | **+12.7%** |
| 95% CI | +3.5% to +22.1% |
| splits that beat always-retry | **100%** |

## The question design was the limiting factor, not the model

The Noul above was the wrong primitive, and the reason is structural rather
than incidental: **a Noul answer carries no confidence.** The whole argument
for a calibrated model is that it can say "I don't know" — and the first pass
asked in the one shape that cannot. Re-asking the same 343 cases as a Choice
over explicit prognoses, plus a Score, in a single request each:

| design | AUC |
|---|---|
| Noul — "will retrying rescue this?" | 0.609 |
| Score, 0–4 recoverability | 0.679 |
| Choice, P(retry_likely_passes) | 0.708 |
| **Choice, P(passes) − P(fails)** | **0.715**, 95% CI [0.659, 0.767] |
| Choice, on its more-confident half | **0.729** |

The lower bound of the Choice interval sits above the Noul's point estimate.
Held-out threshold selection over 400 random half-splits gives a mean
**+16.9%** over unconditional retry (95% CI +8.7% to +24.4%), beating it in
100% of splits.

What the Choice actually said, against a 48.4% base rate:

| bucket | n | actually rescued |
|---|---|---|
| `retry_likely_passes` | 198 | 62.6% |
| `retry_likely_fails` | 101 | 30.7% |
| `cannot_tell` | 44 | 25.0% |

## Confidence gating is what makes the economics work

Skipping a retry trades a saved worker attempt against a rescue given up, and
those are not worth the same: a lost rescue means the task simply fails, and
a human picks it up. So the ratio of saved-to-lost has to clear the ratio of
those two costs.

Skipping only `retry_likely_fails`, gated on the Choice's confidence:

| gate | skipped | saved | lost | ratio | 90% CI on ratio |
|---|---|---|---|---|---|
| none | 101 | 70 | 31 | 2.26 | — |
| confidence ≥ 0.3 | 71 | 54 | 17 | 3.18 | [2.1, 5.4] |
| confidence ≥ 0.5 | 27 | 23 | 4 | 5.75 | [2.8, 23.0] |
| confidence ≥ 0.7 | 8 | 8 | 0 | — | small n |

That is the vendor's own three-band advice applied literally, and it is the
difference between a trade not worth making (1.6:1 on the Noul) and one that
is (2.8:1 at the pessimistic end of a confidence-gated Choice).

## Prioritisation, which forfeits nothing

If retries are ordered best-first instead of cancelled, no work is given up —
capacity just goes to the likeliest rescues first.

| retries run first | rescues captured | random order |
|---|---|---|
| 50 | 38 | 24.1 |
| 100 | **75** | 48.8 |
| 172 | 114 | 83.2 |

## The original Noul threshold sweep, for reference

Skipping a retry trades a saved worker attempt against a rescue given up, and
those are not worth the same: a lost rescue means the task simply fails.

| threshold | skipped | attempts saved | rescues lost | ratio | share wasted |
|---|---|---|---|---|---|
| 0.20 | 24 | 15 | 9 | 1.67 | 62.5% |
| 0.25 | 89 | 50 | 39 | 1.28 | 56.2% |
| 0.30 | 182 | 110 | 72 | 1.53 | 60.4% |
| 0.32 | 205 | 127 | 78 | 1.63 | 62.0% |
| 0.35 | 244 | 145 | 99 | 1.46 | 59.4% |
| 0.40 | 286 | 157 | 129 | 1.22 | 54.9% |

The base rate of "wasted" across all 343 cases is 51.6%, so any share above
that is signal. It peaks around 62%.

## Read this honestly

- **AUC 0.72 is useful, not decisive.** Real and worth acting on behind a
  confidence gate; still not an oracle.
- **The first design was mine, and it was wrong.** Asking a Noul threw away
  confidence, which is the one thing this class of model sells. Any future
  decision wired to this seam should be asked as a Choice or a Score unless
  there is a reason not to.
- **The scores cluster tightly** — min 0.11, median 0.30, max 0.60. Jev is
  systematically pessimistic about retries and never confident one will work.
  A threshold has to sit inside that band; the vendor's own documentation
  warns that thresholds must be set per question against measured data, which
  is exactly what this file is.
- **Mean separation on the Noul was only +0.036** (0.332 rescued vs 0.296
  wasted). The ranking beat the separation, which is why AUC is the metric
  quoted throughout and a comparison of means would have misled.
- **The confidence >= 0.5 gate rests on 27 cases.** Its ratio floor is sound
  but its ceiling is not estimable; prefer >= 0.3 if you want a number with
  tighter error bars.
- **One corpus, one machine, one model version.** Re-measure before trusting
  these thresholds anywhere else.
- **Nothing is wired into the retry path.** These numbers are the argument for
  doing it, and the baseline any change must be held against.
- **A vendor adapter must absorb rounding.** Jev returns probabilities rounded
  for display, which can sum to 0.99; the seam requires 1.0 to 1e-6. Four of
  343 calls failed until `decisions/jev.py` renormalised them.

## Switching it on

Off by default. To enable, add to your Ringer config:

```toml
[decisions]
skip_retries   = true
provider       = "jev"
min_confidence = 0.5          # the measured gate; 0.3 trades more volume for a lower ratio
modules        = ["decisions.jev"]   # imported so the provider registers
```

and put the credential in the environment:

```sh
export TYPESAFE_API_KEY=...   # never stored in the repo or the config
```

Expect it to touch roughly 8% of retries at `min_confidence = 0.5`. Every
other outcome retries exactly as before, so removing the section, unsetting
the credential, or the vendor going down all return Ringer to its current
behaviour with no other change.

A skipped retry is recorded on the task as `retry_skipped` and
`retry_skip_reason`, so a forfeited attempt is visible in the run record
rather than silent.

Only the FIRST attempt is ever skipped. The thresholds were calibrated on
first-attempt evidence, and applying them to a later attempt would be using
them outside the data that justifies them.

## Reproducing

```sh
TYPESAFE_API_KEY=... python3 ~/.ringer/jobs/jev-integration/eval_jev.py
```

Answers are cached per case, so a re-run costs nothing and a threshold sweep
never re-queries.
