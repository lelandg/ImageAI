# Sprite tab — SDD archive, sub-projects 1 through 6

Working documents from the `feat/sprite-tab` SDD chain, archived on 2026-08-30 when the
sub-project 6 workspace was removed. Sub-project 7 (CLI, version bump, docs, the single PR)
is not in this archive; it had not started.

| File pattern | What it is |
|---|---|
| `*-ledger-archive.md` | The controller ledger for one sub-project: every dispatch, review verdict, ruling and fix round, in order. `image-route-ledger-archive.md` is sub-project 6. |
| `*-final-review.md` | The whole-sub-project final review: findings, refuted findings, deferred-minor triage, assessment. |
| `image-route-rereview.md` | The scoped re-review of sub-project 6's final-review fix wave: closure per finding, regression sweeps, assessment. |
| `task-N-brief.md` | The implementer brief for one task of sub-project 6. |
| `task-N-report.md` | The implementer's own report for that task. |
| `task-N-review.md`, `task-10-rereview.md` | Per-task reviews. |
| `final-fix-{A,B,C,D}-report.md` | The four fix-wave implementer reports. |
| `final-review-context.md`, `rereview-context.md` | The context files the review workflows read. |
| `global-constraints.md`, `preflight-scan.md` | Sub-project 6's seam contract list and its pre-flight verification scan. |
| `implementer-contract.md`, `reviewer-contract.md` | The standing contracts every agent in the chain followed. |
| `*.diff` | The two review packages the sub-project 6 reviews cite by line. Every other diff package is regenerable with `git diff`. |
| `2026-09-01-opus-crop-export-changes.patch` | The reverted 2026-09-01 diff (cell-aspect crop, queue flip, dialog sizing); kept for reference, not reapplied. |

Completion summaries live one level up: `Notes/2026-08-30-sprite-image-route-complete.md`,
`Notes/2026-08-30-sprite-gui-b-complete.md`, `Notes/2026-08-30-sprite-gui-a-complete.md`.
