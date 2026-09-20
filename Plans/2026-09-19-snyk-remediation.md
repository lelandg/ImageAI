# Snyk remediation implementation checklist

**Last Updated:** 2026-09-19 19:05
**Status:** Local validation complete; PR delivery

- [x] Preserve the original checkout and environment; branch from origin/main in an isolated worktree.
- [x] Investigate the 98-advisory baseline and enforce the seven-day package publication cutoff.
- [x] Upgrade affected dependencies and remove unused MoviePy.
- [x] Obtain explicit approval for MediaPipe Tasks migration and exactly three temporary LiteLLM proxy exceptions.
- [x] Migrate Sprite and Character Animator, validate official model downloads and native inference, register model-cache ownership.
- [x] Pass local Snyk with the approved policy and verify the unfiltered result contains only those three findings.
- [x] Reconcile independent patch reviews and complete focused validation.
- [x] Finish broader regression assessment; record baseline Qt and logging-test limitations.
- Delivery: commit, apply the version-manager patch release, push, and open the PR.
- Delivery gate: inspect automated reviews and linked autofix results, fix verified findings, and merge after reviews pass. GitHub is the source of delivery status.

The Snyk policy is documented in Docs/Snyk-Exceptions.md and expires 2026-10-19. Protobuf has no exception. Known baseline typecheck and native Qt test limitations are recorded in Notes/2026-09-19-snyk-remediation.md. The original checkout and environment remain preserved.
