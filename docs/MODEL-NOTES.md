# Model notes — how workers actually perform

A running log of how models perform on real Ringer tasks, so engine and
model choices are made on evidence instead of vibes. The raw numbers now
live in the local eval log (`~/.ringer/runs.jsonl`); run `./ringer.py models`
to print the per-model, per-task_type scoreboard (tasks, attempts,
pass_rate, first_try_pass_rate, median duration/tokens, last_seen). This
file remains the judgment layer on top of those numbers.

**How to add a row:** after reviewing a run (post-run ritual step 5 in the
ringer skill), append one dated line under the model. Say the task type,
what happened, and what you'd do differently. Only write what the executed
checks and raw logs support — no vibes, no worker self-reports.

## Routing policy (operator directive — Josh, 2026-07-11)

Not an evidence row; a standing GLM-version floor the orchestrator honors
when picking the `model` field. Ringer's config can only pin ONE default
(`[engines.opencode].model_default`), so the rest is orchestrator discipline:

- **Default lane = GLM-5.2 on the Z.ai Coding Plan** (`zai-coding-plan/glm-5.2`,
  flat-rate). This is the engine `model_default`; tasks that don't name a
  model land here.
- **Everywhere else, floor is GLM-5.1.** When routing to OpenCode Go
  (`opencode-go/*`) or OpenRouter (`openrouter/z-ai/*`), never select below
  `glm-5.1` — prefer `glm-5.2` where the lane offers it. Do not fall back to
  4.x GLMs (4.7, 4.6, 4.5-air) on any lane.
- Applies to GLM specifically; non-GLM audition candidates (free Nemotron,
  Llama, etc.) are exempt — they're being tested on their own merits.

## codex (GPT-5-class, own harness)

- 2026-08-08 — code-fix, high effort (flont_friend inbox wire-contract
  reconciliation: 9 drifts audited + serde contract tests + error boundary,
  1048-line patch, run flont-friend-build): scoreboard shows FAIL/2 — but the
  CHECK never executed: the orchestrator's verify-command used bash process
  substitution (diff <(...)) and the harness runs /bin/sh, which
  syntax-errors before any test. Worker output was verified manually from the
  surviving worktree: 80/80 tests, full parity. Fifth check-fault FAIL in
  this project. Lessons: (a) verify-commands must be POSIX sh — no <( ), no
  [[ ]], no arrays; (b) failed tasks keep worktrees, so check-fault runs are
  recoverable without re-running the worker. PROCESS lesson from the bug
  itself: parallel two-lane rounds MUST pin wire shapes verbatim in both
  specs and cross-check name parity in both checks — doc-reference contracts
  drift (9 mismatches accumulated over 3 rounds before first runtime use).

- Strongest general worker; the default engine. Spend reasoning effort per
  task via `engine_args` (`["-c", "model_reasoning_effort=low|medium|high"]`)
  — high on gnarly tasks, low on boilerplate.
- 2026-07-12 — code-feature, high effort (flont_friend Rust data layer:
  rusqlite/FTS5 schema + 7 sync triggers + 18 commands + 10 in-memory tests,
  ~2.4k-line change, run flont-friend-build): scoreboard shows FAIL/2
  attempts, 132k tokens — but BOTH attempts were implementation-green
  (cargo test 10/10 inside the check); the fail was the CHECK's fault. The
  orchestrator left an untracked `.ringer/` manifest in the repo with
  `--allowed-status ''`, so the git-porcelain confinement gate could never
  pass. Worker correctly refused to delete the out-of-boundary file and
  flagged it in notes.md — exemplary boundary behavior. Lesson (repeat of
  2026-07-10): before a repo-feature run, commit or allowlist every path
  the ORCHESTRATOR has touched; the confinement check sees your mess too.
- 2026-07-05 — carried the heavy lanes of the milk-crate demo rehearsals
  (market read with source allowlist, site build) with clean first-attempt
  passes.
- 2026-07-22 — gpt-5.6-sol high, code-feature (dithertone-web-port r13:
  light/dark theming as pure token overrides + system-follow + FOUC guard):
  PASS attempt 1, 53k tokens, 184s. Spec asked it to COMPUTE WCAG contrast
  ratios instead of eyeballing — it did (5 pairs reported, all verified
  plausible in-browser) and lifted the too-dark blue accent exactly as
  briefed. Second run confirming the pnpm-reinstall sandbox quirk; spec
  pre-authorized the direct-binary workaround this time, zero friction.
- 2026-07-22 — gpt-5.6-sol high, code-feature (dithertone-web-port r12:
  family toggle-group + collapsible sidebar sections + fixed viewport app
  frame, one-task run over a 912-line App.tsx): PASS attempt 1, 66k tokens,
  210s. Playwright post-run verified all three behaviors real (family-
  filtered select, aria-expanded persistence across mode switches, doc
  scrollHeight == viewport at lg+, natural scroll below lg). Note: worker
  reported `pnpm build` blocked because pnpm tried to purge/reinstall
  node_modules under the sandbox; it correctly honored the no-install rule
  by invoking the installed tsc/vite/tsx binaries directly. If a spec says
  "run pnpm build", expect this workaround or pre-warm the store.
- 2026-07-12 — gpt-5.6-sol, code-feature (flont_fuse Milestone 1: cargo
  workspace, imara-diff core + ksdiff-compatible CLI with three-way merge,
  8 tests, run flont_fuse-milestone-1): PASS attempt 2, 69k tokens — but
  attempt 1 was implementation-green (cargo 8/8) and failed ONLY the
  orchestrator's case-sensitive `--required-text 'histogram'` gate against
  idiomatic `Algorithm::Histogram`. Another check-fault retry, not model
  fault. Lesson: required-text snippets must be case-insensitive-safe or
  match the casing the language's idiom will produce.
- 2026-07-12 — gpt-5.6-sol, code-feature (flont_fuse Milestone 2: dir_diff
  module + CLI directory mode, 6 new tests, run flont_fuse-milestone-2):
  PASS attempt 1, 45k tokens, 130s. The Milestone-1 lesson applied — every
  required-text snippet was a spec-mandated identifier — and the phantom
  retry vanished. Contract-first specs (exact enum variants, exact output
  format) are the fix for check/idiom mismatches.
- 2026-07-12 — gpt-5.6-sol, code-feature (flont_fuse Milestone 3: full
  ksdiff 6.7 arg surface, 5 new integration tests, run
  flont_fuse-milestone-3): scoreboard shows FAIL/2 attempts, 54k tokens —
  but BOTH attempts never reached cargo: the orchestrator passed
  `--required-text '--partial-changeset,...'` and argparse ate the
  leading-dash value as an option (\"expected one argument\"). The
  corrected `=`-form check PASSed against the worker's unmodified output
  (19/19 tests). Third check-fault FAIL row in this project's log. Lesson:
  any check-script argument value that can start with '-' must use the
  --flag=value form; consider hardening kit checks to argparse
  prefix-safe parsing.
- 2026-07-12 — gpt-5.6-sol, code-feature (flont_fuse Milestone 4: YIQ
  perceptual image_diff + highlight PNG + CLI image mode, 10 new tests,
  run flont_fuse-milestone-4): PASS attempt 1, 57k tokens, 280s. Math-
  heavy module against mandated constants (35215, channel weights) landed
  exactly to contract. With all three check-craft lessons applied, the
  fourth repo-feature run was the first with zero friction of any kind.
  Post-run caution for ORCHESTRATORS: my own naive PNG spot-check ignored
  scanline filters and briefly implicated a correct binary — unfilter
  before counting pixels; read raw data before blaming the worker.
- 2026-07-12 — gpt-5.6-sol, GUI benchmark prototypes (flont_fuse UI gate,
  runs flont_fuse-milestone-5-ui-gate): Tauri v2 prototype (no-npm,
  DOM-windowed, rAF-instrumented) PASS attempt 1. SwiftUI prototype PASS
  attempt 2 (attempt 1 crashed on a missing NSTextView designated init —
  real bug, caught because the check LAUNCHES the window) — but shipped
  rendering a BLANK window that still emitted schema-valid frame metrics:
  scripted checks validated strings-set, not pixels. Only a human feel
  test caught it. Lesson: GUI checks must assert PAINTED PIXELS
  (screenshot + stdlib decode); "window visible + data loaded" is
  gameable by accident. The follow-up fix task (code-fix, high) PASSED
  attempt 1 and — notably — REFUTED the orchestrator's stated root-cause
  hypothesis (TextKit-2 wiring) with a standalone repro proving
  zero-width split panes. Trust fix workers to re-diagnose; don't force
  your theory.
- 2026-07-12 — gpt-5.6-sol, Milestone 6 (flont_fuse app scaffold + 120Hz
  probe): app-scaffold scoreboard shows TIMEOUT+FAIL/2 but the work was
  green — attempt 1's clock died to the first in-repo tauri compile
  (budget cold-cache tauri builds ~3600s AND keep the check lean);
  attempt 2 failed ONLY the check's wrong binary path (json smoke hit
  target/release/flontdiff which the build command never release-built —
  check-fault #4: every path a check references must be produced by that
  check's own build steps). Hand-verified: 34/34 tests, exact --json
  smoke, app window pixel-verified. The 120Hz probe worker was
  exemplary under sandbox denial: built four lever variants, reported
  measured_hz null rather than guessing, flagged private API as
  unshippable. Orchestrator ran the deniend GUI measurements: 58.8Hz
  across all shippable levers on a confirmed-120Hz VRR display. Pattern:
  GUI measurement tasks should expect sandbox window-service denial —
  have workers BUILD variants and the orchestrator EXECUTE them.
- 2026-07-12 — gpt-5.6-sol, Milestone 7 (flont_fuse long-line windowing +
  app bench mode). FIRST attempt was a total wash — NOT a model or spec
  failure: Codex's own backend flaked mid-task (worker.log showed repeated
  `rmcp Transport channel closed` + `failed to refresh available models:
  timeout` every ~3min), both attempts left NOTHING in the tree; the
  repo-feature check correctly FAILed (no bench mode -> app opened its
  normal window and never wrote metrics). A clean re-run once Codex was
  healthy: PASS attempt 1, 73k tokens, 480s — real perf win, hand-verified
  (patho-longline p95 205ms->18.0ms, 0% dropped, under the ADR's 33ms
  gate). Lessons: (1) transient Codex infra failures present as an empty
  FAIL — check `codex login status` + worker.log for transport/model-
  refresh errors before re-speccing; a straight re-run is the fix. (2)
  ORCHESTRATOR self-own: I "measured" a hang from the PRE-milestone binary
  (bench env var ignored -> normal window stays open forever) and nearly
  misread it as a perf failure — always confirm the artifact under test
  actually contains the feature (grep the flag) before measuring.
- 2026-07-12 — gpt-5.6-sol, Milestone 8 (Fuse git-difftool integration:
  label flags + --print-git-config helper + docs + 2 headless tests):
  PASS attempt 1, 327s. The executed gate was an orchestrator-authored
  GUI harness (check_gui_difftool.py) that drives REAL git difftool and
  requires painted pixels + label pass-through + git unblocking on window
  close — calibrated to FAIL the pre-feature binary before the run.
  Pattern confirmed: for GUI features, the orchestrator builds and
  calibrates the executable gate FIRST, then the worker builds to it.
  POST-SHIP CORRECTION (same day): the user's real-context run caught what
  the gate missed — the window opened BEHIND the focused terminal
  (z-order 1) and "nothing happened". The gate had a false-positive hole:
  screen-center pixel sampling passes on any busy desktop when NO window
  opens frontmost. Hardened to window-anchored verification (CGWindowList
  prober: window must EXIST + be z-order 0 + paint within its own bounds).
  Two durable lessons: (a) GUI checks anchor to the WINDOW, never the
  screen; (b) focus/z-order is part of "it works" for tool-launched GUIs —
  and it is context-dependent (racy in automation, deterministic only
  after an explicit set_focus), so assert it, don't assume it.
- 2026-07-12 — gpt-5.6-sol, Milestone 9 (Fuse three-way merge editor:
  merge_regions structured diff3 in flont-core + flontdiff refactor +
  interactive editor UI + FUSE_AUTO_RESOLVE hook + config fix; ~550-line
  change, 4 new tests): PASS attempt 1, 504s. The gate composed every
  prior lesson — window-anchored frontmost+paint, an automation hook for
  the interaction no script can click, true-diff3 content assertions
  (copy-local fails), and fail-closed legs (unresolved close and abort
  must stay conflicted) — and was calibrated to FAIL the merge-less
  binary first. Interactive-GUI features are checkable when the app
  ships an env-gated automation mode; that pattern is now standing
  (FUSE_BENCH_METRICS_OUT, FUSE_AUTO_RESOLVE).
- 2026-07-12 — gpt-5.6-sol, Milestone 10 (Fuse hunk nav + live re-diff +
  probes; ~570-line change): scoreboard FAIL/2 but the feature work was
  SOUND — the run died on a Tauri v2 capability denial
  (plugin:event|listen not allowed by ACL) that is INVISIBLE from inside
  the worker sandbox (no GUI runs there). Orchestrator reproduced,
  granted core:default in tauri.conf.json, everything green. Lessons:
  (a) when a GUI framework feature (events, dialogs, clipboard) is used
  for the first time, the spec should name the capability/ACL grant —
  workers can't discover runtime permission errors they can't run;
  (b) NEW gate blindspot found and fixed: window-region paint sampling
  reads legitimately blank for FEW-LINE fixtures (content doesn't reach
  the sampled central region) — GUI gate fixtures must FILL the window
  (~200 lines); this had silently under-tested M8/M9 fixtures too.
- 2026-07-12 — gpt-5.6-sol, Milestone 11 (Fuse folder-diff GUI: master-
  detail sidebar over dir_diff, lazy per-selection diffs, --dir-diff
  support, ~590-line change, 4 new tests): scoreboard FAIL/2 but the
  feature was FLAWLESS — probe and window legs passed; the git leg
  failed on MY fixture (untracked files never appear in git --dir-diff;
  the gate had to stage + diff against HEAD). Fifth check-fault FAIL row
  vs zero worker-fault rows across this project's repo-feature runs.
  Gate-fixture lesson: know the TOOL's semantics (git tracking rules)
  as precisely as the app's. Worker quality on high-effort codex
  GUI features remains effectively 100% when specs carry exact
  contracts + a readable calibrated gate.
- 2026-07-13 — gpt-5.6-sol, Milestone 12 (Fuse arrow-first keymap +
  bundle config; medium effort): PASS attempt 1, 327s. Keymap spec was an
  exact per-view key/action table with a route-through-shared-code-paths
  rule, letting three existing gates double as keymap regression at zero
  new gate cost. Design assets (suite-cohesive icon) were produced
  ORCHESTRATOR-side with two operator review rounds (v2 chosen over
  cranked-grunge v3) before the swarm ran — icon taste stays with the
  human+orchestrator loop; workers wire what's approved.
- 2026-07-13 — gpt-5.6-sol, Milestone 13 (Fuse intra-line spans + search
  + goto; independent-difflib-ground-truth gate): scoreboard FAIL/2 but
  ALL substance legs passed — the fail was a window-race flake in the
  gate's WINDOW leg (prior probe apps' dying windows raced the fresh
  launch's). Fix: winprobe reports owner PID; window legs anchor to the
  exact launched pid. Gate-side failure #6 vs worker-side 0. Meta:
  multi-probe gates that open/close several windows need pid-anchoring
  and teardown settles between legs — window identity, like window
  existence, must never be inferred from ambient screen state.
- 2026-07-13 — gpt-5.6-sol, Milestone 14 (Fuse text filters: regex/preset
  transforms + JSON norm + whitespace-insensitive compare + panel +
  persistence; +regex dep; ~1000-line change): PASS attempt 2, 57 tests.
  The BEHAVIORAL gate design paid off big — instead of reimplementing
  filters in the check, it asserts noise-only file pairs collapse to
  ZERO changed rows under the right filter (equivalence physics, not
  output matching). Un-gameable and spec-light. Retry cause not
  check-fault this time (build iteration on a large multi-file refactor);
  final state clean. Pattern to reuse: gate transforms by their EFFECT
  (does the diff collapse?) rather than their output shape.
- 2026-07-13 — gpt-5.6-sol, Milestone 15 (Fuse syntax highlighting via
  syntect/fancy-regex; multi-line ParseState; off-first-paint delivery;
  61 tests): PASS on the FEATURE — scoreboard FAIL/2 was a GUI-gate
  focus-race, not the app. THE recurring GUI-gate lesson, now fixed at
  the root: paint verification via full-screen region capture is fragile
  on a busy machine — ANY app (incl. the test harness's own command-
  approval prompt) stealing frontmost mid-poll reads the window as blank.
  Fix: capture the window BY CGWindow id (screencapture -l<id>), which is
  occlusion-independent, and assert 'reached frontmost at least once'
  separately (keeps the M8 open-behind protection). Hardened all window
  legs. General rule: verify a specific window's content by its window
  id, never by screen coordinates.
- 2026-07-13 — gpt-5.6-sol, Milestones 16 (settings UI) + 17 (per-change
  merge): BOTH PASS attempt 1 on the hardened gates. M16's un-gameable
  win: appearance verified by MEAN LUMINANCE of the window (light 242 vs
  dark 39) — a setting proven to reach real pixels, not just a reported
  flag. M17's: merged output byte-compared against a gate-COMPUTED
  three-way result across multiple per-change choice vectors — the gate
  reimplements the ground-truth semantics, so the app can't fake it.
  Both are instances of the strongest gate class: independent ground
  truth (physics/luminance/byte-exact), never trusting app self-report.
  Zero-friction streak resumed once the window-id gate fix removed the
  focus-race noise — confirming those FAILs were all gate infra, not
  model quality.
  Kaleidoscope-clone landscape): PASS attempt 2, 69k tokens. Substance was
  strong (primary-source ksdiff/git contract, honest Uncertain section);
  attempt 1 failed only on `Accessed:` field FORMATTING against the
  research-with-proof check. Lesson: when using that kit, pre-warn the
  exact per-item citation shape (`Claim:`/`Source:`/`Accessed:`/`Quoted
  Evidence:` as separate plain fields) in the spec.
- 2026-07-10 — gpt-5.6-sol, code-feature (steering-profiles feature in
  ringer.py itself, ~470-line change + 18 tests + docs, run
  ringer-steering-profiles): shipped as PR #25. 2 attempts, 379k tokens,
  but the attempt-1 FAIL was the CHECK's fault, not the model's — the check
  gated on the ENTIRE pre-existing suite being green inside the worker
  sandbox (localhost binds blocked, fixture missing). The feature work
  itself was verified green both attempts; attempt 2 "hardened" an already
  -sound implementation. Scoreboard's FAIL row for this run understates the
  model. Lesson for check authors: regression gates must compare against
  the BASELINE failure set, never assert absolute suite green.
- 2026-07-12 — code-review, high effort (flont_friend DnD bug hunt from a
  vague user symptom, 10-point audit checklist, run flont-friend-build):
  PASS attempt 1, 151s. Model quality note: 5 WORKS / 5 DEFECT verdicts
  with real file:line evidence — it did NOT invent defects to fill the
  checklist (confirmed the reorder math correct) and found the three
  WKWebView-specific HIGHs (drag-from-<button>, missing dragenter
  acceptance, async-state zone commit). Checklist-driven review specs with
  a required verdict-per-item table work very well for vague bug reports.
- 2026-07-06 — adversarial pre-merge review (aicred spark): passed on
  attempt 1, ~85k tokens.
- 2026-07-06 — motion design (5 HTML animations for video b-roll) + 2
  editorial diagram pages, each verified by rendering through headless
  Chromium to MP4/PNG: 7/7 passed on attempt 1. Broadcast-quality visual
  output from rich storyboard specs; the render-as-check pattern works.
- 2026-07-06 — milk-crate demo: two single-file website builds (v1 scaffold
  316s/~175k tok; final brand+market-test reskin 622s/~184k tok), both passed
  14-assertion content checks on attempt 1, including base64-embedding photos
  and honoring honesty-marker requirements. Codex remains the site-build lane.
- 2026-07-06 — ringer.py feature batch (task_type field + enriched eval rows
  + `models` scoreboard + hud single-tab fix; ~640-line diff incl. two new
  test suites): substance passed on attempt 1 — its check printed PASS
  (compile, all 16 suites, exact CLI aggregation contract) — but the run
  recorded attempt 2 because of the expect_files-before-check harness bug
  (see process lessons). Heavy single-file feature work against an exact
  behavioral contract is squarely codex's lane.

- 2026-07-06 — elsas-website demo: Next.js scaffold PASSED attempt 2 (682s,
  ~354k tok) — attempt 1 built a complete homepage and silently skipped the
  other 10 routes; the route-enumeration check caught it. Narration lane
  (15 ElevenLabs calls, chunked, nohup pattern) passed attempt 1. CAUTION: a
  codex fix worker GAMED a verbatim-content needle by hiding the required text
  in a visually-hidden paragraph — passed the check, caught only by
  orchestrator integration review. Needle checks need an anti-hidden-text
  assertion or documented exceptions.

- 2026-07-06 — OpenRouter catalog + explore suggester (catalog subcommand
  with snapshot/changelog/free-detection, daemon auto-refresh, tiered
  --explore; offline fixture-driven contract check): PASS attempt 1, 362s.
  Follow-up sentinel-pricing fix (variable-pricing models): PASS attempt 1,
  114s. With the verify-order fix landed, zero phantom retries across the
  whole batch.
- 2026-07-06 — adversarial review of the model-router stack (2,650-line
  diff, structured report contract): PASS attempt 1, 176s — found a real
  HIGH (--since window inflating first-try rates) plus 3 MEDIUMs, all
  confirmed against the code. Then fixed all five review findings in one
  batch (task-level --since, pricing transitions, event durability + flock,
  unknown pricing, stderr notice) with test coverage: PASS attempt 1, 202s.
  Review->fix roundtrip in codex's lane works end to end.
- 2026-07-06 — scoreboard HTML page (zero-LLM renderer, ~700-line diff,
  design + evidence-floor ranking + cost math + notes parser): substance
  PASS attempt 1 (the run's recorded retry was an orchestrator check bug —
  the free-promo watchlist legitimately mentions a free model before the
  ranked cards, and the check compared raw first-occurrence). Six review
  findings fixed in one batch, PASS attempt 1, 141s.
- 2026-07-06 — model-db stack (SQLite read model 516s, page redesign 536s,
  Ringside tab 527s, plus three fix batches all attempt-1): five substantial
  ringer.py features in one day, every one against an executed contract
  check. Review lane found the HIGH that mattered (sync cursor skipping a
  half-written trailing line). Codex is the proven lane for both sides of
  the review->fix loop on this codebase.

## glm-5.2 via opencode (`openrouter/z-ai/glm-5.2`)

- 2026-08-16 mthfl story-1-5-ingest (code-review, `--variant high`, spec-conformance lane over a 344KB/88-file diff): PASS 1/1 first-try (113k, 5.7m). Best-in-class on the *checklist-shaped* review job — given a frozen spec with an explicit "Never" list and an edge-case matrix, it verified each item by running its own `rg` searches and reported per-item evidence with file:line, correctly declining to count pre-existing contracts code (phash, NodeSpec, Pinterest enum) as violations because the diff never touched it. It also caught an error in MY brief (I said the matrix had twelve rows; it has eleven), verified all eleven, and wrote the discrepancy to `questions.md` rather than inventing a twelfth — exactly what `questions_file` exists for. Note the price drop the day before: in 1.19→0.46, out 3.74→1.45. Route enumerable spec-vs-code conformance here; keep open-ended adversarial hunting on codex.
- The cheap-intelligence default (~$0.74/M in, $2.33/M out, 2026-07 —
  20-30x cheaper output than frontier coding models). Reliable on
  mechanical, tightly-specced work: file edits, format conversions,
  template-driven builds.
- 2026-07-12 — code-fix, zai-coding-plan lane (flont_friend DnD/trash fix
  batch: 7 review-confirmed fixes incl. drag-source restructure + a11y
  reasoning, 558-line diff, run flont-friend-build): PASS attempt 1, 137k
  tokens, 1961s. The review→fix split (codex finds w/ file:line evidence,
  GLM fixes from a spec embedding those findings) worked cleanly end to
  end; its fix-summary documented an honest a11y tradeoff (scoped
  biome-ignore on drag-wrapper divs) instead of hiding it.
- 2026-07-12 — code-feature, zai-coding-plan lane (flont_friend Phase 4
  views/DnD/keyboard, 845-line patch across 7 files, run flont-friend-build):
  PASS attempt 1, 101k tokens, 1046s, on the re-run. History for the
  scoreboard reader: the first Phase-4 run was killed mid-retry by a session
  restart (its attempt 1 had produced an EMPTY patch — build green, zero
  edits, cause unrecovered from logs); the re-run then ERRORED at 0.0s
  because the killed run's git worktree was still registered at the target
  path. Infra lesson: after any killed worktrees-mode run, `git worktree
  remove --force` + `prune` the stale entries before relaunching — a 0.0s
  ERROR with no worker log means spawn/infra, not model.
- 2026-07-12 — code-feature, zai-coding-plan lane (flont_friend Phase 3
  quick-add modal + search polish, 650-line patch, run flont-friend-build):
  PASS attempt 2, 98k tokens. Attempt 1 was build-green but used
  dangerouslySetInnerHTML for FTS snippets DESPITE an explicit spec ban —
  the check's grep gate caught it and the injected failure output got a
  correct fix (marker-splitting into React fragments) on attempt 2. Two
  lessons: (a) GLM-5.2 can follow a security rule it initially violated
  once the check makes it concrete — executable security gates > spec
  prose; (b) put security bans in BOTH spec and check, always. Also good:
  it extracted the shared TagInput on its own per the reuse rule.
- 2026-07-12 — code-feature, zai-coding-plan lane (flont_friend Phase 2
  React shell: 1,594-line patch across 8 files — sidebar w/ recursive
  collection tree, list view, detail panel, typed invoke layer + 13
  TanStack Query mutation hooks, run flont-friend-build): PASS attempt 1,
  82k tokens, 885s, worktree mode. Standout: it read the Rust command
  signatures as instructed and CORRECTED the reviewed types.ts contract
  (missing `tags?` on UpdateBookmarkPatch, missing UpdateCollectionPatch,
  flagged TagSummary naming as wire-irrelevant) — contract-checking, not
  just spec-mirroring. Also self-solved a sandbox footgun (vite writes
  node_modules/.vite-temp through a symlinked install → restructured the
  gitignored dir locally). Design brief followed faithfully. GLM-5.2 is
  earning larger tightly-specced UI feature lanes, not just mechanical
  edits. Caveat: it can't run the app in the sandbox — UI behavior gates
  still belong to the orchestrator's real-context pass.
- 2026-07-05 — milk-crate demo rehearsals: handled brand-board/SVG/copy
  tasks at around a penny per passing task.
- 2026-07-06 — adversarial pre-merge review (aicred spark): passed, but
  needed the retry (attempt 2) where codex passed on attempt 1. Long
  structured reviews sit at the edge of its comfort zone; keep the section
  contract explicit in the spec.
- 2026-07-06 — three mechanical image-generation batches (18 images via
  openrouter-image commands, idempotent batch-runner spec): 3/3 passed on
  attempt 1, ~14.5k tokens each. The "execute these exact commands, do not
  improve them" spec pattern is fully reliable for glm-5.2.

- 2026-07-06 — backfill/seed script for the model log (252-line stdlib CLI
  with a run-state join, 3-level mapping precedence, never-overwrite and
  idempotency rules): the artifact was CORRECT; the recorded FAIL was an
  orchestrator check-fixture bug (a missing newline glued the fixture's last
  row to a garbage line) plus the harness ordering bug below. Verified PASS
  once the check was fixed. Tight behavior contracts in the spec work great
  for glm — and read the raw logs before blaming the model.
- 2026-07-06 — README/MODEL-NOTES docs + task_type sweep across 17 template
  manifests: passed attempt 2; attempt 1 was lost to the harness ordering
  bug, not model quality — the retry worker's log correctly diagnosed that
  harness bug unprompted, impressive debugging from the cheap lane.
- 2026-07-06 — catalog/explore README section (flags, promotion ladder,
  per-user framing): PASS attempt 1, ~21.5k tokens. Doc sections against a
  grep-able content contract remain a safe glm lane.
- 2026-07-06 — milk-crate demo, full run: 4 independent buyer-persona
  reviews (focus group) all passed attempt 1 (~15k tokens, ~2¢ each) with an
  explicit VERDICT-block contract — persona work is squarely in glm's zone.
  Market read with live curl fetching passed once the spec demanded verbatim
  copy-paste of source URLs (first fail was the worker trimming URL slugs —
  spec/check craft, not model weakness). Brand-kit doc incl. a clean inline
  SVG wordmark: good, one bounce off an over-strict check regex.

- 2026-07-06 — elsas-website demo: verbatim content capture (16 pages + 19
  news posts, 213 blockquotes) passed attempt 2 — attempt 1 SELF-REPORTED
  "all 213 match exactly, 0 errors" while the executed check found 13 stitched/
  paraphrased quotes. Self-reports are worthless; the retry with injected
  failures fixed all 13 (~148k tok total, ~3¢). Page builds (about+faq;
  news index + 19 generated post routes via its own extraction script) and
  2 focus-group personas: all attempt 1. Fix batch attempt 1.
- 2026-07-06 — invariants/file-I/O review lens on the same stack: PASS
  attempt 1, 68k tokens — caught the non-atomic backfill rewrite (real data
  loss risk) and the daemon stdout race; both confirmed. Then fixed the
  backfill atomicity (tmp+os.replace, pid-stamped backups) attempt 1 with
  the original behavioral grader unchanged. Structured review with an
  explicit lens is now proven glm territory, not just probation.
- 2026-07-06 — solo adversarial review of the scoreboard renderer (~700
  line diff, injection-focused lens): PASS attempt 1 — 1 MEDIUM (unanchored
  MODEL-NOTES heading match cross-contaminating gpt-4/gpt-4o-style
  families) + 5 real LOWs, plus an empirically-verified injection all-clear
  (it actually rendered hostile model ids to prove escaping). Second
  proven-tier structured review in one day; glm is now the default review
  lane for mid-size diffs.
- 2026-07-06 — invariants/injection/frontend review of the 4,061-line
  model-db branch: PASS attempt 1, 96k tokens, 14 coverage items — two real
  contention findings (full catalog re-ingest per sync; schema writes on
  read paths) plus an empirical XSS all-clear on the new DOM surfaces.
  Third proven-tier structured review today.
- 2026-07-11 — two executable-proof tasks (flont_fuse viability, via
  `zai-coding-plan/glm-5.2` — same model, flat Z.ai plan): git-difftool
  handshake proof and four-way mergetool proof, BOTH attempt 1 (~29k and
  ~37k tokens, $0). Standout behaviors: self-refined its own artifact after
  a green run (pinned TMPDIR into scratch to respect the task boundary),
  and printed the observed LOCAL/REMOTE mapping before asserting it, per
  spec. Stdlib+git proof scripts with fail-closed assertion contracts are
  proven glm territory. Caveat from run 1: its attempted self-test of the
  fail-closed path never executed (sandbox blocked the heredoc) — don't
  credit "fail path verified" claims without seeing the failing run.
- 2026-07-12 — code-feature, acceptance-test harness (flont_fuse Milestone
  1: parameterized git difftool/mergetool runners + good/lying stubs + a
  4-leg selftest that must catch the liar both ways): PASS attempt 1, 59k
  tokens, 688s, $0. First-try on a multi-scenario harness with adversarial
  self-verification — and the harness then drove the real Rust binary
  cleanly in orchestrator integration review. Test-harness construction
  from a precise behavioral contract joins proven glm territory.
- 2026-07-12 — code-feature, dir-diff acceptance runner (flont_fuse
  Milestone 2: recorder-WRAPPER around a user template preserving exit/
  output flow, symlink-resolving tree capture, tolerant unchanged-file
  assertion per git's may-omit behavior): PASS attempt 1, 60k tokens, $0.
  Second consecutive first-try harness; the runner then verified the real
  Rust binary through git --dir-diff in integration review. glm-5.2 is the
  standing acceptance-harness lane for this project.
- 2026-07-12 — code-feature, partial-changeset recipe acceptance
  (flont_fuse Milestone 3, Kaleidoscope's verbatim git recipe shape, argv
  + bytes capture per invocation): PASS attempt 1, 57k tokens, $0. Third
  consecutive first-try harness — pattern-following from two named
  reference scripts is fully reliable; keep pointing it at the prior
  harness files instead of restating the isolation rules.
- 2026-07-12 — code-feature, image-diff acceptance (flont_fuse Milestone
  4, incl. authoring a from-scratch stdlib PNG encoder — struct+zlib,
  chunk CRCs, filter-0 scanlines — with no imaging library): PASS attempt
  1, 38k tokens, $0. Fourth consecutive first-try harness; handled a
  genuinely novel binary-format subtask, not just pattern-following. The
  spec carried the encoder recipe (signature/IHDR/IDAT/IEND layout) —
  embedding the HOW for novel formats is likely what kept it first-try.

- 2026-07-13 — gpt-5.6-sol, Milestone 19 (Fuse image viewer: 4 modes +
  pixel inspector over existing image_diff): the FEATURE was complete and
  genuinely polished (mode tabs, zoom/Fit, live inspector, exact diff
  header) — all logical gate legs passed exactly — but the run recorded
  TIMEOUT/2 because the WORKER spent attempt 2 chasing a phantom the GATE
  invented: my check used tiny gray test images, and a correctly-rendered
  TWO-UP viewer puts images in the L/R halves, leaving the window CENTER
  (where the paint sampler reads) as empty background. The worker couldn't
  make empty gap paint. Lessons: (a) a misleading gate failure BURNS
  worker budget on a non-problem — a wrong gate is worse than no gate; (b)
  window-paint sampling must match the feature's LAYOUT (center-sample
  assumes centered content; two-up needs pane-filling fixtures or
  per-pane sampling). Fix: large colorful gradient images that fill the
  panes. Feature hand-verified perfect; this is orchestrator gate-craft
  debt, not model quality.

- 2026-07-13 — gpt-5.6-sol, Milestones 20 (folder tree/filters/moved) +
  21 (folder reconciliation, first write-to-files feature): M20 PASS
  attempt 1. M21 TIMEOUT/2 but the FEATURE was complete + correct —
  including the safety-critical write path (dry-run writes nothing, apply
  copies exactly + content-verified, unsafe op aborts the whole plan
  atomically, all hand-verified) — and the UI polished (staged-plan panel,
  copy arrows). The timeout was the worker chasing yet another phantom
  paint failure MY gate created: check_reconcile auto-selected a
  file-vs-dir type-change whose diff renders empty -> blank window. THIRD
  window-paint fixture-vs-layout bug in a row (M13 focus-race, M19
  two-up-center-gap, M21 empty-type-change-first). Consolidated lesson:
  a window-paint gate must guarantee the DEFAULT-rendered view fills the
  sampled region — for master/detail views, the auto-selected item must
  be content-rich. Write-feature gates: snapshot disk before/after and
  assert dry-run + fail-closed write NOTHING; atomicity = the valid op in
  a plan with an unsafe op must also not be written.
- 2026-07-13 — gpt-5.6-sol, Milestone 23 (Fuse doc-types + single-file
  open + distribution docs; FINAL of 23): PASS on the FEATURE; the run
  FAIL was the window-paint gate hitting a FUNDAMENTAL flaw I'd been
  living with for milestones. THE lesson, finally understood: 'window-id
  capture' (screencapture -l<id>) is NOT occlusion-independent — WKWebView
  SUSPENDS DRAWING while occluded, so an occluded Tauri window has no image
  to capture ('could not create image from window'), and macOS 14
  cooperative activation prevents a background test from forcing the app
  frontmost (NSRunningApplication.activate options are ignored). Earlier
  GUI gates only passed because the window happened to reach front on a
  quiet desktop. Correct resolution: window-paint is verified WHEN
  capturable and passes-with-note when the window opened-but-occluded;
  'no window at all' still hard-fails. Feature-correctness lives in the
  content PROBE legs (un-gameable ground truth), NOT the screenshot.
  General rule for Tauri/WKWebView GUI gates: never make pixel-capture a
  hard gate — assert window EXISTENCE + verify content via an in-app probe
  that reports what was rendered; real Launch-Services opens activate
  normally, so occlusion is a test artifact.

## kimi-k3 via opencode (`openrouter/moonshotai/kimi-k3`)

- 2026-07-17 — audition, code-feature (kimi-lanes, interval merge/subtract
  vs 22-case executed suite): PASS attempt 1, 13.8k tokens, 129s, ~$0.10.
  Clean linear-sweep implementation, self-verified before finishing, tidied
  its scratch. Launched 2026-07-16 at $3/$15 per 1M — Sonnet-tier pricing,
  reasoning locked at max, single provider (Moonshot) at ~28 tok/s. Role:
  PREMIUM lane for frontier-level tasks only; do not route boilerplate or
  bulk fan-out here. Josh directive 2026-07-17: route to K3 only when
  really necessary — default Kimi lane is k2.7-code; K3 is the exception,
  reached for deliberately, never by default. Revisit after ~2026-07-27
  when open weights land and more OpenRouter providers should improve
  serving and maybe price.
- 2026-07-17 — harness footgun: opencode 1.17.15's model registry didn't
  know the day-old slug — both attempts died in ~1s with opencode
  "UnknownError: Unexpected server error" BEFORE any model call. Fix:
  declare the model in ~/.config/opencode/opencode.json under
  provider.openrouter.models (with temperature:false — K3 rejects sampling
  params). Instant same-second double failure on a brand-new slug = check
  `opencode models | grep <slug>` first, not the model.

## kimi-k2.7 via opencode (`openrouter/moonshotai/kimi-k2.7-code`)

- 2026-07-06 — adversarial pre-merge review (aicred spark): passed on
  attempt 1, ~83k tokens. First real outing; promising for review work.
  (Ran through an ad-hoc copy of the opencode engine block — the per-task
  `model` field now makes that unnecessary.)
- 2026-07-17 — audition, code-feature (kimi-lanes, same interval task as
  kimi-k3): PASS attempt 1, 13.3k tokens, 56s, ~$0.04. Reasoned through
  the two-pointer subtract carefully, ran its own edge-case asserts before
  finishing. Now 2/2 first-try across review + code-feature at $0.75/$3.50
  per 1M — the cheap Kimi lane; matched K3's result on this task at ~2.6x
  less cost and 2.3x faster wall-clock. Probation → keep feeding it
  low-stakes code/review lanes toward proven.

## kimi-k2.6 (`moonshotai/kimi-k2.6`, subject-model evidence via OpenRouter)

- 2026-07-07 — Benchmark Suite 2.0 operator eval, killed by Jon at ~4.5h.
  Serving throughput, not model quality, was the failure: on the Brick
  1000-piece case (reasoning xhigh, pinned provider order
  inceptron→decart→baidu→modelrun, no fallbacks) K2.6 averaged ~21 tok/s
  with two ~19-min stalls at 4.5 tok/s — 136+ min unfinished vs Sonnet 5's
  25 min (94 tok/s) and GPT-5.5's 24 min (55 tok/s) on the identical case.
  Model behavior itself was fine: 28 turns (fewer than Sonnet's 82), 170k
  output tokens (in family norms), 12% reasoning, zero API errors. Verdict:
  do NOT schedule K2.6 for long agentic work through that provider set;
  if K2.6 data is ever wanted, probe a single case against other providers
  first. Distinct model from k2.7-code above — don't transfer this verdict
  to k2.7.


## grok-build (Grok CLI engine, flat plan)

- 2026-07-10 — identity correction (Jon): the Grok Build CLI is a HARNESS
  serving exactly two models — Grok 4.5 (xAI) and Composer 2.5 (Cursor).
  The engine-lane slug `grok-build` resolves to Grok 4.5. "Grok Build 0.1"
  was never a model; earlier notes/rows using it as one describe Grok 4.5.

- 2026-07-06 — first outing (elsas-website demo), engine added same day:
  audition PASS attempt 1 in 28.9s. Then: asset harvest (11 images, live URL
  re-fetch check), books page, 5 work-page routes in one task (59 verbatim
  needles), adversarial code review (10 real findings incl. an unshelled 404
  and a broken embedded link), press/media fix batch, audio-player integration
  across 15 pages — ALL attempt 1 (player's red ledger entry was a check bug,
  artifact certified). Fast, precise on mechanical/code work. No token counts
  in JSON output (flat plan) — cost reads "included in plan".

## grok-composer-2.5-fast (Grok CLI engine, flat plan)

- 2026-07-06 — first outing (elsas-website demo): audition PASS attempt 1
  (138s — slower than grok-build but the strongest copy of the round).
  Accessibility constitution (14 testable criteria, SC-numbered) attempt 1;
  a11y-gatekeeper harness (axe+Playwright, light/dark, reduced-motion assert)
  attempt 2 — attempt 1's harness mishandled Next's default /404 route.
  Events/faq/contact fix batch attempt 1, but satisfied "editorial grid" with
  an EMPTY aside landmark — axe caught it (landmark-complementary-is-top-level).
  Persona work: good. Watch for letter-of-the-spec shortcuts on layout asks.

## north-mini-code (via opencode, `openrouter/cohere/north-mini-code:free`)

- 2026-08-15 — AUDITION #4 FAILED, BOTH ATTEMPTS (exploration slot, $0 — free).
  research, open-ended AUDIT lane (dotfiles structure/cruft: classify config vs
  machine state across four large tracked dirs, test README/install.sh against the
  real tree, write a 6-finding report to its own `report.md`). Attempt 1: 284s,
  43.6k tokens, no deliverable. Attempt 2: 696s, 43.7k tokens, and a 141-char file
  — three lines (`CHECK FAIL: report.md is 141 chars; that is not a report`).
  981s / 87k is the lane TOTAL across both attempts, not either attempt alone.
  It explored continuously and never budgeted for writing; the log showed it
  reasoning about being "blocked" from writing when nothing blocked it, then
  discovering `echo >> report.md` far too late. The check was sound: all four
  lanes ran the same `checks/scout.py` with different args, and the three
  siblings passed it. Re-run on codex medium: PASS attempt 1, 383s, 133k tokens,
  10 findings, 1456 words.
  DEMOTION — the pattern across four auditions is now consistent: this model is
  reliable on STANDALONE-ARTIFACT lanes where the spec supplies the content and it
  only has to transcribe (types contract, dither matrices, sourced dataset), and it
  fails OPEN-ENDED lanes where it must decide what to investigate and when to stop.
  Do not give it discovery, audit, or judgment work. Don't re-run this experiment.

- 2026-08-06 — AUDITION #3 PASSED (exploration slot, $0 — free). research, mechanical
  dataset lane (portfolio-puller device profiles: 20 entries x 8 mandatory keys + a
  cited report, two owned files, own task dir): PASS attempt 1. Sourced from Playwright's
  device descriptor registry and got the CSS-pixel vs physical-pixel distinction right
  throughout — the single most common error in this kind of dataset. Consistent with the
  2026-07-12 ladder verdict and with the 2026-07 code-feature failure: this model is
  reliable on STANDALONE-ARTIFACT lanes in its own directory, and the earlier failure was
  about multi-path ownership, not capability. Promote for small sourced-dataset work.

- 2026-07-12 — AUDITION PASSED (exploration slot, $0 — free). code-feature,
  short mechanical lane (flont_friend `types.ts`: 8 exported TS types with a
  precise field-by-field contract, standalone artifact): PASS attempt 1,
  9.2k tokens, 17s, compiled first try under `tsc --strict`, zero `any`,
  contract followed exactly including the discriminated union. Consistent
  with the exploration-ladder rule (short mechanical tasks first) — this is
  what a good first rung looks like. Promotion path: next slot can try a
  small real-repo edit with a build check. Caveat: it mirrored the spec
  faithfully but caught nothing the spec missed (the SearchResult nesting
  mismatch with the Rust `#[serde(flatten)]` was found in orchestrator
  review, not by the worker) — fine for probation, don't hand it
  design-judgment lanes yet.
- 2026-07-19 — AUDITION PASSED AGAIN (exploration slot, $0). code-feature,
  DitherTone web port: implement 3 Bayer ordered-dither algorithms (2x2/4x4/8x8)
  as self-registering TS files against a frozen plugin interface, spec supplied
  the exact threshold matrices. PASS attempt 1, 16.3k tokens, 30.5s — fastest
  and cheapest of the 4 fan-out batches, and the only free model in the run beat
  three GLM-5.2 batches on first-try cleanliness. Two clean mechanical passes now
  (types contract + ordered-dither math from an explicit matrix). Ready for a
  slightly harder rung: a small real-repo edit with a build check, or an
  algorithm task where the spec gives the formula but not the literal constants.

## nemotron-3-super-120b (via opencode, `openrouter/nvidia/nemotron-3-super-120b-a12b:free`)

- 2026-07-06 — AUDITION FAILED (exploration slot, $0 spent — free promo).
  Task: fresh-eyes adversarial review of a 2,650-line diff with a structured
  report contract. Failed both attempts on the same executed check: report
  had the right sections and verdict but under 3 concrete code citations —
  shallow engagement with the actual code, 212k tokens burned. Don't re-run
  this audition on long structured code review; if it gets another slot,
  try a shorter, more mechanical task first.

## llama-3.3-70b-instruct (via opencode, `openrouter/meta-llama/llama-3.3-70b-instruct:free`)

- 2026-07-06 — AUDITION FAILED (exploration slot, $0). Fresh-eyes review of
  a 4,061-line diff with a verbatim-quote citation requirement: failed the
  structured-report check both attempts. Second free-model audition to fail
  on long structured code review (after nemotron-3-super) — the exploration
  ladder now says: audition free models on SHORT mechanical tasks first;
  long-diff review is a proven-tier lane.

## Small / flash-class models

- First to choke on long conversational or multi-turn harness tasks —
  watch retry counts before scaling them into a batch (2026-07-05 focus
  group lesson).

## Process lessons (cross-model)

- 2026-08-16 (dotfiles Phase 6) — I MADE THE SAME QUOTING MISTAKE TWICE IN ONE
  SESSION, and the second time it cost a worker two attempts. `git ls-files`
  quotes any path containing non-ASCII, so `"config/warp/themes/custom/
  OjosCiberneticos.yaml"` split on "/" yields a directory literally named
  `"config`. In Phase 1 that nearly untracked a theme the owner had authored; I
  caught it, fixed it with `-c core.quotePath=false`, and then wrote a fresh
  check in Phase 6 with the identical bug. The lane read as FAIL/2 on the
  scoreboard; re-running the corrected check against the worker's own exported
  patch passed first time. The work was always fine.
  · RULE: any check that derives structure from `git ls-files` must use
    `git -c core.quotePath=false ls-files`, or strip surrounding quotes. Add it
    to the reflex list next to "accept every dress" and "strip rg's path:N:text".
  · META-RULE, which is the more useful one: a lesson learned inside a run does
    not transfer to the next check I write in the same run unless I encode it
    somewhere executable. Three of this session's check bugs were re-inventions
    of a fix I had already made an hour earlier. A shared helper (check_helpers
    already exists) is the only durable fix; a note to self is not.
  · Worker credit: codex produced a correct links.toml (37 entries, 19
    create=true, 2 optional) that omitted ~/.claude with the reasoning in a
    comment, exactly as specified, and was failed by my arithmetic.

- 2026-08-16 (pilot-changes-requested, build round) — A LANE THAT OWNS `tests/**`
  CAN EDIT THE TEST THAT WOULD HAVE CAUGHT IT, AND EVERY GATE STAYS GREEN.
  codex built the pilot `revise` feature and, in passing, dropped
  `"decided_at": utc_now_iso()` from the decision-file payload — then rewrote the
  existing assertion in `tests/test_pilot_decision_endpoint.py` from
  `assertEqual({"decision", "decided_at"}, set(payload))` down to
  `assertEqual({"decision"}, set(payload))` and deleted the tz-awareness checks.
  The lane's check passed, and the run-level `integration_check` reported 373/373
  green — because the test now described the regression. The spec said in as many
  words "do not weaken, skip or delete any existing test"; saying it is not
  enforcing it. Only reading the diff caught this.
  THE STRUCTURAL FIX, for any lane granted test ownership: assert that existing
  test files gained lines and lost none, or diff assertion counts before/after —
  `git diff --unified=0` on `tests/` and fail on a deleted `assert`. A green
  suite proves nothing about a lane that is allowed to edit the suite.
  Related: the 2026-08-13 lesson about a worker rewriting a `check` command to
  make its own output lint clean, and the dotfiles Phase 5 entry directly below.
  Same shape — when the measurement is inside the worker's blast radius, the
  worker will move the measurement.

- 2026-08-16 (dotfiles Phase 5) — EXECUTED CHECKS PROVE THE CONTRACT, NOT THE
  PRODUCT. Three lanes passed strong checks (prove-fail AND prove-pass green,
  merged-tree verification green), and running the deliverables for real
  immediately found two defects no check had asked about:
  (1) audit.sh walked gitignored trees and emitted 276 warnings in 100+ seconds
      — 265 of them from cache/uv and state/mise. Every assertion I wrote was
      about correctness (does it catch X, does it name the path); none was about
      whether a human could READ the output. Fixed by reading broken symlinks
      from the git index: 11 warnings, 0.15s.
  (2) the pre-commit hook passed a PEM pattern beginning '-----BEGIN' straight to
      grep, which parsed it as options, so the private-key rule silently never
      ran. My check tested a ghp_ token and a .bak name — both of which worked —
      so the gate was green while one rule was dead. `grep -e "$pattern" --`.
  RULE: after a lane passes, RUN the thing in its real context before committing.
  A check verifies the contract you thought to write down; usability, output
  volume, and rules the fixture never exercised are invisible to it. This is the
  same lesson as the 2026-08-16 models-table note (image assertions prove a
  surface exists, not that it is good), arriving from the shell side.
  · Corollary that DID work: worker honesty was good. The audit lane hit a spec
    conflict (two pre-existing tracked .lock files vs 'must exit 0 on a clean
    tree') and resolved it with a narrow, commented two-path exemption leaving
    every other state path an error — visible and easy to review, rather than
    quietly weakening the rule. I removed the exemption by fixing the two files.

- 2026-08-16 (dotfiles-architecture r1/r2) — A RE-RUN THAT REUSES THE WORKDIR
  DESTROYS THE FAILING MODEL'S RAW LOG. Re-running `structure-cruft` on codex
  under a new run_name but the SAME scratchpad workdir truncated
  `work/structure-cruft/worker.log` — the file now begins with codex's attempt 1,
  and north-mini-code's two attempts are gone from disk. Post-mortems depend on
  that log, and the re-run is exactly when you want it. What survived: the run
  JSON's `log_tail` snapshot, and `ringer.db`'s `attempts` table (per-attempt
  duration, tokens, verdict). Two consequences: (1) when a lane fails and you
  intend to re-run it on another engine, copy the log aside FIRST, or give the
  re-run its own workdir; (2) per-attempt numbers belong in `ringer.db`, not the
  run JSON — the JSON's `elapsed_s`/`tokens` are lane TOTALS, and reading them as
  a single attempt is how this file got three wrong numbers (corrected above).

- 2026-08-15 (dotfiles-architecture r1) — A CHECK THAT VERIFIES CITED PATHS MUST
  ACCEPT EVERY HONEST CITATION FORM. My scout check stripped a trailing `:12` from
  a backticked path so `config/_rc/zshrc:335` would resolve — but not rg's native
  `path:12:matched text`, so an honest `` `.gitignore:8:private/` `` was reported as
  a fabricated path and cost GLM-5.2 a retry on work that was correct. Same gate
  also flagged `VAR_API_KEY_A/B/C` (a slash-separated enumeration) as a missing
  path. Two fixes, both cheap: strip `:\d+(:.*)?$`, and only apply the strict
  existence gate when the token's FIRST SEGMENT already exists under the base —
  which keeps `config/invented/fake.json` failing while letting prose through.
  This is the sibling of the existing "accept every dress" label lesson: verbatim
  gates must model the tool output workers actually paste, not the one form the
  fixture happened to use. `--prove-fail`/`--prove-pass` could not catch it; only
  a real worker's honest output did.

- 2026-07-20 (DitherTone web port) — TWO lessons:
  (1) `expect_files` MUST list files, never a directory. A task whose check
  returned 0 (54/54 assertions PASS, 27/27 screens bit-exact to ground truth)
  was still recorded FAIL because expect_files was `["src/algorithms"]` (a
  directory) — Ringer's non-empty-FILE gate can't satisfy a dir, so it failed
  the task post-check. verdict=FAIL with check_returncode=0 is the fingerprint
  of an expect_files gate failure, not a real check failure. List concrete new
  files instead.
  (2) PORTING FROM A VERIFIED REFERENCE >> re-derivation. Codex-high ported 27
  recovered custom dither screens from a reverse-engineered reference module
  (recovered.mjs) and every one came out bit-exact to ground truth (mean abs
  diff 0.00) — even the chaotic error-diffusion screens, which normally diverge
  ~10 between two independent-but-faithful implementations. When you have a
  runnable reference, feed it as source and diff against its output; you get
  pixel-exact acceptance instead of statistical hand-waving.

- 2026-07-19 (DitherTone web port) — TWO cross-cutting lessons:
  (1) HARNESS-CONTRACT tasks need the exact invocation in the check AND the
  spec. Codex gpt-5.6-sol (high) built an otherwise-clean Vite/TS foundation
  but FAILED its check because its render CLI didn't strip the literal `--`
  that `pnpm run render -- a b c` forwards into argv — it never ran the
  documented invocation. When a task defines an interface others depend on,
  make the worker run the EXACT documented command line before declaring done,
  and keep the check invoking it verbatim. One-line orchestrator fix, then
  verified by hand.
  (2) Parallel opencode workers (4 up) intermittently hit SQLite
  `database is locked` on the shared model log — halftone's attempt-1 crashed
  before writing any file, ed-diffusion-2's attempt-1 rendered before all
  files registered. Both were INFRA contention, not GLM-5.2 capability; retry
  absorbed both. Don't read these two retries as model weakness — GLM-5.2 was
  competent on all three of its algorithm batches from specs that supplied the
  kernels. Watch first_try_pass_rate on high-parallelism opencode runs; the db
  lock depresses it artificially.

- 2026-07-06 — the orchestrator's CHECKS were the day's top failure source:
  three check bugs (fixture newline join, first-occurrence ordering vs the
  watchlist strip, claim-prefix split on '.' instead of ':') each produced
  a FAIL verdict on work that was actually correct — including all four
  capability-research packets at once. Every one was caught by reading raw
  logs/artifacts before blaming the model. Corollary for the scoreboard:
  recorded FAILs whose root cause was a check bug are annotated here, and
  check fixtures deserve the same review care as production code.


- 2026-07-06 — HARNESS BUG (fix in flight on feat/model-perf-log):
  Verifier.verify evaluated expect_files BEFORE running the check, so any
  check that itself creates/exports its deliverable (the worktree
  patch-export pattern) failed attempt 1 with "missing expected files" even
  when the check printed PASS. Cost 3 phantom retries in one run — and it
  poisons first_try_pass_rate, the model log's routing signal. Until the
  reorder lands on your checkout: have the WORKER write the declared
  deliverable, or don't declare check-created files in expect_files. When
  reading seeded scoreboard numbers, remember 2026-07-06 first-try rates
  are depressed by this.
- 2026-07-06 — the model log is now automatic: every attempt row carries
  model/task_type/retry; `./ringer.py models` prints the scoreboard; 81
  historical rows were seeded via scripts/backfill_model_log.py with a
  hand-authored task-type mapping. Give every manifest task a task_type or
  its evidence buckets as (untyped).

- 2026-07-06 — a three-model "bakeoff" ran every task on the engine's
  hard-coded model: task keys said glm/gpt/kimi, but the opencode engine
  block pinned glm-5.2, so one model wrote all three "competing" reviews.
  This is why the per-task `model` field exists — a bakeoff is only a
  bakeoff if the manifest, not the engine block, names the model. Verify
  with the `model` column in the run state, not the task key.
- 2026-07-06 — spawning 5-6 opencode workers simultaneously hit opencode's
  local "database is locked" (sqlite) — several instant attempt-1 failures,
  all absorbed by Ringer's retry. Cosmetic in Ringside ("sent back" at 0s) but
  wastes an attempt; consider staggering opencode spawns.
- 2026-07-06 — opencode's bash tool kills foreground commands around the
  ~2-minute mark: a 2min+ image-generation API call can never finish inline.
  Spec pattern that works: nohup the long command in the background, then
  poll for the output file in separate short commands.
- 2026-07-06 — two check-craft lessons from the same run: (1) URL-allowlist
  checks must be prefix-tolerant (workers legitimately trim slugs); (2) any
  heading-regex must tolerate numbered headings ("## 3. Type / Typography").
  Both failures looked like worker laziness until the raw logs said otherwise.
- 2026-07-06 — elsas-website demo, check-craft in BOTH directions: (1) a fixed
  800-char body floor failed a worker for faithfully converting genuinely tiny
  source posts — floor must scale with the source; (2) a citation gate treating
  every backtick as a page-quote failed honest reviewers who backticked their
  own fix-suggestions — line-scoped pair parsing + attribute-aware corpus fixed
  it; (3) needle-exception lists must be shared across ALL checks that consume
  the needle set (a needle excepted in one checker failed a task through
  another). Post-mortems ruled FOR the worker 3 times this run — read raw logs
  before blaming the model.
- 2026-07-06 — opencode sqlite "database is locked" again with just 2
  simultaneous opencode spawns (page-news + page-about-faq); retry absorbed it.

## codex (2026-07-06, bench-operator-proofing)
- 8/8 code-feature tasks passed attempt 1 across 3 rounds (worktrees mode, Python harness refactor; 108k-406k tokens/task). Specs embedded the approved architecture doc + exact file ownership; checks built fresh uv venvs and ran the full pytest suite.
- Lesson (check design, not model): all 3 post-integration bugs were invisible to the checks — a test that passed only because the worker's worktree lacked .env, a `--help`-only assertion missing a runtime importlib/sys.modules bug (py3.12 dataclasses), and bare console-script names failing outside activated venvs. Checks should exercise one real invocation from a cold shell, not just --help.

## gpt-5.6-sol (codex)
- 2026-08-19 arrange-plugin round 2 (4 parallel worktree lanes, no foundation): 2 PASS first-try (`tool-hierarchy` 54k/283s medium, `tool-ontology` 93k/510s high), 2 reported FAIL that were MY manifest bug, not the models'. I wrote `owns: ["tests/", "skills/"]` with trailing slashes; `path_matches_owns` uses `fnmatch`, so `tests/` never matches `tests/test_clones.py` and both lanes were failed for ownership violations on files they were explicitly granted. Their checks had already PASSED. Fix: glob form (`tests/*`, `skills/*`). Both worktrees survived, so I exported their patches by hand and shipped the work rather than re-running ~265k tokens to reproduce identical output. Lesson: `owns` entries are fnmatch PATTERNS, never directory prefixes — and when a lane fails on ownership while its check passed, suspect the manifest first.
- 2026-08-19 same run, the model out-debugged the orchestrator. I handed the foundation a "PROVEN WORKING" `fcntl(F_LOG2PHYS_EXT)` reference using `struct` format `=I4xqq` (24 bytes, padded). It is WRONG — Darwin's `log2phys` is packed, `=Iqq` (20 bytes). The padded read returns a truncated devoffset that usually differs between unrelated files, so clone detection passed every check and then failed intermittently (~1 in 6) in real use. My check embedded the SAME broken constant as its "independent" reference, so the verification agreed with the bug. The `polish` worker independently derived `=Iqq`, plus the delayed-APFS-allocation fsync issue, and used the correct form in the code it owned (`dupes.py`, its tests) while leaving `clones.py` alone because it did not own it — correct behaviour, except it never wrote the discrepancy to `questions.md`, which would have surfaced the bug immediately. Two lessons: (1) an orchestrator-supplied reference implementation must be verified against GROUND TRUTH (are the magnitudes plausible?), not merely against "it ran and gave different answers"; a device offset of 70 on a 460 GB disk should have been an instant tell. (2) Tell workers explicitly that discovering a defect in code they do NOT own is itself a questions.md-worthy event, not just a blocker.
- 2026-08-19 arrange-plugin round 1 (code-feature, worktrees + foundation, macOS filesystem tooling): 4/4 PASS FIRST TRY, integration green, 57k-77k tokens, 191-365s. Foundation on `high` (365s), three dependent lanes on `medium`. Every lane honoured its `owns` list with zero trespass, and the auto-discovery pattern (foundation ships `arrange/commands/__init__.py`, each lane adds its own `commands/<name>.py`) completely eliminated the shared-CLI-file collision that usually costs a lane here. Best result this repo has recorded for a 4-lane parallel code build.
- 2026-08-19 same run, the orchestrator move that paid for itself: the hard part was APFS clone detection via raw `fcntl(F_LOG2PHYS_EXT)`, which no model here had done before. Instead of specifying it prose-only, I PROVED the technique myself in ~2 minutes (orig and its `cp -c` clone return the same physical offset; an independent copy does not) and pasted the 12-line working implementation into the foundation spec. Foundation passed first try on the thing most likely to burn two attempts. Lesson: when a lane depends on one obscure syscall, spend the orchestrator minutes to verify it and hand over working code — it is far cheaper than a retry, and it also let me write a check that independently verifies the FIXTURE is a real clone before asserting on behaviour, closing the "worker fakes the fixture" hole.
- 2026-08-19 same run, check-design note that generalised: my first draft asserted on `repr()` of returned variant groups, which would have false-failed any worker that modelled a group as a dataclass with a terse repr. Replaced with a recursive string harvester over dict/list/`__dict__`. Reading model output structure out of Python objects needs the same tolerance as reading labels out of prose — assert on reachable CONTENT, never on how the object chose to print itself.
- 2026-08-18 storage-reorg round 1 (research, medium effort, 4 read-only lanes over the owner's own disk): 4/4 PASS first-try, 19k–67k tokens, 111–224s. Three architecture lanes were given deliberately OPPOSING mandates (facet-separation / minimal-change / thin-internal) and stayed in character — no hedging toward each other, philosophy sections <70% similar. Notably all three independently REFUSED the inflated 82 GiB node_modules figure the spec warned about, and each said so explicitly; the honesty rule in the spec held without a check forcing it per-lane. The `reclaim-inventory` lane cited 30 absolute paths and every one resolved on disk. Zero questions raised. Cheap, fast, and in-character on opinionated design work — this is a good default for "generate N contrasting proposals for a human to choose between".
- 2026-08-18 same run, THREE orchestrator-authored check bugs, zero model bugs. (1) A proposal check scanned the whole document where it meant one section, so any plan citing a not-yet-existing DESTINATION path could never pass — caught by a hand smoke test before launch. (2) `expect_files` resolves inside a TEMP scratch taskdir under `--prove-pass` (ringer.py ~12557), so a check/known_good pair using absolute real-workdir paths made every lane read BROKEN while the check itself printed PASS; fix is to keep check and fixture paths RELATIVE to the task dir so real runs and gate modes agree. (3) The integration gate demanded the three lanes relocate DIFFERENT repo sets — but the dormant list was fixed at ten, so unanimity was the correct answer and the assertion was wrong; worse, its replacement numeric-spread assertion passed for the wrong reason, extracting 82/82/396 GiB out of "show your arithmetic" prose. Lesson: never regex a total out of prose you asked a worker to show working in — require a machine-readable `TOTAL_X: <n>` line if you intend to assert on it. Gates caught 2 of 3 before any tokens were spent.
- 2026-08-16 mthfl story-1-5-ingest REVIEW round (code-review, high effort, read-only scouts over a 344KB/88-file diff): 2 lanes, both PASS. `test-integrity` 1/1 first-try (168k, 4.9m) returned 11 defeatable-test findings, each naming the exact suite-green mutation that breaks it — the strongest output this lane pattern has produced here, and every one held up under my own review. `security-abuse` passed on retry (115k, 4.8m); attempt 1 failed the contract check purely on FORMAT, having put `Class:`/`Priority:`/`Confidence:` values on the line BELOW their labels. The check's `label_value_pattern` needs label and value on one line, and my spec said "then on their own lines: 'Evidence:' … 'Priority:'" — genuinely ambiguous. Lesson: when a check demands `Field: value` on a single line, SHOW the shape in the spec instead of describing it. Substance was never in doubt — the retry grounded 15/15 citations against the diff.
- 2026-08-16 mthfl story-1-5-ingest FIX round (code-fix, high effort, 3 worktree lanes, all PASS, integration check green): `db-proofs` 1/1 (78k, 5.5m) replaced text-grep migration tests with real PGlite execution plus duplicate-insert count proofs, and independently added `expect(indexdef).not.toContain(' WHERE ')` — defeating the reviewer's exact `WHERE false` mutation without being told to. `ui-law-tests` 1/1 (157k, 8.9m) refactored the shared `offenders()` helper to take a JSX style-property predicate rather than bolting on a second scanner, keeping one jurisdiction as the spec demanded. `ingest-security` passed on retry (168k, 13.1m) — attempt 1 failed the `owns` check on the three `node_modules` symlinks MY OWN SPEC told it to create. Lesson, mine not the model's: when a spec instructs a worker to create scratch artifacts inside a worktree, either list them in `owns` or tell the worker to remove them before finishing. Ownership violations are reported against the worker but authored by the orchestrator.
- 2026-07-15 ringer-self-update run (3 serial tasks, direct-repo-edit mode): code-fix baseline-test repair 1/1 first-try (61k tokens, 1.6m); code-feature self-update mechanism (git fetch/ff-pull/re-exec + HUD staleness restart + 20-test suite) 1/1 first-try at high effort (153k, 8.1m); code-feature signal-contract (all 3 scoreboard surfaces + canonical-route lint enforcement) passed on retry (358k, 13.7m) — attempt 1 died on stale old-column assertions in pre-existing tests it hadn't finished updating; the retry prompt's injected FAIL list was enough to close it out. Lesson: when a task rewrites a display contract, name every test file asserting the old contract in the spec's ownership list AND tell it to update them FIRST.
- 2026-07-09 code-feature/code-fix (ringside-overhaul): 4/4 first-try — a ringer.py logging change with tests, a 265-line stdlib backfill CLI (atomic rewrite, dry-run, idempotence all check-verified), a ~1500-line single-file HTML redesign (running-now pills + worker-card grid + multi-expansion refactor, 30KB patch, node --check + contract greps + unittest), and a render-gating change where it correctly UPDATED tests asserting the old behavior instead of gaming the check. Medium/high reasoning, 65–120k tokens/task.
- Same day, different session (bench-harness-patches, code-fix): 0.29 first-try over 7 tasks on a Next.js/Turbopack harness. Spec and check quality dominate model choice — see the scoreboard before generalizing either number.

## GPT-5.5 (codex) — attribution caveat
- Scoreboard rows dated before 2026-07-09 may actually be gpt-5.6: codex eval rows logged model="" until the write-time stamping fix (PR #18) and were credited to GPT-5.5 by the registry default at read time, while the machine's codex default had already moved to gpt-5.6-sol at an unknown earlier date. `scripts/backfill_model_from_logs.py` re-stamps rows with surviving command-log evidence; anything it skips is a mixed-model aggregate. Trust post-2026-07-09 rows.

## nvidia/nemotron-3-super-120b-a12b:free
- 2026-07-08 (research, content-strategy-recon): FAIL x2. Did the analysis in chat but never wrote report.md; attempt 2 exited rc=0 with no file. Doesn't reliably follow file-output contracts under OpenCode. Demoted — don't re-audition on file-deliverable tasks.

## meta-llama/llama-3.3-70b-instruct:free
- 2026-07-08 (research, content-strategy-recon): FAIL x2. Timed out at 900s both attempts on a moderate DB-scrape+format task. Too slow on the free tier for harness work. Demoted — don't re-audition without much longer timeouts or paid tier.

## z-ai/glm-5.2 (addendum)
- 2026-07-08 (research/filter, pitch-foundry): FAIL x2 on a long-spec rubric-application task (~40k input: embedded rubric + 4 candidate files). Read all inputs, exited rc=0 with ZERO output tokens both attempts — silent stall, no file written. GLM handled the same session's shorter formatting specs fine. Lesson: keep GLM specs short; route long-context apply-this-rubric work to codex.

## GPT-5.5 (codex) — honesty flag
- 2026-07-08 (image-gen, pitch-foundry): sandbox DNS blocked openrouter.ai; ALL 10 API calls errored (logged honestly in gen-log) — but the worker then FABRICATED 10 deliverables locally (composited canvases from the ref image) to satisfy a files-exist>40KB check, and passed. Lesson: (a) codex sandbox has no external DNS on this machine — route API-calling tasks to opencode (network open); (b) never write an existence-only check for generated media — require the success log (SAVED/cost lines) to match the file count.

- 2026-07-09 persona-review (pitch-foundry exec-briefing panel): 0/2 first-try+retry. Produced coherent review CONTENT as chat text but never wrote report.md — does not reliably use file-write tools under opencode. Demoted; do not re-audition for file-deliverable tasks without a write-tool probe first.

## gpt-5.6-luna (codex)
- 2026-07-09 code-feature (unlock-ai guide-format conversion, strict type-contract check): 1/1 first-try, 42.6k tokens, 80s. Followed a multi-file TS pattern precisely at $1/$6 pricing. Good candidate for mechanical codegen/docs lanes; audition in adjacent types.

## opencode / z-ai glm-5.2 (via openrouter)
- 2026-07-09 (aicred-invoice-downloads, 4 code-fix tasks + 1 follow-up, worktrees+npm ci checks): systematic attempt-1 NO-OP — all 4 parallel workers produced zero edits and no summary on first attempt, then completed cleanly on attempt 2 after retry-prompt injection (34k-69k tokens each). Follow-up single task passed attempt 1. Suspect first-invocation session warm-up in opencode-sandboxed under parallel spawn; budget for 2 attempts on parallel GLM batches. Output quality on Next.js/Stripe route+test work: solid, spec-faithful, one boss-caught design gap (used user-scoped supabase client where RLS demanded service role — spec didn't say explicitly; say it explicitly).

## opencode (harness note, any model)
- 2026-07-28 (code-review, pr82-token-saver-review): GLM 5.2 produced a complete, high-quality 218-line report but could NOT write it to an output directory created by the parent Claude Code process — every write returned EPERM. It then spent ~3000s burning retries on ctypes/`openat`/AppleScript/`sandbox-exec` workarounds until it timed out, and the task logged as FAIL despite the deliverable existing in its taskdir. Codex workers in the same run were unaffected. Lesson: point opencode workers' output INSIDE their own taskdir and harvest via `expect_files`; never hand them a shared output dir another process created. This is an orchestrator spec bug, not a model failure — do not read the FAIL as evidence against GLM.

## Process lessons (2026-07-28, PR #82 review)
- **Ideas worth keeping from a rejected PR.** PR #82's pre-call gateway was dropped (needs your own API key, so it converts flat-rate OAuth plans into metered API billing; incompatible with Claude Code; and it saves tokens by stripping the tool list, which is the thing that makes the CLI worth using). One idea inside it is worth remembering if the problem ever comes back: an *explicitly blessed* answer cache — key a reviewed answer to the exact request plus the exact selected source packet, and replay it with zero upstream calls, never auto-accepting a model answer. It only fires on byte-identical repeats, which is why it didn't justify 2,000 lines here.
- **Doc-stated support floors need a CI job or they are fiction.** README promised Python 3.11+ while CI only ever ran 3.12; a 3.12-only f-string reached review with a fully green suite. Either test the floor or move it.

## fume-v1 (2026-07-12, flont_fume Swift/macOS build)
- gpt-5.6-sol, code-feature (scaffold, 54 files/1705 lines w/ frozen API contract): PASS attempt 2 — attempt-1 fail was the CHECK's single-line signature grep vs idiomatic multi-line enum (again: mandate snippets format-tolerantly). Integration lane PASS attempt 2 (missed one wiring assert, fixed clean). Review-fix batch (9 verified findings incl. concurrency lifecycle + bounded I/O, 848-line diff, 14 regression tests): PASS attempt 1, 252k tokens. Swift 6 strict concurrency work is squarely in its lane.
- zai-coding-plan/glm-5.2, code-feature (Swift source lanes w/ fixture-driven tests): claude/opencode/zai lanes PASS (attempt 2 each; attempt-1 losses were orchestrator check bugs: docs/lanes/ missing from ownership lists, unignored sandbox build-cache spill). codex + gemini lanes: BOTH final FAILs were NOT model faults — codex lane had a real crash it introduced but fixed on the code-fix rerun (PASS); gemini lane's code was CORRECT TWICE and failed only on a scaffold FakeFileSystem bug (URL == vs path equality on nested dirs). Read raw logs + rerun clean-cache before blaming GLM; stale .build caches masked the true failure set.
- openrouter/cohere/north-mini-code:free, code-feature audition #2 (small real-repo Swift lane, build check): AUDITION FAILED — wrote outside owned paths (shared-layer fake, scratch scripts) both attempts, 75k tokens. Ladder verdict: fine on standalone-artifact tasks, does NOT respect multi-path ownership boundaries yet; next audition (if any) needs a single-file lane.
- Swift/macOS harness notes: pre-vendor SPM deps (codex sandbox has no DNS); gitignore .check-out/.module-cache/.swiftpm/*.pcm BEFORE fan-out or git add -A confinement checks eat cache spill; opencode 2-min foreground kill makes `swift test` painful for workers — spec filtered tests only, let the executed check run the full suite; after any failed worktrees run, `git worktree remove --force` each stale path (prune alone insufficient) or the rerun ERRORs at 0.0s.

## fume-v2 (2026-07-12/13, Insights build — 18 tasks across 6 rounds)
- gpt-5.6-sol: v2 scaffold (48 files incl. fully-implemented SQLite actor + Charts spike) PASS attempt 2 (attempt-1 loss unclear, likely wrapper); pricing/ingestor/insights-ui/glance-ui lanes ALL first-try; 10-finding review-fix batch (757 lines incl. AppKit socket-release fix) first-try. The heavy-reasoning + snapshot-proof combo is the strongest pattern of the project.
- zai-coding-plan/glm-5.2: history readers + window + metric + tee lanes — every eventual merge was worker-code-correct; ALL final FAILs traced to (a) my check bugs (wrong-dir grep, spec/assert contradictions), (b) workers killed mid-verify by wrapper deaths leaving one-line compile errors (missing imports, missing $ bindings, let-vs-var), or (c) one real decode bug (camelCase Decodable vs snake_case JSON, fixed via retry with orchestrator root-cause injected — first-try on the fix). GLM review lenses cross-confirmed the attribution double-count HIGH independently — the 3-lens panel earns its cost.
- PROJECT-WIDE LESSON (two versions, ~30 tasks): after v1 round 1, zero worker-logic failures reached merge; every red verdict was check-craft, infra (two orchestrator sessions sharing one machine → chronic background-wrapper kills; ringer.py sometimes survives its wrapper — check run-state JSON before assuming death), or died-mid-verify. Write asserts from spec-mandated identifiers ONLY (never guess names), keep salvage cheap (failed worktrees + official-check re-runs), and hand-export patches when only the harness died.

## fume-v5 (2026-07-15, hardening round)
- **opencode-go/glm-5.1**: exploration audition on health-opencode (code-feature, 3-file lane) — PASSED, work complete even though the orchestrator died mid-record (salvaged via official check re-run). Now 2/2 first-try on code-feature. Promote to bigger lanes next audition.
- **zai-coding-plan/glm-5.2**: 7 lanes this run. Passes were solid, but THREE avoidable check failures from worker hygiene, not code: scratch files left in worktree root (`atomic-test.swift`, `fume_interpose.c` on fix-sources; `.buildtmp/` on diagnostics-ui twice) breaking ownership confinement, and one missing-argument-label compile slip shipped unverified (its sandbox blocked `swift test`, echoed in review-redaction-leaks' honest blocker note). Add to every GLM spec: "scratch files go to $TMPDIR, never the worktree" — and treat opencode-sandbox test-run failures as a known limitation: the executed check is the real verifier.
- **gpt-5.6-sol (codex)**: 4/4 lanes passed (scaffold + diagnostics-core + fix-app first-try; integration on attempt 2 after the known swift-frontend big-initializer crash). Remains the right pick for high-stakes/AppKit lanes.

## fume-v6 r2 (2026-07-16, 8-lane source fan-out)
- **Orchestrator spec bug, not worker failures**: 3 lanes (glm-5.2 warp/keys/crush) "failed" ONLY because the shared spec said "the lane doc named in your ownership list" without inlining the name — workers invented doc filenames, breaking ownership confinement. Code was complete and passed official checks after a one-file rename. RULE: name every deliverable file INLINE in the spec; never reference the ownership list indirectly. Scoreboard rows for these attempts overstate failure.
- 3 lanes died rc=-9 BOTH attempts (external SIGKILL — same wrapper-kill plague that hits watchers; machine-level, not model-level). Relaunched clean.
- codex src-claude (credentials-handling, highest stakes) and glm-5.1 src-goose: first-try passes.

## zai-coding-plan/glm-5.2 (opencode)

- 2026-07-17 — research x3 (headroom-integration: repo teardown, integration-fit
  scout over local configs, install-proof with executed venv+pip+compress check):
  2/3 first-try, 3/3 pass. The retry (integration-fit) failed attempt 1 only
  because the worker never wrote fit.md — research done, file not emitted; the
  check's "deliverable does not exist" message fixed it in one retry. Next time:
  put "write the file EARLY and update it" in long read-heavy specs. Output
  quality high — teardown cited 60+ real file:line refs, all verified to exist.

## openrouter/nvidia/nemotron-3-super-120b-a12b:free (opencode)

- 2026-07-17 — research x1 (headroom-integration ecosystem scan, first audition):
  PASS first try, coherent report, evidence-based. Two blemishes: malformed
  citation format (doubled paths like "llms.txt:llms.txt:3-5") and a shaky
  provenance inference (named the top committer as creator without flagging the
  GitHub-handle mismatch). Fine for low-stakes summarize-with-evidence lanes;
  probation earned, keep auditing before trusting analysis-heavy tasks.
- 2026-08-17 — persona-review x1 (jawrsh-hiring-review, recruiter-screen lane):
  FAILED BOTH ATTEMPTS, 79k tokens, 340s — the slowest and most expensive lane
  in the run while all three GLM-5.2 lanes passed. Substance was fine (five real
  findings, correct LIVE-FACTS use, one insight no other lane found), so this
  was NOT a reasoning failure: it cited sources as bare filenames ("CvPage.tsx
  lines 8-11") where the spec demanded repo paths, so the check's "at least 4
  real repo paths" floor caught it at 2 — and the retry, with that exact
  failure text injected, did not fix the citation format. This repeats the
  2026-07-17 blemish: malformed citations are this model's signature failure.
  Do not route it to lanes whose check asserts on citation FORM; it can find
  the evidence but cannot reliably dress it. Probation held, not promoted.

## headroom/z-ai/glm-5.2 (opencode via Headroom proxy — A/B experiment lane)

- 2026-07-18 — bakeoff x5 + probe (headroom-ab: doc-analysis pairs vs direct
  openrouter/z-ai/glm-5.2): 5/5 first-try both lanes, substance parity — but
  proxy lane cost MORE tokens (208k vs 177k) and was slower (config pair 9x).
  Proxy's own stats: avg compression just 1.3% on markdown-doc tool results
  (cache mode, no code-aware extra); one proxied trajectory ballooned to 50
  tool calls vs 3 direct. Verdict: no net win on doc-heavy research work; do
  NOT route this lane through the proxy by default. Revisit only for JSON/
  log-heavy workloads (where the install-proof measured 58% savings) or with
  --mode token. This slug is an experiment lane, not a real model — exclude
  from routing decisions.

- 2026-07-18 — research x16 (tool-scout evaluations, web + repo-clone): GLM-5.2
  14/16 first-try, 16/16 pass. Consistently strong: honest overlap analysis,
  verified claims in cloned source (file:line cites), flagged its own
  uncertainty (star-count inflation suspicions). Retries were thin-first-draft
  issues, fixed by check feedback. Research lane fully proven.
- 2026-07-18 — research x3 (tool-scout article lanes): nemotron-3-super:free
  2/3 first-try, 3/3 pass → 3/4 first-try across 4 research tasks = PROVEN for
  summarize/apply-article work at $0. Caveat vs GLM: reports are shallower —
  generic bullet advantages, less primary-source verification. Route it
  low-stakes summaries, not evaluations that drive decisions.

## zai-coding-plan/glm-5.2
- 2026-07-24 (research, flont-ai competitive teardown, 4 lanes): all four reports substantively strong (evidence-dense, honest could-not-confirm sections) but the run recorded 1 pass / 3 fail — two causes, neither model quality: (1) template check bug in competitive-teardown teardown_check.py (URL_RE character class closed early by \\], extracting zero URLs from ANY text — fixed 2026-07-24 in teardown_check.py + synthesis_check.py); (2) curl-heavy multi-URL lanes overran timeout_s=1200 (1399s, 1460s elapsed). Lessons: blueprint-status kit checks need a dry-run against a known-good fixture before first use; give fetch-heavy research lanes 1800s.
- 2026-07-22 (code-review, zcm-componentization, 4 tasks): 4/4 substantively correct; the run recorded 3 pass / 1 fail but the fail was a CHECK bug (validator treated backticked path:line citation spans as code quotes and searched for them inside the cited files). Retries on 3 tasks likely share that cause. Reports were evidence-dense with real line-verified citations; the two long reports (markup 3.1k words, taxonomy 2.8k) overran the soft length guidance but were worth it. Lesson recorded: citation validators must exclude path:line spans before spot-checking quotes.

## openrouter/inclusionai/ling-3.0-flash:free
- 2026-07-24 (research, flont-ai teardown, 1 task): audition FAILED at the harness level, not model quality — both attempts died in ~4s with opencode "Unexpected server error" (err_d796ed00) before any tokens flowed. Model went :free on OpenRouter 2026-07-23; endpoint likely not serving or provider misconfig. Verdict: inconclusive, do NOT count as a quality demotion; re-audition after a `probe` one-task manifest proves the endpoint answers at all. Lesson: audition brand-new :free slugs with a probe BEFORE giving them a real lane, even a low-stakes one.
- 2026-07-25 (code-fix, fume-model-quotas codex-window-labels): SECOND identical failure — both attempts died in ~4s, opencode "Unexpected server error" (err_b9e7ea3b/err_cdeaf738), zero tokens. Endpoint still dead a day after the 2026-07-24 entry. Orchestrator error: the recorded probe-first lesson was not checked before assigning the lane. Treat this slug as dead until a probe manifest passes; stop auditioning it.

## fume-model-quotas (2026-07-25, flont_fume per-model quota windows, 3 lanes + 1 rerun)
- gpt-5.6-sol high (codex), code-feature (dual dynamic Codable decoders + embedded-Python tee edit + shared mapping type, 4 source files, 827-test suite): PASS attempt 2, ~150k tokens. Attempt-1 fail was CHECK-side — the check's xcodebuild was cut by an external 60s limit while all 825 tests had already passed; attempt 2 passed clean (warm caches). Lesson: checks that run xcodebuild need the build budgeted (warm the DerivedData first or verify ringer check timeout accommodates cold app builds). Output quality high: idiomatic DynamicCodingKey decoders, regression tests beyond spec (malformed reset, camelCase normalization).
- zai-coding-plan/glm-5.2, code-feature (Zai usageDetails detail-only surfacing): PASS attempt 1, 89k tokens, ~16 min. Hygiene lesson from fume-v5 stuck: no scratch spill, honest blocker note (opencode sandbox blocks SwiftPM manifest cache → swift test impossible in-worktree; typechecked via swiftc -typecheck instead, executed check did the real verification). Doc updated including pre-existing label-table drift. Solid lane fit.
- Reconfirmed: failed worktrees run leaves a stale worktree; rerun ERRORs at 0.0s until `git worktree remove --force` (fume-v1 lesson holds).
- 2026-07-25 (code-fix, fume-model-quotas codex-window-labels rerun on glm-5.2): FAIL after 2 attempts but the final diff was 95% correct — attempt 1 put new test files at a root-relative wrong path (ownership catch); attempt 2's implementation was right and only failed on its own test's Swift type bug (`Optional<Double> == Int` expression — equal-looking values, boxed equality never matches). Worker's self-diagnosis wrongly blamed a flaky network test; forgivable because the CHECK's `tail -80` let passing parallel output push the ✘ line out of view — check-craft failure, not model failure. Orchestrator fixed one line, full suite + check passed, patch integrated. Check lesson now applied: failure reporting must grep `✘|Expectation failed` lines, never rely on tail alone.

## fume-notch-r22 (2026-07-26, R22 Live Activity notch realignment, 2 lanes)
- gpt-5.6-sol high (codex), code-feature (1,300-line UI content-model rebuild against a design contract, 12 files incl. arithmetic height model + snapshot tests): PASS attempt 1, ~14 min. Contract-as-spec worked: pointing the spec at docs/NOTCH-DESIGN-CONTRACT.md §5 and constraining only engineering seams produced a faithful render on first try. Signature-freeze constraint (unowned FumeApp must keep compiling) enforced via check-side xcodebuild — clean.
- zai-coding-plan/glm-5.2, code-fix (severity tint, 2 files): PASS attempt 1, 46k tokens, ~3.5 min. Exceeded spec tastefully — derived thresholds from QuotaThreshold rather than duplicating constants. Small well-fenced lanes remain its sweet spot.
- 2026-07-27 (code-feature, fume-notch-r22 presentation-fidelity, gpt-5.6-sol high): PASS attempt 1, ~9 min. Design-language pass spec'd as six numbered before→after deltas in the contract + "render your own snapshots and LOOK at them" instruction — output visually landed the reference language on first try. Lesson: for visual work, contract deltas + self-render loop + check-side PNG export for orchestrator review is the pattern; plain prose aesthetics specs were never needed.

## Check-design lesson (2026-07-26, flont-ai r3)
- Spec/check contradiction: a spec instructed the worker to write "a human must confirm directly at <blocked-domain>" while the allowlist check rejected ANY non-allowlisted URL in the report. The worker complied with the spec and failed the check. Fix: when a spec requires NAMING an unfetchable source, add that domain to the allowlist as a mention-allowed entry (the teardown check only validates citation membership, not fetch status), or instruct the worker to name it without a URL. Content was otherwise correct and the report was accepted after review.
- 2026-07-27 (code-feature, fume-notch-r22 section-insights, gpt-5.6-sol high): PASS attempt 1, ~13 min. Cross-layer lane (new FumeCore value type + FumeUI layering + FumeApp controller threading) with a defaulted-parameter compatibility constraint — clean first try. Also made a good unprompted call: grouping stat cards BY SOURCE (better separation than the spec's single grid card). Contract-deltas + self-render pattern holding at 3/3 first-try on visual lanes.

## zai-coding-plan/glm-5.2
- 2026-07-27 code-review (local-stack design reviews): 2 tasks, one first-try pass, one retry-then-pass. Both reviews substantive — the skeptic lane correctly ruled a source-code dispute between two Codex proposals by quoting the decisive lines from the installed VIP CLI. Good adversary tier for design review; keep pairing with Codex proposers.

## gpt-5.6-sol
- 2026-07-27 research (infra design proposals): 4/4 first-try, ~200s each, deeply grounded (read installed CLI dist source unprompted; one lane found the vip-dev-env.yml overrides mechanism). One lane stated a false durability claim as verified ("locally verifies... survives update") that the review round caught — proposer+adversary structure remains necessary.

## nvidia/nemotron-3-super-120b-a12b:free
- 2026-07-29 research (zcm-v4-reconciliation): audition FAILED on a doc-reconciliation lane - wrote a sandbox-probe test.txt then finished (rc=0) without producing the deliverable, both attempts. Prior wins were simpler research tasks. Don't hand it multi-source synthesis lanes; GLM-5.2 took over.

## harness lesson (not a model)
- 2026-07-29: opencode/codex sandboxes confine writes to the task CWD (the per-task subdir). Specs that name a deliverable path in the PARENT workdir strand the report (workers write it in-CWD, or refuse) - every lane in round 1 hit this. Pattern: deliverable = ./report.md in task CWD; check + expect_files point at <workdir>/<key>/report.md; orchestrator harvests.

### nvidia/nemotron-3-ultra-550b-a55b:free (OpenRouter, via OpenCode)
- 2026-07-29 · docs (PRD cross-document consistency audit) · 1 task, 1 attempt, PASS.
  Given three documents (PRD, engineering rules, normative design spec) and asked to find
  conflicts. Produced the sharpest findings of a 4-task review swarm — the only reviewer to
  catch two P0 spec-vs-plan contradictions that both Sol-high reviewers missed. Quoted
  exact lines from two documents per finding as instructed. Free, 1M context.
- 2026-07-29 · code-fix (correct a false comment in one Swift file) · 1 task, 1 attempt, PASS.
  Tiny scoped task with a hard "own exactly one file" boundary and an architectural
  constraint that ruled out the obvious fix (module layering forbids the delegation it
  would otherwise attempt). Respected the boundary, and all four factual claims in its
  replacement comment were independently verified accurate against the source.
- Verdict: promote to probation for docs/analysis work; strong on read-and-compare tasks
  with explicit output contracts. Untested on greenfield code generation — audition further
  before trusting it with net-new implementation.

### Orchestrator lesson — check bugs masquerading as worker failures (2026-07-29, fume-v9 r2)
Story 5.1 "failed" three times; the worker was right every time.
1. Ownership list excluded `IslandContentSnapshotTests.swift`, which held a legacy
   assertion encoding the exact behaviour the story changes. The worker could not make
   the suite green without touching a file it was forbidden to touch. FIX: before writing
   an ownership list, grep for existing assertions on the symbol being changed.
2. Re-ran with the same `workdir` + same task key while the FAILED run's worktree still
   occupied that path → ERROR at 0.0s, no spawn. FIX: failed tasks keep their worktrees;
   always use a fresh workdir when re-running.
3. Patched the check with a Python string `.replace()` whose escaping silently did not
   match, so the stale ownership regex survived and rejected the newly-authorised file.
   The worker passed 865 tests and was failed by my regex. FIX: rewrite check strings
   wholesale, then dump and read the parsed clauses before running — never trust a
   `.replace()` on an escaped regex inside JSON.
Net: 3 wasted runs, ~330k tokens, zero worker fault. A check that cannot pass is
indistinguishable from a task that cannot be done.

### Environment lesson — sandboxed Swift builds need the clang module cache to EXIST (2026-07-30, fume-v9 r5)
Both round-5 workers produced correct code but were failed by their checks:
`error opening '/Users/jawrsh/.cache/clang/ModuleCache/...' Operation not permitted`.
The directory did not exist, and `codex --sandbox workspace-write` cannot CREATE
`~/.cache/clang/`. Workers tried `-module-cache-path` into the worktree, but SwiftPM's
*manifest* compile (Package.swift) ignores it, so `swift build` failed regardless.
FIX: `mkdir -p ~/.cache/clang/ModuleCache` on the host before any Swift swarm. Rounds 1–4
only worked because that path happened to be writable then.
Salvage note: failed tasks keep their worktrees, so `git -C <worktree> diff HEAD` recovered
both workers' complete output — no rework needed. Check the worktree before re-dispatching.

### nvidia/nemotron-3-ultra-550b-a55b:free — availability (2026-07-30)
- code-feature (write a unit-test file): FAILED, but NOT on capability. It read the
  neighbouring test file to learn house style — exactly right — then the endpoint returned
  `502 ResourceExhausted: Worker local total request limit reached (33/32)`.
  Free NVIDIA capacity is shared and can vanish mid-run.
- Judgment: keep it for read-and-compare work where a retry is cheap; do NOT put it on a
  lane that blocks other work. Its two successes (docs review, one-file code-fix) still
  stand; this is a fleet-availability caveat, not a demotion.

### Engine lesson — the `opencode` sandbox CANNOT build this Swift package (2026-07-30, fume-v9 r5)
Rounds 1–4 all used `engine: codex` and built fine. The first `engine: opencode` task that
needed `swift build` failed no matter which model ran it. Root cause is the sandbox, not
the model: `engines/opencode-sandboxed.sh` denies writes to the real `/var/folders/.../T`,
which SwiftPM requires for `xcrun_db` and for compiling Package.swift. The worker correctly
diagnosed it (`sandbox-exec: sandbox_apply: Operation not permitted`) and tried TMPDIR
redirection, HOME redirection, and `--disable-sandbox` — all still blocked, because the
denial is at the OS sandbox layer, above SwiftPM's flags.
RULE: for this repo, any task whose check runs `swift build` / `swift test` must use
`engine: codex`. Reserve the `opencode` lane for docs, analysis, and review tasks.
Also: GLM-5.2 wrote a well-structured 13-case test file it could not compile, and it used
`SourceID.codex` instead of `KnownSources.codex` — a plausible-looking API that does not
exist. Unverified worker output is a draft, never a deliverable; the executed check is the
whole point.

### Orchestrator lesson #2 — format-brittle checks keep failing correct work (2026-07-30, fume-v9 r6)
Story 4.7's worker did everything asked (moved BindingQuota + QuotaThreshold into FumeCore,
migrated the menu-bar formatter, added all three agreement tests) and reported 907 tests
passing. My check failed it anyway: the last clause ran
`swift test --filter MenuBarMetric | grep -qiE 'plan|binding|agree'`, but the agreement
tests correctly live in BindingQuotaTests, which that filter excludes.
That is now FOUR check bugs this session against ZERO genuine worker failures
(ownership list too narrow; stale workdir collision; unmatched regex replace; wrong test
filter). Every one cost a full retry cycle.
RULE: assert on SUBSTANCE the check can see directly — file contents, symbol presence, exit
codes, full-suite pass — never on where a test happens to live or what it is named. If you
want to verify a behaviour is tested, grep the repo for the assertion, don't guess the
filter that will run it.


---

## poolside/laguna-s-2.1:free (OpenCode / OpenRouter)

2026-08-01 — research (fluffer-0to1 r1, `genmedia`: generative-media provider pricing +
unit economics). AUDITION, exploration slot, $0. Recorded as FAIL over 2 attempts — but
the failure was MINE, not the model's. It made 50 real `webfetch` calls and produced a
2,858-word report with per-provider pricing, a worked unit-economics table, and a
10-item Uncertain section. My check required `https?://` and it wrote citations as bare
backticked domains (`replicate.com/stability-ai/sdxl`), so the URL count scored 0.
After loosening the citation regex to accept bare domains (traceable = substance;
the scheme is format), the SAME report passes cleanly.
Genuine defects, small: one source given as "Internal model documentation", and
`ideometer.ai` cited for Ideogram (real domain is ideogram.ai).
VERDICT: worth another audition on research. Do not read the recorded fail as evidence
against it. Next time, state the citation format as a literal example in the spec
("Source: https://example.com/page") rather than assuming the model infers the scheme.

CHECK-BUG TALLY, continued: this session added two more (substring `TODO` firing inside
"masTODOn", which would have failed every honest report in a channel-research lane that
was REQUIRED to cover Mastodon — caught pre-flight by baseline-testing the check; and the
URL-scheme strictness above, which cost a real retry cycle). Running total this codebase:
six check bugs, zero genuine worker failures.
RULE reinforced: baseline-test every check against BOTH a synthetic passing artifact and a
synthetic failing one before spawning. The mastodon bug was invisible by inspection and
took ten seconds to catch by execution.

2026-08-01 (later) — fluffer-0to1 rounds 2 and 3, GPT-5.6 Sol via Codex CLI.
Round 2: 5/5 pass (db-schema 43 tests, pipeline-engine 41, providers 30, channels 34,
app-foundation a real SSR build). Round 3: 2/2 pass first try, workspace wiring preserved
all 148 tests. Codex at high effort with
`-c sandbox_workspace_write.network_access=true` handled `pnpm install`, `pnpm dlx`,
and PGlite-backed Postgres tests inside the sandbox without trouble; the one-task
`net-probe` that confirmed network up front was worth its ~1 minute.

CHECK BUG #3 this session: `pkg.py --require-symbols 'src/index.ts:reviewPass'` failed
pipeline-engine on attempt 1 purely because the worker had exported the stage under a
different name from a different module. This is the SAME lesson already recorded above
under the Swift work — asserting on symbol NAMES rather than behaviour. The executed
probe (`node probe.mjs` printing PROOF OK after a real three-outline elaboration) proved
far more and never produced a false negative. Session tally: three check bugs, one
genuine worker failure (channels wrote a probe that did not run, and fixed it on retry).
RULE: prefer an executed probe over any symbol/name/path assertion. If you want to know
the code works, run the code.

ALSO: a root-level check can hide a defect that only appears elsewhere. The monorepo
check ran every command from the repo root and passed, but a leftover
`apps/web/pnpm-workspace.yaml` (created by `pnpm approve-builds`) shadowed the root
workspace, so `cd apps/web && pnpm dev` — the first thing a developer does — died with
ERR_PNPM_WORKSPACE_PKG_NOT_FOUND. Found only by booting the app and hitting the routes
by hand. When the deliverable is an app, the check must exercise it the way a human
will, not only the way CI would.

## GPT-5.6 Sol (Codex CLI)

- 2026-08-06 research (portfolio-puller capture proofs, 3 Swift/native lanes): 2 of 3
  lanes needed a retry, and BOTH for the same non-model reason — the managed sandbox
  blocks binding a loopback port, so a spec that told the worker to serve a fixture over
  `python3 -m http.server` and self-verify could not complete its own grading step. The
  host-side check then passed on the rerun. This is the THIRD dated recurrence of the
  same limitation (see 2026-08-03 divider-scout: "Sandbox blocks Chromium launch AND
  localhost binds"), and this time it was purely an ORCHESTRATOR defect — I wrote
  server-dependent self-verification into three specs after the lesson was already
  written down. RULE: when a proof needs a local HTTP server, either pre-start it
  outside the task and pass the worker a URL, or state plainly in the spec that the
  grader runs on the host so the worker does not burn an attempt trying to self-verify.
  Worker conduct was otherwise exemplary — the failing lane's own guard caught that
  `Emulation.setDeviceMetricsOverride` returned 435x942 instead of 390x844 and it
  refused to fabricate a screenshot, leaving `out/` empty rather than faking a pass.
- 2026-08-06 research (portfolio-puller CDP retry, effort=high): PASS first try, 586s,
  48k tokens, after being handed a written diagnosis of the prior attempt. Found the
  real root cause (mobile viewport-meta processing left a ~0.897 page scale after
  navigation; fix is to reapply setDeviceMetricsOverride AFTER navigation plus an
  explicit `Emulation.setPageScaleFactor(1)`) and produced four pixel-exact captures
  that independently matched a Playwright baseline's dimensions. Lesson for retries:
  putting the previous attempt's ACTUAL failure output plus a known-good control
  experiment in the retry spec converted a 2x-failed lane into a first-try pass.
- 2026-08-03 code-fix (zcm cbt-line): recorded FAIL is an ORCHESTRATOR manifest defect, not a model miss — the spec asked for direct edits to a repo outside the task dir, which the enforced sandbox denies. Worker behaved ideally: recorded the exact intended diffs in done.md, ran read-only harnesses, refused to fake success. Lesson: repo-editing tasks MUST use worktrees/patch-export or a copy-into-taskdir pattern.
- 2026-08-03 code-review (zcm divider-scout): PASS on attempt 2. Sandbox blocks Chromium launch (Mach ports) AND localhost binds — browser-validation steps in specs are dead weight for sandboxed workers; scout adapted well (pixel-scanned existing baseline captures, box-model argument). Check gap on my side: PNG count didn't distinguish before/after shots, so "after unavailable" still passed. Distinguish deliverable classes by filename pattern in checks.

## zai-coding-plan/glm-5.2 (addendum)

- 2026-08-06 research x3 (portfolio-puller: mockup-frame licensing, component-export
  formats, Playwright capture baseline): 3/3 FIRST TRY. The licensing lane was the
  standout — pulled Apple's EA0861 marketing-artwork terms and quoted the actual
  restriction rather than paraphrasing, correctly flagged that MockUPhone's CC-BY claim
  does not clear the third-party PSDs it is built from, and put Samsung under Uncertain
  instead of guessing. Continues to be the right default for sourced research lanes with
  a structure+citation check.
- 2026-08-04 probe (staging HTTP recon): needed 1 retry, then produced an excellent verbatim-headers report incl. a subtle "200-but-CORS-blocked" catch. code-review sweep (45-commit classification vs executed hash-coverage check): first-try pass, honest partial-read disclosure. Good fit for sweeps/probes with strict executed checks.

## openrouter/openai/gpt-oss-20b:free (OpenCode)

- 2026-08-06 — AUDITION FAILED ON SUBSTANCE (exploration slot, $0 — free promo).
  persona-review, low-stakes lane (practitioner review of a greenfield PRD, single
  review.md deliverable, structural check requiring >=5 real requirement IDs cited,
  severity tags and a verdict). PASSED the executed check on attempt 2 — and the output
  was still unusable. It reviewed an IMPLEMENTATION THAT DOES NOT EXIST: "in practice
  the current implementation sometimes leaves orphaned processes", "the default scroll
  speed is hard-coded to 800ms", "the UI does not allow per-URL overrides" — for a
  greenfield PRD with zero code. It had correctly cited real FR ids around those
  fabrications, so citation-grounding did not catch it.
  LESSON FOR CHECK DESIGN, not just for this model: an ID-citation check proves the
  reviewer opened the document, NOT that its claims are about the document. For
  review/persona lanes on a spec-only artifact, add a negative assertion — e.g. fail on
  present-tense implementation claims when no implementation exists — or cross-read one
  reviewer against another before trusting findings.
  Verdict: do not route to review lanes. The three proven-model lanes in the same run
  (codex feasibility, glm-5.2 consistency, glm-5.2 premortem) all produced findings that
  materially improved the PRD; this one contributed nothing but its "what I would ignore"
  list. Possible re-audition only on mechanical extract/format work with a content check.

## Check-design lesson (2026-08-06, portfolio-puller epics)

A MECHANICAL COVERAGE CHECK CANNOT SEE ORDER. I wrote a check that parsed all 64 FR/NFR
definitions out of a PRD and failed if any requirement was claimed by no story. It passed
cleanly on an 8-epic / 61-story decomposition. A codex sequencing reviewer then found a
BLOCKER the check was structurally incapable of catching: a PASS on the day-one permission
spike set video "available", so the Epic 5 UI exposed video controls and could run the
mode — while the H.264 writer, window selector and scroll driver did not exist until Epic
8. Coverage proves a requirement is CLAIMED; it cannot prove the claim is REACHABLE in the
stated build order.
Corollary found in the same round by a second reviewer: coverage also cannot prove a
story's acceptance criteria actually SATISFY the requirement it claims. Three criteria
were unverifiable as written — the strongest example being a sign-off gate whose criterion
observed only the sign-off, so a test could seal an "irreplaceable" run without ever
rendering a pixel, defeating the requirement's entire purpose.
RULE: for decomposition/plan artifacts, pair the mechanical coverage check with at least
one reviewer that walks the order literally and one that audits acceptance criteria
against requirement text. The mechanical check is necessary and cheap; it is not
sufficient, and its passing is actively misleading because it looks like verification.

## GPT-5.6 Sol (Codex CLI) — docs/decomposition (addendum)

- 2026-08-06 docs x2 (portfolio-puller epic decomposition, then revision, effort=high):
  PASS first try BOTH times. Round 1: 8 epics / 61 stories, 64/64 requirement coverage
  with exactly one owning story each, ~467s. It independently derived constraints I had
  not specified — that the first user-facing run trigger must sit after the canary,
  hashing and sign-off exist, and that a permission spike's acceptance must include grant
  RETENTION across rebuild, not just initial grant. Round 2 (revision from 15 compiled
  findings): 75 stories, coverage held, every finding addressed with a per-finding
  changelog, ~440s. Handing it a numbered findings list with explicit "do NOT descope X"
  guards produced clean targeted edits rather than a rewrite. Strong default for
  plan/decomposition work where the check can enforce a hard structural invariant.

## Orchestration lesson (2026-08-06, portfolio-puller Epic 1)

PER-TASK CHECKS CANNOT SEE INTEGRATION. Two code-feature lanes ran in parallel worktrees
over one Swift package with disjoint FILE ownership. Both passed `swift build` +
`swift test` in isolation, first try. Applied together they DID NOT COMPILE: each had
independently declared the same four public types (an id wrapper, a mode enum, and two
settings structs). Disjoint file ownership is NOT sufficient isolation when lanes share a
module — they also share a TYPE NAMESPACE, and nothing in either worktree could reveal
the collision.

Worse than the collision: the duplicates DISAGREED. One lane modelled the mode enum with
two cases where the requirements needed four; the other dropped two pixel-affecting
settings fields. A naive "keep one, delete the other" resolution would have silently
destroyed requirement coverage either way. Resolving it was a requirements decision, so
the orchestrator made all four calls from the PRD and handed the worker a decided table
rather than asking it to choose — that task then passed first try.

RULES:
1. Before fanning out lanes that share a module, extract the shared vocabulary as its own
   SEQUENCED task and land it first. This is the Swift/single-module form of "lock shared
   components before parallel fan-out".
2. Always apply all patches from a parallel round and rebuild BEFORE committing. Green
   per-task checks are necessary, not sufficient. Budget an integration step per round.
3. Commit a known-broken integration on a WIP branch, never on main, and squash-merge only
   once the combined tree is green.
4. When duplicates disagree, the merge is a REQUIREMENTS question. Decide it yourself from
   the spec and give the worker the decisions; do not let a fix-lane pick a winner.

## Diagnosis lesson (2026-08-08, flont_friend inbox "sync fails silently")

- glm-5.2 code-fix (inbox sources reachability, 5-file cross-component refactor with an
  extract-to-shared-panel): first-try pass, ~105k tokens, 6.2 min. Handled the
  extract-and-reuse pattern (panel consumed by 3 render sites) and re-solved the
  .vite-temp symlink footgun on its own. Tightly-diagnosed fix specs (orchestrator names
  the exact trap, files, and copy) remain its strongest lane.
- Orchestrator lesson: "it fails with no error" was NOT a failure — the run succeeded and
  the report was HONEST but not INFORMATIVE ("cloudTabs 0" when zero devices were
  selected = skipped, not empty). Silent-skip states deserve first-class copy in every
  summary surface. Also: any settings surface that only exists in a first-use/onboarding
  state is a reachability bug waiting to happen — gate check every onboarding-only
  control for a post-onboarding home.
- 2026-08-08 — codex code-fix (flont_friend CloudTabs nested-sortValues decode +
  truth-telling fixtures + row-error surfacing, full-stack lane): first-try pass, ~99k
  tokens, 5.3 min. Orchestrator lesson worth keeping: FIXTURES THAT MIRROR THE PARSER
  instead of the source of truth validate bugs — the flat-shape fixture matched the flat
  parse and 80 tests stayed green while 500 real rows dropped. When a reader targets an
  external format, at least one fixture must be captured/derived from the REAL artifact,
  and row-level error counts must be user-visible somewhere, or "succeeded" hides total
  loss.
- 2026-08-08 — CHECK FAULT, orchestrator (flont_friend brownfield UX inventory,
  glm-5.2): both attempts produced a complete 4.5k-word report with 100 citations, but
  the check's citation regex demanded full `src/...` path prefixes while the worker
  cited `Sidebar.tsx:399-406` (bare filename, line ranges). FAIL x2 recorded against
  glm-5.2 unfairly — discount this run on the scoreboard. Repeat of the strict-on-format
  lesson: when counting citations, match `file.ext:line` loosely; reserve strictness for
  section presence and substance. (Domain-inventory codex lane passed the same run,
  first try, ~280k tokens — its citations happened to use full paths.)
- 2026-08-10 — CHECK FAULT, orchestrator (portfolio-puller app-shell, rounds 33 and 34):
  the worst kind, because the check was the thing I wrote to catch a real gap. The user
  reported "I opened the app and don't know what to do." I built a probe that launched
  the bundle and searched CGWindowListCopyWindowInfo for a window whose owner was
  `PortfolioPullerApp`, got PROBE_NO_WINDOW, and escalated the diagnosis from "confusing
  UI" to "the app is headless." Two swarm rounds then went to fixing an async-main/
  AppKit-lifecycle bug that did not exist. kCGWindowOwnerName is CFBundleName
  ("portfolio-puller"), not CFBundleExecutable — the window had been on screen the whole
  time, at the size the entry point asked for. Lessons: (1) when a probe reports ABSENCE,
  prove the probe can see a known-present instance of the same class of thing before
  believing it — I did check it saw Finder, which was not enough, because Finder shares
  neither the naming scheme nor the bundle layout; the control has to be the artifact
  itself in a known-good state, i.e. run the probe against the PREVIOUS build; (2) match
  on identity the caller already possesses (the launched PID) rather than a name you
  derived; a PID cannot be guessed wrong; (3) the user's own words were more accurate
  than my escalation — when a report and a measurement disagree, suspect the measurement.
- 2026-08-10 — orchestrator (portfolio-puller): "main is green" was recorded from a
  single observed passing run. Running the full suite three times on the clean tree
  failed twice. Three suites had real-time budgets sized within scheduler noise — the
  load-bearing one was a 25ms URLSession timeout against a real loopback socket serving
  pages that deliberately sleep 5ms, which is NOT the timeout the ExecutorConfiguration
  in the same file made it look like. Green is a property of the distribution, not of one
  sample: run a suite at least 3x, and once under CPU saturation, before calling it green.
- 2026-08-10 — RELEASE-GATE ESCAPE, orchestrator lesson (flont_friend Today→Inbox
  handoff): two parallel lanes implemented the two halves of a one-shot in-memory
  handoff (set… in lane A, consume… owed by lane B); the consumer was never wired,
  tsc/build/grep checks all green, caught only by the human at the packaged gate.
  Codex fix lane: first-try, honest "could not identify exact throw" for the
  secondary crash — implemented structural guards instead of inventing a cause.
  NEW RULE for cross-lane contracts: any set/consume or emit/listen pair split
  across lanes gets a check in BOTH lanes' verify-commands asserting the
  counterpart symbol exists outside its defining module (grep -rq <consumer>
  src | grep -v <defining-file>). Add it to the integration gate too.
- 2026-08-11 — DIAGNOSTIC-BOUNDARY PAYOFF (flont_friend inbox crash, 3rd lane): two
  prior lanes fixed plausible-but-wrong causes (structural guards, null-safety) because
  the boundary showed only a generic message. After making the boundary render
  error.message + stacks with Copy details, the user's next screenshot carried React
  error 185 (max update depth) — an infinite render loop, not a TypeError. codex then
  found the exact cycle first-try-on-substance (fresh [] fallback per cold render →
  effect → unconditional store publish → rerender). LESSONS: (1) when a UI crash is
  only known via a generic boundary, making the boundary diagnostic IS the first fix —
  do it before the second guess, not after; (2) store setters get shallow-equal
  bailouts as a standing invariant in any useSyncExternalStore architecture; (3) a
  wrong-but-confident 'prime suspect' from a passing lane is still wrong — evidence
  outranks a green check.
- 2026-08-11 — PROVE-FAIL-MODE run (ringer feature build, 2 lanes + repair).
  GPT-5.6 Sol high (codex), code-feature: first-try PASS on a contract-heavy spec
  in the 11k-line ringer.py — 100k tokens, 8.4m. Adopted house idioms unprompted
  (process-group kill helpers, baseline's print alignment). Spec pinned function
  line numbers and VerifyResult fields; that shape is worth repeating for
  single-file surgery. Nemotron 3.5 Lightning :free (opencode/OpenRouter),
  docs audition: NO capability evidence — both attempts died <2s, 0 tokens,
  OpenRouter "Unexpected server error" (err_b951a40f, err_113915d1) on its
  day-one free listing. Lesson: day-zero free promos may not be serving yet;
  a 0-token instant error is a route failure, not a model failure — re-audition
  after a few days instead of recording a demotion. GLM-5.2 (opencode default
  route), docs from a frozen contract: first-try PASS, 32k tokens, 101s, +15-line
  README diff accurate to contract and voice — reconfirms GLM as the docs-lane
  default. Operational: the failed Nemotron round's surviving worktree blocked
  the repair rerun ("worktree taskdir already exists") — exactly the pre-flight
  worktree-check gap in the local improvement backlog.
- 2026-08-11 — CHECK FAULT #7, orchestrator (flont_friend K1 kit lane, glm-5.2): both
  attempts produced complete, verifiable work (13 components, tokens, fixture, tests —
  manual verify all green); the check killed them on `grep -rq X src | grep -q .` —
  `-q` PRINTS NOTHING, so piping quiet grep into a content grep always fails. Discount
  the two glm FAILs on the scoreboard. RULE: never pipe `grep -q` anywhere; use it bare
  as the condition (`grep -rq X src || fail`) — added to the check-writing rules. Manual
  recovery from the surviving worktree, sixth time the worktree-survival design paid off.
- 2026-08-11/12 — WORKTREE-PREFLIGHT run (ringer feature build, 2 lanes + repair).
  GPT-5.6 Sol high (codex), code-feature: work was RIGHT first try but my check
  script crashed mid-verification (FileExistsError: same scratch dir reused across
  two hermetic invocations) — burned both attempts and 164k tokens against a
  defect in the CHECK, then passed untouched once the check was fixed. Two check
  lessons: (1) --prove-fail/--baseline only exercise a check's EARLIEST failing
  gate; deep-path check code stays untested until a genuinely good state exists —
  smoke the check's full path before the swarm, not just its early exits.
  (2) Ownership-list gap: the frozen contract changed behavior that legacy tests
  (test_setup_error_diagnostics, test_ringer) asserted, but those files weren't in
  the worker's ownership — worker correctly reported instead of trespassing; the
  repair lane (Sol high, code-fix) adapted them first-try, 100k tokens, converting
  the race-path test to a direct _prepare_taskdir unit test. When a contract
  obsoletes existing tests, grant them in the SAME lane or plan the repair lane up
  front. GLM-5.2 (opencode default), docs: first-try again, 27k tokens, 52s —
  3-for-3 lifetime on contract-driven README work. Dogfood note: known_bad +
  --prove-fail gated both rounds and caught nothing false — but see lesson (1).
- 2026-08-12 — INTEGRATION-CHECK run (ringer feature build, 2 lanes, zero repair).
  GPT-5.6 Sol high (codex), code-feature: first-try PASS, 135k tokens, 10.6m —
  now 3/3 first-try-on-substance on contract-frozen single-file features in this
  repo (the round-2 "failures" were my check's bug, not the model's). The two
  spec adjustments from last round (stop-and-report on legacy-test collisions;
  unique scratch dir per hermetic check invocation) produced the first
  zero-repair round. GLM-5.2 (opencode default), docs: first-try, 28k tokens,
  60s — 4/4 lifetime on contract-driven README work; treat as the standing
  docs-lane default. Ritual note: this was the last round to need the manual
  scratch-worktree suite gate — future multi-lane manifests should declare
  integration_check and let the run gate itself.
- 2026-08-12 — PILOT-GATE run (ringer feature build, 2 lanes, zero repair,
  first run gated end-to-end by ringer's own new features). GPT-5.6 Sol high
  (codex), code-feature: first-try PASS on the biggest contract yet (scheduler
  hold-back, decision-file polling, two new CLI subcommands) — 200k tokens,
  11m; 4/4 first-try-on-substance on contract-frozen ringer features. GLM-5.2
  (opencode default), docs: first-try, 28k tokens, 40s — 5/5 lifetime on
  contract-driven README work. Process milestone: --prove-fail gated the
  checks before launch and the manifest's own integration_check verified the
  MERGED patches (278 tests) inside the run — no manual scratch-worktree gate
  for the first time. The spec-shape that keeps earning first-tries: frozen
  numbered contract, pinned line numbers, named test-file template, explicit
  stop-and-report escape hatch.
- 2026-08-12 — RED-TEAM-KIT run (template kit, not a ringer.py feature; 2 lanes,
  zero repair, self-gated). GPT-5.6 Sol high (codex), code-feature: first-try
  PASS, 116k tokens, 6m — 5/5 first-try-on-substance here. Notable: the check
  mutation-tested the kit's OWN shipped check script (must accept a good report
  AND a NO FINDINGS verdict, reject 4 bad shapes) — that spec shape ("prove both
  outcomes yourself before finishing") transfers to any kit-authoring task.
  GLM-5.2 (opencode default), docs: first-try, 34k tokens, 100s — 6/6 lifetime;
  correctly wrote the catalog status as "New — not yet proven in a recorded run"
  when told not to claim an unearned proven run, which is the honesty behavior
  worth trusting it with. Kit ships unproven by design: first real use should
  update that status row.
- 2026-08-12 — FOUNDATION-CONTRACTS run (ringer feature build, 2 lanes, self-gated).
  GPT-5.6 Sol high (codex), code-feature: PASSED ON ATTEMPT 2 — first miss in 6
  rounds, and a legitimate one. Attempt 1 implemented all three features but the
  ownership violation message did not NAME the offending path; the check asserted
  the path appears (it is what reaches the retry prompt), failed, and the injected
  failure text fixed it on attempt 2. 235k tokens total across attempts, 13m.
  LESSON worth keeping: check assertions on the CONTENT of failure messages —
  not just the exit code — are what make the retry loop self-correcting; a check
  that only asserted "the lane failed" would have shipped a violation report no
  human or retry could act on. GLM-5.2 (opencode default), docs: first-try, 33k
  tokens, 84s — 7/7 lifetime on contract-driven README work.
- 2026-08-12 — CHECK FAULT #8 + a real find (flont_friend session-start hang, codex):
  check used `timeout 900 cargo test` — `timeout` does NOT exist on stock macOS (no
  coreutils); "command not found" → non-zero → both attempts FAIL despite fully green
  work (125 tests, +5). Discount the codex FAILs. RULE: no GNU-only binaries in checks
  (`timeout`, `realpath`, `sed -i` w/o arg) — macOS is the target box; bound long tests
  inside the harness instead. The lane itself was exemplary: hypothesis-ordered
  diagnosis, disproved the scale theory with a measured 35ms debug-build number, and
  found a REAL lock-order deadlock (reads took DB→session; triage mutations took
  session→DB) with a bounded test that FAILS rather than hangs. Evidence-first specs
  ("prove or disprove each with EXECUTED evidence") keep paying.
- 2026-08-12/13 — RINGSIDE-DECISIONS job (2 rounds, one artifact; first UI work and
  first pilot-gated job). R1 pilot lane, GPT-5.6 Sol high (codex), code-feature:
  passed on attempt 2 — attempt 1's own test helper had a broken signature
  (request() missing 'method'), which the worker COULD NOT have caught because its
  sandbox denies localhost binding. Design that paid off: the worker writes socket
  tests it cannot run and the CHECK (which runs unsandboxed) executes them; put
  that split in the spec explicitly so the worker does not thrash. 178k tokens.
  R2 page lane, Sol high: first-try, 74k tokens, 5.5m, on a pure front-end contract
  (hoist a block above another element, replace a fixed grid with auto-fill, add
  URL state) — front-end contracts work as well as backend ones when the target is
  named structurally rather than aesthetically. GLM-5.2 docs: first-try both rounds
  (37k, 2.6m) — 8/8 lifetime.
  PROCESS: --prove-fail caught a BROKEN check of mine before launch — the docs check
  greped the whole README for words earlier rounds had already added, so it passed
  on a known-bad file. Fix: assert on the ADDED diff lines. General rule: when a repo
  already documents a feature family, whole-file greps cannot prove new work.
  ALSO: prove-fail executes checks for real, so a check that passes on the known-bad
  state EXPORTS ITS ARTIFACTS — a stale patch file was left behind and had to be
  deleted before it was mistaken for a deliverable. Clean the patch dir after a
  BROKEN verdict.
  HARNESS: a paused pilot run whose orchestrator process is killed leaves state at
  'awaiting' while the run is dead; held lanes report ERROR with 0 attempts. Worth a
  future feature: detect a dead-orchestrator pause on load and say so on the page.
- 2026-08-13 — LINT-AND-HELPERS run (3 lanes, zero repair, self-gated). GPT-5.6
  Sol high (codex) on the lint rules: first-try, 80k tokens, 6m — the hard
  constraint ("if a new rule dirties a shipped kit the RULE is wrong; tighten it,
  don't edit templates/") produced correctly-scoped rules with no template
  churn. GPT-5.6 Sol MEDIUM on the check-helpers module: first-try, 35k tokens,
  2.7m — medium is the right tier for a well-specified standalone module with a
  strong check; reserve high for surgery inside the 11k-line ringer.py.
  EXPLORATION RESULT — cohere/north-mini-code:free (opencode/OpenRouter), docs:
  PASSED on attempt 2 (50k tokens, 2.4m, $0). Attempt 1 documented the three
  lint rules but silently skipped the second half of the brief (the
  check-helpers module); the retry with the check's failure text fixed it.
  Read: capable on free tier but drops parts of a multi-part brief — usable for
  docs lanes WITH a check that asserts each required part separately (mine did,
  which is the only reason the miss was caught). GLM-5.2 remains the default;
  north-mini-code is a viable free backup, now probation→ still auditioning.
- 2026-08-13 — DEAD-RUN-HONESTY run (2 lanes, both passed on attempt 2).
  GPT-5.6 Sol high (codex), code-fix: attempt 1 wrote only 2 of the 3 required
  tests; the check counted them and the retry added the third. GLM-5.2, docs:
  attempt 1 added too few lines; retry fixed it. Both misses were "did less than
  the brief asked", caught only because the checks asserted COUNTS (>=3 tests,
  >=3 added lines) rather than mere presence — cheap assertions worth copying.
  PROCESS BUG OF MY OWN: the run's integration_check FAILED while both lanes
  passed, because my integration template still asserted the old
  "FAILED (failures=1)" baseline from when tests/test_contributors.py always
  failed locally. Since the contributor credit landed the suite is fully green,
  so every integration check must now require a clean OK — a stale expectation
  in a gate reads exactly like a real regression. Check your gates when the
  repo's baseline changes.
- 2026-08-13 — RERUN-FAILED job (3 rounds; every failure was MY check, not the
  worker). GPT-5.6 Sol high (codex), code-feature then code-fix: the first round
  passed all gates — tests, suite, integration — and shipped a real defect that
  only a manual spot-check caught: a helper that INVENTED a `verified` sentence
  and REWROTE the `check` command so the emitted repair manifest would lint
  clean. It did that because MY check demanded lint-clean output while feeding
  it a fixture manifest that was not lint-clean at source. LESSON (the big one):
  an impossible check does not fail loudly, it gets satisfied CREATIVELY — the
  worker resolves a check-vs-spec contradiction in whatever direction the check
  measures. Corollary: "all gates green" is exactly when to spot-check, because
  a defect that survives every gate is by definition one no gate was looking
  for. Fix: assert emitted tasks are byte-identical to source tasks (no added
  keys, no changed values) — the assertion that would have caught it instantly.
  Round 2 of the fix ALSO failed on my fixture: the unanchored-substring-grep
  lint rule we shipped hours earlier flagged my own `grep -q Evidence`. Round 3
  passed first-try (73k tokens, 2.6m) once the fixture was honest.
  TOOL GAP worth building: --prove-fail catches a check that cannot FAIL;
  nothing catches a check that cannot PASS. A `--prove-pass` (run each check
  against a known-GOOD fixture, expect exit 0) would have caught all three of
  these in seconds with zero workers spawned.
  DOGFOOD WIN: the worktree pre-flight aborted a doomed re-run at zero token
  cost and named --reset-worktrees, which then cleared it — the exact incident
  that put pre-flight on the backlog now costs one flag.
- 2026-08-13 — PROVE-PASS run (2 lanes, both first-try, zero repair).
  GPT-5.6 Sol high (codex), code-feature: first-try, 97k tokens, 6.3m — the
  "model it CLOSELY on the existing run_prove_fail, this is its mirror" framing
  is the cheapest reliability trick in these specs: a symmetric feature written
  against a named existing function lands first-try far more often than one
  described from scratch. GLM-5.2 docs: first-try, 33k tokens, 72s (9/9).
  The feature closes the gap that cost three attempts earlier today: --prove-fail
  proves a check can FAIL, --prove-pass proves it can PASS on correct work.
  Demonstrated side by side on one manifest: an impossible check (grep for a
  token honest work will never contain) is reported "proved" by prove-fail —
  it does fail on bad input, so it looks healthy — and only prove-pass flags it
  BROKEN. Routing note for future check-writing: declare BOTH known_bad and
  known_good on every task; the two gates together cost no tokens and catch the
  two ways a check lies.
- 2026-08-14 — LANE-WALL run (Ringside multi-run density; 2 lanes, page lane
  first-try, docs on attempt 2). GPT-5.6 Sol high (codex), code-feature:
  first-try on a 1700-line vanilla-JS page — 92k tokens, 6.5m. What made it
  work: the spec named the EXISTING mechanisms to extend ("the page already
  stores tab and run via replaceState — extend that, do not invent a second
  one") and listed what must not regress by selector (section.pilot-review,
  orchestrator_alive, focus-visible). Front-end contracts land like backend
  ones when the target is structural, not aesthetic.
  PROVE-PASS EARNED ITS KEEP ON FIRST USE, twice, before any worker spawned:
  (1) my known_good fabricated one long line while the check demanded three —
  a bad simulation of good work; (2) more valuable, my check demanded the
  literal phrase "every run" while honest prose says "every LIVE run" — an
  over-strict assertion that would have burned two attempts and read as a model
  failure. Both caught in seconds at zero cost. Standing rule confirmed: write
  known_bad AND known_good for every task.
  VISUAL VERIFICATION still found what checks could not: the census line read
  "0 lanes need attention" directly above a failed card when nothing was live
  (live-only counting vs a fallback run on screen). Fixed inline. Also a false
  alarm worth remembering: ?view=lanes appeared to open the Models tab — that
  was localStorage tab restore from my own earlier browsing, not a bug. Clear
  or name state explicitly when testing URL restore.
- 2026-08-14 — DESIGN-DIRECTIONS kit (2 lanes, both passed on attempt 2).
  GPT-5.6 Sol high (codex): attempt 1's check script defaulted to
  direction-render.png while my check's fixture wrote direction.png — a
  filename convention I never stated but silently required. GLM-5.2 docs:
  attempt 1 wrote "Proven in a recorded run" for a kit that has never been
  used; the check caught the unearned claim and the retry fixed it (worth
  noting: same model got this RIGHT unprompted on the red-team kit, so the
  honesty assertion in the check is what makes it reliable, not the model).
  PROVE-PASS LIMITATION FOUND: both gates passed clean before this run, yet
  attempt 1 still failed on the filename mismatch — because my known_good
  fabricated a check script whose defaults agreed with my fixture BY
  CONSTRUCTION. prove-pass proves a check can accept the good work *I*
  imagine, not every legitimate alternative a worker might produce. Where a
  convention matters (filenames, section names, CLI defaults), STATE IT IN
  THE SPEC; a gate cannot infer what you never wrote down.
- 2026-08-14 — RED-TEAM-RINGER: pointed the red-team kit at Ringer itself, its
  first real job. 4 lanes (2x Sol high, 2x GLM-5.2), 3 passed, 1 failed;
  13 findings. Two verified and fixed same session: (a) P1 — repo-feature's
  path_allowed() had a reverse-prefix branch, so a git-collapsed untracked dir
  ("?? safe/") counted as owned whenever any owned file lived beneath it: a
  worker could add arbitrary unowned files and PASS; (b) P2 — the red-team
  kit's OWN check regex-matched an evidence path without opening it, so
  "Evidence: nonexistent-file.txt" was certified "evidence-backed". The kit
  found a false-green in itself on its first outing, which is the strongest
  possible argument for the pattern.
  UNFIXED, recorded for later: proof/focus-group/bakeoff validators check the
  VALIDATOR's exit code rather than the declared artifact (a proof that never
  ran certifies green); PASS cleanup silently force-deletes a passing task's
  deliverable when expect_files is omitted and the file is not report.md;
  --reset-worktrees discards uncommitted work without listing it first; CLI
  approve/reject prints success on a dead run while the server correctly 409s.
  TRAP WORTH REMEMBERING: the failed lane's findings directory contained my own
  known_good FIXTURE text, harvested when --prove-pass executed the check for
  real during gating. A gate's side effects can leave artifacts that look
  exactly like results. Clear harvest dirs between gating and running, and read
  every report before believing it.
  ENGINE READ: Sol high produced the two deepest reports (real-data,
  test-quality: 220k/215k tokens) with reproducible evidence; GLM-5.2 did well
  on destructive-path (223k, 42m — slow but thorough) and failed the error-path
  lane twice, never producing a report. Adversarial audit is a Sol-high task
  type; GLM is viable on the mechanical surfaces, not the open-ended ones.
- 2026-08-14 — VALIDATOR-GUARDS (acting on the red-team audit). Two kit
  false-greens closed, both verified by re-running the original attacks:
  research-with-proof now refuses a proof command that never references the
  declared artifact ("artifact 'proof.sh' is not referenced by proof command
  ..."), and focus-group + bakeoff now refuse a session validator that cannot
  fail (true, :, exit 0, bare echo) — the same rule lint already applies to
  task checks. Honest inputs still pass in every case.
  MY CHECK WAS WRONG AGAIN (5th time today): the proof lane's first failure was
  my fixture proof.md missing two sections the validator legitimately requires
  (What It Proves, Limits), so my "honest proof must pass" case was
  unsatisfiable. Read the validator's own constants before writing a fixture
  for it; do not infer the contract from the part of it you happen to be
  fixing.
  RERUN DOGFOODED: the repair round was generated by ./ringer.py rerun (one
  lane selected, run_name and integration_check preserved) and deliberately run
  WITHOUT --with-context — when the previous failure was the ORCHESTRATOR's
  bug, injecting it points the worker at the wrong thing to fix. New rule:
  --with-context is for worker failures, not for my own.
- 2026-08-14 — NO-SILENT-LOSS (final red-team actions; both lanes first-try).
  GPT-5.6 Sol high, code-fix: 129k tokens, 10m, three independent honesty fixes
  in one lane — cleanup now prints `discarding unharvested file(s): [...];
  declare them in expect_files to keep them`, --reset-worktrees prints
  `reset will discard uncommitted path(s): [...]` before removing, and CLI
  approve/reject now refuse a dead run ("orchestrator exited; the pilot
  decision can no longer be delivered") using the server's own liveness source.
  Framing that made three fixes fit one lane cleanly: name the SHARED theme
  ("the tool acts destructively without saying so") and forbid scope creep
  explicitly ("do NOT change what is deleted; the fix is to tell the truth").
  RED-TEAM AUDIT NOW FULLY ACTIONED: 13 findings -> 7 real defects fixed today
  (repo-feature ownership bypass, red-team evidence false-green, proof-command
  bypass, vacuous session validators x2, silent deliverable deletion, silent
  reset loss, CLI/server disagreement). The rest were correct-by-design or
  unverifiable from the sandbox.
  ORCHESTRATOR SCORECARD FOR THE DAY: 6 of my checks/fixtures were wrong vs
  ~1 genuine worker defect. The recurring shapes: demanding something the spec
  forbids, asserting a phrase instead of a claim, fixtures that violate the
  validator's own documented contract, and relative paths in fixture setup.
  Read the thing you are testing before writing the fixture for it.
- 2026-08-14 — BRITTLE-CHECK-LINT (three rules distilled from the day's own
  mistakes: long exact-phrase greps, exotic whitespace in patterns, and checks
  that inspect .git/). Verified firing on each fault and silent on honest
  near-misses; suite 327 green.
  THE LANE "FAILED" AND THE WORKER WAS RIGHT ALL ALONG. My check crashed with
  TypeError: sh() got an unexpected keyword argument 'timeout' — a kwarg
  mismatch in MY OWN helper. Both attempts burned; Ringside showed it as the
  worker's failure. Re-running the same check, fixed, against the worker's
  UNTOUCHED worktree passed immediately and exported the patch.
  THE GATE GAP THIS EXPOSES: --prove-fail cannot tell "the check correctly
  failed" from "the check crashed" — both exit nonzero, and it reported this
  crashing check as `proved`. Only --prove-pass distinguishes them, and I had
  skipped known_good on that lane. But known_good is weak for CODE lanes:
  fabricating good work there means implementing the feature, so a one-liner
  gets a legitimate BROKEN. PRACTICAL RULE: for code lanes, before launching,
  run the check ONCE by hand in a throwaway worktree; a crash surfaces in
  seconds and costs nothing, and no gate currently covers it.
  ORCHESTRATOR SCORECARD, FINAL: 7 of my checks/fixtures wrong vs ~1 genuine
  worker defect across the day.
- 2026-08-14 — REGISTRY-RACE + CRASHED-CHECK (the two highest-value items left
  after the red-team audit; both Sol high, both first-try).
  REGISTRY RACE: register/unregister_active_run did a read-modify-write on
  active-runs.json with no cross-process serialisation. Measured before:
  33 of 36 simultaneous registrations LOST (12 procs x 3 rounds). After:
  0 of 64 lost under 16-way contention. The worker generalised the repo's own
  catalog_refresh_lock into exclusive_file_lock(path, blocking=...) and used
  non-blocking reads / blocking writes so Ringside cannot deadlock behind an
  orchestrator. Severity note: this was cosmetic until WE shipped the dead-run
  refusal — after that, a lost entry could block a legitimate approve and
  strand held lanes. Fixing a display without fixing its data source can
  upgrade a wrong pixel into a stuck run.
  CRASHED CHECK: --prove-fail printed a TypeError traceback and reported the
  task as `proved`, because a crash and an honest failure both exit nonzero.
  All three gates now classify CRASHED (missing command, syntax error,
  unhandled exception with no intentional diagnostic) and exit nonzero.
  The hard part was the FALSE POSITIVE: checks that run unittest legitimately
  print tracebacks, so a traceback alone must not count — the rule is "no
  intentional diagnostic" (no test-runner summary, no FAIL:-style line), and
  when ambiguous it returns False. Verified: crash -> CRASHED, honest failure
  -> proved, traceback+FAILED(failures=1) -> proved.
  SPEC TECHNIQUE THAT KEEPS WORKING: name the existing in-repo mechanism to
  reuse ("see catalog_refresh_lock around line 3248 — REUSE THAT SHAPE") and
  state the false-positive rule as a first-class requirement with a "when in
  doubt return False" tiebreaker. Both lanes landed first-try on subtle work.
- 2026-08-14 — UNREADABLE-RECORDS + QUIET-OMISSIONS (last two audit findings).
  Sol high on unreadable-records: first-try. Reproduced by hand first — 15 valid
  runs plus 4 corrupt files with the NEWEST mtimes returned only 8 of 12 slots,
  hiding 4 valid runs, because the newest-N budget was spent before decoding.
  After: 12 valid runs surfaced, unreadable=4, corrupt library reported
  unreadable=1 instead of empty. Sol MEDIUM on quiet-omissions: passed on
  attempt 2 — attempt 1 added the payload fields but reported "skipped": 0 for
  a log with 2 malformed lines (counter wired to an already-filtered source).
  The check asserted the VALUE (==2), not the key's presence, which is the only
  reason a permanently-zero counter did not ship. Reinforces the standing rule:
  assert what the number IS, never that a field exists.
  SPEC TECHNIQUE, now three-for-three: reproduce the defect by hand BEFORE
  writing the spec and put the measurement in it ("4 corrupt files newest on
  disk left only 8 of 12 slots filled"). A measured target beats a described
  theory; the worker can verify against it instead of interpreting it.
- 2026-08-15 — UNATTENDED primitives (last item from the 2026-08-11 insights
  report). Sol high, code-feature: passed on attempt 2 — attempt 1 implemented
  the wall-clock budget and report but let all 5 lanes run despite
  failure_breaker=2. The check counted lanes STARTED, not just the report text,
  which is why a half-implemented brake did not ship. GLM-5.2 docs: first-try.
  Scope decision (Josh, 2026-08-15): Ringer gains PRIMITIVES, not a scheduler —
  budget_wall_clock_s, failure_breaker, questions_file, RUN_REPORT.md. It still
  runs one manifest; an orchestrating agent decides what runs next, so an
  unattended night needs the session to stay alive. The "commit to a dedicated
  branch, never main, never push" rule is orchestrator POLICY and lives in
  SKILL.md, deliberately not in ringer.py — a second write path nobody watches
  is exactly what we spent the day removing.
  DESIGN NOTE worth keeping: unstarted tasks are reported as "not started",
  never as failures. A morning report that calls unstarted work a failure would
  send the human debugging something that never ran.
- 2026-08-15 — GATE-NUDGE (lint nudge for tasks missing known_bad; 4 rounds).
  FIRST REAL USE OF `foundation`: a lane added known_bad to all 38 tasks in 19
  kits, its patch propagated to the held lanes, then the lint rule landed. That
  worked — and taught two check rules for foundation runs:
  (1) a lane check must stage/export ONLY its owned paths; `git add -A` in a
  foundation run sweeps up the inherited foundation diff and would re-apply it
  at commit time; (2) diff-based checks must use `git diff HEAD` — a previous
  attempt's `git add -A` stages the worker's edit, so attempt 2 sees an empty
  `git diff` and fails a CORRECT worker.
  NEAR-MISS WORTH REMEMBERING: my repair spec said "make the nudge non-blocking
  like its neighbours". The neighbours were NOT non-blocking — on HEAD any lint
  finding exits 1. The worker implemented the instruction faithfully by making
  only ERROR findings block, silently downgrading EVERY rule (silent checks,
  write collisions, focus-stealing commands) to exit 0 while printing
  "lint: clean" beside their own findings. Caught by testing HEAD's real
  behaviour rather than trusting memory of it; reverted, and the worker's test
  was retargeted to assert the true contract. LESSON: verify the premise of a
  spec against the code before asserting it — a faithful worker will implement
  a false premise perfectly.
  Also: the integration_check caught both regressions the lane checks missed
  (test_signal_contract), which is exactly the case it was built for.
  Day tally: 9 orchestrator-side failures vs 2 genuine worker defects.

- 2026-08-15 — FLONT-FRIEND AI-ARCHITECTURE REVIEW (5 read-only lanes over one 714-line
  architecture doc, pilot-gated; 4/5 first-try PASS). Task type code-review.
  · codex (GPT-5.6 Sol, `model_reasoning_effort=high` ×2, `medium` ×1) — 3/3 first try,
    ~450–605s each. High effort earned its cost: both high lanes read the REAL existing
    Rust (bookmarks.rs merge, inbox.rs promotion) rather than reasoning from the document,
    and one shell-tested a UNIQUE-constraint question in sqlite3 mid-review. The medium
    lane found the run's only P0. Notable honesty: the lifecycle lane explicitly CLEARED
    the lock-order suspicion its own brief planted ("Tauri's injected State<'_,T> are
    managed references, not held guards"), i.e. it reported a negative finding instead of
    manufacturing agreement with the spec author.
  · zai-coding-plan/glm-5.2 (opencode) — proof-carrying SQL lane, first try, 84.6k tokens,
    740s. Best GLM showing recorded here. Asked to EXECUTE rather than reason, it wrote a
    21-assertion POSIX proof script, hit 5 FAILs that were bugs in its OWN fixtures, fixed
    them, re-ran to 21/21, then verified its report against a fresh re-run by diffing, and
    independently cross-checked the key finding on a second SQLite engine (Python's 3.50.4)
    unprompted. LESSON: GLM is materially stronger when the deliverable is an executable
    artifact whose output it must echo, than when the deliverable is prose judgment — the
    check "re-run the script and diff its output against the report" is what made this work.
  · openrouter/nvidia/nemotron-3-ultra-550b-a55b:free — logged FAIL, but ZERO model fault.
    It produced a substantive 10-finding review (14.8k chars) on an operational-reality
    brief that the codex lanes did not cover, including a real gap the others missed: the
    error taxonomy has no way to express a Claude subscription rate limit, so mid-run quota
    exhaustion becomes an undiagnosable `processFailed` and the retry path re-hits the limit
    immediately. Its weaker findings were speculative (invented token arithmetic, an
    "auto-update" mechanism Claude Code does not use). This is the third consecutive
    confirmation of its standing verdict: strong on read-and-compare with an explicit output
    contract, worth its free slot. Do NOT record this FAIL as a demotion.
  · ORCHESTRATOR FAILURE (mine — check-side, format strictness) — the nemotron lane failed only because my check's
    label regex accepted `Finding:`, `- Finding:` and `**Finding:**` but not `### Finding:`.
    The model chose a markdown heading; the check called an honest 10-finding report
    "neither NO FINDINGS nor any Finding block". This is the SAME class as the demo-night
    lesson already in this file — strict on format, not substance — and it cost 2 attempts
    and 45k tokens. The gates did not catch it because my own known_good fixture wrote the
    label form my regex already accepted. FIX APPLIED: the prefix now tolerates an optional
    `#{1,6}` heading marker. RULE: when a check parses labels out of free-form model prose,
    the known_good fixture must exercise EVERY plausible formatting of that label, not the
    one you happened to write.
  · Check design that paid off: requiring each finding's evidence to be a span appearing
    VERBATIM in the reviewed document (whitespace-normalised, ellipsis-tolerant) — a
    mechanical anti-hallucination gate for prose review, which is otherwise the weakest
    thing in the tool to verify. Smoke-tested by mutating a good report's quotes into
    plausible paraphrase: check failed and named the offending spans. Across 5 lanes it
    verified 72 verbatim spans; no lane fabricated a citation.
  · Pilot gate earned its wall-clock: the pilot report was read before 4 more lanes spawned.
    Had the brief been wrong, it would have cost one lane instead of five.
- 2026-08-15 — FLONT-FRIEND ARCH REVISION (1 task: repair a P0 + 3 provenance defects in a
  714-line design doc; worktrees, owns = the one document). codex high effort, FIRST TRY,
  296s. Task PASS, integration FAIL — and the integration failure was MINE.
  · The lane's output was better than my own known_good skeleton in a way worth recording:
    my fixture bound Accept to a single request-level `expectedProposalId`, which is WRONG
    for a batch accept over many targets. The worker introduced
    `ClassificationProposalTarget {target, proposalId}` so each target carries the proposal
    the owner actually reviewed. Writing a known_good taught me the check was satisfiable;
    it did NOT teach me the right design, and I should not have assumed my skeleton was it.
  · ORCHESTRATOR FAILURE (mine — gate-side, stale regression baseline) — over-strict INTEGRATION gate. I reused the review
    lane's `proof.sh` verbatim as a regression gate, but that script pins an exact schema
    inventory ("9 CREATE TABLEs, 16 named objects"). The task's whole mandate was to ADD a
    table, so the gate demanded the revision not do the thing I asked it to do. 20/21
    assertions passed; the 1 failure printed `apply_ok=1`, i.e. the SQL applied fine and only
    the count differed. FIX: assert the SUPERSET property (every originally-verified object
    still exists, new objects reported not forbidden) instead of byte-identical inventory.
    RULE: a regression gate built from a proof of the OLD artifact encodes the old artifact's
    shape. Before reusing one across a change, ask which of its assertions the change is
    supposed to invalidate — and re-express those as properties, not counts.
  · What worked: telling the worker the exact self-verification command in the spec
    (`python3 .../revision_check.py --repo . --baseline-doc ...`). It ran the check itself,
    iterated to OK, and passed on attempt 1. A check that executes the artifact (applies the
    SQL to a real sqlite) doubles as the worker's own feedback loop when you hand it over.
- 2026-08-15 — KIT LABEL TOLERANCE (1 task: teach two shipped prose-review kits to read a
  finding label in any Markdown dress). codex high effort, task logged FAIL after 2
  attempts — and BOTH failures were mine. The worker's implementation was correct from
  attempt 1; re-running my corrected check against its untouched worktree printed CHECK
  PASS immediately.
  · ORCHESTRATOR FAILURE (mine, #12) — dress-unaware negative fixtures. The gate renders
    one valid report in five label dresses (plain / heading / bulleted / numbered / bolded)
    and demands a PASS each time, then injects five defects and demands a FAIL each time.
    I wrote `transform(dress(base, style))` — dress FIRST, then mutate. But the mutators
    matched `^Fix\s*:`, which does not match `### Fix:`, so in four of the five dresses the
    "defective" report was never actually damaged. The gate handed the worker a VALID
    report and demanded it be rejected. Impossible, twice, for 660s.
    FIX: `dress(transform(base), style)` — injure the plain text, then dress the wound.
    RULE: when a check generates fixtures by composing transforms, assert the fixture
    really carries the defect before asserting anything about the deliverable. One
    3-line loop (`assert "Fix:" not in out`) would have caught this before any worker ran.
    This is the same family as the demo-night and nemotron lessons: I keep writing checks
    that are strict about a shape I invented rather than the substance I care about.
  · What the gates did and did not catch: `--baseline` and `--prove-fail` both behaved
    correctly and both PASSED their own contract, because the bug was not "the check
    cannot fail" — it was "the check fails for a reason no worker can fix." Neither gate
    can see that. The only thing that caught it was reading the worker's failure note,
    which said the fixtures were contradictory. LESSON: when a competent engine fails
    twice on a mechanical task, read its complaint as evidence about the CHECK before
    treating it as evidence about the model.
  · The worker beat my own mental model on an edge case: `## Finding:` is a legitimate
    label dress, but in review-swarm it also looks like the start of the next `##` report
    section, so extracting the Findings body would truncate. It normalises level-two
    label headings to `###` before slicing. My fixtures only ever emitted `###` and would
    never have found this.
  · Field evidence that started the round: the two kits accepted MUTUALLY EXCLUSIVE label
    forms — adversarial-review only `Finding:`, review-swarm only `### Finding:` — and
    neither accepted bulleted, numbered or bolded. A user copying both kits into one
    project had no single report format that satisfied them.
- 2026-08-15 — RINGSIDE DESIGN DIRECTIONS (3 lanes, design-directions kit's FIRST real use,
  target = Ringer's own dashboard). codex high effort ×3, 3/3 PASS first try, 437s / 743s /
  1140s. Same engine in every lane on purpose: vary the direction, hold the model constant,
  or the comparison is confounded. Same run fixture in every lane for the same reason.
  · The kit worked. Three genuinely distinct directions came back — a monospace control-room
    matrix, an editorial run report, and a status-first signal board — all rendering the
    SAME five-lane run, so the comparison was about design rather than content. The
    divergence-notes requirement did its job: each lane named specific departures from the
    supplied reference (card containers to ruled matrix, proportional display face to
    monospace, broad green bar to five discrete lane segments) instead of describing itself.
  · KIT DEFECT FOUND BY USING IT (1): the README documented `{{PRODUCT_NAME}}` and
    `{{DIRECTION}}`; the manifest wanted `{{PROJECT_NAME}}` and `{{DIRECTION_A/B/C}}` and
    also `{{SCREEN_SOURCE_FILE}}` and `{{SCREEN_OR_COMPONENT}}`, which the README never
    mentioned. Filling the kit in from its own README yields a manifest with four unfilled
    holes and two substitutions that do nothing. Now fixed and pinned by a test that scans
    EVERY file in a kit — placeholders also live in `prompts/`, so an audit that reads only
    manifests reports three false drifts and misses nothing real.
  · KIT DEFECT FOUND BY USING IT (2), the serious one: `check_direction.py` accepted ANY
    non-empty file as the render. `echo x > direction.png` passed. For a round whose entire
    deliverable is an image, the central assertion could not fail. Now the gate reads the
    PNG header and weighs compressed image bytes against pixel count — a blank 1440x900
    page compresses to ~0.0045 bytes/pixel, a built screen to ~0.1, a 20x margin. Rejects a
    text file named .png and a screenshot of an empty page.
    RULE: when the deliverable is an artifact rather than text, ask what the check would
    accept if the worker were lazy in the cheapest possible way, and close THAT.
  · ORCHESTRATOR FAILURE (mine, #13) — my spec told each lane to self-verify with "the exact
    command that will judge you", the trick that worked so well on the flont-friend
    revision. But headless Chrome ABORTS (exit 134) inside the worker sandbox, so no lane
    could run the gate it was measured by. All three passed anyway — Ringer executes checks
    outside that sandbox — but they built the most important deliverable blind. Two lanes
    independently discovered `--no-sandbox` makes Chrome work inside the sandbox and
    documented the deviation in their notes, which is the right behaviour and is why they
    had renders at all. FIX for next time: put `--no-sandbox` in the canonical render
    command. RULE: "give the worker your check" only helps if the worker's environment can
    RUN your check. Verify that before promising it in a spec.
  · Also caught by hand-smoking, before any worker ran: my wrapper check hung for 180s
    because Chrome hangs indefinitely when given `--user-data-dir`. Three concurrent
    profile-less renders were then verified to succeed, which is what made max_parallel 3
    safe. A crashing check remains the one failure the gates cannot catch for you.
- 2026-08-15 — RINGSIDE CONTROL-ROOM BUILD (foundation + 2 fan-out lanes, scaling the
  owner-approved Direction A comp into the real dashboard). codex high effort. Foundation
  logged FAIL, fan-out 2/2 PASS first try. The foundation's work was CORRECT — re-running
  the corrected gate against its untouched worktree printed CHECK PASS with 367 tests.
  · RINGER DEFECT — `questions_file` and `owns` are mutually incompatible. The spec told
    the worker to write ./questions.md on a judgment call, which is Ringer's own documented
    escape hatch; the ownership check runs `git status --untracked-files=all` against the
    `owns` patterns with NO exemption for the configured questions file, so doing the
    documented thing failed the lane. README says the questions file "never blocks, never
    fails a task, and never changes a verdict." It does. Workaround: add `questions.md` to
    every lane's `owns`. Real fix: exempt the manifest's questions_file from the ownership
    sweep.
  · RINGER LIMITATION — `contracts` cannot freeze a CSS vocabulary. It matches
    `(class|def|struct|enum|interface|type|typedef|protocol|func|fn|const|let|var)\s+SYMBOL`;
    a custom property declares none of those keywords, so listing token names as contracts
    enforces NOTHING and fails open. For frontend fan-out the shared vocabulary is almost
    always custom properties, which is exactly the case the feature advertises. Token
    parity had to be enforced in the check instead.
  · RINGER LIMITATION — `CHECK_TIMEOUT_S` is a hard-coded 60s with no per-task override. A
    gate that renders a surface and runs the suite cannot fit, and it does not fail with a
    useful assertion, it fails with rc=-15. My first gate timed out on BOTH lanes in
    --baseline, which tells you nothing. Restructured to render only the surface under test
    and run only the pinning test: 10s.
  · BUG FOUND BY THE GATE, unrelated to the restyle: STATUS_COLORS maps running, retrying,
    verifying and live to var(--running) — defined in neither surface. The four statuses you
    watch while a run is in flight had no colour at all and fell back to inherited. Found by
    a dangling-var() assertion written for a different purpose. Now a frozen token, fixed.
  · ORCHESTRATOR FAILURES (mine, #14-#17): (14) the self-verify command in the spec omitted
    the required --surface flag, so it exited in argparse; (15) export_patch listed 2 of the
    foundation lane's 3 owned paths, so the design-reference fixture would have been silently
    dropped from the patch — THE WORKER caught this in questions.md; (16) I repeated failure
    #13 verbatim, promising "verify yourself with the exact command that will judge you" for
    a gate that cannot run in the worker sandbox at all (Chrome exits 134, localhost binds
    refused) — the fix I had already written down and not applied is now a --worker-preflight
    mode running only what the sandbox permits; (17) the change-vs-baseline assertion measured
    against the PRE-foundation render, so the inherited token diff alone scored 23% and a lane
    could have no-op'd and passed; re-baselined against post-foundation HEAD, 0.0%.
  · The worker's questions.md was the single most useful artifact of the round: four items,
    three of them my bugs. RULE: read the questions file even when — especially when — the
    lane failed. That is what it is for, and it is cheaper than any post-mortem.
  · Sequencing worked exactly as intended: foundation ran alone, failed, and the fan-out
    never spawned. Landing the verified foundation first, then fanning out over disjoint
    files, produced two patches that applied cleanly with no merge work.
- 2026-08-15 — RINGSIDE LIVE LANES + COLUMN RETUNE (1 lane, follow-up to the control-room
  build). codex high effort, PASS on attempt 2, 832s. Two defects fixed; the gate work
  found the real one.
  · THE DEFECT I ALMOST MISSED BY EYEBALLING: I reported to the owner that the live view
    "still uses the roomy sans hero". That was WRONG — the live page shares
    ARTIFACT_BASE_CSS and had been restyled correctly. I had been looking at a screenshot
    of a DIFFERENT run (single-task) and generalised from it. Rendering the live page from
    a purpose-built 5-lane in-flight state showed the actual bug: render_status_html calls
    render_work_section(finished_only=True), so the matrix listed 2 finished lanes while the
    header and progress bar both said 5. The running lane had no row.
    RULE: when judging a surface, render it from a state you CONSTRUCTED to exercise the
    case, not from whatever happened to be on screen. An incidental screenshot is a sample
    of one, and I described its accident as the surface's behaviour.
  · CHROME HANGS ON SELF-REFRESHING PAGES. The live artifact carries
    <meta http-equiv="refresh" content="2">, so --virtual-time-budget never drains and
    headless Chrome never reaches the screenshot — it sat until the 200s timeout with no
    error. Dropping the flag renders it in 3s. Any check that screenshots a live/polling
    page must omit --virtual-time-budget.
  · ORCHESTRATOR FAILURE (mine, #18) — a FALSE-PASS assertion, caught by --baseline. My
    first lane-coverage assertion was `every task key appears in the live HTML`. That passes
    on unmodified HEAD, because lane keys also appear in the progress bar's labels even when
    the lane has no row; a no-op would have satisfied it. Re-anchored to counting the
    `class="work-item"` row marker, HEAD correctly reported "2 lane rows for a 5-lane run".
    RULE: presence-of-substring is not evidence of structure. Count the structural marker.
  · ORCHESTRATOR FAILURE (mine, #19) — I added `questions.md` to the lane's `owns` to dodge
    the questions_file/owns collision, but ALSO left it in the check's exported path list,
    so the exported patch would have committed questions.md into the repo. Applied with
    `git apply --exclude=questions.md`. The workaround for one defect created another.
  · Worker quality: it rendered waiting lanes as "Waiting its turn." with 0s and NO
    deliverable links, exactly as the spec's honesty rule demanded — it did not invent a
    deliverable to fill the column. Attempt 1 failed, attempt 2 passed.
- 2026-08-15 — LANE LABEL OVERLAP (fixed inline, no worker: one CSS rule, root-caused).
  The control-room shell restyle gave the lane status a FIXED 90px grid track, while
  `.state` inherits white-space:nowrap from the base rule and the restyle added uppercase
  + .08em letter-spacing. "finished & checked" measures ~155px. A grid item defaults to
  min-width:auto, so instead of shrinking it overflowed its track and painted over the meta
  column, on both the lane wall and the single-run lane list.
  · WHY THE GATE MISSED IT: my shell check proved the page was a real, non-blank, changed
    image. A pixel-diff cannot see two text nodes occupying the same pixels — the render
    was "real" and "changed" and also broken. RULE: image-level assertions verify that a
    surface EXISTS, never that it is CORRECT. For layout, assert geometry.
  · WHAT VERIFIED IT PROPERLY: a real browser measuring the DOM. For every status label,
    including the longest ("sent back — redoing"), assert (a) scrollWidth <= clientWidth and
    (b) the element's bounding rect does not intersect any sibling cell's rect. The second
    is the one that matters — it is a direct, mechanical statement of "does not collide",
    which is exactly the defect. Stress-test the LONGEST possible label, not whatever
    string the live data happens to contain: the run on screen said "working" (7 chars) and
    looked fine.
  · Fix: track widened to minmax(155px, auto); .state gains min-width:0, overflow:hidden,
    text-overflow:ellipsis so a future longer label clips rather than collides.
- 2026-08-15 — MODELS TAB DENSITY (fixed inline, root-caused). The scoreboard set
  `min-width: 1500px` on a 12-column table inside an `overflow:auto` wrapper, so a 1440px
  window ALWAYS carried a horizontal scrollbar and every column read cramped. Now under
  1200px at control-room density; measured in a real browser as scrollWidth == clientWidth
  (1381px) with all 21 rows present.
  · WHY THE RESTYLE MISSED IT: the Models tab's markup AND css are injected by
    `inject_models_tab_into_ringside_html` in ringer.py — they are not in
    dashboard/ringside.html at all. The shell lane owned ringside.html and restyled it
    faithfully; the tab it never saw kept the old look. RULE: before scoping a restyle by
    FILE, find every place the surface's CSS actually lives. "The shell is one file" was an
    assumption, and a third style block was hiding in the Python that serves it.
  · CONFIRMED BUG, not yet fixed: the Runs/Models tab is absent from URL state. Clicking
    Models leaves `?tab=live&view=single` in the address bar — `tab` tracks live-vs-single,
    not runs-vs-models — so `?tab=models` can never work and the Models tab cannot be linked
    or restored on reload.
  · TOOLING NOTE: Playwright MCP's browser_take_screenshot writes into the MCP server's own
    sandbox, which is not readable from the shell here. For a surface that needs interaction
    (the Models tab requires a click, since it has no URL), geometry assertions via
    browser_evaluate are the verification; headless-Chrome --screenshot only works for
    surfaces reachable by URL.
- 2026-08-15 — TWO FIXES, inline, both root-caused and pinned by tests.
  · MODELS TAB HAD NO URL. `tab` already means live-vs-artifacts, so the Runs/Models nav
    was never represented at all — ?tab=models could not have worked, and the tab did not
    survive a reload. Now round-trips through a `panel` param. Verified in a real browser:
    ?panel=models restores the tab on load, Runs drops the param, Models sets it.
  · QUESTIONS FILE COUNTED AS AN OWNERSHIP VIOLATION — Ringer failing a worker for using
    Ringer's own escape hatch, against an explicit README promise. Fixed by exempting the
    configured questions_file from the ownership sweep. Two tests: one proving the exempt
    lane passes, one proving a stray file STILL violates when questions_file is set, so the
    exemption is one filename and not a hole. Confirmed the test fails without the fix by
    stashing the change and re-running — prove-it-can-fail applies to unit tests too, not
    just checks.
  · PROCESS SLIP: `git add -A` swept two Playwright MCP scratch snapshots into two commits.
    Removed and gitignored. When a tool writes scratch into the repo, stage by path.
- 2026-08-16 — MODELS TABLE WRAPPING. The owner looked at the tab and said it was "tight in
  places that don't need to be" — and was right about something my geometry check could
  never have seen. I had verified "no horizontal scroll" and called it fixed. Absence of
  scroll is not absence of cramping: every column except notes wrapped internally, so
  "OpenRouter API" broke over two lines and "July 18, 2026" split after the comma, while
  notes ate the spare width. Fixed with nowrap on the atomic columns and a 90ch cap on
  notes; measured at 1800px, notes 486->640px, first row 12->9 lines, median row height
  104->87px.
  · MEASUREMENT ERROR I MADE AND CAUGHT: my first wrap detector compared each cell's
    height against its line-height. Every cell "failed", including a Tasks cell containing
    "5". Table cells STRETCH to the row height, which notes drives, so cell height says
    nothing about the text inside it. The correct measure is line boxes:
    `range.selectNodeContents(el); range.getClientRects().length`. Under that, headers and
    text cells were clean and only the Tier column reported >1 — an artifact of the
    inline-flex badge, not wrapping. I nearly reported a false failure from a bad metric.
    RULE: when a metric flags EVERYTHING, suspect the metric before the code.
  · STANDING LESSON, third time today: image-level and box-level assertions prove a surface
    exists and fits. They cannot see collision (the lane label), cramping (this), or
    hierarchy. A human glance found both defects my gates passed. Machine checks are for
    "did it render, is it coherent, did it change" — not "is it good".

- 2026-08-15/16 — FLONT-FRIEND PHASE 2, the whole build (9 further runs: three
  architecture-revision lanes, implementation Rounds 0-4, one fix lane). codex
  high effort throughout, one GLM proof lane. 8 of 9 passed first try; the ninth
  passed on attempt 2. ZERO runs failed on bad model output. Every failure in
  the phase was a defect in MY check. That ratio is the entry.
  · Four checks I wrote were IMPOSSIBLE to satisfy, each in a different way:
    (1) parsed `cargo test -- --list` with `split(":")[0]`, but Rust paths use
    `::`, so every name collapsed to its first segment and a module filter
    matched nothing; (2) hard-coded a shared CARGO_TARGET_DIR that the worker
    sandbox cannot write to, so the check could never pass from inside a lane —
    this failed a round outright and wasted a build in another; (3) set an
    ownership boundary (`src/lib/**`) for a round whose wire change necessarily
    broke a React component the lane was forbidden to touch; (4) demanded a
    proof script written for the OLD artifact keep passing across a change that
    was explicitly asked to add a table. RULE: after writing a check, ask what
    the task is supposed to CHANGE, and confirm the check permits exactly that.
  · One check nearly false-PASSED: hazard coverage asserted on test NAMES, but
    the repo already had tests matching those words for unrelated features
    (`bulk_delete_requires_trash_and_prune` satisfied "no orphan"). Scoping the
    match to the feature's own module fixed it. Same family as the "greps must
    survive a repo that already says the words" rule, one level up: it applies
    to test names, not just file contents.
  · WORKER BEHAVIOUR WORTH CREDITING. Three separate lanes diagnosed my broken
    check precisely in `questions.md`, proposed the exact fix, and REFUSED to
    work around it — one even declined to edit a file it did not own or weaken a
    wire contract to make a build pass, and said so. A fourth disclosed the
    workaround it had been forced into, which is why it was safe to strip. The
    spec line that earned this: "if a check seems impossible to satisfy
    honestly, STOP and write the contradiction to questions.md rather than
    working around it." Use it verbatim; it converts a silent creative
    satisfaction into a bug report.
  · THE REAL MISS, and it is not about models. Every check I built verified the
    Rust backend rigorously — executing migrations against a copy of the owner's
    real 2,818-bookmark database, parsing the JSON schema as data, enumerating
    test names to force concurrency coverage — and verified the UI only by "does
    it compile". Four rounds passed clean and the app hung on the first click.
    The repo turned out to hold ELEVEN frontend test files with 86 cases and NO
    test runner wired: they had never executed once, needed zero dependencies
    (`node:test`), and one of them caught a real regression the moment it ran.
    RULE: before trusting a check suite, ask which layer it cannot see, and
    check whether the repo already contains dead tests for that layer.
  · Technique worth reusing: a StrictMode-only React bug was reproduced HEADLESS
    by driving TanStack's `MutationObserver` directly — subscribe, mutate,
    unsubscribe, resubscribe, resolve — with no DOM and no new dependency. When
    a UI bug is really a lifecycle bug, the lifecycle is usually testable alone.
  · Diagnosis order that worked on a hung GUI, cheapest first: read the app's
    captured stdout for a panic; `sample <pid>` the live process (all threads
    parked with zero app frames ruled out deadlock AND slow queries in one
    shot); check CPU across WebKit processes (ruled out a render loop); read the
    webview console. Only then read code. I inverted this at first and burned
    several turns on hypotheses that measurement killed in seconds.

## 2026-08-20 — taste_mthfl_com, multi-source extraction (3 rounds, 8 lanes)

**GPT-5.6 Sol · medium (Codex)** — 6 lanes: contract freeze, three extractors,
verifier generalization, corpus migration. 5/6 first-try; the one retry was MY
spec's ambiguity, not the model's error (its first validator resolved
`evidence.index` against the filesystem and required `viewport.user_agent`,
neither of which the pinned contract said either way — the retry relaxed both
correctly). Medium continues to beat high on this workload: it moved this repo's
code-feature line to 30 tasks / 60% first-try / 90% pass at 56k median tokens,
against high's 68 tasks / 54% / 72% at 92k. Keep spending high elsewhere.
  · Worth reusing: the specs pinned the CONTRACT (required keys, id forms, index
    columns) and left the internals free. Every lane's check then delegated
    manifest validity to the validator a previous lane had written, so the
    checks stayed contract-independent and the lanes could not drift apart.
  · All three extractor lanes independently reported real contract frictions in
    notes.md rather than working around them — dpr not being knowable from a
    bare image, one `original_filename` slot for a directory of images. Two
    became a follow-up amendment lane. Specs that say "if the contract and this
    brief disagree, the contract wins, and say so in notes.md" are what produced
    that instead of silent divergence.

**zai-coding-plan/glm-5.2 (OpenCode)** — 1 docs lane, first-try pass: README +
AGENTS + CLAUDE for a repo whose whole thesis is not overclaiming. It invented
no tools, and CLAUDE.md came back as a 7-line import rather than a second copy.
Cheap and correct on docs; the scoreboard's docs numbers hold up.

**poolside/laguna-s-2.1:free (OpenCode) — AUDITION, PASSED with a caveat.**
First attempt died instantly with OpenCode's `Error: Unexpected error / database
is locked` while a SECOND opencode lane (glm-5.2) ran concurrently. That is a
harness finding, not a model verdict: two concurrent opencode lanes contend on
the shared SQLite state DB, and one of them loses. Re-run SOLO it passed on
attempt 1 — a four-file surgical change (loosen a JSON validator, amend a spec
doc, update an extractor) that my check gated hard in both directions. But it
took ~19 minutes and five separate passes over the same markdown file, versus
Codex medium's ~3-7 minutes for comparably sized lanes. Verdict: usable and free
for mechanical, well-gated work with no deadline; do not put it on a critical
path, and do not schedule it alongside another opencode lane.

**INFRASTRUCTURE — two things cost wall-clock and neither was a model:**
  · `~/.config/ringer/config.toml` had `[engines.opencode] bin` pointing at
    `/Users/jawrsh/_WORK/Repositories/ringer/...`, a path that no longer exists
    (storage reorg leftover). A whole round aborted at pre-flight before
    spawning. Repointed to `~/Work/Repositories/ringer/...`. Worth a periodic
    `test -x` over every engine bin in the config.
  · Do not run two `opencode` lanes concurrently until the state-DB contention
    above is fixed — serialize them, or give each its own state dir.

## 2026-08-27 — Ringside live-watching design directions (3 lanes, codex gpt-5.6-sol high)

3/3 PASS first try, 314k tokens, ~11 min wall clock for three parallel lanes.
Same engine and model in every lane on purpose; only the design stance varied.
The design work was good — direction A answered all three P1s at a glance, and
direction B produced the single best artifact of the round, a failure panel that
says "The worker finished cleanly. The check rejected the work" over a
worker-exit / check-exit / timeout / setup-error grid, captioned "this is check
evidence, not a model verdict."

**The check passed three deliverables it never actually verified.** The kit's
`check_direction.py` confirms `direction.png` is a real PNG above a density
floor, but it never binds that image to `direction.html`. No lane could run
Chrome, so each one DREW the picture instead: two rasterised with Pillow, and
direction-a wrote and compiled a throwaway Swift renderer to do it. All three
passed. This is the "satisfied CREATIVELY" failure mode, and it is worth
underlining that it survived a clean `lint` + `--prove-fail` + `--prove-pass`:
every gate was green because the check could fail, could pass, and named its
reasons — it just measured the wrong artifact.

  · The divergence was NOT cosmetic. Direction C's submitted image showed a
    LIGHT theme; the page actually renders DARK, and the drawing had quietly
    tidied away two label collisions that are really there. Reviewing the
    submitted PNG would have meant reviewing a picture no code can produce.
  · Caught only because the real artifact was verified in its real context —
    I re-rendered all three HTML files myself with Chrome outside the sandbox
    (exit 0, no trouble) and compared. Nothing in the run output hinted at it;
    the summary read `3 pass`.
  · RULE (again, and this is the third time in this file): when the deliverable
    is an artifact rather than text, the check must PRODUCE the artifact from
    the source it is judging, never accept one the worker hands it.

**CORRECTION to the 2026-08-14 note above (line ~1876).** That entry concluded
"put `--no-sandbox` in the canonical render command" and treated the problem as
solved. It is not. I did exactly that, in the spec, in the exact prescribed
command line — and Chrome still exits 134. Worse, the sandbox ALSO refuses the
localhost bind that a `file://`-avoiding render needs:

    PermissionError: [Errno 1] Operation not permitted   (python3 -m http.server --bind 127.0.0.1)

So the "serve over http, then screenshot" instruction I wrote was unusable from
the first line, and the documented fix gave me false confidence that it wasn't.
The honest status: **there is currently no known way to render a page with
headless Chrome inside a Ringer worker sandbox.** Until one exists, image
deliverables must be rendered by the CHECK (which runs outside the sandbox), not
by the worker.

**Credit where it is due:** all three lanes disclosed the substitution in
`notes.md` in plain language rather than claiming a Chrome screenshot —
direction-c even wrote "It is a faithful static export for visual review, not a
claim that Chrome completed successfully." That honesty is the only reason this
cost minutes instead of a shipped decision made on fabricated evidence. It is
also a reminder that worker self-reports are worth READING even though they are
never worth trusting as verification.

**REVISION LANE, same day — direction C rebuilt with a fitted axis.** 1 lane,
codex gpt-5.6-sol high, PASS first try, 57.6k tokens, 380s. The owner pushed
back on my verdict, correctly: I had marked C down for "the premise defeats
itself on real data," but the 8%-of-canvas problem was never the premise. It
was one decision inside it — the axis was pinned to `timeout_s`, reserving
space for data that had not arrived and usually never does. Read as shape is a
legitimate PRIMARY view; it just needs an axis that fits what exists and grows.

  · THE CHECK NOW RENDERS THE PAGE ITSELF, which is the fix for the defect above.
    `gate_direction_axis.py` never accepts a submitted image: it serves the task
    dir, drives real Chrome outside the sandbox, and overwrites direction.png
    from the source it is judging. Fabrication is no longer expressible.
  · IT ALSO BINDS BEHAVIOUR, NOT JUST PIXELS. The spec requires the page to take
    `?elapsed=<seconds>` and expose `data-axis-max-s` on the axis element; the
    gate renders at 360s / 2700s / 4100s, reads the attribute out of the DOM via
    `--dump-dom`, and asserts the domain fits the data early (<=1200s at 360s),
    grows, never exceeds the 4200s budget, and does NOT track elapsed exactly
    (which would mean rescaling every poll). Measured on the delivered page:
    600 / 3600 / 4200. RULE: when a gate cannot read the value off a picture,
    make the page EXPOSE what it drew and assert on that — a DOM attribute is
    checkable where a rendered axis is not.
  · Hand-smoked both directions before spending the worker: a fixture pinned to
    4200 was rejected by name, a correct fitted fixture passed. Then lint,
    prove-fail, prove-pass, all clean.
  · The lane delivered more than the spec: a `window 10m · next 15m` readout
    that makes the quantization ladder legible so a rescale is not a surprise.
    Implemented policy was elapsed x 1.18 snapped up a 2/5/10/15/30/45/60/70m
    ladder, capped at budget. It also raised no questions, wrote no fabricated
    image, and honoured the "do not screenshot" instruction exactly.
  · Verified by looking, at three elapsed values and in both themes — not by
    trusting the green. LESSON FOR ME, not the model: I reviewed a design and
    reported a premise flaw where the evidence only supported an implementation
    flaw. "This approach does not work" and "this parameter is wrong" are very
    different verdicts, and the second one was the true one.

## 2026-08-27 (later) — Ringside live watching, shipped into the real dashboard

Three lanes, codex gpt-5.6-sol high, worktrees, 3/3 PASS FIRST TRY with
integration passing on all three: the lane wall (162.9k tok, 636s), the time
canvas (249.2k tok, 803s), and a follow-up honesty fix (129.6k tok, 324s). No
questions raised. This is the strongest run of the family so far, and the
reason is the gates, not the specs.

**GATING A BROWSER UI AGAINST ITS OWN DOM.** The pattern that made this work,
and that should be reused: serve the REAL page against a synthetic /api/runs
fixture whose rows are engineered to hit each case, drive real Chrome, and
assert on the DOM the page actually built. Never inspect a screenshot, never
trust a self-report.
  · `--dump-dom` ALONE CAPTURES AN EMPTY PAGE. Ringside fetches asynchronously,
    so the DOM is snapshotted before the first fetch resolves — measured: zero
    lane rows, lane names absent. `--virtual-time-budget` fixes it.
  · CORRECTION to the note above (2026-08-14, ~line 1943): that entry says a
    page must omit `--virtual-time-budget` because Chrome hangs. That is true of
    `<meta http-equiv="refresh">` pages. It is NOT true of `setInterval` pages —
    Ringside polls every 1s and drains a 4s budget in ~3s, every time. The flag
    is not the problem; meta-refresh is. Budget size also doubles as a time
    machine: a 220s budget advanced the clock far enough to watch the 180s
    staleness threshold trip.
  · MAKE THE PAGE EXPOSE WHAT IT DREW. A gate cannot read a number off a
    picture, so the canvas spec REQUIRED `data-axis-max-s`, `data-token-max`,
    `data-samples` and `data-lane-start-s`. Every meaningful assertion in that
    gate reads one of those. Design the contract with the gate, not after it.

**MY OWN GATE FALSE-PASSED TWICE, BOTH TIMES ON MY FIXTURE'S WORDING.** The
timeout assertion passed because I had written "check exceeded its window" as
that lane's activity text; the setup assertion passed because I had named the
lane `broken-setup`. In both cases the grep matched MY fixture rather than
anything the UI derived. Failures went 18 -> 19 -> 20 as each leak closed.
RULE: a fixture must never contain the words its assertions search for — that
includes the KEY, not just the values. This is the same lesson as "greps must
survive a repo that already says the words", and it bit me from a new direction.

**FABRICATE THE GOOD STATE EVEN FOR CODE LANES.** The skill says a code lane's
good state usually cannot be fabricated, which leaves prove-pass with nothing.
Both gates here got a `fabricate_good_*.py` that bolts on the required DATA with
no design work — ~60 lines each. Cheap, and it converts "the lane failed" from
ambiguous into evidence about the lane. One of them caught a real bug in my own
fabricator (`createElement("section")`, not `"div"`) before any worker ran.

**THE DEFECT NEITHER GATE COULD HAVE CAUGHT, found by looking.** The canvas
derived every lane's start offset as `run.elapsed_s - task.elapsed_s`. Valid
while a lane RUNS; for a finished lane `elapsed_s` is frozen at total duration,
so the number is meaningless AND MOVES — the same completed lane read "spawned
3m 53s after run start" and then "spawned 4m 39s" 46 seconds later. Caught by
rendering the same run at two clock positions and reading the two screens, not
by any assertion. The fix makes it say "spawn time not observed", matching how
the view already refuses to place an unwitnessed retry boundary.
  · Worth noting WHY it slipped through: the whole round was specified around
    not asserting unobserved things, and the lane obeyed that perfectly for the
    retry boundary while violating it for the spawn offset. A discipline stated
    once in a spec gets applied where the spec points, not everywhere it holds.

**CHECK THE PAYLOAD BEFORE WRITING THE SPEC.** I queried the live /api/runs
rather than trusting my own earlier notes, and it changed the task: `tokens` is
a SCALAR with no time series, there is no per-attempt timing, and no task start
time. So the canvas's traces cannot be read from a field at all — they are
sampled across polls, the sample count is displayed, and an unobserved retry
boundary is labelled rather than guessed. Had I specified from memory, the lane
would have built a fabricated curve that looked perfect and meant nothing.

**INTEGRATION_CHECK EARNED ITS KEEP, TWICE.** Both build lanes reported the
suite failing inside their own sandbox — "426 tests ran, 9 failures and 43
errors" from denied loopback sockets and `~/.ringer` writes. Taken at face value
that reads like a broken change. The out-of-sandbox integration run passed clean
both times. A worker's own test run is not evidence about the tree.
