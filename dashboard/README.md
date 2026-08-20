# Handoff: Ringside Dashboard Redesign

## Overview
A Swiss-modernist realignment of **Ringside**, the dashboard for the Ringer multi-agent swarm runner. It replaces the current glow/pill/rounded-card HUD with one strict system: hairline rules, a single left rail, poster-scale numerals, mono micro-labels, and color used exclusively for run/lane status. It covers five views — multi-run overview, lane wall, pilot review workspace, artifact preview, models scoreboard — plus a slide-over single-run detail panel and system edge states.

## About the Design Files
The files in this bundle are **design references created in HTML** — prototypes showing intended look and behavior, not production code to copy directly. The task is to **recreate these designs in the target codebase's existing environment** (the current Ringside is a vanilla single-file HTML/JS app served by `ringer.py`; recreating in that same vanilla stack is appropriate) using its established patterns — or, if adopting a framework, choose the most appropriate one and implement the designs there.

- `Ringside Prototype.dc.html` — the working prototype: all five views, navigation, slide-over, review flow, loading states. **This is the primary reference.**
- `Ringside Redesign.dc.html` — the exploration canvas: turn 4/5 sections are the finalized static mocks (ids 4a, 4b, 4d, 4e, 5a, 5b, 5c); earlier turns are history; turn 0 is a recreation of the current UI for comparison.

## Fidelity
**High-fidelity.** Colors, typography, spacing, and interactions are final. Recreate pixel-perfectly. Mock data (run names, lanes, activity lines) is illustrative — wire to the real `/api` state payloads that today's `ringside.html` consumes (`runs[]`, `tasks[]`, `pilot`, artifacts library).

## Design Tokens

### Color — light theme (shipped)
| Token | Value | Use |
|---|---|---|
| ground | `#FFFFFF` | page + card background |
| surface-active | `#F4F3F0` | selected nav, working-lane rows, decision aside, expanded panels |
| surface-hover | `#f8f7f4` | row hover |
| ink | `#141412` | text, primary buttons, active nav bar, 2px section rules |
| body-muted | `#6d6c66` / `#3a3935` | secondary prose |
| label-muted | `#8a8983` | mono micro-labels, metadata |
| hairline | `#dddcd6` | row/section dividers |
| hairline-soft | `#e7e6e0` | inner-list dividers, track backgrounds |
| rule-strong | `#b9b8b0` | table header underline |
| terminal | `#353531` | stream/log blocks (text `#e8e7e2`) |

### Color — status (Mapping II of the 10-color ramp)
| Status | Fill | Text-on-light | Tint row bg |
|---|---|---|---|
| working | `#577590` | `#577590` | `#F4F3F0` |
| pass | `#90be6d` | `#5f9a3e` | — |
| fail / died | `#f94144` | `#f94144` | `#fdefee` |
| pilot / retry | `#f9c74f` (dark text `#141412` on fill) | `#c28e0e` | `#fdf8e9` |
| waiting | `#c9c8c1` (outline style: `1.5px solid #c9c8c1`, transparent fill) | `#8a8983` | — |

Reserved for future per-project accents (unused): `#f3722c #f9844a #4d908e #277da1`.

### Dark theme (drafted, see Redesign canvas 4c)
ground `#16181c`, row `#1b1e23`, ink `#f0efec`, muted `#8b8a84`, hairline `#2a2d32`, rule `#3d4147`; status lifted: working `#7e9fc4`, pass `#a3cb82`, fail `#ff5a57`, pilot `#f9c74f` (unchanged), waiting fill `#3d4147`. Tinted rows: pilot `#24211a`, fail `#251b1c`.

### Typography
- **Grotesk (UI/display):** `"Helvetica Neue", Helvetica, Arial, sans-serif`
- **Mono (labels, numerals, code):** `ui-monospace, Menlo, monospace` — all numerals `font-variant-numeric: tabular-nums`
- Scale:
  - Poster stat numerals: 700 76px/0.9, letter-spacing −.04em (secondary unit inline at 34px `#8a8983`)
  - View titles: 700 26px/1, −.01em
  - Panel title: 700 20px/1.2, −.01em
  - Stat-block numerals (slide-over): 700 26px
  - Run names in tables: 600 14px/1.3 grotesk
  - Lane names: 600 12px mono
  - Body/meta: 400 10–11px
  - Micro-labels: 600 9px mono, letter-spacing .12–.14em, uppercase, `#8a8983`
  - Status words: 600 9px mono, .08em, uppercase, status text color
  - Badges: 700 8px mono, .1em, uppercase, 2px 5px padding, status fill

### Spacing & structure
- No border radius anywhere. No shadows except the slide-over (`-24px 0 48px rgba(20,20,18,.18)`).
- Left rail: 216px fixed, `border-right: 1px solid #dddcd6`.
- Rail header: 52px tall, `border-bottom: 2px solid #141412` (the 2px ink rule marks every top-level section header).
- Nav item: 11px 16px padding, 3px left bar (`#141412` active / transparent), active bg `#F4F3F0`.
- Content gutter: 28px horizontal (16px left of status bars in tables).
- Table rows: 13px vertical padding, 4px×34px status bar, 16px column gap.
- Lane strips: flex row, 1px gaps, 10px tall (5px in rail minis, 14px in poster rows), one segment per lane, status fill; working segments pulse.
- Rounds dot-matrix: 9–10px squares, 3px gap; filled = attempted (status color), outlined `1px solid #c9c8c1` = unused.
- Elapsed bars: 4px track `#e7e6e0`, ink fill at % complete (status color when dead), 9px mono label below.

## Screens / Views

### 1. Runs overview (default view) — prototype + canvas 4a
- **Layout:** rail | main. Main stacks: poster stat band → pilot strip (conditional) → table header → run rows → legend.
- **Stat band:** 3 equal columns, 1px hairline verticals, 2px ink bottom rule. Cells: 76px numeral + micro-label. Cell 2 numeral "41lanes" with inline unit; sub-line colored counts. Cell 3 numeral + label in fail red when attention > 0.
- **Pilot strip:** bg `#fdf8e9`, gold badge "1 PILOT REVIEW", bold run name prose, right-aligned black `REVIEW NOW` button (10px mono on `#141412`). Hidden after decision.
- **Run rows:** grid `10px | project/run 1.3fr | lane strip 1.2fr | done 70px | pass·fail 96px | elapsed 116px | started 68px`. Live rows bg `#F4F3F0`, finished rows opacity .72, pilot row bg `#fdf8e9`, died row bg `#fdefee`. Done cell "7/12" — bold count, muted denominator. Canvas 4a also includes a tokens sparkline column (88×16 SVG polyline, 1.2px ink stroke) — include when token telemetry is displayed.
- **Legend:** 8px swatches + 9px mono labels, one row under the table.

### 2. Slide-over run detail — prototype + canvas 4b
- 560px wide (max 80vw), right-anchored overlay above a `rgba(20,20,18,.18)` backdrop. `border-left: 1px solid #141412` + shadow.
- Header (2px ink rule below): 4px working bar, breadcrumb 10px mono muted, 20px run name; actions `ARTIFACT` (1px ink border; hover inverts), `FOLDER` (hairline border, muted), `✕`.
- Stat strip: 4 columns (Done/Pass/Fail/Tokens), 26px numerals, hairline verticals.
- Lane list: rows `8px dot | name 128px | state 84px | activity 1fr | elapsed 54px`; dot = 8px square status fill (waiting = outline only); row tints per status; selected lane bg `#eceae5`.
- Expanded detail (selected lane): bg `#F4F3F0` — rounds dot-matrix + "passed on round 3 of 5" + terminal block (`#353531`, 10px/1.6 mono, `white-space: pre-wrap`).
- Footer: run id · elapsed · keyboard hints (`↑↓ lanes · esc close`).

### 3. Pilot review workspace — prototype + canvas 5a
- Layout: main evidence column (1fr) | decision aside (320px, bg `#F4F3F0`, hairline left).
- Title row (2px ink rule): "Pilot review" 26px + run/pilot metadata + right-aligned gold wait counter (`waiting 6m of 30m · 5 lanes held`, `#c28e0e`).
- Evidence: 2-up bordered grid (Deliverable / Check), rounds matrix, terminal stream block, held-lanes callout (3px gold left bar on `#F4F3F0`).
- Decision aside, top to bottom: micro-label "Clear this item"; **primary approve** — full-width 38px black button `APPROVE & RELEASE 5 LANES`; "Request changes note" label (gold); textarea (`1px solid #c9c8c1`, white); `SEND NOTE & RE-RUN PILOT` outline-gold button (disabled at .45 opacity until note non-empty); `Reject & end the run` — red underlined text link with confirm dialog; status line; terminal CLI equivalents pinned at bottom.
- Rail variant: "Reviews" nav item carries gold count badge; queue list under "Queue · oldest first" with selected item marked by `inset -3px 0 0 #141412`.

### 4. Lane wall — prototype + canvas 5b
- Title row (2px ink rule) + census + sort note ("attention → working → pass").
- Rows: grid `10px | lane 150px | run 1fr | state 100px | activity 2fr | elapsed 90px`, same status treatment as slide-over lanes, sorted attention-first. Pilot-gated lane reads "review" in gold with held-lane note.

### 5. Artifact preview — prototype + canvas 4e
- Layout: rail | artifact list (260px, hairline right) | stage.
- List rows: 4px status bar + name (12px mono 600) + meta (9px mono muted); active row bg `#F4F3F0` + `inset -3px 0 0 #141412`.
- Stage toolbar: working dot, run name, meta, right controls (`version: live ▾`, `open folder`, `↻` — hairline-bordered, bg `#F4F3F0`).
- Stage body: the artifact iframe (prototype shows a striped placeholder).
- Footer summary strip: lane strip + `7/12 · 7·1 · 412k tok · 42m` + `open run detail →` link (`#577590`) opening the slide-over.

### 6. Models scoreboard — prototype + canvas 4d
- Title row (2px ink rule) + meta. Table: `model 1.2fr | tier 92px | win rate 1fr | pass 80px | fail 80px | avg tok 90px`.
- Tier badges: outlined mono uppercase — proven `#5f9a3e`, probation `#c28e0e`, new `#8a8983`.
- Win-rate: 6px track `#e7e6e0` + fill (pass green ≥ proven, gold probation, `#c9c8c1` new) + 9px mono caption.

### 7. System states — canvas 5c
- **Empty:** centered `0` (34px, `#c9c8c1`) + "NO SWARMS LIVE" + CLI hint chip on `#F4F3F0`.
- **Reconnecting:** `#F4F3F0` bar, pulsing gray dot, "RECONNECTING…" + staleness note + `RETRY NOW` outline button.
- **Update banner:** 3px working-blue left bar, prose with bold commit count, dismiss ✕.
- **Build mismatch:** 3px gold left bar, outlined gold build chip + explanation prose.

## Interactions & Behavior
- **View switching:** rail items swap main view; show a skeleton (3–5 shimmer bars, `shimmer` 1.1s linear, gradient `#f4f3f0→#eceae5`) for ~350ms; new view fades in (`fadeIn .25s`), rows stagger (`fadeUp .3s`, 50ms increments).
- **Slide-over:** opens from run rows / rail live-now items / "open run detail"; `slideIn .28s cubic-bezier(.2,.8,.2,1)` from translateX(40px); backdrop fades in .2s; closes on ✕, backdrop click, or Escape.
- **Review flow:** approve → button reads `APPROVED ✓`, status "Approved. Held lanes will resume." (green), queue badge → 0, pilot strip disappears, lane-wall row flips to pass. Send-note requires non-empty note → status "Changes requested…" (gold). Reject → `window.confirm` → status "Rejected. The run will end." (red). All controls disable after a decision (0.45 opacity).
- **Artifact selection/refresh:** ~420ms "re-rendering artifact…" pulse state, then content fades in.
- **Live telemetry:** clock ticks 1s; working-lane activity lines rotate every ~2s; elapsed counters increment; all pulsing uses `pulse` 1.4s ease-in-out (opacity to .35). Respect `prefers-reduced-motion`.
- **Hovers:** rows `#f8f7f4`; nav/list items `#F4F3F0`; black buttons lighten to `#3a3935`; bordered buttons darken border to ink.

## State Management
- `view: "runs" | "lanes" | "reviews" | "artifacts" | "models"` (persist like today's tab key)
- `loading: boolean` (view-switch skeleton)
- `panelOpen: boolean`, `selectedRun`, `selectedLane`
- `selectedArtifact`, `artifactLoading`, artifact version selection
- `pilotDecision: "" | "approve" | "revise" | "reject"` per run + note text (today's `pilotDecisions`/`pilotNotes` maps carry over)
- Clock/ticker; data from existing polling — keep the existing morph/patch rendering approach so polls don't blow away focus or animation state.

## Assets
None. No icons, no images — glyphs are text (`✕ ↻ ▾ →`), all graphics are CSS boxes or one inline SVG polyline (sparkline). No icon font needed.

## Files
- `Ringside Prototype.dc.html` — working prototype (primary reference)
- `Ringside Redesign.dc.html` — mock canvas; finalized screens: 4a, 4b, 4d, 4e, 5a, 5b, 5c; dark draft: 4c; current-UI recreation: 0a/0b
