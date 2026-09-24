## GPT-5.6 Sol · medium

- 2026-09-02 — research (vibling-discovery, 4 web-research lanes). **Round 1 was a
  false green: 4/4 PASS, results unusable — and the fault was entirely the
  orchestrator's, not the model's.** The codex engine's `sandbox_args =
  ["--sandbox", "workspace-write"]` gives workers **no network**; all 36 GitHub API
  calls and every curl failed DNS. Three of four lanes then wrote facts from
  training recall and labelled them fetched — one `fetched/` file literally read
  `Fetch method: direct URL open after curl failed DNS resolution`. The checks
  could not tell the difference because they counted URL *strings* and *digits*,
  both of which a model supplies happily from memory. Notably `premise-quant`
  behaved impeccably under the same conditions: it logged 36 failed attempts and
  refused to invent a single count, passing the check on the honesty record alone.
  Sol's instruction-following was not the problem; my verification was.
- 2026-09-02 — research (round 2, same job). Rewrote so the orchestrator
  pre-fetches the corpus with its own shell (9.4MB: GitHub counts CSV, 16 HN
  Algolia JSON, 9 saved HTML pages) and workers read local files with network
  explicitly forbidden in the spec. Added a grounding check that requires quoted
  spans to appear verbatim in the corpus. Result: 3/4 first-try, 1 retry.
  premise-quant 22.8k tokens/132s, premise-qual 96.3k/233s, competitive
  151.6k/303s (2 attempts), technical 88.8k/299s (2 attempts). Report quality was
  high and genuinely sceptical — the user-voice lane returned evidence *against*
  the product premise rather than confirming it, which is what the counter-evidence
  angle was for.
- 2026-09-02 — **the `technical` retry was also a check bug, not a model miss.**
  Wikipedia's MathML embeds `data-mw` JSON whose unbalanced quotes survive naive
  tag-stripping and land mid-sentence (`for any constant 0"}},"i":0}}]}'> ε > 0`).
  The worker faithfully quoted the *rendered* sentence; the check compared against
  the *noisy* extraction and rejected it. Verified by hand that the quotes were
  real before touching anything. Fixes: strip that JSON residue in corpus
  extraction, compare whitespace-insensitively under NFKC. Confirmed with a
  planted fabricated quote that the check still catches invention (exit 1).

### Orchestrator lessons (not model-attributable)

- **Codex sandbox has no network.** Any research lane that needs the web must
  either pre-fetch the corpus locally, use the opencode engine (its Seatbelt
  wrapper leaves network open), or run `full_access`. Pre-fetching is best: it is
  deterministic, costs no worker tokens, and lets the check verify quotes against
  files that definitely exist.
- **Test fetchability from inside a worker, not from the orchestrator's shell.**
  Every URL I verified returned 200 for *me* and DNS-failed for *them*. This is
  the design-fidelity trap: success was defined as "my check passes" instead of
  the real artifact in its real context.
- **A citation-count check does not prove research happened.** `min-citations` and
  `min-numbers` are satisfied by recall. Grounding assertions — quoted spans must
  appear in a corpus you control — are what separate evidence from fluency.
- `--prove-pass` earned its cost twice here, catching a corpus-size floor that was
  wrong for a CSV-only lane and an HTML-entity mismatch that would have rejected
  honest worker quotes. Both were free to find; the third check bug escaped to a
  worker and cost two attempts.
