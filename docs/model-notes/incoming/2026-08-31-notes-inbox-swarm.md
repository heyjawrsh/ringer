## GPT-5.6 Sol (Codex CLI)

- 2026-08-31 code-feature + test-hardening (2-lane notes-inbox run, no worktrees, serial):
  both lanes produced correct work. `notes-curate-command` passed first try at 66k tokens /
  469s against a gate whose central assertion is a round trip (parsed sections must be
  identical before and after curation) — a non-obvious contract it satisfied without a retry.
  It also lifted the notes parser to a module-level helper so curation and rendering share
  one implementation; more restructuring than the spec invited, but behaviour-preserving and
  verified three ways. `inbox-policy-tests` was recorded FAIL/TIMEOUT across two attempts and
  ~80k tokens, and was **not** at fault: its deliverable was present, green, and provably
  binding. Both failures were harness defects (below). Notable: it solved the genuinely hard
  half of its spec unprompted — distinguishing an *instruction* to write to the canonical log
  from a legitimate mention of it — with a negation regex beside the write-instruction pattern.

## Gate authoring — timing is a satisfiability condition

- 2026-08-31 — `CHECK_TIMEOUT_S = 60` is the default check budget and is separate from a task's
  `timeout_s`, which is the WORKER budget. A gate that ran a test suite three times (~300s) was
  killed at 60s on both attempts because only `timeout_s` was set. It surfaced as
  `verdict=TIMEOUT`, which reads as a slow worker, and cost two attempts on correct work.
  A check can be unsatisfiable in the TIME ALLOWED rather than in logic, and none of the four
  gate modes is framed around that shape. Set `check_timeout_s` on any check that runs a suite.

## Gate authoring — attribution has two failure directions, not one

- 2026-08-31 — a mutation gate must attribute a new test failure to the mutation only when the
  failure comes from the test under scrutiny. Getting this wrong in EITHER direction is fatal
  and both happened in one gate within an hour. Too broad: counting any new failure credited
  `test_contributors`, which fires because the harness's own commit author is not a credited
  contributor — the gate then reported a binding test that did not exist. Too narrow: filtering
  on a module substring while the failure-capturing regex was `^(?:FAIL|ERROR):\s+(\S+)` matched
  nothing, because unittest prints `FAIL: test_name (module.Class.test_name)` and `\S+` stops at
  the bare method name. That false negative rejected a correct implementation. Capture the whole
  identifier, filter on the module, and print ignored failures rather than discarding silently.
- 2026-08-31 — the coverage gap accepted at preflight is the one that bites. `preflight` refused
  this manifest at lint over a missing `known_good`; the workaround was to hand-verify only the
  faster gate. Had `--prove-pass` run, it would have executed the slow gate against a known-good
  state, hit the 60s wall, and reported the check BROKEN before any worker spawned. Preflight was
  right and routing around it cost ~80k tokens. When a proof mode cannot cover a task, that task
  is where the next failure will come from.
