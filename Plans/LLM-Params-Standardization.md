# LLM Parameter Standardization

**Status:** Complete (v0.44.0) — all rollout steps done 2026-08-03
**Started:** 2026-08-03
**Branch:** `feat/llm-param-standardization`

> Outcome: 26 unit tests + 19 live boundary tests all green (Anthropic,
> OpenAI, Gemini); full suite 683 passed. Style-analyzer regression verified
> live on claude-opus-5 and claude-sonnet-5. Two additional silent bugs fixed
> beyond the plan: `generate()` keyword mismatch in duration estimation, and
> missing `anthropic/` prefixes in storyboard/llm-sync paths.

## Trigger bug (root cause)

Style analysis (Image tab → style dialog) fails against Anthropic:

```
litellm.BadRequestError: AnthropicException - {"type":"error","error":
{"type":"invalid_request_error","message":"`temperature` is deprecated for this model."}}
```

Path: `core/styles/analyzer.py:255` → `UnifiedLLMProvider.analyze_image()`
(`core/video/prompt_engine.py:939`) which always sends `temperature=0.7`.
The Claude 5 family (`claude-opus-5`, `claude-sonnet-5`, `claude-fable-5`) and
Opus 4.7/4.8 **reject** `temperature`/`top_p`/`top_k` with a 400.

Two aggravating facts:

1. **LiteLLM 1.89.0's capability table is wrong** — it claims `temperature` is
   supported on `anthropic/claude-opus-5`, so `litellm.drop_params=True` (set
   nearly everywhere) does *not* drop it. LiteLLM cannot be the validator.
2. The same class of per-model constraint is hand-patched all over the code
   (`if 'gpt-5' in model: temperature = 1.0` appears ≥5 times), so each new
   model generation breaks a different subset of features.

## Call-site inventory (from mapping workflow, 2026-08-03)

~40 chat-completion call sites across four architectures:

| Area | Sites | Notes |
|---|---|---|
| `core/video/prompt_engine.py` (`UnifiedLLMProvider`) | 5 | enhance, batch, video-batch, analyze_image, enhance_for_video; GPT-5 hack at :980 |
| `core/video/` others | 8 | `llm_sync.py`, `llm_sync_v2.py` (×3), `scene_suggester.py`, `storyboard_v2.py` (×3), `end_prompt_generator.py` — inline prefix chains, hardcoded temperatures 0.1–0.8 |
| `core/` others | 6 | `styles/analyzer.py` + `applicator.py` (via engine), `lyrics_to_prompts.py`, `prompt_enhancer_llm.py`, `layout/designer.py` (imports gui.llm_utils — inversion), `font_generator/glyph_identifier.py` (google-genai SDK, not LiteLLM) |
| `gui/` dialogs | 17+ | `prompt_generation_dialog.py` (6 sites incl. direct-SDK fallbacks), `prompt_question_dialog.py` (3), `enhanced_prompt_dialog.py`, `layout/text_gen_dialog.py`, `video/start_prompt_dialog.py`, `video/workspace_widget.py` (delegating) |
| `cli/` | 2 | `runner.py` lyrics (only `--lyrics-temperature`, **no range validation**), `commands/layout.py` (no temperature flag) |

Latent bug found during mapping: `core/video/llm_sync.py:546-550` and
`core/video/llm_sync_v2.py:641` read `self.llm_provider.PROVIDER_PREFIXES`,
which **does not exist** on `UnifiedLLMProvider` → AttributeError swallowed by
broad `try/except` → LLM sync silently degrades to estimated timing.

Dead code: `gui/prompt_question_dialog_old.py` (unreferenced, duplicates all
the quirk hacks). Follow-up candidate, not touched in this change.

## Design — `core/llm_params.py`

One core-level module (no gui imports) that owns *populate → validate →
corral → error* for every chat call.

```
@dataclass LLMParams          # what callers want
    temperature, max_tokens, top_p, top_k,
    reasoning_effort, verbosity, response_format, timeout, seed, stop

@dataclass ModelParamRules    # what the model accepts
    temperature: Range | Fixed | Unsupported
    top_p / top_k: Supported | Unsupported
    tokens_param: 'max_tokens' | 'max_completion_tokens'
    max_output_tokens: Optional[int]
    supports_reasoning_effort / verbosity / response_format
    temp_top_p_exclusive: bool     # Claude 4.x: only one of the two

get_param_rules(provider_id, model) -> ModelParamRules
    merge order (highest wins):
      1. curated per-family pattern table (authoritative, in this module)
      2. registry capabilities (core/model-registry.fallback.json:
         max_output_tokens, context_window, mode, supports_*)
      3. litellm.get_model_info() fallback for token limits
    unknown model on a known provider -> provider defaults;
    unknown provider (ollama/lmstudio custom) -> permissive defaults

validate_params(provider_id, model, params, *, strict=False,
                on_warning=None) -> (litellm_kwargs, warnings)
    - out-of-range numeric  -> clamp to nearest bound   (corral, warn)
    - unsupported param     -> drop                     (corral, warn)
    - fixed-value param     -> drop unless equal        (corral, warn)
    - tokens over model max -> clamp to max_output_tokens
    - mutually exclusive    -> keep temperature, drop top_p (warn)
    - nonsense (negative max_tokens, unknown reasoning_effort,
      wrong type)           -> raise LLMParamError (or exit path in CLI)
    - strict=True           -> corralling still applies, but anything that
                               *would* be dropped/clamped raises instead
                               (CLI opt-in via --strict-llm-params later; not
                               wired anywhere by default)
    Every correction is logged (logger.warning) and echoed to the optional
    console callback — per the "log every LLM interaction" project rule.

build_completion_kwargs(provider_id, model, messages, params,
                        api_key=None, api_base=None, auth_mode=None)
    -> dict ready for litellm.completion(**kwargs)
    - prefixes model via get_provider_prefix() (gemini/ vs vertex_ai/ when
      auth_mode='gcloud'; lmstudio -> bare model + api_base)
    - applies validate_params()
```

### Curated rules table (initial; live tests verify)

| Family (regex on model id) | temperature | top_p/top_k | tokens param | notes |
|---|---|---|---|---|
| anthropic: `opus-4-[78]`, `opus-5`, `sonnet-5`, `fable-5`, `mythos` | **unsupported** | unsupported | max_tokens | Claude 5-line removed sampling params |
| anthropic: other `claude-*` (4.6, 4.5, 3.7, haiku-4-5…) | 0.0–1.0 | supported, exclusive with temperature | max_tokens | Anthropic range is 0–1, not 0–2 |
| openai: `gpt-5*`, `o1*`, `o3*`, `o4*`, `chat-latest` | fixed 1.0 (only default) | unsupported | **max_completion_tokens** | reasoning_effort + verbosity supported |
| openai: other (`gpt-4*`, `gpt-3.5*`) | 0.0–2.0 | 0–1 supported | max_tokens | |
| gemini: `gemini-*` | 0.0–2.0 | supported | max_tokens | |
| ollama / lmstudio | 0.0–2.0 (permissive) | supported | max_tokens | local servers ignore extras |

## Rollout order

1. **Plan committed** (this doc).
2. `core/llm_params.py` + unit tests (`tests/test_llm_params.py`).
3. Rewire `core/video/prompt_engine.py` (fixes the style-dialog bug at the
   root — analyzer/applicator/enhancer all route through it).
4. Rewire remaining `core/video/*` (incl. PROVIDER_PREFIXES bug), `core/*`,
   `gui/*` call sites — mechanical: inline kwargs → `build_completion_kwargs`.
   Remove all scattered GPT-5/temperature hacks.
5. CLI: validate `--lyrics-temperature` (and layout LLM path) through
   `validate_params` — corral with printed warning, exit(2) with the valid
   range on un-corralable input.
6. Live API boundary tests (`tests/test_live_llm_params.py`, marker `live`,
   skipped unless `IMAGEAI_LIVE_TESTS=1`). Keys present: anthropic, openai,
   google. Matrix verifies the curated table against reality:
   - claude-sonnet-5: raw temperature → 400 (documents the bug); corralled → 200
   - claude-haiku-4-5: t=1.0 → 200, t=1.5 raw → 400, corralled → 200;
     temperature+top_p together → 400, corralled → 200
   - gpt-5.6-luna: t=0.5 raw → 400, corralled → 200; reasoning_effort ok;
     max_tokens→max_completion_tokens rename verified
   - gpt-4o / gpt-4.1-mini: t=2.0 → 200, t=2.5 raw → 400, corralled → 200
   - gemini flash-lite: t=2.0 → 200, t>2 raw → 400, corralled → 200;
     max_output_tokens clamp verified
   - end-to-end: style-analysis path (analyzer → analyze_image) succeeds on
     claude-opus-5 with corralled params (regression for the trigger bug)
   All calls: tiny prompts, max_tokens ≤ 32, cheapest family member available.
7. Full suite + version bump (minor) + changelog in same commit; PR.

## Non-goals / follow-ups

- Deleting `gui/prompt_question_dialog_old.py` (dead) — separate cleanup.
- Fixing the core→gui import inversion in `core/layout/designer.py` beyond
  what the rewire requires.
- Registry-side capability additions (temperature support flags upstream).
- GUI widgets adapting ranges dynamically per model (only backend corralling
  in this change; a UI pass can consume `get_param_rules` later).
