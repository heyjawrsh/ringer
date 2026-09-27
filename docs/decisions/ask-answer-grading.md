# Grading an `ask` answer

Measured 2026-09-27 against `jev-1.13.0`.

## The hole this fills

`ask` spawns one worker over a source packet and verifies the result by
checking that `answer.md` exists and is not empty. The playbook says so
plainly, and calls it the weakest check in the tool — honestly, because there
is nothing to execute against free-form prose. `ask` proves a worker answered.
It has never proved the answer was any good.

This is the one place in Ringer where a typed judgment is not competing with an
executed check. It is filling a gap no check can reach.

## It is advisory, and that is a decision

The retry skip acts on its provider's answer because the trade was measured:
23 attempts saved against 4 rescues forfeited. Nothing comparable has been
measured here, so this prints beside the answer and changes nothing.

The safety is structural rather than promised. `ask_answer_note` returns
`str | None` — display text and nothing else — so it has no channel through
which it could alter what `ask` returns.

## What it asks

The vendor's own guardrails recipe: a battery of Nouls, one per failure mode,
plus one Score for the overall read, all in a single request.

| question | catches |
|---|---|
| addresses the question | an answer to a different question |
| complete | truncation, a cut-off mid-thought |
| committal | hedging until nothing is said |
| unsupported claims | specifics absent from the source |
| usefulness (Score, 0–4) | the overall read |

## What it scored

Six real answers, each degraded six ways:

| | usefulness | the dimension that catches it |
|---|---|---|
| real answers | **3.17** | — |
| off topic | 0.01 | addresses-the-question 0.90 → **0.01** |
| generic filler | 0.23 | addresses-the-question 0.90 → **0.12** |
| truncated | 2.54 | complete 0.82 → **0.22** |
| over-hedged | 2.40 | committal 0.84 → **0.45** |
| fabricated specifics | 2.31 | unsupported 0.85 → **0.97** |
| contradicted | 2.11 | — |

**Usefulness AUC, real vs degraded: 0.969.**

Note that two of these are caught by their dedicated Noul and *not* by the
Score — over-hedging separates by only 0.77 on usefulness but by 0.39 on
`committal`. That is why it is a battery and not one question.

Separately, on answers assembled **verbatim** from one source so groundedness
holds by construction:

| | P(unsupported) |
|---|---|
| clean, straight from the source | **0.084** |
| + one invented specific | **0.946** |
| + two | 0.972 |
| + three | 0.981 |

**AUC 1.000.** At a 0.5 threshold: 42/42 fabrications caught, 0/14 clean
answers false-flagged. And paraphrased-but-true answers score **0.09–0.12**,
so it reads meaning rather than matching strings — the result that makes this
usable on real prose at all.

## The limit, stated precisely

The unsupported-claims Noul detects specifics **absent from the source**. That
is not the same as specifics that are **false**. A genuine report that
synthesises beyond its packet scores around 0.80 on it.

For `ask`, whose contract is *answer from this packet*, surfacing those is
correct. But the flag says "worth checking against the packet or an additional
source" and never "fabricated", "invented" or "wrong" — and the note is
suppressed outright if it ever contains *verified*, *confirmed*, *validated*,
*proven* or *guaranteed*. `ask` proves a worker answered; a grade does not
upgrade that.

## Also worth knowing

- **Small corpus.** Four real answers after excluding document fragments;
  the degradations are synthetic. This shows the battery detects known
  failure modes. It does **not** show it ranks two genuinely different real
  answers correctly — that needs graded history nobody has yet.
- **Three of the four problems found while measuring were mine, not the
  model's**: a truncated source, a source filename that did not exist, and a
  bare Evidence section scored as though it were an answer. Each first looked
  like weak signal. Build the corpus carefully before doubting the model.

## Switching it on

On by default **once a provider is configured** — grading forfeits nothing, so
it does not wait behind `skip_retries`, which does.

```toml
[decisions]
provider      = "jev"
modules       = ["decisions.jev"]
grade_answers = true   # the default; set false to silence it
```

With no provider configured, `ask` prints exactly what it prints today.
