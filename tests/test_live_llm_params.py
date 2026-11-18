"""Live (paid) cloud tests for core/llm_params.py and core/chameleon_llm.

These hit real provider APIs and cost a few cents. They are skipped unless
``IMAGEAI_LIVE_TESTS=1`` is set, and each provider's tests skip when its API
key is not configured. Keys are read through the app's config
(``ConfigManager.get_api_key``), never from the test command.

Purpose: empirically verify the curated capability rules against provider
documentation:
  - Anthropic Claude 5-line rejects ``temperature`` (the style-dialog bug),
  - older Claude accepts temperature only in [0, 1] and rejects
    temperature+top_p together,
  - OpenAI reasoning models (gpt-5.x) reject non-default temperature and
    require ``max_completion_tokens``,
  - classic OpenAI models accept temperature up to 2.0 and reject beyond,
  - Gemini accepts temperature up to 2.0 and rejects beyond,
and that the corralled request succeeds in every case where the raw one 400s.
``TestRoutes`` also runs one text, one JSON-mode and one image call per cloud
route.

Model ids come from ``resolve_model`` (the model registry) or are picked from
the curated list in ``core.llm_models`` by behaviour; none is written out here.

Run:  IMAGEAI_LIVE_TESTS=1 python -m pytest tests/test_live_llm_params.py -m live -v
"""

import base64
import io
import os

import pytest

from core import chameleon_llm
from core.llm_models import LLM_PROVIDERS, resolve_model
from core.llm_params import (LLMParams, build_completion_kwargs, get_param_rules,
                             validate_params)
from core.llm_parsing import LLMResponseParser

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("IMAGEAI_LIVE_TESTS") != "1",
        reason="live API tests disabled (set IMAGEAI_LIVE_TESTS=1)"),
]

_MSGS = [{"role": "user", "content": "Reply with the single word: ok"}]
_TIMEOUT = 90


@pytest.fixture(scope="module")
def keys():
    from core.config import ConfigManager
    config = ConfigManager()
    return {
        "anthropic": config.get_api_key("anthropic"),
        "openai": config.get_api_key("openai"),
        "google": config.get_api_key("google"),
    }


def _need(keys, provider):
    if not keys.get(provider):
        pytest.skip(f"no {provider} API key configured")
    return keys[provider]


def _raw_call(**kwargs):
    return chameleon_llm.completion(timeout=_TIMEOUT, **kwargs)


def _corralled_call(provider, model, params, api_key):
    kwargs = build_completion_kwargs(provider, model, _MSGS, params,
                                     api_key=api_key)
    kwargs.setdefault("timeout", _TIMEOUT)
    return chameleon_llm.completion(**kwargs)


def _content(response):
    return response.choices[0].message.content


def _curated(provider, wanted):
    """First curated model of ``provider`` for which ``wanted(model_id)`` holds."""
    for model_id in LLM_PROVIDERS[provider].models:
        if wanted(model_id):
            return model_id
    pytest.skip(f"no curated {provider} model fits this test")


_NO_OLDER_CLAUDE = "no current Claude model accepts sampling parameters"


def _older_claude_candidates():
    """Claude ids whose rules take a temperature in [0, 1] (1.5 clamps to 1.0).

    Derived from the rules, never written out: the resolved ``haiku`` first
    when it qualifies, then the curated list. Claude 5 and later take no
    sampling parameters, so they never qualify.
    """
    def wanted(model_id):
        rules = get_param_rules("anthropic", model_id)
        return (rules.temperature_range is not None
                and rules.temperature_fixed is None
                and rules.temperature_range[1] == 1.0)
    candidates = []
    current = resolve_model("anthropic", "haiku")
    if current and wanted(current):
        candidates.append(current)
    candidates += [m for m in LLM_PROVIDERS["anthropic"].models
                   if wanted(m) and m not in candidates]
    return candidates


def _is_model_not_found(exc):
    text = str(exc)
    return "not_found" in text or "model:" in text


def _pick_available(candidates, probe):
    """First candidate ``probe`` accepts. A retired model ("model not found")
    is passed over; when none is left the caller's class is skipped."""
    for model in candidates:
        try:
            probe(model)
        except chameleon_llm.BadRequestError as exc:
            if _is_model_not_found(exc):
                continue
            raise
        return model
    pytest.skip(_NO_OLDER_CLAUDE)


@pytest.fixture(scope="class")
def older_claude(keys):
    """A current Claude that takes sampling parameters, probed once per class
    with a sampling-free call (the curated list holds retired dated ids)."""
    api_key = _need(keys, "anthropic")
    return _pick_available(
        _older_claude_candidates(),
        lambda model: _raw_call(model=f"anthropic/{model}", messages=_MSGS,
                                max_tokens=8, api_key=api_key))


def _sdk_sends(*names):
    """Skip unless the installed anthropic SDK sends every named sampling
    parameter. With anthropic SDK 2.x the adapter drops them before the
    request, so there is nothing for the API to reject."""
    from core.chameleon_llm.anthropic_adapter import sdk_accepts
    if not all(sdk_accepts(n) for n in names):
        pytest.skip("installed anthropic SDK drops sampling parameters before "
                    "the request")


def _classic_openai():
    """An OpenAI model that keeps ``temperature`` (not a reasoning model)."""
    def wanted(model_id):
        params, _ = validate_params("openai", model_id, {"temperature": 0.5})
        return params.get("temperature") == 0.5
    return _curated("openai", wanted)


# --- Anthropic: Claude 5-line rejects sampling params ------------------------

class TestAnthropicClaude5:
    # The "raw" tests pass sampling params straight to completion(). With
    # anthropic SDK 0.x they reach the API, whose 400 these tests assert. With
    # SDK 2.x the Messages API accepts no sampling parameter for any model and
    # the adapter drops them before the request, so those tests skip.
    @staticmethod
    def model():
        return resolve_model("anthropic", "sonnet")

    def test_raw_temperature_rejected(self, keys):
        """Documents the bug from imageai_current.log: temperature -> 400."""
        _sdk_sends("temperature")
        api_key = _need(keys, "anthropic")
        with pytest.raises(chameleon_llm.BadRequestError, match="temperature"):
            _raw_call(model=f"anthropic/{self.model()}", messages=_MSGS,
                      temperature=0.7, max_tokens=32, api_key=api_key)

    def test_raw_top_p_rejected(self, keys):
        _sdk_sends("top_p")
        api_key = _need(keys, "anthropic")
        with pytest.raises(chameleon_llm.BadRequestError, match="top_p"):
            _raw_call(model=f"anthropic/{self.model()}", messages=_MSGS,
                      top_p=0.9, max_tokens=32, api_key=api_key)

    def test_corralled_succeeds(self, keys):
        api_key = _need(keys, "anthropic")
        response = _corralled_call(
            "anthropic", self.model(),
            LLMParams(temperature=0.7, max_tokens=32), api_key)
        assert _content(response)


# --- Anthropic: older Claude, temperature range 0..1 -------------------------

class TestAnthropicOlder:
    # The success tests run under both SDK generations: with SDK 2.x the
    # sampling parameters are dropped and the call must still succeed. Only
    # the "rejected_raw" tests need an SDK that sends them.
    def test_temperature_upper_bound_ok(self, keys, older_claude):
        api_key = _need(keys, "anthropic")
        response = _raw_call(model=f"anthropic/{older_claude}", messages=_MSGS,
                             temperature=1.0, max_tokens=32, api_key=api_key)
        assert _content(response)

    def test_temperature_above_one_rejected_raw(self, keys, older_claude):
        _sdk_sends("temperature")
        api_key = _need(keys, "anthropic")
        with pytest.raises(chameleon_llm.BadRequestError, match="temperature"):
            _raw_call(model=f"anthropic/{older_claude}", messages=_MSGS,
                      temperature=1.5, max_tokens=32, api_key=api_key)

    def test_temperature_above_one_corralled(self, keys, older_claude):
        api_key = _need(keys, "anthropic")
        model = older_claude
        params, warnings = validate_params(
            "anthropic", model, {"temperature": 1.5, "max_tokens": 32})
        assert params["temperature"] == 1.0 and warnings
        response = _corralled_call(
            "anthropic", model, LLMParams(temperature=1.5, max_tokens=32), api_key)
        assert _content(response)

    def test_temp_and_top_p_together_rejected_raw(self, keys, older_claude):
        _sdk_sends("temperature", "top_p")
        api_key = _need(keys, "anthropic")
        with pytest.raises(chameleon_llm.BadRequestError):
            _raw_call(model=f"anthropic/{older_claude}", messages=_MSGS,
                      temperature=0.5, top_p=0.9, max_tokens=32, api_key=api_key)

    def test_temp_and_top_p_corralled(self, keys, older_claude):
        api_key = _need(keys, "anthropic")
        response = _corralled_call(
            "anthropic", older_claude,
            LLMParams(temperature=0.5, top_p=0.9, max_tokens=32), api_key)
        assert _content(response)

    def test_max_tokens_over_limit_corralled(self, keys, older_claude):
        """The ceiling comes from the rules; a 100k request must be capped to it."""
        api_key = _need(keys, "anthropic")
        model = older_claude
        params, warnings = validate_params(
            "anthropic", model, {"max_tokens": 100_000})
        ceiling = get_param_rules("anthropic", model).max_output_tokens
        if ceiling is None:
            pytest.skip(f"no output-token ceiling known for {model}")
        assert params["max_tokens"] == ceiling and warnings
        response = _corralled_call(
            "anthropic", model,
            LLMParams(temperature=0.0, max_tokens=100_000), api_key)
        assert _content(response)


# --- OpenAI: reasoning models (gpt-5.x) --------------------------------------

class TestOpenAIReasoning:
    # The cheapest current flagship (GPT-6 at the time of writing). That GPT-6
    # rejects a non-default temperature like gpt-5 is assumed by the rules in
    # core/llm_params.py; test_raw_nondefault_temperature_rejected proves it.
    @staticmethod
    def model():
        return resolve_model("openai", "gpt-nano")  # cheapest of the family

    def test_raw_nondefault_temperature_rejected(self, keys):
        api_key = _need(keys, "openai")
        with pytest.raises(chameleon_llm.BadRequestError, match="temperature"):
            _raw_call(model=self.model(), messages=_MSGS, temperature=0.5,
                      max_completion_tokens=32, api_key=api_key)

    def test_corralled_succeeds_with_renamed_tokens(self, keys):
        api_key = _need(keys, "openai")
        params, warnings = validate_params(
            "openai", self.model(),
            {"temperature": 0.5, "max_tokens": 256, "reasoning_effort": "low"})
        assert "temperature" not in params
        assert params["max_completion_tokens"] == 256
        assert params["reasoning_effort"] == "low"
        assert warnings
        response = _corralled_call(
            "openai", self.model(),
            LLMParams(temperature=0.5, max_tokens=256, reasoning_effort="low"),
            api_key)
        assert response.choices  # reasoning may consume tokens; call must succeed


class TestOpenAIClassic:
    def test_temperature_upper_bound_ok(self, keys):
        api_key = _need(keys, "openai")
        response = _raw_call(model=_classic_openai(), messages=_MSGS,
                             temperature=2.0, max_tokens=32, api_key=api_key)
        assert response.choices

    def test_temperature_above_two_rejected_raw(self, keys):
        api_key = _need(keys, "openai")
        with pytest.raises(chameleon_llm.BadRequestError, match="temperature"):
            _raw_call(model=_classic_openai(), messages=_MSGS,
                      temperature=2.5, max_tokens=32, api_key=api_key)

    def test_temperature_above_two_corralled(self, keys):
        api_key = _need(keys, "openai")
        response = _corralled_call(
            "openai", _classic_openai(),
            LLMParams(temperature=2.5, max_tokens=32), api_key)
        assert response.choices


# --- Gemini ------------------------------------------------------------------

class TestGemini:
    @staticmethod
    def model():
        return resolve_model("gemini", "flash-lite")

    def test_temperature_upper_bound_ok(self, keys):
        api_key = _need(keys, "google")
        response = _raw_call(model=f"gemini/{self.model()}", messages=_MSGS,
                             temperature=2.0, max_tokens=32, api_key=api_key)
        assert response.choices

    def test_temperature_above_two_rejected_raw(self, keys):
        api_key = _need(keys, "google")
        with pytest.raises(chameleon_llm.BadRequestError):
            _raw_call(model=f"gemini/{self.model()}", messages=_MSGS,
                      temperature=2.5, max_tokens=32, api_key=api_key)

    def test_temperature_above_two_corralled(self, keys):
        api_key = _need(keys, "google")
        response = _corralled_call(
            "gemini", self.model(),
            LLMParams(temperature=2.5, max_tokens=32), api_key)
        assert response.choices


# --- One text / JSON-mode / image call per cloud route -----------------------

def _adc_project():
    """Google Cloud application-default credentials, without a network call.

    Returns (available, project). ``google.auth.default()`` only reads local
    files and environment; it does not contact Google.
    """
    try:
        import google.auth
        _, project = google.auth.default()
        return True, project
    except Exception:
        return False, None


# Same image as the red_png_data_url fixture in tests/local/conftest.py (no shared helper module).
def _red_png_data_url():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (255, 0, 0)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# Generous token budgets: reasoning models spend tokens thinking before they
# answer, and an empty reply would fail a test for the wrong reason.
_ROUTE_MAX_TOKENS = 1024

# (id, builder provider, key provider or None, model resolver, auth mode).
# Every route builds its request with build_completion_kwargs exactly as the
# application does (route prefix, max_tokens vs max_completion_tokens, dropped
# sampling params), so these tests exercise the real path.
_ROUTES = [
    pytest.param("openai_chat", "openai", "openai",
                 lambda: resolve_model("openai", "gpt-mini"), None,
                 id="openai-chat"),
    # Whether this model is Responses-only is unconfirmed by documentation;
    # this live test is the proof (the adapter routes by model-id pattern).
    pytest.param("openai_responses", "openai", "openai",
                 lambda: resolve_model("openai", "gpt-pro"), None,
                 id="openai-responses"),
    pytest.param("anthropic", "anthropic", "anthropic",
                 lambda: resolve_model("anthropic", "haiku"), None,
                 id="anthropic"),
    pytest.param("gemini", "gemini", "google",
                 lambda: resolve_model("gemini", "flash-lite"), "api-key",
                 id="gemini-api-key"),
    # Vertex: Google Cloud login, no key; the adapter's default location
    # ("global") serves the current models, so none is passed.
    pytest.param("vertex", "gemini", None,
                 lambda: resolve_model("gemini", "flash-lite"), "gcloud",
                 id="vertex"),
]


def _route_request(keys, provider, key_provider, resolver, auth_mode, messages,
                   params):
    api_key = None
    extra = {}
    if key_provider is None:
        available, project = _adc_project()
        if not available:
            pytest.skip("no Google Cloud application-default credentials "
                        "(run: gcloud auth application-default login)")
        if project:
            extra["vertex_project"] = project
    else:
        api_key = _need(keys, key_provider)
    kwargs = build_completion_kwargs(provider, resolver(), messages, params,
                                     api_key=api_key, auth_mode=auth_mode)
    kwargs.update(extra)
    kwargs.setdefault("timeout", _TIMEOUT)
    return kwargs


@pytest.mark.parametrize("name,provider,key_provider,resolver,auth_mode", _ROUTES)
class TestRoutes:
    def test_text(self, keys, name, provider, key_provider, resolver, auth_mode):
        kwargs = _route_request(keys, provider, key_provider, resolver, auth_mode,
                                _MSGS, {"max_tokens": _ROUTE_MAX_TOKENS})
        response = chameleon_llm.completion(**kwargs)
        assert _content(response).strip()

    def test_json_mode(self, keys, name, provider, key_provider, resolver, auth_mode):
        kwargs = _route_request(
            keys, provider, key_provider, resolver, auth_mode,
            [{"role": "user",
              "content": 'Reply with only this JSON object: {"ok": true}'}],
            {"max_tokens": _ROUTE_MAX_TOKENS,
             "response_format": {"type": "json_object"}})
        response = chameleon_llm.completion(**kwargs)
        parsed = LLMResponseParser.parse_json_response(_content(response), dict)
        assert isinstance(parsed, dict), _content(response)

    def test_image(self, keys, name, provider, key_provider, resolver, auth_mode):
        kwargs = _route_request(
            keys, provider, key_provider, resolver, auth_mode,
            [{"role": "user", "content": [
                {"type": "text", "text": "What colour is this image? One word."},
                {"type": "image_url", "image_url": {"url": _red_png_data_url()}}]}],
            {"max_tokens": _ROUTE_MAX_TOKENS})
        response = chameleon_llm.completion(**kwargs)
        assert _content(response).strip()


# --- End-to-end regression: the style-analysis path --------------------------

class TestStyleAnalyzerRegression:
    """Replicates the exact failing path from imageai_current.log:
    core/styles/analyzer.py -> UnifiedLLMProvider.analyze_image with a
    Claude 5-line model and temperature=0.7 (previously a 400)."""

    @pytest.mark.parametrize("family", ["opus", "sonnet"])
    def test_analyze_image_claude5(self, keys, family):
        api_key = _need(keys, "anthropic")
        model = f"anthropic/{resolve_model('anthropic', family)}"
        from core.video.prompt_engine import UnifiedLLMProvider
        provider = UnifiedLLMProvider({"anthropic_api_key": api_key})
        result = provider.analyze_image(
            messages=[{"role": "user",
                       "content": "Answer with one word: what color is grass?"}],
            model=model,
            temperature=0.7,   # would have 400'd before the param layer
            max_tokens=64,
            max_retries=0,
        )
        assert isinstance(result, str) and result.strip()
