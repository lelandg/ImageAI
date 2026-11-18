# Replace LiteLLM with an in-house adapter package (`chameleon_llm`) — design

**Date:** 2026-11-18 10:58
**Status:** Implemented 2026-11-18 on `feat/replace-litellm`. See "What changed during the build" at the end.
**Updated:** 2026-11-18 14:40
**Pilot:** ImageAI. ChatMaster follows as a separate project.

## Intent

LiteLLM has carried open security advisories for weeks. Most of them are in
its proxy server, which ImageAI never runs, yet each one fires the scanners
and forces another pin shuffle (`litellm>=1.101.3,<1.102`, the `httpx2` /
`httpcore2` direct pins, entries in `.snyk` and `Docs/Snyk-Exceptions.md`).
ImageAI uses a very small part of LiteLLM. Replacing that part with a small
package we own removes the dependency and its advisory stream.

## What ImageAI uses today (measured on `origin/main` b47a111)

- About 45 calls to `litellm.completion` in 22 files under `core/`, `gui/`
  and `scripts/`. All synchronous.
- No streaming, no tool calling, no embeddings, no async.
- Inputs: text messages; image input as `image_url` data URLs
  (`core/video/style_analyzer.py`); JSON mode as
  `response_format={"type": "json_object"}`; `timeout`; `api_key`; `api_base`;
  `vertex_project` / `vertex_location` (`scripts/generate_tags.py`).
- Outputs read: `response.choices[0].message.content`,
  `response.choices[0].finish_reason`, `response.usage.prompt_tokens` /
  `completion_tokens` / `total_tokens`, `response.model`.
  `gui/prompt_generation_dialog.py` also probes `choices[0].text`.
- `litellm.get_model_info` is called once, in `core/llm_params.py`, as a
  fallback for the output-token ceiling after the model registry.
- `litellm.drop_params = True` is set in many places, but real parameter
  validation already lives in `core/llm_params.py` (`validate_params`,
  `build_completion_kwargs`), because LiteLLM's tables were wrong.
- Routes in use, from `core/llm_models.py`: OpenAI (no prefix), Anthropic
  (`anthropic/`), Gemini with an API key (`gemini/`), Gemini through Google
  Cloud login (`vertex_ai/`), Ollama (`ollama/`), LM Studio (`openai/` prefix
  plus `api_base`).
- No call site catches a LiteLLM exception type; they catch `Exception`.
  `core/video/prompt_engine.py` (`_is_retryable_error`) decides on retries
  from the error text and from type names containing "timeout" or
  "connection".
- Some sites pass a bare model id and rely on LiteLLM guessing the provider:
  `core/video/prompt_engine.py` (`analyze_image`), `core/lyrics_to_prompts.py`,
  `core/video/style_analyzer.py`.
- Keys and endpoints often arrive through environment variables that the call
  sites set (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`,
  `OLLAMA_API_BASE`, `OPENAI_API_BASE` for LM Studio); some calls pass no key.
- `core/video/style_analyzer.py` also sends Anthropic-native
  `{"type": "image", "source": {...}}` blocks.
- The app retries on its own (`prompt_engine.py`, up to 4 attempts), and GUI
  callers pass `max_retries=0` so the interface never blocks.
- `LiteLLMHandler.setup_litellm()` returns the module, and callers invoke
  `.completion` on it.
- Several sites keep a "LiteLLM not installed, use the SDK directly" branch.
- ImageAI already installs `openai`, `anthropic` and `google-genai`.

## Goals

1. ImageAI no longer installs or imports `litellm`.
2. Every existing LLM feature behaves as it does today for the six routes above.
3. The replacement is self-contained, so ChatMaster can reuse it later.
4. The scanner exceptions and pins that exist only because of LiteLLM are removed.

## Non-goals (this project)

- Streaming, tool calling, async, embeddings, extended thinking, fallbacks.
  ChatMaster needs these; they are added when ChatMaster migrates.
- Azure and Bedrock routes. `core/llm_params.py` recognises the prefixes but
  no provider in `LLM_PROVIDERS` produces them. The shim raises a clear
  "route not supported" error for them.
- Cost tracking, caching, a proxy, or any provider not listed above.
- Changing prompts, models, or the rules in `core/llm_params.py`.

## Anti-goals

- Growing a second LiteLLM. A provider or feature is added only when one of
  our own apps calls it.
- Silent behaviour change. A dropped or translated parameter is always logged.

## Constraints

- `AGENTS.md`: every LLM request and full response is logged to the file
  logger and the status console; errors shown to users are logged.
- No Qt outside PySide6. The shim has no GUI imports at all.
- Model IDs come from `resolve_model()`; the shim never hardcodes one.
- Tests marked `live` cost money and run only with `IMAGEAI_LIVE_TESTS=1`.
- New package versions must be at least 7 days old; no new dependency is
  expected.

## Approaches considered

- **A. Thin adapters over the official SDKs (chosen by Leland, 2026-11-18).**
  One `completion()` with LiteLLM's call and response shape; inside, three
  adapters over `openai`, `anthropic` and `google-genai`. Smallest amount of
  new code; Google Cloud login and HTTP details stay with the vendors.
- **B. Raw `httpx`, no SDKs.** Fewest dependencies, but we would own the wire
  formats and Google auth. About twice the code, and more upkeep.
- **C. A module private to ImageAI.** Fastest, but ChatMaster would need its
  own copy or a second migration.

## Design

### Shape

A self-contained Python package named `chameleon_llm`, vendored at
`core/chameleon_llm/` (the same pattern as `core/model_registry/`). It imports
nothing from ImageAI. Files:

| File | Purpose |
|---|---|
| `__init__.py` | Public names: `completion`, `LLMError` and subclasses, `__version__` |
| `types.py` | Response dataclasses: `Completion`, `Choice`, `Message`, `Usage` |
| `errors.py` | `LLMError`, `AuthError`, `RateLimitError`, `TimeoutError_`, `BadRequestError`, `UnsupportedRouteError` |
| `routing.py` | Splits `"prefix/model"` into (adapter, bare model id) |
| `openai_adapter.py` | OpenAI, Ollama, LM Studio |
| `anthropic_adapter.py` | Anthropic |
| `gemini_adapter.py` | Gemini API key and Vertex AI |

### Public call

```python
from core.chameleon_llm import completion

resp = completion(
    model="anthropic/<id>",      # same prefixed strings as today
    messages=[...],              # OpenAI chat format, incl. image_url parts
    api_key=None, api_base=None,
    temperature=None, top_p=None, top_k=None,
    max_tokens=None, max_completion_tokens=None,
    reasoning_effort=None, verbosity=None,
    response_format=None, seed=None, stop=None, timeout=None,
    vertex_project=None, vertex_location=None,
    max_retries=0,
)
resp.choices[0].message.content   # str
resp.choices[0].finish_reason     # "stop" | "length" | "content_filter"
resp.usage.prompt_tokens / .completion_tokens / .total_tokens
resp.model
```

A keyword the chosen adapter does not accept is dropped and logged at
WARNING on the `chameleon_llm` logger. That is what `drop_params = True` did, minus
the silence. `drop_params` itself does not exist in the shim.

### Keys and endpoints

Explicit arguments win. Otherwise the shim reads the same environment
variables the call sites set today: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`GEMINI_API_KEY` (then `GOOGLE_API_KEY`), `OPENAI_API_BASE` for the OpenAI
route and `OLLAMA_API_BASE` for the Ollama routes. The SDKs do not read the
two base-URL variables themselves, so the shim passes them in.

### Routing

| Prefix | Adapter | Notes |
|---|---|---|
| none, `openai/` | OpenAI | `api_base` given means an OpenAI-compatible server (LM Studio) |
| `ollama/`, `ollama_chat/` | OpenAI | base URL `<api_base or http://localhost:11434>/v1`, dummy key |
| `lm_studio/` | OpenAI | `api_base` required |
| `anthropic/` | Anthropic | |
| `gemini/` | Gemini | `genai.Client(api_key=...)` |
| `vertex_ai/` | Gemini | `genai.Client(vertexai=True, project=..., location=...)` |
| `azure/`, `bedrock/`, anything else | none | `UnsupportedRouteError` |

A bare model id means OpenAI; the shim does not guess providers from names.
The call sites that pass bare Claude or Gemini ids today are changed to build
their arguments through `build_completion_kwargs` (or to prefix with
`infer_provider_from_model`), so every call reaches the shim with a route.

Only the first path segment is treated as a route, and only when it is in the
table. LM Studio model ids contain slashes; `build_completion_kwargs` already
handles that and keeps doing so.

### Translation rules

**OpenAI adapter.** Parameters pass through unchanged (they were already
validated by `core/llm_params.py`). `top_k` goes in `extra_body` for local
servers and is dropped for `api.openai.com`.

*Responses path.* Some OpenAI models are served only by the Responses API
(`gpt-pro` family, `o3-pro`, `o1-pro`); LiteLLM bridged these silently. The
adapter keeps a small pattern list of such models. For a match it calls
`client.responses.create` instead of chat completions: `system` messages
become `instructions`, the remaining messages become `input` (text parts as
`input_text`, images as `input_image`), `max_tokens` /
`max_completion_tokens` become `max_output_tokens`, `reasoning_effort`
becomes `reasoning={"effort": ...}`, `verbosity` and JSON mode go under
`text`. The reply is normalised to the same `Completion` shape: `output_text`
as content, `status` "incomplete" as `length`, usage `input_tokens` /
`output_tokens` as prompt and completion tokens. The builder confirms the
model list and field names against the current `openai` SDK and proves each
with a live test before relying on them.

**Anthropic adapter.**
- `system` role messages are joined and sent as the `system` parameter.
- `max_tokens` is required by the API. When the caller sends none, use 4096.
- `image_url` data URLs become base64 `image` blocks; an `https` URL becomes a
  `url` image source. Anthropic-native `image` blocks pass through unchanged.
- `response_format={"type": "json_object"}` has no native switch. Append one
  sentence to the system text asking for a single JSON object and no other
  text. ImageAI's `LLMResponseParser` already strips Markdown fences.
- `stop` becomes `stop_sequences`. `seed`, `reasoning_effort`, `verbosity`
  are dropped and logged.
- Text blocks of the reply are joined into `message.content`.
- `stop_reason`: `end_turn` and `stop_sequence` map to `stop`, `max_tokens`
  to `length`, `refusal` to `content_filter`.

**Gemini adapter.**
- `system` messages become `system_instruction`; `assistant` becomes role
  `model`; `image_url` data URLs become inline-data parts.
- `max_tokens` becomes `max_output_tokens`; `stop` becomes `stop_sequences`;
  `temperature`, `top_p`, `top_k`, `seed` map directly.
- `response_format` json_object becomes `response_mime_type="application/json"`.
- Vertex: `vertex_project` then `GOOGLE_CLOUD_PROJECT` then the login default;
  `vertex_location` then `GOOGLE_CLOUD_LOCATION` then `us-central1`.
- Finish reasons: `STOP` to `stop`, `MAX_TOKENS` to `length`, `SAFETY` and the
  other block reasons to `content_filter`. An empty candidate list returns
  `content=""` with `content_filter`, never an exception, so the existing
  empty-response fallbacks keep working.

### Errors, retries, timeouts

- Each adapter wraps the SDK's exceptions in the `LLMError` family and keeps
  the original as `__cause__`. `LLMError` subclasses `Exception`, so existing
  `except Exception` blocks behave as before. The wrapped error keeps the
  original message text, and the family includes `ConnectionError_` and
  `ServerError` next to `TimeoutError_`, so `_is_retryable_error` keeps
  matching.
- Retries: none by default. The app already retries where it wants to, and
  GUI callers need a call that returns promptly. `max_retries` is accepted
  and handed to the SDK client for callers that ask for it.
- Timeout: the caller's value, else 600 seconds.
- A client object is created per call. ImageAI makes few calls; no pooling.
- SDKs are imported inside each adapter, so a missing SDK breaks only its own
  provider, with a message naming the package to install.

### Logging

The shim logs on the logger `chameleon_llm`: one DEBUG line per request (route,
model, parameter names, never the key) and the WARNING lines above. The full
request and response logging required by `AGENTS.md` stays where it is, in the
call sites and `gui/llm_utils.py`.

### Changes in ImageAI

1. Add `core/chameleon_llm/` and its tests.
2. `core/llm_params.py`: delete `_litellm_max_output_tokens`. The model
   registry supplies the output ceiling. For each model in `LLM_PROVIDERS`
   that the bundled registry snapshot does not cover (today
   `claude-opus-4-20250514` and `claude-3-7-sonnet-20250219`), the ceiling is
   added to the curated family rules, so no model loses its cap. Docstrings
   stop naming LiteLLM.
3. `gui/llm_utils.py`: `LiteLLMHandler` becomes `LLMHandler`;
   `setup_litellm()` becomes `setup_llm()`, attaches the console handler
   to the `chameleon_llm` logger, and returns `(True, core.chameleon_llm)` so callers
   keep calling `.completion` on the returned module. Every reference is
   updated in the same PR.
4. All call sites: `import litellm` / `self.litellm = litellm` /
   `litellm.completion(...)` become the shim equivalents; `drop_params` and
   `set_verbose` lines are deleted. The `choices[0].text` probes in
   `gui/prompt_generation_dialog.py` are removed if they are only LiteLLM
   leftovers. The "LiteLLM not installed, use the SDK directly" branches
   are deleted; the shim is always present.
5. `requirements.txt`, `requirements-security.txt`: remove `litellm`.
   Re-resolve; remove the `httpx2` / `httpcore2` direct pins and their comment
   block if nothing else pulls them.
6. `.snyk`, `Docs/Snyk-Exceptions.md`: remove LiteLLM entries.
7. Docs that name LiteLLM: `AGENTS.md` ("Prefer LiteLLM" becomes "Use
   `core/chameleon_llm`"), `README.md`, `Docs/ImageAI-CLI-Guide.md`,
   `Docs/Claude Desktop Instructions.md`, both `imageai-cli` `SKILL.md`
   copies, and a regenerated `Docs/CodeMap.md`. `CHANGELOG.md` is not edited
   by hand.
8. `tests/test_litellm_sdk_compatibility.py` is replaced by shim tests.
   `Plans/litellm_gpt5_conversation/` is historical and left alone.

### Tests

- Unit tests per adapter with the SDK client mocked: request translation
  (system lifting, images, JSON mode, parameter mapping, dropped-parameter
  warning) and response normalisation (content, finish reason, usage, empty
  reply).
- Routing table test, including slash-containing LM Studio ids and the
  unsupported routes.
- Error-wrapping test per adapter.
- A guard test that fails if any file under `core/`, `gui/`, `cli/`,
  `providers/`, `scripts/` or `main.py` imports `litellm`, in the style of
  `tests/test_no_hardcoded_paths.py`.
- Live tests in `tests/test_live_llm_params.py` re-pointed at the shim: one
  text call, one JSON-mode call and one image call per cloud route.

#### Automated local-server and dialog tests (Leland, 2026-11-18)

Leland wants as much of the checking as possible automated, so that other
people can run it. Nothing in "Done means" is a hand check any more.

Three tiers, each one command:

| Tier | Marker | Runs when | Command |
|---|---|---|---|
| Unit and dialog | none | always, and in CI | `python -m pytest -m "not local and not live"` |
| Local servers | `local` | the server answers; otherwise each test skips with the reason | `python -m pytest -m local -v -rs` |
| Cloud | `live` | `IMAGEAI_LIVE_TESTS=1` and the provider key is in the keyring | see below |

A bare `python -m pytest` also runs the local tier, which can load a model
into LM Studio; the unit command excludes it. The cloud tier stays off unless
`IMAGEAI_LIVE_TESTS` is `1`. These are the same commands as in
`Docs/Testing-LLM.md`.

PowerShell:

```powershell
$env:IMAGEAI_LIVE_TESTS = "1"
python -m pytest -m live -v -rs
Remove-Item Env:IMAGEAI_LIVE_TESTS
```

bash:

```bash
IMAGEAI_LIVE_TESTS=1 python -m pytest -m live -v -rs
```

**LM Studio (`tests/test_local_lmstudio.py`).** A fixture talks to LM
Studio's own REST API, not the OpenAI-compatible one, because only the REST
API reports which models are downloaded and which are loaded:

1. Base URL from `IMAGEAI_LMSTUDIO_URL`, else the `lmstudio` endpoint in
   `LLM_PROVIDERS` (`http://localhost:1234`).
2. List models over REST with a 2 second timeout. No answer: skip, with
   "LM Studio is not running at <url>".
3. Pick the model: `IMAGEAI_LMSTUDIO_MODEL` if set, else a model already
   loaded, else the smallest downloaded chat model, which the fixture loads
   over REST. No chat model downloaded: skip, saying so.
4. Run the shim through the `lm_studio/` route: a text call, a JSON-mode
   call, and an image call when the REST listing marks the model as
   vision-capable (otherwise that one test skips).
5. A model the fixture loaded is unloaded at the end; a model that was
   already loaded is left alone.

The builder confirms the REST paths and field names against the LM Studio
version current at build time (the API has had a `/api/v0` and a `/api/v1`
form) and supports whichever the running server answers.

**Ollama (`tests/test_local_ollama.py`).** The same pattern over Ollama's
REST API: `IMAGEAI_OLLAMA_URL` or the default endpoint, `GET /api/tags` to
list, `IMAGEAI_OLLAMA_MODEL` or the smallest installed model, the same three
calls through the `ollama/` route. The existing `fetch_ollama_models` in
`core/llm_models.py` is reused for the listing.

**Dialogs (`tests/gui/test_llm_dialogs.py`).** The suite already builds
dialogs offscreen (`tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`).
For each dialog and worker that calls the LLM, a test constructs it, replaces
`core.chameleon_llm.completion` with a fake that returns a canned `Completion`,
triggers the primary action, and asserts that the result reaches the widget
and that the request and response appear in the status console. This
replaces "open each dialog by hand", and it runs in CI with no keys.

**For other people.** A short `Docs/Testing-LLM.md` lists the three commands,
the environment variables above, what each tier costs (the cloud tier a few
cents, the others nothing), and what a skip message means. `pytest.ini`
gains the `local` marker.

### Done means

- A fresh virtual environment built from `requirements.txt` has no `litellm`.
- `grep -ri litellm` over code and current docs returns nothing outside
  `Plans/`, `Notes/` and `CHANGELOG.md`.
- The full test suite passes, including the offscreen dialog tests.
- The `live` tier passes for OpenAI (one chat model and one Responses-only
  model), Anthropic, Gemini API key and Vertex.
- The `local` tier passes against LM Studio and Ollama on Leland's machine,
  with the output in the PR body. If a server is not running when Claude runs
  it, that tier is the one runbook step: start the server, run the one
  command.
- `pip-audit`, `osv-scanner` and `snyk test` report no LiteLLM finding, and
  the before and after advisory counts are in the PR body.

### Delivery

One PR in `lelandg/ImageAI` on branch `feat/replace-litellm`.
`Release: minor`.

## Calls made by Claude (not decided by Leland)

- The package is born vendored inside ImageAI. Its own repository is created
  when ChatMaster becomes the second user, and ImageAI's copy is then synced
  from it, as `core/model_registry/client.py` is today. This replaces my
  earlier suggestion of pinning a git tag: a git dependency would force every
  ImageAI user to have `git` installed for `pip install`.
- Anthropic JSON mode is done with a system-text instruction.
- Default `max_tokens` 4096 for Anthropic, default timeout 600 seconds,
  no retries inside the shim unless a caller asks, one client per call.
- Claude runs all three test tiers, the paid one included. Proposed to
  Leland 2026-11-18, not yet confirmed.
- Ollama gets the same automated treatment Leland asked for on LM Studio.
- The fixture may load a model into LM Studio and unloads only what it
  loaded.
- Bare model ids are fixed at the call sites, not guessed inside the shim.
- Environment-variable fallbacks for keys and endpoints, as listed above.
- Azure and Bedrock are unsupported in this version.

## Decided by Leland

- Approach A, SDK adapters (2026-11-18).
- ImageAI is the pilot; Heimdallr and PromptAlchemy are unused and out of scope.
- `gpt-pro`, `o3-pro` and `o1-pro` keep working (2026-11-18). See "Responses
  path" under the OpenAI adapter.
- The package is named `chameleon_llm` (2026-11-18).
- LM Studio is tested through its REST API, and testing is automated as far
  as possible so other people can run it (2026-11-18).

## Left to the builder

- The exact mechanical edit at each of the ~45 call sites.
- Whether `choices[0].text` branches are dead code.
- Whether `httpx2` / `httpcore2` can go after the re-resolve.
- How the Vertex project id reaches today's calls outside
  `scripts/generate_tags.py`, so the shim receives the same value.

## Later, for ChatMaster (not designed here)

Async `acompletion`, streaming, tool calling, embeddings, extended thinking,
fallback lists, a Mistral route, and a typed timeout exception that matches
its `litellm.exceptions.Timeout` handling.

## What changed during the build (2026-11-18)

The build followed this design except where the real SDKs and APIs disagreed
with it. Each change below was found by a review or by the paid live tests.

- **The package refuses instead of guessing.** A bare `claude...` or
  `gemini...` id, or a wrong first segment such as `claude/` or `google/`,
  raises `BadRequestError` naming the right prefix when no base URL is in
  effect. The design sent anything unrecognised to OpenAI, which made every
  routing mistake fail silently. Five call sites had that mistake.
- **Every chat call builds its arguments through
  `core.llm_params.build_completion_kwargs`** (or `route_completion_kwargs`).
  The design assumed parameters were already validated everywhere; they were
  not.
- **Vertex defaults to the `global` location,** not `us-central1`. Current
  Gemini models return 404 in `us-central1`.
- **Anthropic sampling parameters.** With `anthropic` 2.x, `messages.create`
  has no `temperature`, `top_p` or `top_k`, and the API rejects them for every
  model. The adapter inspects the installed SDK: parameters it accepts are
  passed, others are dropped with one WARNING per parameter per process.
- **OpenAI.** The Responses path takes `seed`, `stop` and `top_k` nowhere
  (dropped with a WARNING), needs `detail` on images, and sends assistant
  history as plain text. A chat call that fails because the model needs the
  Responses API, or because it wants `max_completion_tokens`, is retried
  once. Whether `gpt-pro`, `o3-pro` and `o1-pro` are Responses-only is still
  not confirmed by documentation; the Responses path is proven to work for
  `gpt-pro` by the live tests.
- **Parameter rules in `core/llm_params.py`** now treat GPT-5 and every later
  GPT generation as reasoning models, and Claude Opus, Sonnet and Haiku 5 and
  later as models without sampling parameters. The model registry had moved
  on to ids the old patterns did not match.
- **Local endpoints never receive `OPENAI_API_KEY` from the environment.**
  Ollama, LM Studio and any call with a base URL use an explicit key or a
  placeholder.
- **Transport errors are classified by class name,** so both `httpx` and
  `httpx2` exceptions map to `TimeoutError_` and `ConnectionError_`.
- **`response.model` is the model the provider reports,** when it reports one.
- **Logging levels.** A dropped parameter is a WARNING. An approximation
  (Anthropic JSON mode by instruction, a dropped empty assistant turn) is
  DEBUG. A lossless rename is not logged.
- **Dependencies.** `httpx2` and `httpcore2` stay pinned: the OpenAI and
  Anthropic SDKs require `httpx2` themselves. `jsonschema` and `tqdm` are now
  declared directly; they had only ever arrived through LiteLLM. `openai` has
  a floor of 2.0.0.
- **Tests.** The default command is `python -m pytest -m "not local and not
  live"`. In the local tier a skip means there is nothing to test; any
  unexpected answer from a running server fails. Offline tests bind the
  adapters' arguments to the real SDK call signatures, so an SDK that drops a
  parameter fails a unit test.
- **Removed:** `gui/prompt_question_dialog_old.py` (nothing imported it).

Changes after the first automated review of the pull request:

- **A failed Responses reply is an error.** A Responses API reply with status
  `failed` or `cancelled` arrives as HTTP 200. The adapter now raises an
  `LLMError` subclass chosen from the provider's error code
  (`rate_limit_exceeded`, `server_error`, a `*timeout` code, anything else
  is a bad request) and carries the code and message. It used to return an
  empty completion, which also hid the failure from the retry in
  `PromptEngine`.
- **`top_k` on local routes.** LM Studio and a custom base URL still receive
  `top_k` in `extra_body`. The `ollama/` routes drop it with a WARNING:
  Ollama's OpenAI-compatible endpoint has no such field.
- **Cleartext warning.** When a real API key would be sent to a base URL that
  is not https and whose host is not loopback, the OpenAI and Anthropic
  adapters log one WARNING per base URL per process
  (`core/chameleon_llm/endpoint.py`). The request is still sent, and the key
  is never logged.
- **`vertex_project`.** `build_completion_kwargs` and
  `route_completion_kwargs` take the Google Cloud project saved in Settings
  and send it on the `vertex_ai/` route only. `saved_vertex_project(config)`
  reads it. Without it the adapter fell back to `GOOGLE_CLOUD_PROJECT` or the
  project of the login, which may not be the configured one.
- **More call sites moved to the shared builder:** the layout designer, the
  scene suggester, the three storyboard calls, `LLMSyncAssistant.sync_with_llm`,
  the end-prompt generator, and the Google branch of Ask AI (which still
  imported `google.generativeai`). They had prefixed the model by hand, which
  sent LM Studio requests to cloud OpenAI and ignored Google Cloud login.
- **Credentials follow the resolved provider.** `analyze_image` picked a key
  by substring of the model id and could hand a cloud key to a local route.
  Start Prompt passed a Google Cloud access token as a Gemini API key. Both
  now decide from the provider and the configured auth mode.
- **`gpt-oss` names are local.** `infer_provider_from_model` no longer treats
  the open-weight `gpt-oss` family as cloud OpenAI.
- **Local tier:** only a refused connection or a connect timeout skips; any
  other connection error fails. `IMAGEAI_LMSTUDIO_MODEL` may name one loaded
  instance.
- **Cloud tier keys:** the tests see only keys stored in the keyring, because
  the test sandbox hides `config.json`. `Docs/Testing-LLM.md` has the
  procedure.

Changes after the independent review of those fixes:

- **A key never follows a route prefix to another provider.**
  `build_completion_kwargs` still honours a prefix on the model id, but when
  the prefix belongs to another provider than the caller's (`ollama/...` under
  Google, `anthropic/...` under OpenAI) it does not send the caller's key. It
  logs a WARNING without the key, calls `on_warning`, and raises
  `LLMParamError` when `strict`. A provider's key on its own route is
  unchanged, including an Ollama or LM Studio token.
- **Google Cloud login is decided in one place.** `google_auth_settings(config)`
  returns the auth mode and the saved project, from the caller's config when
  it carries them, else from the saved Settings. `UnifiedLLMProvider`, the
  lyrics generator, `StyleAnalyzer` and the sprite chat calls use it. In
  `gcloud` mode the configured Google value is an OAuth access token: it is
  never sent as a key, and Gemini models take `vertex_ai/` with the saved
  project. The GUI code that builds provider configs was not changed; it
  still fetches the token, which is now ignored.
- **The Google key is no longer written to `GEMINI_API_KEY`.**
  `UnifiedLLMProvider` and the lyrics generator keep their Google key, auth
  mode and project on the object and pass them with every request
  (`api_key`, `auth_mode`, `vertex_project`). Exporting the key let one
  object change another's route: a second object in `gcloud` mode removed
  the variable a first object in API-key mode relied on. The OpenAI and
  Anthropic keys are still exported as before.
- **A missing Google key never moves a request to Vertex.** These objects
  always pass their auth mode: `api-key` is the `gemini/` route, and without
  a key the request fails with the package's `AuthError`; only `gcloud` uses
  `vertex_ai/`. In API-key mode a key the config dict lacks is read once per
  object through `ConfigManager.get_api_key("google")` (`google_credentials`
  in `core/llm_params.py`), because a key kept in the keyring is in no config
  dict. That lookup is never made in `gcloud` mode, where it would return an
  access token. The video workspace's single-scene Enhance built its provider
  config from top-level config entries and found no key for keyring storage;
  it now uses `get_api_key` like the other builders.
- **An explicit Google auth mode decides the route, also over a prefix.**
  With `auth_mode` given, `build_completion_kwargs` sends `gemini/x` on
  `vertex_ai/` in `gcloud` mode (no key, with the project) and `vertex_ai/x`
  on `gemini/` in API-key mode, each with a warning. Without `auth_mode` a
  Google prefix is honoured as written. `core/styles/analyzer.py`, which
  prefixes its model with `gemini/`, now follows the auth mode and no longer
  demands an API key under Google Cloud login.
- **`StyleAnalyzer` uses the package for Google too.** Its Google branch built
  its own `genai.Client`; it now sends the image as a base64 data URL through
  `build_completion_kwargs` and `chameleon_llm.completion`, on `gemini/` or
  `vertex_ai/` by auth mode. Its single key is not sent when the model id
  routes to another provider.
- **Base URLs are logged only in sanitised form.** `endpoint.display_url`
  keeps scheme, host, port and path and removes user info, query and
  fragment. Both adapters' DEBUG lines and the cleartext WARNING use it.
- **Not verified:** the local tier's real-server paths have never run. No LM
  Studio or Ollama server was running on the build machine.
