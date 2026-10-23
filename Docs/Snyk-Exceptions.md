# Snyk applicability exceptions

Reviewed: 2026-10-21 08:42. Exceptions expire 2026-11-20.

The maintainer explicitly approved documented exceptions for exactly these six LiteLLM proxy findings. On 2026-09-19 three were approved, alongside the migration away from the vulnerable Protobuf release; no Protobuf exception is approved or included. On 2026-10-21 those three were renewed and three later proxy advisories were added, after a raw reassessment ([Notes/2026-10-21-snyk-litellm-reassessment.md](../Notes/2026-10-21-snyk-litellm-reassessment.md)).

| Advisory | CVE | Approved | Affected upstream surface | Why the reported path is absent |
| --- | --- | --- | --- | --- |
| SNYK-PYTHON-LITELLM-17391451 | CVE-2026-12772 | 2026-09-19, renewed 2026-10-21 | Proxy authenticate_user/session handling | ImageAI does not start the LiteLLM proxy or expose its management API. |
| SNYK-PYTHON-LITELLM-17393717 | CVE-2026-12795 | 2026-09-19, renewed 2026-10-21 | Proxy /sso/debug/login and /sso/debug/callback | ImageAI has no LiteLLM HTTP SSO endpoints. |
| SNYK-PYTHON-LITELLM-17393719 | CVE-2026-12796 | 2026-09-19, renewed 2026-10-21 | Proxy OpenID redirect/session handling | ImageAI does not use LiteLLM proxy authentication or browser login sessions. |
| SNYK-PYTHON-LITELLM-17391455 | CVE-2026-12771 | 2026-10-21 | Proxy M2M JWT handler, user_api_key_auth.py | ImageAI never authenticates inbound requests with LiteLLM JWT handling. |
| SNYK-PYTHON-LITELLM-20257373 | CVE-2026-93355 | 2026-10-21 | Proxy JWT email-fallback identity lookup | ImageAI has no LiteLLM proxy users, roles, or identity-provider login. |
| SNYK-PYTHON-LITELLM-20840174 | CVE-2026-108575 | 2026-10-21 | Proxy add_new_model and team model endpoints | ImageAI exposes no LiteLLM model-management API; model parameters come from its own code. |

ImageAI imports the SDK in gui/llm_utils.py and builds direct completion calls in core/llm_params.py and its desktop/CLI consumers. The application does not import litellm.proxy, invoke a LiteLLM server command, or serve its authentication or management endpoints. The separate illustrative Discord helper under Notes is not an ImageAI application entry point.

Snyk reports no patched upstream version for these six advisories. As of 2026-10-21 both 1.101.6, the newest eligible release in the manifest's `>=1.101.3,<1.102` range, and 1.105.1 are still affected. The CLI-generated .snyk policy suppresses only their exact IDs for 30 days. Reassess them before expiration and remove these exceptions before adding a LiteLLM proxy or any corresponding inbound endpoint. Do not extend them automatically.

A policy-filtered passing scan is not a zero-advisory raw scan. Retain an unfiltered scan with --ignore-policy when reviewing applicability. Package vulnerability presence and application exploitability are distinct claims.

The same six expiring exceptions must also be applied to the SCM-imported Snyk project `lelandg/ImageAI:requirements.txt`. The hosted exceptions are disregarded once an upstream fix is available. Review both the repository policy and the project policy when resolving or renewing an exception.

## October 23, 2026 dependency floors

No exception changed. Four floors were raised under the remediation rule: a reported advisory with a fixed version is fixed at once, at the lowest fixed version, whatever the release's age.

| Dependency | Previously allowed | Required version | Advisories |
| --- | --- | --- | --- |
| pillow | >=12.3.0 | >=13.0.0 | 39 GHSAs fixed only in 13.0.0 (no 12.x patch); 38 carry CVE IDs. Examples: GHSA-8g5g-8vmr-9782 (JPEG heap overflow), GHSA-cp9v-662q-vvx9, GHSA-27h8-gf7j-v5hc |
| rembg (Sprite ML) | >=2.0.60 | >=2.0.86 | rembg 2.0.85 and earlier require `pillow<13`, so the Sprite ML install forced vulnerable Pillow; 2.0.86 allows `<14` |
| anyio | unbounded | >=4.14.2 | CVE-2026-64847, CVE-2026-63374 (critical in Snyk), via httpx |
| fsspec | unbounded | >=2026.6.0 | CVE-2026-104851 (critical in Snyk), via huggingface-hub |

The Pillow, anyio, and fsspec floors are in both `requirements-security.txt` and the Snyk SCM block of `requirements.txt`. The rembg floor is in `requirements-sprite-ml.txt` and in `REMBG_SPEC` (`core/sprite/ml_install.py`), the source of truth for the in-app **Install ML backends** action; a test keeps the two in sync. Fresh installs already resolved past anyio and fsspec, but an existing environment kept 4.10.0 and 2025.9.0 until these floors were added.

Release checks:

- **Pillow 13.0.0.** All 83 files carry Trusted Publisher attestations (`python-pillow/Pillow`, `wheels.yml`, environment `release-pypi`) whose digests match.
- **rembg 2.0.86.** No PyPI attestations; no rembg release has them. Both files match PyPI's digests, and all 36 package `.py` files are byte-identical to GitHub tag `v2.0.86`, released by the maintainer the same minute. The release adds an `atlascloud` remote session that touches the network only when selected; ImageAI's `REMBG_MODELS` allowlist cannot select it.

`tests/test_pillow_dependency_security.py` runs GHSA-cp9v-662q-vvx9 (`Image.merge` with an `I` band 0) and GHSA-27h8-gf7j-v5hc (median filter on an equal-edge crop) in child processes. Both crash the interpreter on 12.3.0 and raise cleanly on 13.0.0. Base, base plus Sprite ML, and local SD resolve on Linux and Windows. Snyk scans pass with nothing open: `requirements.txt` against the maintainer's upgraded environment (106 dependencies, the six LiteLLM ignores) and the Sprite ML extras (44 dependencies).

## October 21, 2026 reassessment

The three September exceptions expired on 2026-10-19. Scans of a single-package Python 3.12 environment, without the policy (`--ignore-policy`), returned exactly the six LiteLLM advisories above for both `litellm==1.101.6` and `litellm==1.105.1`, and no other LiteLLM advisory. The fixes for 20158379 and 20840177 from the October 13 bounds still hold at 1.101.6. Snyk lists no fixed version for any of the six. OSV names upstream commits for CVE-2026-12771 and CVE-2026-12772, but those commits are an unrelated cost-calculator fix and are absent from every release tag checked, so they are not treated as fixes.

The maintainer approved renewing the three exceptions and adding 17391455, 20257373, and 20840174 for 30 days. A scan using the policy suppresses all six; the scan still fails on transitive certifi and filelock advisories, whose fixed releases do not yet meet the seven-day package-age rule. Those dependencies are not suppressed.

### Transitive dependency floors (same day)

| Dependency | Previously resolved | Required version | Advisories |
| --- | --- | --- | --- |
| filelock | 3.32.7 / 4.1.1 | >=4.2.1 | SNYK-PYTHON-FILELOCK-21280749 through 21280761; upstream GHSA-v4x8-3wr5-3wq8 (high) and 16 other CVE-flagged advisories |

filelock reaches ImageAI through huggingface-hub, which tokenizers (LiteLLM) and the local SD stack use. 4.2.1 was published on 2026-10-17, inside the seven-day window. Upstream published every one of these advisories as a CVE-flagged GitHub security advisory patched in 4.2.1, so it qualifies under the documented exception for CVE fixes. Like the other floors, it is repeated in `requirements.txt` for Snyk SCM. Base, local SD, and Sprite ML manifests resolve with it on Linux and Windows. `tests/test_filelock_dependency_security.py` checks GHSA-69hj-f68j-2879 by behaviour: it fails on 4.1.1 and passes on 4.2.1 (POSIX only). A scan with the policy, of `litellm==1.101.6` plus `filelock>=4.2.1`, leaves one open finding: certifi.

| Dependency | Previously resolved | Required version | Advisories |
| --- | --- | --- | --- |
| certifi | 2026.7.22 | >=2026.10.19 | SNYK-PYTHON-CERTIFI-21280764; upstream GHSA-6q48-6c7w-9gw2 (critical; PYSEC-2026-4320) |

2026.7.22 trusts emSign ECC Root CA - G3, whose intermediates were revoked for key compromise. 2026.10.18 removed every emSign root, and 2026.10.19 restored the three unaffected ones (G1, C1, ECC C3); Snyk tracks the over-removal. requests, httpx, and the Google client libraries verify provider TLS, and therefore API-key traffic, against this bundle.

2026.10.19 is younger than seven days and the advisory has no CVE ID, so the maintainer approved an explicit exception to the package-age rule. The approval depended on an artifact audit, and every check passed:

- **Wheel integrity.** The PyPI wheel's SHA-256 matches PyPI's published digest.
- **Contents.** Compared with 2026.7.22, the only code change is `__version__`; `core.py` and `__main__.py` are byte-identical. Metadata gains one classifier and a newer setuptools generator.
- **CA bundle.** `cacert.pem` drops exactly one root, emSign ECC Root CA - G3, and adds or alters none. That matches upstream PRs #437 (remove all emSign roots) and #440 (restore G1, C1, C3).
- **Provenance.** The wheel's `cacert.pem` is byte-identical to upstream tag `2026.10.19`, and to merge commit `662df63` of #440. PyPI's attestation names Trusted Publisher `certifi/python-certifi`, workflow `release.yml`, environment `release`, and its digest matches the wheel. The Sigstore certificate names `refs/tags/2026.10.19` at `662df63`. The Sigstore signature itself was not verified independently; PyPI checks it on upload.

`tests/test_certifi_dependency_security.py` checks the bundle by fingerprint. It fails on 2026.7.22 (compromised root present) and on 2026.10.18 (unaffected roots missing), and passes on 2026.10.19. All manifests resolve with the floor on Linux and Windows. A scan with the policy, of `litellm==1.101.6` plus both floors, passes with only the six approved LiteLLM ignores.

## October 13, 2026 reassessment

Fresh CLI scans of main at `410b3d4` under organization `lelandg`, using the
preserved Python 3.12 remediation environment, covered 110 dependencies. The
unfiltered result contained 12 distinct advisories; the policy-filtered result
contained nine. The difference was exactly the three exceptions above, still
expiring **2026-10-19 at 00:00 UTC**. Neither result was a passing scan.

The dependency requirements now address the six advisories with published fixes:

| Dependency | Previously scanned | Required version | Advisory suffixes (`SNYK-PYTHON-<PACKAGE>-`) |
| --- | --- | --- | --- |
| urllib3 | 2.7.0 | >=2.8.0 | 20302844, 20302845, 20302846 |
| multidict | 6.8.0 | >=6.9.1 | 20510280 |
| litellm | 1.100.1 | >=1.101.3,<1.102 | 20158379, 20840177 |

These bounds appear in both the base manifest and security constraints because
[Snyk's SCM resolver omits constraint-file directives](https://docs.snyk.io/supported-languages/supported-languages-list/python/scm-integrations-and-python).

The LiteLLM range is deliberately limited to the patched 1.101 line. Although
Snyk suggested 1.101.0rc1 for the combined upgrade, that release is still affected
by [20840177](https://security.snyk.io/vuln/SNYK-PYTHON-LITELLM-20840177).
The same advisory also affects 1.102.0/1.102.1 and 1.103.0, so a broad
`>=1.101.3,<2` floor would still admit known vulnerable releases. Reassess the
advisory ranges and SDK compatibility before relaxing this upper bound.

Three additional package advisories have no reported upstream fix and **are not
ignored**:

| Advisory | Required upstream surface | Application assessment |
| --- | --- | --- |
| SNYK-PYTHON-LITELLM-17391455 | Proxy M2M JWT authorization with limited valid credentials | ImageAI exposes no LiteLLM JWT-authenticated proxy routes. |
| SNYK-PYTHON-LITELLM-20257373 | Proxy JWT email identity fallback and account binding | ImageAI does not host proxy identities or that authentication flow. |
| SNYK-PYTHON-LITELLM-20840174 | Enterprise proxy team-admin model registration with `STORE_MODEL_IN_DB` enabled | ImageAI does not host proxy team/model administration. |

The two fixable LiteLLM findings also concern proxy tenant caching and proxy
session authentication. Static review of `main.py`, `core/`, `gui/`, `cli/`, and
`providers/` still supports SDK-only use, including the existing three exceptions.
This is an application-applicability assessment, not an upstream patch or a claim
that the dependency has no advisories. No new suppression or expiry extension is
approved by this reassessment.

The urllib3 response-parsing issues have a relevant application boundary:
provider image URLs and model downloads reach Requests/urllib3. The certificate
finding additionally requires specific HTTPS-proxy TLS configuration; no direct
application configuration was found. The multidict issue concerns C-extension
items-view set operations; application/transitive reachability was not proven.
Both dependencies are upgraded rather than suppressed.

Snyk reported the organization's private-test quota was exhausted. No further
manual scan is authorized while it is exhausted. Local dependency compatibility
and regression checks do not replace a fresh Snyk rescan. Fixed-version coverage
for these six advisories remains subject to that rescan, and the three additional
unignored LiteLLM advisories remain unresolved in Snyk.

The CLI applied the repository policy and returned organization ignore settings;
it did not verify the separate SCM project's current ignore-until-fix settings,
latest scan, or project UUID. The hosted-policy description above records the
September setup and still needs dashboard verification. Before October 19,
explicitly decide the existing exceptions; do not extend them automatically.
