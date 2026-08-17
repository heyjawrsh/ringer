# Ringside interface patterns — research notes

Pattern research for Ringside, done 2026-08-16 against Mobbin (web corpus) and
a1.gallery. The point of the exercise: Ringside's surfaces were shaped by what
was easy to render from the run JSON, not by what the data actually *is*. This
file maps each data type to the pattern class that fits it, with real references.

Not a redesign spec. A menu of prior art with the reasoning attached, so the
next person picks a pattern instead of inventing one.

## Tool calibration (read before spending more research time)

- **Mobbin** — the workhorse. Its web corpus is full of exactly our neighbours:
  eval harnesses, job runners, log viewers, agent consoles. Use `deep` mode and
  describe ONE screen per query; combining intents returns mush.
- **a1.gallery** — wrong tool for this job. Its corpus is marketing/landing
  sites (hero, pricing, features sections). A query for "monospaced techy dark
  data-dense dashboard" broadened to near-nothing and returned a single result.
  Use a1 for the *visual* layer only — typographic character, palette grounding,
  `analyze_design_tokens` for type scale and spacing norms. Do not ask it for
  application UI.
- **details.so** — no MCP, but the value is real and the workaround is cheap.
  Do NOT try to summarise it from memory. Either (a) screenshot the detail and
  drop the image into the session — images are readable directly, or (b) drive
  it with the Playwright MCP against a logged-in session. Best long-run option:
  save keepers as images under `docs/design/references/` with a one-line note on
  *what problem the detail solves*. That makes the library greppable and lets
  any future session read the actual artifact instead of a description of it.
- **BMAD Method** — take the artifact sequence, not the agent cast. The useful
  half is the front end (brief → UX spec → per-surface stories) which is exactly
  the discipline missing here. The back half (Scrum Master / Dev / QA agents) is
  redundant: Ringer already has a better execution engine, because Ringer's
  lanes are verified by executed checks and BMAD's are not.

## The data types (this is the part that was missing)

Ringside renders five distinct types. Most of the current UI treats four of them
as "a list of things with a status," which is why it reads as developer-designed.

| # | Type | Shape | What makes it hard |
|---|---|---|---|
| 1 | **Live run** | N concurrent lanes, each `status × engine·model × elapsed × attempts × tokens × activity × violations` | Evolves in real time; lanes are *parallel*, not sequential; cost and verdict are both first-class |
| 2 | **Worker log** | append-only stream, structured JSON-ish events | High volume, low signal density, currently rendered as raw mono text |
| 3 | **Pilot gate** | one blocking human decision on one deliverable | Binary today; the decision has no memory and no note |
| 4 | **Artifact library** | job → ordered versions (rounds), each with files | Rounds are diffable and nothing diffs them |
| 5 | **Model scoreboard** | ranked table, ~8 metrics per model, plus tier | Too many columns; no time window; tier ladder is invisible |

Statuses in play (`taskKind`): `pass`, `working`, `retry`, `waiting`, `fail`.
Note `retry` and `waiting` are semantically unlike the other three — one is a
second chance, one is *not started*. Current UI colours all five as peers.

---

## 1. Live run — lane wall

**Today:** a `rounds` strip of tiny status squares, then a stack of `worker-card`
articles. Each card: name, glyph, state word, and a meta line joined with `·`
(`engine · model · duration · attempt N · tokens`). Violations render as a `<ul>`.

**What's wrong:** the meta line packs five unrelated dimensions into one string,
so nothing is comparable across lanes — you cannot see at a glance which lane is
slow or expensive. Duration is a number, never a bar. And a run is *parallel
work over time*, which is the one thing the layout doesn't show.

**References**

- [Vapi — Evaluation Runs](https://mobbin.com/screens/7c24e183-79c5-4666-bfc5-e631e8c9ccde)
  — nearest living relative: an eval harness with Status / Duration / Total Turns
  / Eval Turns as *separate sortable columns*, plus a toast when a run starts.
- [Snowflake — Task History](https://mobbin.com/screens/815a5289-2d5b-40da-a3be-6e2873f5a1da)
  — two ideas worth stealing outright: a **per-row duration-trend sparkline**,
  and a **per-row tally of previous outcomes** as coloured count pills. Ringer
  has this history in `ringer.db` and shows none of it.
- [Databricks — Jobs & Pipelines](https://mobbin.com/screens/84a71801-838b-477f-9bcf-6a07ed99b018)
  — outcome histogram over time above the table, and a **"Top errors" panel
  ranking failure reasons by count**. Ringer's equivalent — which check
  assertion fails most — would be genuinely new information.
- [n8n — Executions](https://mobbin.com/screens/6947469e-9c8c-4644-8cae-56a1250195da)
  — failed rows get a **tinted row background**, not just a badge. Cheap, and
  far more scannable than a coloured glyph.
- [Customer.io — Workspace Performance](https://mobbin.com/screens/b2ebc9f5-2b14-4f18-963e-1a441b10137f)
  — **status filter tabs** (All / Success / Failure / In Progress / Queued /
  Retrying / Canceled) and a plain-language health line above the table.

**Recommended:** keep the card wall for a running lane, but split the meta line
into aligned columns, and render `elapsed_s` and `tokens` as **bars scaled to
the slowest/most expensive lane in the run**. A lane that is 4× the cost of its
siblings should be visible without reading a single number. Add the status
filter tabs, and tint failed cards rather than relying on the glyph.

## 2. Worker log — the expanded stream

**Today:** raw monospace tail, polled.

**References**

- [Better Stack — Live tail](https://mobbin.com/screens/72abcf61-c61a-4460-a0da-b92fef5a3b98)
  — the big one: log lines **tokenised into coloured `key:value` chips** instead
  of a wall of text. Our worker output is JSON events; we are throwing away the
  structure we already have and rendering the serialised form.
- [Modal — App Logs](https://mobbin.com/screens/1f2f0cd1-eadb-435f-9632-116b03a1fc22)
  — timestamp/content split, a **log-volume histogram above for scrubbing**, and
  a persistent `⟳ Streaming` affordance pinned to the bottom.
- [Cloudflare — Workers Observability](https://mobbin.com/screens/df651388-aa38-4859-a81f-684a2ba5d931)
  — a line expands into pretty-printed JSON with per-event actions.
- [Render — build logs](https://mobbin.com/screens/1b400c9e-2ebe-45ad-9d14-83dca9bbd425)
  — filter dropdown + search + `Live tail` toggle + expand, with the destructive
  `Cancel deploy` deliberately outside the log block.
- [v0 — console drawer](https://mobbin.com/screens/c691444b-e765-4232-96c2-a82cb688ea50)
  — preview stays primary, console collapses to a bottom bar. Ringside already
  has an artifact iframe; this resolves the competition between them.

**Recommended:** parse the JSON events we already receive and render chips
(`tokens`, `model`, `tool`, `duration`). Keep a "raw" toggle — the invariant
that logs carry raw worker output is load-bearing and must not be lost, but
that's a constraint on *storage*, not on rendering.

## 3. Pilot gate

**Today:** a banner with Approve / Reject. Reject ends the run.

**References**

- [Relevance AI — agent task review](https://mobbin.com/screens/860b4d5d-622b-4dea-81ed-a5582422fa17)
  — the single most relevant screen found. A **"To Review" queue with a count**
  in the nav; multi-select with **Approve / Rerun / Delete**; and critically a
  **"Leave comment for your agent"** box on the reviewed output.
- [Asana — approval task](https://mobbin.com/screens/e94342b0-adf8-4b9e-85ce-c01c0909cf9a)
  — **three-way**: Approve / Changes requested / Reject.
- [Deel — accept or reject quote](https://mobbin.com/screens/66328d19-07aa-4a67-bacd-4cfea6e32885)
  — decision pinned to a sticky footer while the summary scrolls.

**Recommended, and the highest-value change in this file:** add the middle
option. `Changes requested` + a note, where the note is injected into the
pilot's retry prompt — Ringer already injects check output into retries, so the
mechanism exists and only the UI and one field are missing. Today a pilot that
is 90% right must be approved or killed, and both are wrong.

## 4. Artifact library

**Today:** artifact picker `<select>` + version `<select>` + iframe + Open folder.

**References**

- [Customer.io — version history](https://mobbin.com/screens/84f221e8-ac47-4a9c-8690-0b9caabe833a)
  — **Split view** and a syntax-highlighted red/green diff between versions.
- [WRITER](https://mobbin.com/screens/d6e6654e-119a-456a-acef-fcb72d9ec330) /
  [Sana AI](https://mobbin.com/screens/0d1c373e-876d-48f2-b460-54aa375f8b35) /
  [Fibery](https://mobbin.com/screens/eb05e8be-4a16-47f0-94fe-08ad3da74171)
  — timestamped version rail grouped by day, current version badged, restore
  behind a confirm, and a **"Show changes" / "Highlight changes"** toggle.

**Recommended:** replace the version `<select>` with a timestamped rail and add a
round-to-round diff. "One job, one artifact, many rounds" is already the rule;
the obvious question about round 3 is *what changed since round 2*, and a
dropdown cannot answer it.

## 5. Model scoreboard

**Today:** 12 columns — Model, Lab, Harness, API/Plan, Tier, Tasks, First try,
Pass, Tokens (median), Speed (median), Last used, Notes.

**References**

- [Uxcel — leagues](https://mobbin.com/screens/154735d4-72e4-410c-b748-9225f4c752ac)
  — an explicit **`↑ Promotion Zone ↑` divider** between ranks. This is precisely
  Ringer's untested → probation → proven ladder, which today is a text badge with
  no sense of *distance to promotion*.
- [Duolingo](https://mobbin.com/screens/c60e1207-648b-491d-8eb8-4b626fb22c17) /
  [Brilliant](https://mobbin.com/screens/96cbea83-3e2e-4d87-a84b-9a4cc7f0d0d8)
  — tier badge + "Top 15 advance · 3 days left" + the viewer's own row
  highlighted.
- [Kraken — futures leaderboard](https://mobbin.com/screens/769622b3-915e-4b2e-a69c-f6f90bded4d7)
  — **metric tabs** (P&L / ROI / Volume) plus a **time window** (7D / 1M).
- [X — NBA stats](https://mobbin.com/screens/7c6d17f6-526b-4547-a90b-692beb7730b9)
  — one stat at a time behind a metric selector, rank on the left.

**Recommended:** two changes. Collapse to rank + model + tier + the *selected*
metric behind a metric selector, with the rest on row expand — 12 columns is
why it wraps. And add a **time window**, which is a real correctness gap, not a
cosmetic one: a first-try rate from three months ago currently weighs the same
as last week's, so the scoreboard cannot notice a model getting worse.

---

## Cross-cutting

- **Waiting ≠ failing.** `waiting` lanes are unstarted work and should read as
  absence, not as a peer status. Same for the "not started" tasks in
  `RUN_REPORT.md` after a `budget_wall_clock_s` stop.
- **Cost is a first-class metric and is currently a suffix.** Tokens appear last
  in a `·`-joined string. Ringer's entire thesis is that worker tokens are cheap
  and orchestrator tokens are not — the UI should show what a run cost.
- **The `activity` string is a one-line stub where a step list belongs.** See
  [Lindy](https://mobbin.com/screens/9f4affd5-f387-4149-860e-95c83f9bbba5): an
  ordered checklist of completed steps with ticks, the current step processing,
  each expandable. That is what "what is this worker doing" should look like.
- **Long waits deserve an honest estimate.** See
  [Customer.io Design Studio](https://mobbin.com/screens/507233fa-1da3-404e-b6eb-014bc1cc0aa7):
  a diagram of the pipeline shape plus "could take up to 2 minutes". We know
  each task's `timeout_s`; we show no expected duration anywhere.

## The appearance map

**Correction, 2026-08-16.** An earlier version of this file said Ringside's look
lives in THREE places. It lives in **five**, across **three different reload
lifecycles**. The original claim was made by scoping the search to the files a
restyle had already touched — the same file-scoped reasoning that caused the
miss it was warning about. Established by a read-only review lane
(`ringside-shared`), citations verified.

| # | Source | Covers | To see a change |
|---|---|---|---|
| 1 | `dashboard/ringside.html` | the main multi-run shell: tabs, theme tokens, CSS, client-rendered markup | **browser reload** — `read_ringside_html` reads it per request |
| 2 | `inject_models_tab_into_ringside_html` in `ringer.py` | the Models tab's nav, panel, CSS and script | **server restart** — injection runs per request, but its source is baked into the process |
| 3 | `dashboard/dashboard.html` | the legacy single-run browser shell | **browser reload** — also read per request |
| 4 | `hud/frontend/hud.js` + `dashboard/dashboard.html` | the desktop Tauri HUD (shell plus injected overlay CSS) | **rebuild and relaunch** — `hud/build.rs` copies both into `dist` at build time |
| 5 | `ARTIFACT_BASE_CSS` and `MODEL_SCOREBOARD_CSS` in `ringer.py` | generated status, final report, artifact index, text/log wrappers, model scoreboard | **restart AND regenerate** — process-baked, and the HTML is already materialized to disk |

Worker-produced HTML is linked directly and never restyled, so its visuals
belong to the deliverable, not to Ringside.

**The rule that follows:** scope visual work by *surface*, never by file, and
name explicitly which of the five you are touching — shell, injected tab, legacy
shell, desktop bundle, generated families. Two of the five need more than a
reload, and one needs a rebuild; assuming hot reload is how stale output gets
shipped believing it was verified.

Related: `contracts` cannot see CSS custom properties and fails open, so it will
not catch a lane redefining a design token. Confirmed against the code, not
assumed.
