# Marrow source audit and Ringer UTF-8 stream repair

2026-09-07. These are bounded task observations, not general model rankings.

## Claude Opus 5, source review

Run `marrow-build-or-switch-20260907T054521Z-p22895`, task `expanded-source-audit`: first-attempt parent PASS, 490.3 seconds. The frozen packet covered eight cards; the gate checked exact quotes, source identities, coverage and packet hash. Root read the deliverables and supplemented primary passages omitted from the packet. Most negative verdicts identified packet coverage gaps, not disproven product claims. The worker also overstated absence of ctx capabilities and conflated disabled recall hooks with inability to index existing histories. Preserve review scope, qualify absence claims, and have root check semantics after a citation gate passes.

The raw log stopped mid-JSON after a curly quote despite completed deliverables. Final token usage was unavailable. This is a Ringer capture failure, not evidence that the model failed to finish.

## GLM 5.2 through the configured Z.AI Coding Plan route

Run `marrow-build-or-switch-20260907T104843Z-p70764`, task `ringer-stream-repair`: first-attempt parent PASS, 349.1 seconds. Route was explicitly `opencode:zai-coding-plan/glm-5.2`, confirmed in the installed OpenCode catalog. Ringer's registry still labels the route unregistered/misclassifies its plan column; do not infer OpenRouter billing from that display.

A narrow spec froze the module and permitted edits only in `RingerRunner._tee_stream`. The worker added a bounded UTF-8 continuation counter and left the rest of the module AST unchanged. It honestly reported its sandbox could not allocate PTYs instead of fabricating evidence. Parent execution then passed all 16 byte/transport families, including PTYs. Root's separate full CLI test preserved a 1,100,112-byte Unicode stream and final token/model records; the original source lost the final marker.

Ringer recorded 18,282 tokens before its still-unrepaired stream dropped subsequent output. That number is a partial observed usage value, not the total run cost. The worker's prose also wrongly included the checkmark character as an independent trigger (its continuation bytes are not among the six normal-state introducers); the executable diagnosis and patch do not depend on that example.

## Orchestrator lessons

Keep source preservation ahead of memory indexing. Tail display limits and discarded disk bytes are different failures. Test actual PTY transport and full CLI processing, with data beyond the rolling capture limit and final usage records. Parent tests must distinguish worker-sandbox limitations from implementation failures.

Root corrected two integration-fixture mistakes before acceptance: a missing required check field, then a supposedly over-limit payload that was only 990,112 bytes. The final fixture is 1,100,112 bytes. The original code fails for the intended lost-marker reason, and the repaired source passes. No model call is involved in these regression checks.

