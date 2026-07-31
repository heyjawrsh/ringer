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
