# Replace LiteLLM with `chameleon_llm` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** ImageAI stops installing and importing `litellm`; every LLM feature keeps working through a small vendored package, `core/chameleon_llm/`.

**Architecture:** One `completion()` with LiteLLM's call and response shape. A dispatcher resolves the route from the model prefix, filters parameters, and hands off to one of three adapters built on SDKs ImageAI already installs (`openai`, `anthropic`, `google-genai`). The package imports nothing from ImageAI.

**Tech Stack:** Python, `openai`, `anthropic`, `google-genai`, `pytest`, PySide6 offscreen for dialog tests.

**Spec:** `Plans/2026-11-18-replace-litellm-design.md` (read it first; this plan argues from it).

**Status (2026-11-18 14:40):** Tasks 1 to 11 complete and reviewed. Task 12 in progress. Deviations from this plan are listed in the spec under "What changed during the build".

**Written:** 2026-11-18 11:20. **Branch:** `feat/replace-litellm`, worktree `.worktrees/replace-litellm`, cut from `origin/main` b47a111.

## Global Constraints

- `core/chameleon_llm/` imports nothing from `core`, `gui`, `cli`, `providers`, and nothing from Qt.
- No new dependency. If one seems needed, stop and ask.
- A parameter that is dropped or translated is logged at WARNING on the logger `chameleon_llm`. An API key never appears in any log line.
- `message.content` is always a `str`, never `None` (18 call sites call `.strip()` on it).
- Default `max_retries=0`, default `timeout=600`, default Anthropic `max_tokens=4096`.
- Model ids come from `resolve_model()`; no `claude-*` / `gpt-*` / `gemini-*` literal in package code. Tests may use obviously fake ids such as `"anthropic/test-model"`.
- Tests marked `live` run only with `IMAGEAI_LIVE_TESTS=1`; tests marked `local` skip when the server does not answer.
- Per-task gate: `python -m compileall -q <touched files>` plus that task's tests. The full suite runs once, in Task 12.
- Conventional Commits, subject under 72 characters, with the trailers `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>` and `AI-Model: <session model id>`.
- `CHANGELOG.md` and version numbers are not edited; the lander cuts them.
- Commands are written as `python`; use the repo's `.venv` interpreter on Windows (`.venv_linux` + `python3` in WSL).

## Review Focus

Each line has a test in the task named.

1. **A reply with no text** (refusal, safety block, empty candidates): `content == ""` and `finish_reason == "content_filter"` or `"length"`, never `None` and never an exception. Tasks 2, 3, 4, 5.
2. **The SDK's own retries**: SDK clients default to 2 retries, which would freeze GUI callers that pass `max_retries=0`. Each adapter test asserts the client is built with `max_retries=0` unless the caller passed another value. Tasks 2, 4, 5.
3. **Model ids with slashes** (`lmstudio-community/Meta-Llama-3-8B-GGUF`, and `openai/<id>` with an `api_base`): routed to the OpenAI adapter with the id intact after only the route segment is removed. Task 1.
4. **No key anywhere**: no argument and no environment variable gives `AuthError` whose message names the variable to set, before any network call; and with a key present, the key string is absent from captured log output. Tasks 2, 4, 5.
5. **Message content that is not a plain string**: a list of parts, an empty string, or `None` on an assistant turn translates without raising in every adapter. Tasks 2, 4, 5.

---

## File structure

| File | Responsibility |
|---|---|
| `core/chameleon_llm/__init__.py` | Public names and `__version__ = "0.1.0"` |
| `core/chameleon_llm/types.py` | `Completion`, `Choice`, `Message`, `Usage` |
| `core/chameleon_llm/errors.py` | Error family and `wrap_sdk_error` |
| `core/chameleon_llm/routing.py` | `Route`, `resolve_route` |
| `core/chameleon_llm/dispatch.py` | `completion()` |
| `core/chameleon_llm/openai_adapter.py` | Chat path and Responses path |
| `core/chameleon_llm/anthropic_adapter.py` | Anthropic |
| `core/chameleon_llm/gemini_adapter.py` | Gemini API key and Vertex |
| `tests/chameleon_llm/` | One test file per module above |
| `tests/chameleon_llm/conftest.py` | Fake SDK clients shared by adapter tests |

---

### Task 1: Types, errors, routing, dispatcher

**Files:**
- Create: `core/chameleon_llm/{__init__,types,errors,routing,dispatch}.py`
- Test: `tests/chameleon_llm/test_routing.py`, `test_dispatch.py`, `test_errors.py`

**Interfaces — Produces:**

```python
# types.py (dataclasses)
Message(role: str, content: str)
Choice(index: int, message: Message, finish_reason: str)   # "stop" | "length" | "content_filter"
Usage(prompt_tokens: int, completion_tokens: int, total_tokens: int)
Completion(model: str, choices: list[Choice], usage: Usage, raw: Any = None)

# errors.py
class LLMError(Exception):            # .provider: str, .status_code: int | None
class AuthError(LLMError)
class RateLimitError(LLMError)
class BadRequestError(LLMError)
class TimeoutError_(LLMError)
class ConnectionError_(LLMError)
class ServerError(LLMError)
class UnsupportedRouteError(LLMError)
class MissingSDKError(LLMError)
def wrap_sdk_error(exc: Exception, provider: str) -> LLMError
# message is f"{type(exc).__name__}: {exc}"; caller raises `from exc`.
# By status code: 401/403 Auth, 429 RateLimit, 400/404/409/422 BadRequest, >=500 Server.
# No status: class name containing "timeout" -> TimeoutError_, "connection" -> ConnectionError_,
# otherwise LLMError.

# routing.py
Route(adapter: str, route: str, model: str)     # adapter in {"openai","anthropic","gemini"}
def resolve_route(model: str, api_base: str | None = None) -> Route

# dispatch.py
def completion(*, model: str, messages: list[dict], api_key: str | None = None,
               api_base: str | None = None, timeout: float | None = None,
               max_retries: int = 0, **params) -> Completion

# Adapter contract (Tasks 2-5 implement it):
ACCEPTED_PARAMS: frozenset[str]
def complete(route: Route, messages: list[dict], *, api_key: str | None,
             api_base: str | None, params: dict, timeout: float,
             max_retries: int) -> Completion
```

Routing table (copy from the spec): none or `openai/` → openai; `ollama/`, `ollama_chat/` → openai with `route="ollama"`; `lm_studio/` → openai with `route="lm_studio"`; `anthropic/`; `gemini/`; `vertex_ai/` → gemini with `route="vertex_ai"`; `azure/`, `bedrock/` → `UnsupportedRouteError`. A first segment not in the table is part of the model id.

Dispatcher behavior: params whose value is `None` are removed silently; params not in the adapter's `ACCEPTED_PARAMS` are removed with one WARNING naming them; `timeout` defaults to 600; one DEBUG line with route, model and sorted parameter names; adapters are imported lazily by name, and an `ImportError` for an SDK becomes `MissingSDKError` naming the pip package.

- [x] **Step 1: Write failing tests**

```python
# test_routing.py
@pytest.mark.parametrize("model,api_base,expected", [
    ("test-model", None, Route("openai", "openai", "test-model")),
    ("openai/test-model", None, Route("openai", "openai", "test-model")),
    ("openai/lmstudio-community/Meta-Llama-3-8B-GGUF", "http://localhost:1234/v1",
     Route("openai", "openai", "lmstudio-community/Meta-Llama-3-8B-GGUF")),
    ("lmstudio-community/Meta-Llama-3-8B-GGUF", "http://localhost:1234/v1",
     Route("openai", "openai", "lmstudio-community/Meta-Llama-3-8B-GGUF")),
    ("ollama/llama3", None, Route("openai", "ollama", "llama3")),
    ("ollama_chat/llama3", None, Route("openai", "ollama", "llama3")),
    ("lm_studio/org/model", "http://x/v1", Route("openai", "lm_studio", "org/model")),
    ("anthropic/test-model", None, Route("anthropic", "anthropic", "test-model")),
    ("gemini/test-model", None, Route("gemini", "gemini", "test-model")),
    ("vertex_ai/test-model", None, Route("gemini", "vertex_ai", "test-model")),
])
def test_resolve_route(model, api_base, expected): ...

@pytest.mark.parametrize("model", ["azure/x", "bedrock/x"])
def test_unsupported_routes_raise(model):  # UnsupportedRouteError, message contains the prefix

def test_empty_model_raises_bad_request(): ...

# test_dispatch.py (register a fake adapter via monkeypatch)
def test_none_params_removed_silently(caplog): ...
def test_unaccepted_param_dropped_with_warning(caplog):
    # completion(model="anthropic/test-model", messages=[...], seed=7)
    # adapter receives params without "seed"; caplog has one WARNING containing "seed"
def test_timeout_defaults_to_600(): ...
def test_max_retries_defaults_to_zero(): ...
def test_missing_sdk_becomes_missing_sdk_error(): ...
def test_package_imports_nothing_from_imageai():
    # ast-walk every file under core/chameleon_llm; no import starts with
    # "core", "gui", "cli", "providers", "PySide6"

# test_errors.py
@pytest.mark.parametrize("status,cls", [(401, AuthError), (403, AuthError), (429, RateLimitError),
    (400, BadRequestError), (404, BadRequestError), (500, ServerError), (503, ServerError)])
def test_wrap_by_status(status, cls): ...
def test_wrap_timeout_by_class_name():   # class APITimeoutError -> TimeoutError_
def test_wrap_connection_by_class_name(): # class APIConnectionError -> ConnectionError_
def test_wrapped_message_keeps_original_text_and_type_name(): ...
```

- [x] **Step 2:** Run `python -m pytest tests/chameleon_llm -v`. Expected: collection errors (module not found).
- [x] **Step 3:** Implement the five files to the interfaces above.
- [x] **Step 4:** Run the same command. Expected: all pass.
- [x] **Step 5:** Commit: `feat(llm): add chameleon_llm types, routing and dispatcher`.

---

### Task 2: OpenAI adapter, chat path

**Files:**
- Create: `core/chameleon_llm/openai_adapter.py`, `tests/chameleon_llm/conftest.py`
- Test: `tests/chameleon_llm/test_openai_adapter.py`

**Interfaces — Consumes:** Task 1's adapter contract, `Route`, `wrap_sdk_error`. **Produces:** `openai_adapter.complete`, `openai_adapter.ACCEPTED_PARAMS = {"temperature","top_p","top_k","max_tokens","max_completion_tokens","reasoning_effort","verbosity","response_format","seed","stop"}`, and in `conftest.py` a `fake_openai` fixture that patches `openai.OpenAI` and records constructor kwargs and `chat.completions.create` kwargs.

Decisions:
- Key: argument, else `OPENAI_API_KEY`. For `route in {"ollama","lm_studio"}` or any call with a base URL, a missing key becomes the string `"not-needed"`. For plain OpenAI with no key: `AuthError("... set OPENAI_API_KEY ...")` before building a client.
- Base URL: `route="ollama"` → `(api_base or env OLLAMA_API_BASE or "http://localhost:11434").rstrip("/") + "/v1"` unless it already ends in `/v1`. `route="lm_studio"` → `api_base or env OPENAI_API_BASE`, required, else `BadRequestError`. `route="openai"` → `api_base or env OPENAI_API_BASE or None`.
- `top_k`: sent in `extra_body={"top_k": n}` when a base URL is in effect; dropped with a WARNING otherwise.
- Client: `openai.OpenAI(api_key=..., base_url=..., timeout=timeout, max_retries=max_retries)`, one per call.
- Response: `content = choice.message.content or ""`; `finish_reason` passed through, with `None` → `"stop"`; usage fields default to 0 when the server omits `usage`.

- [x] **Step 1: Write failing tests**

```python
def test_plain_call_builds_client_and_request(fake_openai):
    # route openai, key "k": client kwargs == {api_key:"k", base_url:None, timeout:600, max_retries:0}
    # create kwargs == {model:"test-model", messages:[...], temperature:0.2}
def test_caller_max_retries_passed_through(fake_openai): ...
def test_ollama_base_url_default_and_v1_suffix(fake_openai, monkeypatch):
    # no api_base, no env -> "http://localhost:11434/v1"; env OLLAMA_API_BASE="http://h:1" -> "http://h:1/v1"
def test_lm_studio_requires_base(fake_openai): ...            # BadRequestError
def test_openai_api_base_env_used(fake_openai, monkeypatch): ...
def test_top_k_in_extra_body_for_local_and_dropped_for_cloud(fake_openai, caplog): ...
def test_missing_key_raises_auth_error_before_network(fake_openai, monkeypatch):
    # message contains "OPENAI_API_KEY"; fake client never constructed
def test_key_never_logged(fake_openai, caplog): ...            # caplog at DEBUG has no "sk-test-123"
def test_none_content_becomes_empty_string(fake_openai): ...
def test_missing_usage_becomes_zeros(fake_openai): ...
def test_list_content_and_image_parts_pass_through_unchanged(fake_openai): ...
def test_sdk_error_wrapped(fake_openai): ...                   # status 429 -> RateLimitError, __cause__ set
```

- [x] **Step 2:** Run `python -m pytest tests/chameleon_llm/test_openai_adapter.py -v`. Expected: fail, module missing.
- [x] **Step 3:** Implement `complete` (chat path only).
- [x] **Step 4:** Run again. Expected: pass.
- [x] **Step 5:** Commit: `feat(llm): add OpenAI-compatible adapter`.

---

### Task 3: OpenAI adapter, Responses path

**Files:**
- Modify: `core/chameleon_llm/openai_adapter.py`, `tests/chameleon_llm/conftest.py` (record `responses.create`)
- Test: `tests/chameleon_llm/test_openai_responses.py`

**Interfaces — Produces:** `openai_adapter.RESPONSES_ONLY_PATTERNS: tuple[str, ...]` and `def uses_responses_api(model: str) -> bool`.

- [x] **Step 1: Confirm the facts.** Read the installed `openai` SDK's `resources/responses` signature and the current OpenAI model docs (Context7 `openai-python`). Record in the test file's docstring: which of `o1-pro`, `o3-pro` and the id `resolve_model("openai", "gpt-pro")` returns are Responses-only, and the exact field names for instructions, input parts, output-token cap, reasoning effort, verbosity, JSON mode, status and usage. If a field differs from the spec's "Responses path" paragraph, the SDK wins; note the difference in the commit body.
- [x] **Step 2: Write failing tests**

```python
@pytest.mark.parametrize("model,expected", [("o1-pro", True), ("o3-pro", True),
    ("o3", False), ("o3-mini", False), ("gpt-4.1", False)])
def test_uses_responses_api(model, expected): ...
def test_gpt_pro_family_id_uses_responses_api():   # id shape confirmed in Step 1, e.g. "gpt-N-pro"
def test_responses_request_translation(fake_openai):
    # system message -> instructions; user text -> input_text part; image_url -> input_image part;
    # max_tokens and max_completion_tokens -> max_output_tokens; reasoning_effort -> reasoning.effort
    # chat.completions.create NOT called
def test_responses_reply_normalised(fake_openai):
    # output_text "hi" -> content "hi"; status "completed" -> "stop";
    # status "incomplete" -> "length"; input_tokens/output_tokens -> prompt/completion/total
def test_responses_empty_output_is_empty_string(fake_openai): ...
def test_local_server_never_uses_responses(fake_openai):  # api_base set + model "o3-pro" -> chat path
```

- [x] **Step 3:** Run `python -m pytest tests/chameleon_llm/test_openai_responses.py -v`. Expected: fail.
- [x] **Step 4:** Implement the branch inside `complete`.
- [x] **Step 5:** Run again; also rerun Task 2's file. Expected: both pass.
- [x] **Step 6:** Commit: `feat(llm): route Responses-only OpenAI models`.

---

### Task 4: Anthropic adapter

**Files:**
- Create: `core/chameleon_llm/anthropic_adapter.py`
- Modify: `tests/chameleon_llm/conftest.py` (`fake_anthropic`)
- Test: `tests/chameleon_llm/test_anthropic_adapter.py`

**Interfaces — Produces:** `anthropic_adapter.complete`, `ACCEPTED_PARAMS = {"temperature","top_p","top_k","max_tokens","response_format","stop"}`, and the constant

```python
JSON_INSTRUCTION = "Respond with a single valid JSON object and no other text."
```

Decisions: key is the argument, else `ANTHROPIC_API_KEY`, else `AuthError`. `system` messages are joined with a blank line into the `system` parameter. `max_tokens` defaults to 4096. `image_url` with a `data:` URL → `{"type":"image","source":{"type":"base64","media_type":...,"data":...}}`; with an `http(s)` URL → `{"type":"image","source":{"type":"url","url":...}}`; a part already of type `image` passes through. `response_format={"type":"json_object"}` appends `JSON_INSTRUCTION` to the system text (creating it if absent). `stop` (str or list) → `stop_sequences` list. Reply: text blocks joined with `""`. `stop_reason` map: `end_turn`, `stop_sequence` → `stop`; `max_tokens` → `length`; `refusal` → `content_filter`; anything else → `stop`. Usage: `input_tokens`, `output_tokens`, sum.

- [x] **Step 1: Write failing tests**

```python
def test_system_lifted_and_joined(fake_anthropic): ...
def test_max_tokens_defaults_to_4096(fake_anthropic): ...
def test_data_url_image_becomes_base64_block(fake_anthropic):
    # "data:image/png;base64,AAAA" -> media_type "image/png", data "AAAA"
def test_https_image_becomes_url_source(fake_anthropic): ...
def test_native_image_block_passes_through(fake_anthropic): ...
def test_json_mode_appends_instruction(fake_anthropic):   # with and without an existing system message
def test_stop_string_becomes_list(fake_anthropic): ...
def test_client_built_with_zero_retries_and_timeout(fake_anthropic): ...
@pytest.mark.parametrize("reason,expected", [("end_turn","stop"),("stop_sequence","stop"),
    ("max_tokens","length"),("refusal","content_filter")])
def test_finish_reason_map(fake_anthropic, reason, expected): ...
def test_no_text_blocks_gives_empty_string(fake_anthropic): ...
def test_assistant_none_content_does_not_raise(fake_anthropic): ...
def test_missing_key_names_env_var(fake_anthropic, monkeypatch): ...   # "ANTHROPIC_API_KEY"
def test_key_never_logged(fake_anthropic, caplog): ...
def test_sdk_error_wrapped(fake_anthropic): ...
```

- [x] **Step 2:** Run `python -m pytest tests/chameleon_llm/test_anthropic_adapter.py -v`. Expected: fail.
- [x] **Step 3:** Implement.
- [x] **Step 4:** Run again. Expected: pass.
- [x] **Step 5:** Commit: `feat(llm): add Anthropic adapter`.

---

### Task 5: Gemini adapter (API key and Vertex)

**Files:**
- Create: `core/chameleon_llm/gemini_adapter.py`
- Modify: `tests/chameleon_llm/conftest.py` (`fake_genai`)
- Test: `tests/chameleon_llm/test_gemini_adapter.py`

**Interfaces — Produces:** `gemini_adapter.complete`, `ACCEPTED_PARAMS = {"temperature","top_p","top_k","max_tokens","response_format","seed","stop","vertex_project","vertex_location"}`.

Decisions: `route="gemini"` → `genai.Client(api_key=arg or env GEMINI_API_KEY or env GOOGLE_API_KEY)`, none → `AuthError` naming `GEMINI_API_KEY`. `route="vertex_ai"` → `genai.Client(vertexai=True, project=vertex_project or env GOOGLE_CLOUD_PROJECT or None, location=vertex_location or env GOOGLE_CLOUD_LOCATION or "us-central1")`; no key needed. Timeout and retries go through `http_options`; confirm the option names against the installed `google-genai` before writing the test, and record them in the test docstring. Translation and finish-reason map exactly as the spec's "Gemini adapter" list. Reply text: join the text parts of the first candidate; no candidates or no parts → `""` with `content_filter`. Usage from `usage_metadata` (`prompt_token_count`, `candidates_token_count`, `total_token_count`), missing → 0.

- [x] **Step 1: Write failing tests**

```python
def test_api_key_route_builds_key_client(fake_genai): ...
def test_google_api_key_env_fallback(fake_genai, monkeypatch): ...
def test_vertex_route_builds_vertex_client_with_defaults(fake_genai, monkeypatch):
    # no args, no env -> vertexai=True, project=None, location="us-central1"
def test_vertex_args_beat_env(fake_genai, monkeypatch): ...
def test_system_becomes_system_instruction_and_assistant_becomes_model(fake_genai): ...
def test_param_mapping(fake_genai):
    # max_tokens->max_output_tokens, stop->stop_sequences, temperature/top_p/top_k/seed direct
def test_json_mode_sets_mime_type(fake_genai):   # response_mime_type == "application/json"
def test_data_url_image_becomes_inline_data(fake_genai): ...
@pytest.mark.parametrize("reason,expected", [("STOP","stop"),("MAX_TOKENS","length"),
    ("SAFETY","content_filter"),("RECITATION","content_filter")])
def test_finish_reason_map(fake_genai, reason, expected): ...
def test_no_candidates_gives_empty_content_filter(fake_genai): ...
def test_retries_zero_by_default(fake_genai): ...
def test_missing_key_names_env_var(fake_genai, monkeypatch): ...
def test_key_never_logged(fake_genai, caplog): ...
def test_sdk_error_wrapped(fake_genai): ...
```

- [x] **Step 2:** Run `python -m pytest tests/chameleon_llm/test_gemini_adapter.py -v`. Expected: fail.
- [x] **Step 3:** Implement.
- [x] **Step 4:** Run `python -m pytest tests/chameleon_llm -v`. Expected: every package test passes.
- [x] **Step 5:** Commit: `feat(llm): add Gemini and Vertex adapter`.

---

### Task 6: `core/llm_params.py`, `core/llm_models.py`, `gui/llm_utils.py`

**Files:**
- Modify: `core/llm_params.py` (delete `_litellm_max_output_tokens` at 285-294 and its use at 317-321; docstrings), `core/llm_models.py` (comments naming LiteLLM), `gui/llm_utils.py:90-184`
- Test: `tests/test_llm_params.py`, new `tests/gui/test_llm_handler.py`

**Interfaces — Produces:**

```python
# gui/llm_utils.py
class LLMHandler:
    @staticmethod
    def setup_llm(enable_console_logging: bool = True) -> Tuple[bool, Any]
        # returns (True, core.chameleon_llm); attaches the console handler to logging.getLogger("chameleon_llm")
    @staticmethod
    def prepare_request(...)   # signature unchanged
```

No `LiteLLMHandler` alias is kept; Tasks 7-8 update every caller.

Output ceilings: for each model id in `LLM_PROVIDERS` with no `max_output_tokens` in `core/model-registry.fallback.json` (today `claude-opus-4-20250514` and `claude-3-7-sonnet-20250219`; list them with a short script and include the list in the commit body), add a `_FamilyRule` placed before the generic rule for that provider with `max_output_tokens` taken from the provider's published limit. Local models (Ollama, LM Studio) get no ceiling.

- [x] **Step 1: Write failing tests**

```python
# tests/test_llm_params.py (add)
def test_no_litellm_reference_in_llm_params():
    assert "litellm" not in Path("core/llm_params.py").read_text(encoding="utf-8").lower()
def test_every_cloud_model_has_an_output_ceiling():
    # for provider in ("openai","anthropic","gemini"): for model in LLM_PROVIDERS[provider].models:
    #     assert get_param_rules(provider, model).max_output_tokens
def test_unknown_local_model_has_no_ceiling():
    assert get_param_rules("ollama", "some-local-model").max_output_tokens is None

# tests/gui/test_llm_handler.py
def test_setup_llm_returns_package_with_completion():
    ok, mod = LLMHandler.setup_llm(enable_console_logging=False)
    assert ok and callable(mod.completion)
def test_setup_llm_attaches_console_handler_to_chameleon_llm_logger(): ...
```

- [x] **Step 2:** Run `python -m pytest tests/test_llm_params.py tests/gui/test_llm_handler.py -v`. Expected: the new tests fail.
- [x] **Step 3:** Make the changes. Existing tests in `tests/test_llm_params.py` that patch `litellm` are rewritten against the registry.
- [x] **Step 4:** Run again. Expected: pass.
- [x] **Step 5:** Commit: `refactor(llm): drop LiteLLM from params and handler`.

---

### Task 7: Migrate `core/` call sites

**Files (modify):** `core/layout/designer.py`, `core/layout/prompt_helper.py`, `core/lyrics_to_prompts.py`, `core/prompt_enhancer_llm.py`, `core/sprite/generation/action_cards.py`, `core/sprite/generation/pose_steps.py`, `core/video/end_prompt_generator.py`, `core/video/llm_sync.py`, `core/video/llm_sync_v2.py`, `core/video/prompt_engine.py`, `core/video/scene_suggester.py`, `core/video/storyboard_v2.py`, `core/video/style_analyzer.py`, `core/video/video_prompt_generator.py`
**Test:** new `tests/test_no_litellm.py`; existing tests under `tests/video`, `tests/sprite`, `tests/layout`, `tests/styles`

**Interfaces — Consumes:** `core.chameleon_llm.completion`, `build_completion_kwargs`, `infer_provider_from_model`.

Rules for every site:
1. `import litellm` → `from core import chameleon_llm`. Objects that keep the module in an attribute rename it: `self.litellm` → `self.llm` (`core/lyrics_to_prompts.py`, `core/video/prompt_engine.py`). Readers of `<obj>.litellm.completion` (`core/prompt_enhancer_llm.py`, `core/video/llm_sync.py`, `llm_sync_v2.py`, `scene_suggester.py`, `prompt_engine.py:1458`) follow the rename. If the target object already has an attribute named `llm`, use `llm_client` in all of them.
2. Delete every `drop_params`, `set_verbose`, `suppress_debug_info` line and every "LiteLLM not installed" fallback branch, including the direct-SDK fallback in `core/video/style_analyzer.py:252-276`.
3. A call that passes a bare model id (`core/video/prompt_engine.py` `analyze_image` near 992-1011, `core/lyrics_to_prompts.py:218`, `core/video/style_analyzer.py:230` and `:298`) builds its arguments with `build_completion_kwargs(infer_provider_from_model(model), model, messages, params, api_key=..., api_base=...)`.
4. The `os.environ[...] = ` blocks in `prompt_engine.py:107-130` and `lyrics_to_prompts.py:120-150` stay; the package reads those variables.
5. `core/video/prompt_engine.py` `_is_retryable_error` (164-191): keep its text matching; add `isinstance(e, (chameleon_llm.TimeoutError_, chameleon_llm.ConnectionError_, chameleon_llm.ServerError, chameleon_llm.RateLimitError))` as the first check.
6. Request and response logging at each site is left exactly as it is.

- [x] **Step 1: Write the failing guard test**

```python
# tests/test_no_litellm.py
ROOTS = ["core", "gui", "cli", "providers", "scripts", "main.py"]
def test_no_litellm_import_in_application_code():
    # ast-parse every .py under ROOTS; collect Import/ImportFrom whose module starts with "litellm"
    assert offenders == []
def test_no_litellm_attribute_use():
    # regex r"\blitellm\." over the same files, excluding comments
    assert offenders == []
```

Mark both `@pytest.mark.xfail(strict=True, reason="gui/ and scripts/ migrate in Task 8")` for this task; add a third, unmarked test with `ROOTS = ["core"]`.

- [x] **Step 2:** Run `python -m pytest tests/test_no_litellm.py -v`. Expected: the `core` test fails; the two xfail tests xfail.
- [x] **Step 3:** Apply rules 1-6 file by file.
- [x] **Step 4: Bare-id regression test** in `tests/video/test_prompt_engine_routes.py`: patch `core.chameleon_llm.completion`, call `analyze_image` with a model id starting `claude-` and one starting `gemini-`, assert the `model` argument received starts with `anthropic/` and with `gemini/` or `vertex_ai/`.
- [x] **Step 5:** Run `python -m pytest tests/test_no_litellm.py tests/video tests/sprite tests/layout tests/styles -v`. Expected: pass (two xfail).
- [x] **Step 6:** Commit: `refactor(llm): move core call sites to chameleon_llm`.

---

### Task 8: Migrate `gui/`, `scripts/`, `cli/`

**Files (modify):** `gui/layout/text_gen_dialog.py`, `gui/prompt_generation_dialog.py`, `gui/prompt_question_dialog.py`, `gui/prompt_question_dialog_old.py`, `gui/sprite/action_cards_panel.py`, `gui/video/start_prompt_dialog.py`, `gui/video/workspace_widget.py`, `scripts/generate_tags.py`, `cli/runner.py`
**Test:** `tests/test_no_litellm.py`

Same rules as Task 7, plus:
- `LiteLLMHandler.setup_litellm` callers → `LLMHandler.setup_llm` (Task 6).
- `gui/prompt_generation_dialog.py:256` and `:425-429` read `response.choices[0].text`. `Choice` has no `text`. Trace each branch: if it is reachable only for a LiteLLM text-completion reply, delete it; if it guards something else, rewrite it against `message.content`. State which in the commit body.
- `scripts/generate_tags.py:250-255` keeps passing `vertex_project` / `vertex_location`.
- `gui/prompt_question_dialog_old.py`: if nothing imports it (`grep -rn prompt_question_dialog_old`), delete the file instead of migrating it and say so in the commit body.

- [x] **Step 1:** Remove the two `xfail` marks in `tests/test_no_litellm.py`. Run it. Expected: both fail.
- [x] **Step 2:** Apply the rules.
- [x] **Step 3:** Run `python -m pytest tests/test_no_litellm.py tests/gui -v`. Expected: pass.
- [x] **Step 4:** Commit: `refactor(llm): move gui and script call sites to chameleon_llm`.

---

### Task 9: Offscreen dialog tests

**Files:**
- Create: `tests/gui/test_llm_dialogs.py`

**Interfaces — Consumes:** `core.chameleon_llm.completion`, `Completion`, `Choice`, `Message`, `Usage`.

One fixture, `fake_completion`, monkeypatches `core.chameleon_llm.completion` to record its kwargs and return `Completion(model="test-model", choices=[Choice(0, Message("assistant", CANNED), "stop")], usage=Usage(1, 1, 2))`, where `CANNED` is set per test to text the dialog can parse. A second fixture stubs `config.get_api_key` to return `"test-key"`.

One test per LLM entry point: `gui/prompt_generation_dialog.py`, `gui/prompt_question_dialog.py`, `gui/layout/text_gen_dialog.py`, `gui/video/start_prompt_dialog.py`, the action-cards generation started from `gui/sprite/action_cards_panel.py`, and the LLM action in `gui/video/workspace_widget.py`. Follow the construction pattern in `tests/gui/test_dialog_conventions.py:164` onward. Each test:

1. constructs the dialog or panel offscreen;
2. triggers the primary action (call the worker's `run()` directly when the dialog starts a `QThread`, so the test stays single-threaded);
3. asserts `fake_completion` was called once with a `model` string that carries a route prefix or an `api_base`;
4. asserts the canned text reached the result widget or the result signal;
5. asserts the status console text contains the model name and the canned reply (the `AGENTS.md` full-logging rule).

Plus one failure test per entry point: `fake_completion` raises `chameleon_llm.RateLimitError`; assert the dialog does not raise, the console shows the error text, and the error was logged at ERROR.

- [x] **Step 1:** Write the tests.
- [x] **Step 2:** Run `python -m pytest tests/gui/test_llm_dialogs.py -v`. Expected: pass. A test that fails here has found a migration bug in Task 8; fix it in the dialog, not in the test.
- [x] **Step 3:** Commit: `test(gui): cover LLM dialogs offscreen with a fake completion`.

---

### Task 10: Local-server and cloud tiers

**Files:**
- Create: `tests/local/__init__.py`, `tests/local/conftest.py`, `tests/local/test_local_lmstudio.py`, `tests/local/test_local_ollama.py`, `Docs/Testing-LLM.md`
- Modify: `pytest.ini` (add marker), `tests/test_live_llm_params.py`

**Interfaces — Produces (fixtures in `tests/local/conftest.py`):**

```python
@pytest.fixture(scope="session")
def lmstudio() -> LocalServer    # skips when unreachable
@pytest.fixture(scope="session")
def ollama() -> LocalServer
LocalServer(base_url: str, model: str, vision: bool)   # base_url is the OpenAI-compatible URL to pass as api_base
```

`pytest.ini` marker line: `local: needs a local LM Studio or Ollama server; each test skips when the server does not answer`.

- [x] **Step 1: Confirm the LM Studio REST API.** Read the current LM Studio REST documentation and record in `tests/local/conftest.py`'s docstring the paths and fields for: listing models with downloaded/loaded state and a vision flag, loading a model, unloading a model. Support the newest documented form; if the server answers 404 on it, fall back to the older form if one is documented. If the documented API cannot load a model, the fixture skips with "load a model in LM Studio first" when none is loaded, and the plan's load/unload steps are dropped; say so in the commit body.
- [x] **Step 2: Write the fixtures.**
  - LM Studio: base from `IMAGEAI_LMSTUDIO_URL`, else `http://localhost:1234`. List with a 2 second timeout; any connection error → `pytest.skip("LM Studio is not running at <url>")`. Model: `IMAGEAI_LMSTUDIO_MODEL`, else the first loaded chat model, else the smallest downloaded chat model, loaded over REST with a 120 second timeout. No chat model → skip with "no chat model downloaded in LM Studio". On teardown unload only a model this fixture loaded. `LocalServer.base_url` is `<base>/v1`.
  - Ollama: base from `IMAGEAI_OLLAMA_URL`, else `http://localhost:11434`. List through `core.llm_models.fetch_ollama_models`; empty → skip. Model: `IMAGEAI_OLLAMA_MODEL`, else the smallest by the `size` field of `GET /api/tags`. `vision` is true when `POST /api/show` reports a vision capability.
- [x] **Step 3: Write the tests** (same three in each file, all `@pytest.mark.local`):

```python
def test_text_reply(server):
    r = completion(model=f"{PREFIX}{server.model}", api_base=server.base_url,
                   messages=[{"role": "user", "content": "Reply with the single word: pong"}],
                   max_tokens=20, temperature=0, timeout=120)
    assert r.choices[0].message.content.strip() != ""
    assert r.choices[0].finish_reason in ("stop", "length")
def test_json_mode(server):
    # response_format={"type":"json_object"}, prompt asks for {"ok": true};
    # LLMResponseParser output parses to a dict
def test_image_input(server):
    # skip unless server.vision; 8x8 red PNG as a data URL; reply non-empty
```

`PREFIX` is `"lm_studio/"` and `"ollama/"`. For Ollama, `api_base` is the bare base URL (the adapter adds `/v1`).

- [x] **Step 4:** Run `python -m pytest -m local -v`. Expected: tests pass for each running server and skip, with the reason shown, for each absent one. Zero failures either way.
- [x] **Step 5: Re-point the cloud tier.** In `tests/test_live_llm_params.py` replace `pytest.importorskip("litellm")` and the `litellm_mod` fixture with `from core import chameleon_llm`; the "raw request rejected" tests assert `chameleon_llm.BadRequestError`. Add, per cloud route (OpenAI chat model, OpenAI Responses-only model via `resolve_model("openai", "gpt-pro")`, Anthropic, Gemini API key, Vertex): one text call, one JSON-mode call, one image call. Vertex tests skip when no Google Cloud login is available.
- [x] **Step 6:** Run `python -m pytest tests/test_live_llm_params.py -v` without the environment variable. Expected: all skipped, none errored.
- [x] **Step 7: Write `Docs/Testing-LLM.md`:** the three commands from the spec's tier table, the four `IMAGEAI_*` variables and `IMAGEAI_LIVE_TESTS`, the cost of each tier, where keys are read from (`config.get_api_key()`, never the environment of the test command), and what each skip message means.
- [x] **Step 8:** Commit: `test(llm): add local-server tier and re-point live tier`.

---

### Task 11: Remove the dependency and update the docs

**Files (modify):** `requirements.txt`, `requirements-security.txt`, `.snyk`, `Docs/Snyk-Exceptions.md`, `AGENTS.md`, `README.md`, `Docs/ImageAI-CLI-Guide.md`, `Docs/Claude Desktop Instructions.md`, `.agents/skills/imageai-cli/SKILL.md`, `.claude/skills/imageai-cli/SKILL.md`, `Docs/CodeMap.md`
**Delete:** `tests/test_litellm_sdk_compatibility.py`
**Test:** `tests/test_no_litellm.py`, `tests/test_http_dependency_security.py`

- [x] **Step 1: Add the failing requirements test** to `tests/test_no_litellm.py`:

```python
@pytest.mark.parametrize("name", ["requirements.txt", "requirements-security.txt"])
def test_litellm_not_required(name):
    lines = [l.split("#")[0].strip().lower() for l in Path(name).read_text(encoding="utf-8").splitlines()]
    assert not any(l.startswith("litellm") for l in lines)
```

Run it. Expected: fail.

- [x] **Step 2:** Remove the `litellm` line from both requirements files and delete `tests/test_litellm_sdk_compatibility.py`.
- [x] **Step 3: Re-resolve.** In a fresh virtual environment outside the repo run `python -m pip install -r requirements.txt`, then `python -m pip show litellm` (expected: "not found") and `python -m pip show httpx2 httpcore2`. If nothing requires `httpx2` / `httpcore2` any more ("Required-by:" empty apart from each other), remove both pins and their comment block from both requirements files and update `tests/test_http_dependency_security.py` to match; otherwise keep the pins and rewrite the comment so it no longer names LiteLLM as the reason.
- [x] **Step 4:** Remove every LiteLLM entry from `.snyk` and `Docs/Snyk-Exceptions.md`. Remove nothing else from either file.
- [x] **Step 5: Docs.** `AGENTS.md`: the Hard-rules helper list says `LLMHandler`; the Conventions line becomes "Use `core/chameleon_llm` for chat calls; parameter rules live in `core/llm_params.py`." Update the one-line mentions in `README.md`, `Docs/ImageAI-CLI-Guide.md`, `Docs/Claude Desktop Instructions.md` and both `imageai-cli` `SKILL.md` copies (the two copies stay identical). Add `Docs/Testing-LLM.md` to the Pointers list in `AGENTS.md`. Regenerate `Docs/CodeMap.md` with `python tools/generate_code_map.py`. Leave `Plans/`, `Notes/`, `CHANGELOG.md` and `COMMIT_MESSAGE.txt` alone.
- [x] **Step 6:** Run `python -m pytest tests/test_no_litellm.py tests/test_http_dependency_security.py tests/test_readme_help_anchors.py tests/test_generate_code_map.py -v`. Expected: pass.
- [x] **Step 7:** Run `grep -rli litellm . --include=*.py --include=*.md --include=*.txt --include=.snyk --exclude-dir=.git --exclude-dir=Plans --exclude-dir=Notes --exclude-dir=.venv --exclude-dir=.venv_linux --exclude-dir=.worktrees`. Expected output: `CHANGELOG.md`, `COMMIT_MESSAGE.txt`, `tests/test_no_litellm.py`, and nothing else.
- [x] **Step 8:** Commit: `build(deps): remove litellm`.

---

### Task 12: Branch finish

- [ ] **Step 1:** Full suite: `python -m pytest`. Expected: no failures.
- [ ] **Step 2:** Local tier: `python -m pytest -m local -v`. Save the output. If LM Studio or Ollama skipped as "not running", add a runbook item asking Leland to start it and run this one command (`runbook add`); it is the last gate.
- [ ] **Step 3:** Cloud tier: `IMAGEAI_LIVE_TESTS=1 python -m pytest -m live -v` (PowerShell: `$env:IMAGEAI_LIVE_TESTS = '1'; python -m pytest -m live -v`). Leland has not yet confirmed that Claude runs this paid tier; confirm before running. Save the output.
- [ ] **Step 4:** Start the app once (`python main.py`) and confirm it reaches the main window with no traceback in `imageai_current.log`.
- [ ] **Step 5:** Scans, before and after counts recorded: `pip-audit -r requirements.txt`, `osv-scanner scan source -r .`, `snyk test --file=requirements.txt`, `snyk code test`. Any finding with a fix is fixed in this branch.
- [ ] **Step 6:** Sweep Dependabot (the two commands in the global `AGENTS.md`); close or supersede any open LiteLLM bump PR, naming this PR.
- [ ] **Step 7:** Mark the spec `Status: Implemented` and tick this plan's boxes; commit.
- [ ] **Step 8:** Codex review: `/codex:review --base origin/main`; fix or answer each finding; then `/code-review origin/main...HEAD`.
- [ ] **Step 9:** `git log --oneline origin/main..HEAD` shows only this work. Push; open the PR with: what changed, the three test-tier outputs, scan counts before and after, the Codex findings and answers, and

```markdown
## Release notes

Release: minor

- Chat and prompt features no longer depend on LiteLLM. They now call OpenAI, Anthropic, Google Gemini, Ollama and LM Studio through a small built-in adapter.
- New automated tests for local LM Studio and Ollama servers; see Docs/Testing-LLM.md.
```

- [ ] **Step 10:** Wait for CodeRabbit and GrepTile; read the inline comments, fix or answer, resolve threads. Land with `python ~/.claude/skills/land-pr/pr_tool.py land lelandg/ImageAI#<N> --apply`, run from outside this worktree.
- [ ] **Step 11:** Write the summary to `Notes/2026-11-18-replace-litellm-summary.md` (direct commit to `main`), including the follow-up: ChatMaster migration, and creating the `chameleon-llm` repository at that point.
