# Token counter semantics probe, and what it overturned

2026-09-24. Bounded task observations, not general model rankings.

## GPT-5.6 Sol (Codex CLI)

- 2026-09-24 — probe (`token-counter-semantics`, lane `codex-counters`): one-attempt PASS, 32.4 s, 15,444 tokens. Task was five separate single-file writes, specified as five distinct actions, to force multiple harness steps. Raw log carries exactly ONE counter, `tokens used` followed by `15,444`, written at exit. Codex reports a single final cumulative total, so `parse_token_count`'s last-match behaviour is exactly correct for this engine and needs no change.
- 2026-09-24 — code-fix (`cost-honesty`, lane `unknown-price`): one-attempt PASS, 160.3 s, 21,852 tokens. Produced a smaller fix than the orchestrator's own throwaway — dropped the `or 0` coercion and let `float(None)` raise into the existing `except` rather than adding an explicit guard. Equivalent behaviour, two fewer branches, and it preserves a genuine price of 0 computing as free. Worth preferring the minimal form when the surrounding code already handles the error path.

## zai-coding-plan/glm-5.2 (OpenCode)

- 2026-09-24 — probe (`token-counter-semantics`, lane `glm-counters`): one-attempt PASS, 15.8 s, 18,396 tokens. Six `step_finish` events, each carrying `"tokens":{"total":N}` where total = input + output + reasoning + cache.read for THAT step. The series rises (18,167 → 18,396) only because each step re-reads a slightly larger cached prompt, so it reads as cumulative while being per-step. Component sums for the run: input 18,637, output 229, reasoning 89, cache.read 90,816. Summing the per-step totals gives 109,771 and double-counts the cached prompt once per step; the last total, 18,396, is within 3% of the 18,955 of actual fresh work.

## Orchestrator lessons

- **A prior note's conclusion was wrong, and the probe is what caught it.** The 2026-09-24 source-review note recorded "nine raw step events sum to 506,785; Ringer displayed 94,677, the final-step total" and read that as Ringer under-reporting ~5x. Nine cumulative-looking per-step totals ending at 94,677 sum to roughly that figure by construction. Had the orchestrator "fixed" `parse_token_count` to sum, it would have over-reported OpenCode runs by about 6x and left Codex — which is already exact — corrupted. Probe engine-specific telemetry before changing a parser shared across engines; monotonic is not the same as cumulative.
- **prove-fail caught a faulty mutation, not a failing check.** The first `known_bad` for the cost lane removed an explicit `is None` guard, but `float(None)` raises TypeError into the existing `except`, so the state was never broken and the check honestly passed. Reported as BROKEN, which is the correct verdict on the gate rather than on the code. The real defect was `or 0` inside the `float()` call, and the mutation had to restore that.
- **The scoreboard's cost column is inert on this installation, for a reason neither note found.** Zero of 94 rows resolve a catalog entry: the model log writes route-prefixed ids (`openrouter/z-ai/glm-5.2`, `headroom/z-ai/glm-5.2`) while the OpenRouter snapshot stores `z-ai/glm-5.2`. Stripping the prefix resolves 18 rows to real prices; the other 76 are first-party harness models genuinely absent from that catalog. This — not the `or 0` coercion — is why cost reads as nothing on plan routes.
