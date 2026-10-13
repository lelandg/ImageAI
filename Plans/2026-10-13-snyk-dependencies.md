# October dependency remediation

Scope: the October 13 dependency scan of main at `410b3d4`, using the
preserved Python 3.12 remediation environment. It reported 12 raw advisories
and nine unignored advisories across 110 dependencies.

- Independent pre-patch investigation completed: prioritize the outbound HTTP
  parsing boundary; LiteLLM proxy surfaces are absent from ImageAI entrypoints.
- Raise urllib3 to 2.8.0 and multidict to 6.9.1; constrain LiteLLM to the patched
  1.101.3 SDK line. Preserve all existing exception IDs and expiry dates.
- Validated Python 3.12 dependency consistency and a manifest resolution dry run
  with urllib3 2.8.0, multidict 6.9.1, and LiteLLM 1.101.3; other installed
  distributions match the preserved remediation environment.
- New bounded HTTP/deflate/refcount regressions reproduce eight failures on the
  old dependencies, with three legitimate controls passing. All 11 pass with
  the updated dependencies; two offline real SDK completion cases also pass.
- Focused and expanded application checks: 106 passed, one logging test failed.
  The same logging failure reproduces on the unchanged baseline (identical test
  and logging implementation), and is outside this dependency change. Changed
  Python tests pass Ruff and compilation checks.
- One independent candidate review completed with no blocking findings. Open a
  draft PR and use available CI/review gates before merging.
- An unexpected global pre-commit hook attempted Snyk despite the quota
  instruction: the constraints-file attempt failed package-manager detection;
  its requirements scan completed with 112 dependencies and two unpatched high
  findings (20257373, 20840174), resolving LiteLLM 1.101.6. This was neither an
  unfiltered scan nor a pass. The hook then began its Code step before its
  remaining processes were stopped; upload/completion could not be confirmed.
  Use only the hook's per-invocation SNYK_SKIP=1 option for this work, keeping
  other hooks and required remote checks intact.
- Snyk rescan remains pending quota availability. Do not rerun Snyk, weaken
  checks, add ignores, or claim an unfiltered or policy-filtered Snyk pass.
