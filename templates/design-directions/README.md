# design-directions

## What it is

The round you run BEFORE committing to a visual direction. Two to four lanes, each its own worker and session so the directions do not bleed, each building ONE representative screen or component in a different direction — never a whole product.

Every lane produces two declared deliverables: a rendered visual artifact (a screenshot or exported image) and notes that state where that direction DIVERGES from the reference the human supplied, rather than only describing itself.

The human looks at the renders side by side and picks one; only then does the chosen direction get scaled. It exists because the expensive failure is discovering after a multi-phase rewrite that nobody liked the direction, and because a render that missed a supplied reference costs a full extra pass.

## When to use

Use this before a visual rewrite — when a direction is still undecided and the cost of the wrong choice is a full build nobody likes. It earns its keep when the human can supply a reference to diverge from: each lane's notes must say where it departs, so a render that silently missed the reference is caught now, not after the scale-up.

## Fill in

| Placeholder | What goes there |
|---|---|
| `{{RUN_SLUG}}` | Stable run slug for this design-directions round. |
| `{{WORKDIR}}` | Scratch run directory outside the repo, where session dirs and renders land. |
| `{{KIT_DIR}}` | Absolute path to `templates/design-directions` after copying or installing this kit. |
| `{{PROJECT_NAME}}` | The product being explored, as the lanes name it. |
| `{{SCREEN_OR_COMPONENT}}` | The ONE screen or component every lane builds. Describe it concretely enough that three lanes build the same thing. |
| `{{SCREEN_SOURCE_FILE}}` | The source file each lane writes its built surface to, relative to the task directory (e.g. `direction.html`). |
| `{{REFERENCE_PATH}}` | The reference (screenshot, spec, or direction) the human supplied for each lane to diverge from. |
| `{{HOW_TO_RUN}}` | Exact command lines to build or serve each lane's screen so it produces the visual artifact. |
| `{{BUILD_ENGINE}}` | Engine name each lane runs under to build its direction. |
| `{{DIRECTION_A}}`, `{{DIRECTION_B}}`, `{{DIRECTION_C}}` | The distinct visual direction each lane must build one screen or component in. One per lane; delete a task to run fewer. |

## Checks

The kit invokes `checks/check_direction.py` per lane. It fails a missing or zero-byte render, missing or empty notes, and notes that carry no divergence statement. It is tolerant about wording and headings — strict on the two deliverables and the divergence, loose on how they are phrased.

## Mix with

- Run this before a build round (`repo-feature` or a fix swarm) scales the chosen direction — one screen per direction now beats a full rewrite in the wrong one.
- The human compares the renders and picks one; only the winning direction moves into the build round.
- Keep exploration and scale-up in separate lanes: never let a lane that explored a direction also build it out.

## Gotchas

- One screen or component per lane, never a whole product. The point is to compare directions, not ship features.
- Each lane is its own worker and session; merging directions into one worker makes them bleed.
- Notes must state where the direction diverges from the supplied reference, not only describe it — a lane that missed the reference is the failure this round exists to catch, and the divergence statement is what makes it visible at review time.
