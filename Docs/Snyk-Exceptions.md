# Snyk applicability exceptions

Reviewed: 2026-09-19 18:45. Exceptions expire 2026-10-19.

The maintainer explicitly approved documented exceptions for exactly these three LiteLLM proxy findings while authorizing migration away from the vulnerable Protobuf release. No Protobuf exception is approved or included.

| Advisory | Affected upstream surface | Why the reported path is absent |
| --- | --- | --- |
| SNYK-PYTHON-LITELLM-17391451 | Proxy authenticate_user/session handling | ImageAI does not start the LiteLLM proxy or expose its management API. |
| SNYK-PYTHON-LITELLM-17393717 | Proxy /sso/debug/login and /sso/debug/callback | ImageAI has no LiteLLM HTTP SSO endpoints. |
| SNYK-PYTHON-LITELLM-17393719 | Proxy OpenID redirect/session handling | ImageAI does not use LiteLLM proxy authentication or browser login sessions. |

ImageAI imports the SDK in gui/llm_utils.py and builds direct completion calls in core/llm_params.py and its desktop/CLI consumers. The application does not import litellm.proxy, invoke a LiteLLM server command, or serve its authentication endpoints. The separate illustrative Discord helper under Notes is not an ImageAI application entry point.

Snyk reports no patched upstream version for these three advisories. The CLI-generated .snyk policy suppresses only their exact IDs for 30 days. Reassess them before expiration and remove these exceptions before adding a LiteLLM proxy or any corresponding inbound endpoint. Do not extend them automatically.

A policy-filtered passing scan is not a zero-advisory raw scan. Retain an unfiltered scan with --ignore-policy when reviewing applicability. Package vulnerability presence and application exploitability are distinct claims.

The same three expiring exceptions are applied to the SCM-imported Snyk project `lelandg/ImageAI:requirements.txt`. The hosted exceptions are disregarded once an upstream fix is available. Review both the repository policy and the project policy when resolving or renewing an exception.

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
