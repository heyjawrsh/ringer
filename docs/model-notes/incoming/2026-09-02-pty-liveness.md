## GPT-5.6 Sol (Codex CLI)

- 2026-09-02 code-feature (pty worker liveness, single lane on the orchestrator's most
  critical path): passed first try at 67k tokens / 368s against a gate that measures an
  OBSERVABLE (does a lane's state change while its worker is still alive) rather than an
  implementation. It satisfied all six stated hard requirements and improved on one: asked
  for `run_in_executor` to keep `os.read` off the event loop, it used non-blocking readable
  callbacks with a future instead, which is better. It also wrote a proper state-machine
  escape stripper rather than the regex the spec implied.
- Caveat found only by spot-checking a PASSING lane: it also added an unrequested
  `sys.stdout.buffer.write(chunk)` echoing every worker chunk to the orchestrator's console.
  Unconditional, so every run would flood the terminal and any scripted use of `ringer.py run`
  parsing stdout would break. The gate could not catch it — the gate measures run-state
  liveness, not console cleanliness. Removed by hand. **A green gate bounds what you asserted,
  never what the lane also did.**

## Gate authoring — measure the observable, not the mechanism

- 2026-09-02 — the pty gate asserts "the lane's recorded activity changes at least three
  times while the worker is still running", not "the code calls `pty.openpty`". That let the
  lane choose a better read strategy than the spec suggested while still being held to the
  contract. Write the assertion against what a person would notice, and the implementation
  stays free.
- 2026-09-02 — verifying a gate in BOTH directions before spending a worker is cheap and
  decisive. Ten minutes: run it against the unmodified tree (must FAIL, and for the stated
  reason), then against a throwaway implementation in a temp copy (must PASS). Doing this
  caught nothing here — the lane passed first try — but the one time it was skipped this week
  the gate false-rejected correct work and cost 80k tokens. Cheap insurance, always take it.

## Environment — the worker sandbox blocks the global run registry

- 2026-09-02 — a check that itself invokes `ringer.py run` cannot write
  `~/.ringer/active-runs.json` from inside a worker sandbox; the lane had to set `RINGER_HOME`
  to a temp dir to exercise its own gate. Checks run OUTSIDE the sandbox and are unaffected,
  but a worker asked to reproduce a check's behaviour hits this. Point such specs at a
  temporary `RINGER_HOME` explicitly rather than letting the lane discover it.
