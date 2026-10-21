# LiteLLM Snyk exception reassessment

Checked: 2026-10-21 08:42 America/Chicago

The three LiteLLM exceptions in `.snyk` and in the hosted project `lelandg/ImageAI:requirements.txt` expired on 2026-10-19. This note records the reassessment that [Docs/Snyk-Exceptions.md](../Docs/Snyk-Exceptions.md) requires before any renewal.

## Method

- Two scratch Python 3.12 venvs, each with LiteLLM alone, installed with uv `--exclude-newer 2026-10-14T13:00Z`:
  - `litellm==1.101.6`: the newest eligible release inside the manifest range `>=1.101.3,<1.102`, set by #54 (`0b36843`).
  - `litellm==1.105.1`: the newest eligible release overall.
- Raw scans: Snyk CLI 1.1307.3, `snyk test --file=requirements.txt --package-manager=pip --ignore-policy`, exit 1 for both versions (59 and 56 dependencies). Both returned the same six LiteLLM advisories. Evidence for the manifest-relevant 1.101.6 scan: [2026-10-21-snyk-litellm-raw.json](2026-10-21-snyk-litellm-raw.json).
- After approval, a scan of 1.101.6 using the renewed `--policy-path .snyk` reported all six as ignored, with no unignored LiteLLM advisories.
- Upstream fix status: the Snyk advisory pages and OSV.dev entries, and BerriAI/litellm commit history on GitHub.
- Code check: every ImageAI use of LiteLLM is a plain `import litellm` SDK completion call. Nothing imports `litellm.proxy`, the JWT auth handlers, the SSO endpoints, or the model-management endpoints.

## Expired exceptions

| Advisory | CVE | Severity | Upstream fix | Still in 1.101.6 and 1.105.1 | Verdict |
| --- | --- | --- | --- | --- | --- |
| SNYK-PYTHON-LITELLM-17391451 | CVE-2026-12772 | High | None | Yes | Renewed to 2026-11-20 (approved 2026-10-21) |
| SNYK-PYTHON-LITELLM-17393717 | CVE-2026-12795 | Medium | None | Yes | Renewed to 2026-11-20 (approved 2026-10-21) |
| SNYK-PYTHON-LITELLM-17393719 | CVE-2026-12796 | Medium | None | Yes | Renewed to 2026-11-20 (approved 2026-10-21) |

No upgrade is possible: Snyk lists the vulnerable range as `[0,]` with no fixed version. OSV marks commit `61409275` as the fix for CVE-2026-12772 and `a56541ba` as last-affected for the other two. Neither commit is a security change: one is a March 2026 cost-calculator fix and the other a Dockerfile cleanup. Both are on branches that diverge from every release tag checked. They appear to be the commits the reporter tested, not fixes.

## LiteLLM advisories not covered by any exception

These also appear in the raw scans. All are proxy-only and none has a fixed version. The 2026-10-13 reassessment recorded them as unignored. On 2026-10-21 the maintainer approved adding all three to the policy until 2026-11-20.

| Advisory | CVE | Severity | Published | Affected surface |
| --- | --- | --- | --- | --- |
| SNYK-PYTHON-LITELLM-17391455 | CVE-2026-12771 | Low | 2026-06-21 | Proxy M2M JWT handler, `user_api_key_auth.py` |
| SNYK-PYTHON-LITELLM-20257373 | CVE-2026-93355 | High | 2026-09-29 | Proxy JWT email-fallback lookup (`email_verified` not checked) |
| SNYK-PYTHON-LITELLM-20840174 | CVE-2026-108575 | High | 2026-10-12 | Proxy `add_new_model` / team model endpoints |

The weekly report for 8–15 October showed a High "Incorrect Authorization" finding on `requirements.txt`. Given its timing, it is probably SNYK-PYTHON-LITELLM-20840174. The email does not include advisory IDs.

## Transitive findings outside LiteLLM

| Package | Installed | Severity | Fixed in | Fix release published | Min-age eligible |
| --- | --- | --- | --- | --- | --- |
| certifi | 2026.7.22 | Critical (no CVE) | 2026.10.19 | 2026-10-20 | 2026-10-27 |
| filelock | 3.32.7–4.1.1 | up to 13 Medium/Low | 4.2.1 (one advisory: 4.0.9) | 2026-10-17 | 2026-10-24 |

Correction, later the same day: upstream treats both as security fixes, and the earlier reading of certifi here was wrong.

- **certifi.** 2026.7.22 still trusts emSign root CAs whose intermediate keys were compromised (upstream GHSA-6q48-6c7w-9gw2, critical, PYSEC-2026-4320; no CVE ID). That is a real interception risk, not a fail-closed bundle. Snyk's description refers to the three unaffected roots that 2026.10.18 removed and 2026.10.19 restored. The maintainer chose to wait for the seven-day age rule.
- **filelock.** Its advisories are CVE-flagged GitHub security advisories patched in 4.2.1, so the floor was raised under the CVE exception.

Both outcomes are recorded in [Docs/Snyk-Exceptions.md](../Docs/Snyk-Exceptions.md).

## Other observations

- The checkout's `.venv` has `litellm 1.77.0`, below the `>=1.100.1` floor in `requirements.txt`. It was not reinstalled after the September remediation.
- The Snyk package page warns that LiteLLM once had compromised versions published to PyPI. The floor `>=1.100.1,<2` and the seven-day cutoff already guard against this; keep both.
- The `lelandg` org used all 200 private tests on 2026-10-13. This scan still ran, so the quota has either reset or allows more.
