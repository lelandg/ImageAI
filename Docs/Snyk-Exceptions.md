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
