# Red Team

## What it is

An adversarial hardening round that runs AFTER a build round's tests are green and BEFORE anything is called done. Four lanes, one per adversary lens, each its own worker and session:

1. **real-data** — runs the product against real or realistically-shaped data, hunting silent failures: swallowed decode errors, empty results treated as success, partial writes, dropped records.
2. **destructive-path** — boots the product and exercises bulk, select-all, delete, and overwrite paths plus empty and max-cardinality states, capturing evidence per action.
3. **error-path** — forces network failures, permission denials, malformed input, and timeouts, verifying the user SEES a surfaced error rather than a silent no-op.
4. **test-quality** — audits the test suite and check scripts for false greens: naive substring matches, over-broad assertions, assertions that pass when the feature is absent.

Unlike `adversarial-review`, which reads a diff or artifact, every red-team lane exercises the RUNNING product and files evidence. Every lane is read-only with respect to product source: it may run the product and write its own report and evidence files, nothing else.

## When to use

Use this after the build round's tests are green and before you call the work done — when a passing diff is not enough and you want the running product stressed for silent failures. It earns its keep on data-in, data-out surfaces where empty results, partial writes, swallowed errors, or tests that pass when the feature is absent are the real risk.

## Fill in

| Placeholder | What goes there |
|---|---|
| `{{RUN_SLUG}}` | Stable run slug for this red-team round. |
| `{{WORKDIR}}` | Scratch run directory outside the repo under test. |
| `{{KIT_DIR}}` | Absolute path to `templates/red-team` after copying or installing this kit. |
| `{{PRODUCT_NAME}}` | The product being hardened, as the lanes and reports name it. |
| `{{HOW_TO_BOOT_COMMANDS}}` | Exact command lines to boot or run the product so each lane can exercise it. |
| `{{REAL_DATA_SOURCE}}` | Real or realistically-shaped data the real-data lane runs the product against. |
| `{{DESTRUCTIVE_SURFACES}}` | The bulk, select-all, delete, and overwrite paths plus empty and max-cardinality states the destructive lane must exercise. |
| `{{TEST_COMMAND}}` | The command that runs the product's test suite for the test-quality lane to audit. |
| `{{REVIEW_ENGINE}}` | Engine name each adversary lane runs under, often `opencode`. |

## Checks

The kit invokes `checks/check_redteam_report.py` against each lane's `report.md`. A passing report states `NO FINDINGS` with what it exercised, or carries one block per finding with `Finding`, `Evidence`, `Repro`, `Impact`, `Severity` (P0-P3), and `Silent` (yes/no) labels. A finding without evidence is not a finding, and the check prints why it fails.

`Silent: yes` is the kit's headline signal — a silent failure is what this round exists to catch.

## Mix with

- Run a build round first (`repo-feature` or a fix swarm) so the product is green before red-team exercises it.
- Use `adversarial-review` when you want models reading a diff or artifact; use `red-team` when every lane must drive the running product.
- Feed confirmed findings to a `fix-swarm` — never let the lane that found a silent failure also patch it.

## Gotchas

- Every lane is read-only with respect to product source. It may run the product and write its own report and evidence files, nothing else.
- Each lane is its own worker and session; do not merge lenses into one worker.
- No evidence, no finding. A lane that reports a problem without evidence has not found one.
- Keep `Severity` in P0-P3 and `Silent` a literal yes/no so reports stay machine-readable; the check enforces that contract.
