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

## The threshold is a cost decision, not an accuracy one

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

- **AUC 0.61 is modest.** Real, but nowhere near strong. This is a nudge, not
  an oracle.
- **The scores cluster tightly** — min 0.11, median 0.30, max 0.60. Jev is
  systematically pessimistic about retries and never confident one will work.
  A threshold has to sit inside that band; the vendor's own documentation
  warns that thresholds must be set per question against measured data, which
  is exactly what this file is.
- **Mean separation is only +0.036** (0.332 rescued vs 0.296 wasted). The
  ranking beats the separation, which is why AUC is the metric quoted and a
  simple mean comparison would have been misleading.
- **One corpus, one machine, one model version.** Re-measure before trusting
  these thresholds anywhere else.
- **Nothing is wired into the retry path.** These numbers are the argument for
  doing it, and the baseline any change must be held against.

## Reproducing

```sh
TYPESAFE_API_KEY=... python3 ~/.ringer/jobs/jev-integration/eval_jev.py
```

Answers are cached per case, so a re-run costs nothing and a threshold sweep
never re-queries.
