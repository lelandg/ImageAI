"""Unit tests for core/llm_params.py — rules resolution, corralling, errors."""

import pytest

from core.llm_params import (
    LLMParamError,
    LLMParams,
    build_completion_kwargs,
    get_param_rules,
    infer_provider_from_model,
    normalize_provider,
    strip_route_prefix,
    validate_params,
)


# --- provider/model normalization -------------------------------------------

def test_normalize_provider_aliases():
    assert normalize_provider("Google") == "gemini"
    assert normalize_provider("claude") == "anthropic"
    assert normalize_provider("LM Studio") == "lmstudio"
    assert normalize_provider("OpenAI") == "openai"
    assert normalize_provider("ollama") == "ollama"


def test_strip_route_prefix():
    assert strip_route_prefix("anthropic/claude-opus-5") == "claude-opus-5"
    assert strip_route_prefix("vertex_ai/gemini-2.5-flash") == "gemini-2.5-flash"
    assert strip_route_prefix("gpt-4o") == "gpt-4o"


# --- rules resolution --------------------------------------------------------

def test_claude5_family_rejects_sampling():
    for model in ("claude-opus-5", "claude-sonnet-5", "claude-fable-5",
                  "claude-opus-4-7", "claude-opus-4-8",
                  "anthropic/claude-opus-5"):
        rules = get_param_rules("anthropic", model)
        assert rules.temperature_range is None, model
        assert not rules.top_p_supported, model


def test_older_claude_keeps_temperature_zero_to_one():
    for model in ("claude-opus-4-5-20251101", "claude-sonnet-4-6",
                  "claude-haiku-4-5-20251001", "claude-3-7-sonnet-20250219"):
        rules = get_param_rules("anthropic", model)
        assert rules.temperature_range == (0.0, 1.0), model
        assert rules.temp_top_p_exclusive, model


def test_openai_reasoning_models_fix_temperature():
    for model in ("gpt-5.6-sol", "gpt-5.6-luna", "gpt-5.5-pro", "o4-mini",
                  "o3", "o1-pro", "chat-latest"):
        rules = get_param_rules("openai", model)
        assert rules.temperature_fixed == 1.0, model
        assert rules.tokens_param == "max_completion_tokens", model
        assert rules.supports_reasoning_effort, model


def test_openai_classic_models_allow_temperature():
    rules = get_param_rules("openai", "gpt-4o")
    assert rules.temperature_range == (0.0, 2.0)
    assert rules.tokens_param == "max_tokens"


def test_gemini_rules():
    rules = get_param_rules("Google", "gemini-2.5-flash")
    assert rules.temperature_range == (0.0, 2.0)
    assert rules.top_k_supported


def test_unknown_provider_is_permissive():
    rules = get_param_rules("someprovider", "somemodel")
    assert rules.temperature_range == (0.0, 2.0)


def test_registry_supplies_max_output_tokens():
    rules = get_param_rules("anthropic", "claude-haiku-4-5-20251001")
    assert rules.max_output_tokens == 64000


# --- corralling ---------------------------------------------------------------

def test_temperature_dropped_on_claude5():
    kwargs, warnings = validate_params(
        "anthropic", "claude-opus-5", LLMParams(temperature=0.7, max_tokens=100))
    assert "temperature" not in kwargs
    assert kwargs["max_tokens"] == 100
    assert warnings and "temperature" in warnings[0]


def test_temperature_clamped_on_older_claude():
    kwargs, warnings = validate_params(
        "anthropic", "claude-haiku-4-5-20251001", LLMParams(temperature=1.5))
    assert kwargs["temperature"] == 1.0
    assert warnings


def test_temperature_clamped_on_openai_classic():
    kwargs, _ = validate_params("openai", "gpt-4o", LLMParams(temperature=2.5))
    assert kwargs["temperature"] == 2.0
    kwargs, _ = validate_params("openai", "gpt-4o", LLMParams(temperature=-0.5))
    assert kwargs["temperature"] == 0.0


def test_gpt5_temperature_dropped_unless_default():
    kwargs, warnings = validate_params(
        "openai", "gpt-5.6-luna", LLMParams(temperature=0.5))
    assert "temperature" not in kwargs
    assert warnings
    # the only accepted value is omitted too (provider default applies)
    kwargs, warnings = validate_params(
        "openai", "gpt-5.6-luna", LLMParams(temperature=1.0))
    assert "temperature" not in kwargs
    assert not warnings


def test_tokens_param_renamed_for_reasoning_models():
    kwargs, _ = validate_params(
        "openai", "gpt-5.6-luna", LLMParams(max_tokens=200))
    assert kwargs == {"max_completion_tokens": 200}


def test_max_tokens_capped_at_model_limit():
    kwargs, warnings = validate_params(
        "anthropic", "claude-haiku-4-5-20251001", LLMParams(max_tokens=100_000))
    assert kwargs["max_tokens"] == 64000
    assert warnings


def test_temp_top_p_exclusive_on_older_claude():
    kwargs, warnings = validate_params(
        "anthropic", "claude-sonnet-4-6",
        LLMParams(temperature=0.7, top_p=0.9))
    assert kwargs["temperature"] == 0.7
    assert "top_p" not in kwargs
    assert warnings


def test_reasoning_effort_dropped_where_unsupported():
    kwargs, warnings = validate_params(
        "anthropic", "claude-opus-5", LLMParams(reasoning_effort="low"))
    assert "reasoning_effort" not in kwargs
    assert warnings
    kwargs, _ = validate_params(
        "openai", "gpt-5.6-luna", LLMParams(reasoning_effort="low"))
    assert kwargs["reasoning_effort"] == "low"


def test_dict_params_accepted_and_unknown_keys_ignored():
    kwargs, _ = validate_params(
        "openai", "gpt-4o", {"temperature": 0.3, "not_a_param": 1})
    assert kwargs == {"temperature": 0.3}


def test_on_warning_callback_invoked():
    seen = []
    validate_params("anthropic", "claude-opus-5",
                    LLMParams(temperature=0.7), on_warning=seen.append)
    assert len(seen) == 1


# --- errors -------------------------------------------------------------------

def test_strict_mode_raises_instead_of_corralling():
    with pytest.raises(LLMParamError):
        validate_params("anthropic", "claude-opus-5",
                        LLMParams(temperature=0.7), strict=True)
    with pytest.raises(LLMParamError):
        validate_params("openai", "gpt-4o",
                        LLMParams(temperature=3.0), strict=True)


def test_nonsense_values_raise():
    with pytest.raises(LLMParamError):
        validate_params("openai", "gpt-4o", LLMParams(max_tokens=-5))
    with pytest.raises(LLMParamError):
        validate_params("openai", "gpt-4o", LLMParams(max_tokens=0))
    with pytest.raises(LLMParamError):
        validate_params("openai", "gpt-4o", {"temperature": "hot"})
    with pytest.raises(LLMParamError):
        validate_params("openai", "gpt-5.6-luna",
                        LLMParams(reasoning_effort="ultra"))
    with pytest.raises(LLMParamError):
        validate_params("openai", "gpt-4o", LLMParams(verbosity="loud"))


# --- build_completion_kwargs --------------------------------------------------

_MSGS = [{"role": "user", "content": "hi"}]


def test_build_kwargs_anthropic_prefix():
    kwargs = build_completion_kwargs(
        "anthropic", "claude-opus-5", _MSGS,
        LLMParams(temperature=0.7, max_tokens=64), api_key="k")
    assert kwargs["model"] == "anthropic/claude-opus-5"
    assert kwargs["api_key"] == "k"
    assert "temperature" not in kwargs
    assert kwargs["max_tokens"] == 64


def test_build_kwargs_gemini_auth_modes():
    with_key = build_completion_kwargs("Google", "gemini-2.5-flash", _MSGS,
                                       api_key="k")
    assert with_key["model"] == "gemini/gemini-2.5-flash"
    without_key = build_completion_kwargs("Google", "gemini-2.5-flash", _MSGS)
    assert without_key["model"] == "vertex_ai/gemini-2.5-flash"


def test_build_kwargs_honors_existing_prefix():
    kwargs = build_completion_kwargs(
        "anthropic", "anthropic/claude-sonnet-5", _MSGS)
    assert kwargs["model"] == "anthropic/claude-sonnet-5"


def test_build_kwargs_lmstudio_uses_api_base():
    kwargs = build_completion_kwargs("LM Studio", "local-model", _MSGS)
    assert kwargs["model"] == "local-model"
    assert kwargs["api_base"] == "http://localhost:1234/v1"


def test_build_kwargs_requires_model():
    with pytest.raises(LLMParamError):
        build_completion_kwargs("openai", "", _MSGS)


def test_build_kwargs_lmstudio_slash_model_id():
    # LM Studio ids often contain slashes that are NOT route prefixes;
    # api_base must still be wired (PR #40 review, suggestion 1).
    kwargs = build_completion_kwargs(
        "lmstudio", "lmstudio-community/Meta-Llama-3-8B-GGUF", _MSGS)
    assert kwargs["model"] == "lmstudio-community/Meta-Llama-3-8B-GGUF"
    assert kwargs["api_base"] == "http://localhost:1234/v1"


def test_build_kwargs_gemini_auth_mode_overrides_key_presence():
    # auth_mode wins over api_key presence (PR #40 review, suggestion 2)
    env_key_route = build_completion_kwargs(
        "Google", "gemini-2.5-flash", _MSGS, auth_mode="api-key")
    assert env_key_route["model"] == "gemini/gemini-2.5-flash"
    forced_vertex = build_completion_kwargs(
        "Google", "gemini-2.5-flash", _MSGS, api_key="k", auth_mode="gcloud")
    assert forced_vertex["model"] == "vertex_ai/gemini-2.5-flash"


# --- infer_provider_from_model ------------------------------------------------

def test_infer_provider_from_model():
    assert infer_provider_from_model("anthropic/claude-opus-5") == "anthropic"
    assert infer_provider_from_model("claude-sonnet-5") == "anthropic"
    assert infer_provider_from_model("vertex_ai/gemini-2.5-flash") == "gemini"
    assert infer_provider_from_model("gemini-2.0-flash") == "gemini"
    assert infer_provider_from_model("gpt-4o") == "openai"
    assert infer_provider_from_model("o4-mini") == "openai"
    assert infer_provider_from_model("ollama/llama3.2:latest") == "ollama"
    # bare local model names fall back to the default provider
    assert infer_provider_from_model("local-model") == "openai"
    assert infer_provider_from_model("local-model", default="lmstudio") == "lmstudio"


# --- review follow-ups: seed + unknown keys ----------------------------------

def test_seed_dropped_on_anthropic():
    kwargs, warnings = validate_params(
        "anthropic", "claude-sonnet-5", LLMParams(seed=42, max_tokens=32))
    assert "seed" not in kwargs
    assert warnings
    kwargs, _ = validate_params("openai", "gpt-4o", LLMParams(seed=42))
    assert kwargs["seed"] == 42


def test_unknown_dict_keys_warn_but_do_not_crash(caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="core.llm_params"):
        kwargs, _ = validate_params(
            "openai", "gpt-4o", {"temperature": 0.3, "max_completion_tokens": 99})
    assert kwargs == {"temperature": 0.3}
    assert any("unknown LLM params" in r.message for r in caplog.records)


# --- LiteLLM removal: curated rules + registry are the only ceiling sources ---

def test_no_litellm_reference_in_llm_params():
    from pathlib import Path
    assert "litellm" not in Path("core/llm_params.py").read_text(encoding="utf-8").lower()


def test_every_cloud_model_has_an_output_ceiling():
    from core.llm_models import LLM_PROVIDERS
    from core.llm_params import get_param_rules
    missing = []
    for provider in ("openai", "anthropic", "gemini"):
        for model in LLM_PROVIDERS[provider].models:
            model_id = model if isinstance(model, str) else getattr(model, "id", model)
            if not get_param_rules(provider, model_id).max_output_tokens:
                missing.append(f"{provider}/{model_id}")
    assert missing == []


def test_unknown_local_model_has_no_ceiling():
    from core.llm_params import get_param_rules
    assert get_param_rules("ollama", "some-local-model").max_output_tokens is None
    assert get_param_rules("lmstudio", "some-local-model").max_output_tokens is None


def test_curated_ceiling_caps_max_tokens():
    from core.llm_params import validate_params
    out, warnings = validate_params(
        "anthropic", "claude-opus-4-20250514", {"max_tokens": 10_000_000})
    assert out["max_tokens"] == 32000
    assert warnings


# --- I3: the vertex_ai route never carries api_key ----------------------------

def test_build_kwargs_vertex_route_omits_api_key():
    forced_vertex = build_completion_kwargs(
        "Google", "gemini-test-model", _MSGS, api_key="stored-key",
        auth_mode="gcloud")
    assert forced_vertex["model"] == "vertex_ai/gemini-test-model"
    assert "api_key" not in forced_vertex
    prefixed = build_completion_kwargs(
        "gemini", "vertex_ai/gemini-test-model", _MSGS, api_key="stored-key")
    assert "api_key" not in prefixed
    api_key_route = build_completion_kwargs(
        "Google", "gemini-test-model", _MSGS, api_key="stored-key")
    assert api_key_route["api_key"] == "stored-key"


# --- route_completion_kwargs: display names + Gemini key from the environment -

@pytest.fixture
def _no_gemini_env(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)


@pytest.mark.parametrize("provider,model,expected", [
    ("OpenAI", "gpt-test-model", "gpt-test-model"),
    ("Anthropic", "claude-test-model", "anthropic/claude-test-model"),
    ("claude", "claude-test-model", "anthropic/claude-test-model"),
    ("Ollama", "local-test-model", "ollama/local-test-model"),
    ("LM Studio", "local-test-model", "local-test-model"),
])
def test_route_kwargs_display_names(_no_gemini_env, provider, model, expected):
    from core.llm_params import route_completion_kwargs
    assert route_completion_kwargs(provider, model, _MSGS)["model"] == expected


def test_route_kwargs_google_uses_env_key(_no_gemini_env, monkeypatch):
    from core.llm_params import route_completion_kwargs
    assert route_completion_kwargs(
        "Google", "gemini-test-model", _MSGS)["model"] == "vertex_ai/gemini-test-model"
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    assert route_completion_kwargs(
        "Google", "gemini-test-model", _MSGS)["model"] == "gemini/gemini-test-model"
    assert route_completion_kwargs(
        "Google", "gemini-test-model", _MSGS,
        auth_mode="gcloud")["model"] == "vertex_ai/gemini-test-model"


def test_route_kwargs_google_argument_key(_no_gemini_env):
    from core.llm_params import route_completion_kwargs
    kwargs = route_completion_kwargs("google", "gemini-test-model", _MSGS,
                                     api_key="k")
    assert kwargs["model"] == "gemini/gemini-test-model"
    assert kwargs["api_key"] == "k"


# --- L2: every GPT generation from 5 on, and every o-series number ------------

@pytest.mark.parametrize("model", [
    "gpt-6.2-sol", "gpt-6.1-terra", "gpt-6-luna", "gpt-7-test", "gpt-10-test",
    "o5-test", "gpt-5-test", "o3-test",
])
def test_later_generations_use_reasoning_rules(model):
    kwargs, warnings = validate_params(
        "openai", model, {"temperature": 0.5, "max_tokens": 256})
    assert kwargs == {"max_completion_tokens": 256}
    assert warnings  # the non-default temperature was dropped, with a warning


@pytest.mark.parametrize("model", ["gpt-4.1", "gpt-4o", "gpt-4-turbo",
                                   "gpt-3.5-turbo", "local-test-model"])
def test_classic_models_keep_max_tokens(model):
    kwargs, _ = validate_params("openai", model, {"temperature": 0.5, "max_tokens": 256})
    assert kwargs == {"temperature": 0.5, "max_tokens": 256}


# --- Claude Haiku 5 and every later generation take no sampling params --------

@pytest.mark.parametrize("model", [
    "claude-haiku-5-5", "claude-haiku-5", "claude-sonnet-5-5", "claude-opus-5-5",
    "claude-opus-6-test", "claude-haiku-10-test",
])
def test_claude_5_and_later_drop_sampling_params(model):
    kwargs, warnings = validate_params(
        "anthropic", model, {"temperature": 0.5, "top_p": 0.9, "top_k": 5,
                             "max_tokens": 64})
    assert kwargs == {"max_tokens": 64}
    assert len(warnings) == 3


@pytest.mark.parametrize("model", [
    "claude-haiku-4-5-20251001", "claude-opus-4-20250514", "claude-3-7-sonnet-20250219",
])
def test_claude_4_and_older_keep_temperature(model):
    kwargs, _ = validate_params("anthropic", model, {"temperature": 1.5})
    assert kwargs == {"temperature": 1.0}


@pytest.mark.parametrize("model", [
    "gpt-oss-20b", "gpt-oss:20b", "gpt-oss-120b", "GPT-OSS-20B", "gpt-oss",
    "openai/gpt-oss-20b",  # LM Studio lists it under the publisher name
])
def test_open_weight_gpt_oss_is_not_inferred_as_cloud_openai(model):
    """gpt-oss is an open-weight model served by local servers, never by the
    OpenAI API: the name must fall through to the caller's default."""
    assert infer_provider_from_model(model, default="lmstudio") == "lmstudio"
    assert infer_provider_from_model(model, default="ollama") == "ollama"


@pytest.mark.parametrize("model", [
    "gpt-4o", "gpt-4o-mini", "gpt-5", "gpt-5.5", "gpt-6", "gpt-6-pro",
    "gpt-4.1", "o3", "o4-mini", "chat-latest", "openai/gpt-5.5",
    "gpt-ossified",  # not the gpt-oss family: no separator after "oss"
])
def test_cloud_openai_names_stay_on_openai_whatever_the_default(model):
    assert infer_provider_from_model(model, default="lmstudio") == "openai"


def test_explicit_local_route_prefix_wins_for_gpt_oss():
    assert infer_provider_from_model("ollama/gpt-oss:20b") == "ollama"
    assert infer_provider_from_model("lm_studio/gpt-oss-20b") == "lmstudio"


# --- vertex_project: the saved Google Cloud project reaches Vertex calls ------

_MSGS = [{"role": "user", "content": "hi"}]


def test_vertex_project_sent_on_the_vertex_route():
    kwargs = build_completion_kwargs(
        "gemini", "gemini-test-model", _MSGS, auth_mode="gcloud",
        vertex_project="saved-project")
    assert kwargs["model"] == "vertex_ai/gemini-test-model"
    assert kwargs["vertex_project"] == "saved-project"


def test_vertex_project_sent_when_the_caller_prefixed_the_route():
    kwargs = build_completion_kwargs(
        "gemini", "vertex_ai/gemini-test-model", _MSGS,
        vertex_project="saved-project")
    assert kwargs["vertex_project"] == "saved-project"


@pytest.mark.parametrize("provider,model,extra", [
    ("gemini", "gemini-test-model", {"auth_mode": "api-key", "api_key": "k"}),
    ("openai", "gpt-test-model", {"api_key": "k"}),
    ("anthropic", "claude-test-model", {"api_key": "k"}),
    ("ollama", "llama-test", {}),
    ("lmstudio", "local-test", {"api_base": "http://localhost:1234/v1"}),
])
def test_vertex_project_never_sent_off_the_vertex_route(provider, model, extra):
    """Only the vertex_ai route uses it; elsewhere the adapter would drop it
    with a warning (gemini/) or the dispatcher would (other adapters)."""
    kwargs = build_completion_kwargs(
        provider, model, _MSGS, vertex_project="saved-project", **extra)
    assert "vertex_project" not in kwargs


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_empty_vertex_project_is_not_sent(empty):
    kwargs = build_completion_kwargs(
        "gemini", "gemini-test-model", _MSGS, auth_mode="gcloud",
        vertex_project=empty)
    assert "vertex_project" not in kwargs


def test_route_completion_kwargs_passes_vertex_project(monkeypatch):
    from core.llm_params import route_completion_kwargs
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    kwargs = route_completion_kwargs(
        "Google", "gemini-test-model", _MSGS, vertex_project="saved-project")
    assert kwargs["model"] == "vertex_ai/gemini-test-model"
    assert kwargs["vertex_project"] == "saved-project"


def test_saved_vertex_project_reads_config_objects_and_dicts():
    from unittest.mock import MagicMock
    from core.llm_params import saved_vertex_project

    class _Config:
        def __init__(self, value):
            self._value = value

        def get(self, key, default=None):
            return self._value if key == "gcloud_project_id" else default

    assert saved_vertex_project(_Config("my-project")) == "my-project"
    assert saved_vertex_project({"gcloud_project_id": " my-project "}) == "my-project"
    assert saved_vertex_project(_Config("")) is None
    assert saved_vertex_project(_Config(None)) is None
    assert saved_vertex_project({}) is None
    assert saved_vertex_project(None) is None
    # A mock config answers every lookup with another mock: not a project id.
    assert saved_vertex_project(MagicMock()) is None


# --- a key never follows a route prefix to another provider -------------------

@pytest.mark.parametrize("provider,model", [
    ("gemini", "ollama/gemma-test"),          # Google selected, local model id
    ("gemini", "ollama_chat/gemma-test"),
    ("gemini", "lm_studio/gemma-test"),
    ("openai", "ollama/gpt-oss:20b"),
    ("anthropic", "lm_studio/claude-style-local"),
    ("openai", "anthropic/claude-test-model"),  # cloud X key -> cloud Y
    ("anthropic", "openai/gpt-test-model"),
    ("openai", "gemini/gemini-test-model"),
    ("anthropic", "gemini/gemini-test-model"),
    ("gemini", "openai/gpt-test-model"),
    ("ollama", "openai/gpt-test-model"),
])
def test_key_is_dropped_when_the_route_prefix_names_another_provider(
        provider, model, caplog):
    import logging
    seen = []
    with caplog.at_level(logging.WARNING, logger="core.llm_params"):
        kwargs = build_completion_kwargs(
            provider, model, _MSGS, api_key="provider-secret-key",
            auth_mode="api-key" if provider == "gemini" else None,
            on_warning=seen.append)
    assert kwargs["model"] == model          # the prefix is still honoured
    assert "api_key" not in kwargs
    assert len(seen) == 1 and model.split("/")[0] in seen[0]
    assert "provider-secret-key" not in caplog.text
    assert "provider-secret-key" not in seen[0]
    assert any(r.levelno == logging.WARNING for r in caplog.records)


@pytest.mark.parametrize("provider,model", [
    ("openai", "openai/gpt-test-model"),
    ("openai", "gpt-test-model"),
    ("anthropic", "anthropic/claude-test-model"),
    ("gemini", "gemini/gemini-test-model"),
    ("ollama", "ollama/llama-test"),          # a local provider's own token
    ("ollama", "ollama_chat/llama-test"),
    ("lmstudio", "local-test-model"),
    ("lmstudio", "lm_studio/local-test-model"),
    ("lmstudio", "lmstudio-community/Some-Model-GGUF"),
    ("lmstudio", "openai/gpt-oss-20b"),       # publisher name, LM Studio endpoint
])
def test_key_passes_when_the_route_belongs_to_the_provider(provider, model):
    seen = []
    kwargs = build_completion_kwargs(
        provider, model, _MSGS, api_key="own-key",
        auth_mode="api-key" if provider == "gemini" else None,
        on_warning=seen.append)
    assert kwargs["api_key"] == "own-key"
    assert seen == []


def test_foreign_route_without_a_key_logs_nothing(caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="core.llm_params"):
        kwargs = build_completion_kwargs("gemini", "ollama/gemma-test", _MSGS)
    assert "api_key" not in kwargs
    assert not caplog.records


def test_foreign_route_with_a_key_raises_in_strict_mode():
    with pytest.raises(LLMParamError, match="ollama"):
        build_completion_kwargs("gemini", "ollama/gemma-test", _MSGS,
                                api_key="k", strict=True)


# --- an explicit Google auth mode decides the route, whatever the prefix ------

@pytest.mark.parametrize("auth_mode", ["gcloud", "adc", "Google Cloud Account"])
@pytest.mark.parametrize("model", ["gemini/gemini-test-model",
                                   "vertex_ai/gemini-test-model",
                                   "gemini-test-model"])
def test_gcloud_mode_always_takes_vertex_and_never_sends_a_key(auth_mode, model):
    seen = []
    kwargs = build_completion_kwargs(
        "gemini", model, _MSGS, api_key="oauth-access-token",
        auth_mode=auth_mode, vertex_project="saved-project",
        on_warning=seen.append)
    assert kwargs["model"] == "vertex_ai/gemini-test-model"
    assert "api_key" not in kwargs
    assert kwargs["vertex_project"] == "saved-project"
    # only a re-routed prefix is worth a message
    assert len(seen) == (1 if model.startswith("gemini/") else 0)
    assert all("oauth-access-token" not in message for message in seen)


@pytest.mark.parametrize("auth_mode", ["api-key", "api_key", "API Key"])
@pytest.mark.parametrize("model", ["gemini/gemini-test-model",
                                   "vertex_ai/gemini-test-model",
                                   "gemini-test-model"])
def test_api_key_mode_always_takes_the_gemini_route(auth_mode, model):
    seen = []
    kwargs = build_completion_kwargs(
        "gemini", model, _MSGS, api_key="stored-key", auth_mode=auth_mode,
        vertex_project="saved-project", on_warning=seen.append)
    assert kwargs["model"] == "gemini/gemini-test-model"
    assert kwargs["api_key"] == "stored-key"
    assert "vertex_project" not in kwargs
    assert len(seen) == (1 if model.startswith("vertex_ai/") else 0)


def test_google_prefix_is_honoured_when_no_auth_mode_is_given():
    kwargs = build_completion_kwargs("gemini", "gemini/gemini-test-model", _MSGS,
                                     api_key="k")
    assert kwargs["model"] == "gemini/gemini-test-model" and kwargs["api_key"] == "k"
    kwargs = build_completion_kwargs("gemini", "vertex_ai/gemini-test-model", _MSGS,
                                     api_key="k")
    assert kwargs["model"] == "vertex_ai/gemini-test-model"
    assert "api_key" not in kwargs


def test_auth_mode_reroute_raises_in_strict_mode():
    with pytest.raises(LLMParamError, match="vertex_ai"):
        build_completion_kwargs("gemini", "gemini/gemini-test-model", _MSGS,
                                auth_mode="gcloud", strict=True)


@pytest.mark.parametrize("provider,model", [
    ("openai", "gpt-test-model"), ("anthropic", "anthropic/claude-test-model"),
    ("ollama", "ollama/llama-test"),
])
def test_google_auth_mode_does_not_touch_other_providers(provider, model):
    kwargs = build_completion_kwargs(provider, model, _MSGS, api_key="own-key",
                                     auth_mode="gcloud")
    assert kwargs["api_key"] == "own-key"
    assert not kwargs["model"].startswith("vertex_ai/")


def test_gcloud_mode_does_not_reroute_a_foreign_local_prefix():
    kwargs = build_completion_kwargs("gemini", "ollama/gemma-test", _MSGS,
                                     api_key="oauth-access-token", auth_mode="gcloud")
    assert kwargs["model"] == "ollama/gemma-test"
    assert "api_key" not in kwargs
