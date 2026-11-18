# Replace LiteLLM with an in-house adapter package (`llm_shim`) — design

**Date:** 2026-11-18 10:58
**Status:** Design, awaiting Leland's approval. Nothing is built.
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

A self-contained Python package named `llm_shim`, vendored at
`core/llm_shim/` (the same pattern as `core/model_registry/`). It imports
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
from core.llm_shim import completion

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
WARNING on the `llm_shim` logger. That is what `drop_params = True` did, minus
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

The shim logs on the logger `llm_shim`: one DEBUG line per request (route,
model, parameter names, never the key) and the WARNING lines above. The full
request and response logging required by `AGENTS.md` stays where it is, in the
call sites and `gui/llm_utils.py`.

### Changes in ImageAI

1. Add `core/llm_shim/` and its tests.
2. `core/llm_params.py`: delete `_litellm_max_output_tokens`. The model
   registry supplies the output ceiling. For each model in `LLM_PROVIDERS`
   that the bundled registry snapshot does not cover (today
   `claude-opus-4-20250514` and `claude-3-7-sonnet-20250219`), the ceiling is
   added to the curated family rules, so no model loses its cap. Docstrings
   stop naming LiteLLM.
3. `gui/llm_utils.py`: `LiteLLMHandler` becomes `LLMHandler`;
   `setup_litellm()` becomes `setup_llm()`, attaches the console handler
   to the `llm_shim` logger, and returns `(True, core.llm_shim)` so callers
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
   `core/llm_shim`"), `README.md`, `Docs/ImageAI-CLI-Guide.md`,
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

### Done means

- A fresh virtual environment built from `requirements.txt` has no `litellm`.
- `grep -ri litellm` over code and current docs returns nothing outside
  `Plans/`, `Notes/` and `CHANGELOG.md`.
- The full test suite passes; the live tests pass for OpenAI, Anthropic,
  Gemini API key and Vertex; Ollama and LM Studio are checked by hand.
- `pip-audit`, `osv-scanner` and `snyk test` report no LiteLLM finding, and
  the before and after advisory counts are in the PR body.
- Each LLM dialog in the GUI is opened once and produces a result.

### Delivery

One PR in `lelandg/ImageAI` on branch `feat/replace-litellm`.
`Release: minor`.

## Calls made by Claude (not decided by Leland)

- The name `llm_shim`.
- The package is born vendored inside ImageAI. Its own repository is created
  when ChatMaster becomes the second user, and ImageAI's copy is then synced
  from it, as `core/model_registry/client.py` is today. This replaces my
  earlier suggestion of pinning a git tag: a git dependency would force every
  ImageAI user to have `git` installed for `pip install`.
- Anthropic JSON mode is done with a system-text instruction.
- Default `max_tokens` 4096 for Anthropic, default timeout 600 seconds,
  no retries inside the shim unless a caller asks, one client per call.
- Bare model ids are fixed at the call sites, not guessed inside the shim.
- Environment-variable fallbacks for keys and endpoints, as listed above.
- Azure and Bedrock are unsupported in this version.

## Open, waiting on Leland

1. **OpenAI models served only by the Responses API** (`gpt-pro` family,
   `o3-pro`, `o1-pro` in `core/llm_models.py`). LiteLLM bridges these to the
   Responses API without saying so. Either the OpenAI adapter gets a second
   request path for them, or they leave the model list.
2. **Who runs the checks that need accounts and a screen:** the live tests
   (they cost a little money), the Ollama and LM Studio checks, and opening
   each LLM dialog.

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
