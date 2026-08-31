## minimax/minimax-m2.7:free (OpenRouter, via OpenCode)

- 2026-08-29 code-review (repo-lineage sweep over 11 archived repos): 0/2 attempts, **zero tokens**,
  2.2s total. Both attempts returned `{"type":"error","error":{"name":"UnknownError","data":
  {"message":"Unexpected server error."}}}` — provider-side, before any generation. This is NOT evidence
  about capability: the model never ran. Re-homed the identical lane to codex/high, which passed first
  try at 186k tokens / 450s. Verdict: the free endpoint is unreliable enough that it cannot be trusted
  even for an exploration lane on a deadline. Retry the audition only when a run has slack.

## GPT-5.6 Sol · high (Codex CLI)

- 2026-08-29 code-review (10-lane brownfield analysis of a 14-repo inherited codebase, ~2.3M tokens):
  9/9 lanes passed, 7 on the first attempt. Both second-attempt lanes (`frontend-architecture`,
  `orphan-backend`) were the widest surfaces, not defective specs. Notably strong at the reconciliation
  task — mapping 59 archived HTTP endpoints against 108 current ones and classifying each — and at
  respecting a hard "cite only files you opened" rule under a citation-grounding check. Spot-checks of
  four claims across two lanes found zero fabrications. Median ~200k tokens/lane; the two reconciliation
  lanes ran 478k and 495k.
- Practical note: a citation-grounding check (resolve every backticked path against the filesystem,
  fail below 80%) is cheap to write and appears to change behaviour — reports cited conservatively and
  pushed uncertainty into an Assumptions section rather than guessing paths. Reuse this for any
  read-a-codebase-and-report lane.
