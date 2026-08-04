"""Live API boundary tests for core/llm_params.py.

These hit real provider APIs and cost (a little) money. They are skipped
unless ``IMAGEAI_LIVE_TESTS=1`` is set, and each provider's tests skip when
its API key is not configured.

Purpose: empirically verify the curated capability rules against provider
documentation —
  - Anthropic Claude 5-line rejects ``temperature`` (the style-dialog bug),
  - older Claude accepts temperature only in [0, 1] and rejects
    temperature+top_p together,
  - OpenAI reasoning models (gpt-5.x) reject non-default temperature and
    require ``max_completion_tokens``,
  - classic OpenAI models accept temperature up to 2.0 and reject beyond,
  - Gemini accepts temperature up to 2.0 and rejects beyond,
and that the corralled request succeeds in every case where the raw one 400s.

Run:  IMAGEAI_LIVE_TESTS=1 python3 -m pytest tests/test_live_llm_params.py -m live -v
"""

import os

import pytest

from core.llm_params import LLMParams, build_completion_kwargs, validate_params

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("IMAGEAI_LIVE_TESTS") != "1",
        reason="live API tests disabled (set IMAGEAI_LIVE_TESTS=1)"),
]

_MSGS = [{"role": "user", "content": "Reply with the single word: ok"}]
_TIMEOUT = 90


@pytest.fixture(scope="module")
def litellm_mod():
    litellm = pytest.importorskip("litellm")
    saved = litellm.drop_params
    litellm.drop_params = False  # raw tests must NOT be silently rescued
    yield litellm
    litellm.drop_params = saved


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


def _raw_call(litellm_mod, **kwargs):
    return litellm_mod.completion(timeout=_TIMEOUT, **kwargs)


def _corralled_call(litellm_mod, provider, model, params, api_key):
    kwargs = build_completion_kwargs(provider, model, _MSGS, params,
                                     api_key=api_key)
    kwargs.setdefault("timeout", _TIMEOUT)
    return litellm_mod.completion(**kwargs)


# --- Anthropic: Claude 5-line rejects sampling params ------------------------

class TestAnthropicClaude5:
    MODEL = "claude-sonnet-5"

    def test_raw_temperature_rejected(self, litellm_mod, keys):
        """Documents the bug from imageai_current.log: temperature -> 400."""
        api_key = _need(keys, "anthropic")
        with pytest.raises(litellm_mod.BadRequestError, match="temperature"):
            _raw_call(litellm_mod, model=f"anthropic/{self.MODEL}",
                      messages=_MSGS, temperature=0.7, max_tokens=32,
                      api_key=api_key)

    def test_raw_top_p_rejected(self, litellm_mod, keys):
        api_key = _need(keys, "anthropic")
        with pytest.raises(litellm_mod.BadRequestError, match="top_p"):
            _raw_call(litellm_mod, model=f"anthropic/{self.MODEL}",
                      messages=_MSGS, top_p=0.9, max_tokens=32,
                      api_key=api_key)

    def test_corralled_succeeds(self, litellm_mod, keys):
        api_key = _need(keys, "anthropic")
        response = _corralled_call(
            litellm_mod, "anthropic", self.MODEL,
            LLMParams(temperature=0.7, max_tokens=32), api_key)
        assert response.choices[0].message.content


# --- Anthropic: older Claude, temperature range 0..1 -------------------------

class TestAnthropicHaiku:
    MODEL = "claude-haiku-4-5-20251001"

    def test_temperature_upper_bound_ok(self, litellm_mod, keys):
        api_key = _need(keys, "anthropic")
        response = _raw_call(litellm_mod, model=f"anthropic/{self.MODEL}",
                             messages=_MSGS, temperature=1.0, max_tokens=32,
                             api_key=api_key)
        assert response.choices[0].message.content

    def test_temperature_above_one_rejected_raw(self, litellm_mod, keys):
        api_key = _need(keys, "anthropic")
        with pytest.raises(litellm_mod.BadRequestError, match="temperature"):
            _raw_call(litellm_mod, model=f"anthropic/{self.MODEL}",
                      messages=_MSGS, temperature=1.5, max_tokens=32,
                      api_key=api_key)

    def test_temperature_above_one_corralled(self, litellm_mod, keys):
        api_key = _need(keys, "anthropic")
        params, warnings = validate_params(
            "anthropic", self.MODEL, {"temperature": 1.5, "max_tokens": 32})
        assert params["temperature"] == 1.0 and warnings
        response = _corralled_call(
            litellm_mod, "anthropic", self.MODEL,
            LLMParams(temperature=1.5, max_tokens=32), api_key)
        assert response.choices[0].message.content

    def test_temp_and_top_p_together_rejected_raw(self, litellm_mod, keys):
        api_key = _need(keys, "anthropic")
        with pytest.raises(litellm_mod.BadRequestError):
            _raw_call(litellm_mod, model=f"anthropic/{self.MODEL}",
                      messages=_MSGS, temperature=0.5, top_p=0.9,
                      max_tokens=32, api_key=api_key)

    def test_temp_and_top_p_corralled(self, litellm_mod, keys):
        api_key = _need(keys, "anthropic")
        response = _corralled_call(
            litellm_mod, "anthropic", self.MODEL,
            LLMParams(temperature=0.5, top_p=0.9, max_tokens=32), api_key)
        assert response.choices[0].message.content

    def test_max_tokens_over_limit_corralled(self, litellm_mod, keys):
        """Registry says 64000 output max; 100k request must be capped."""
        api_key = _need(keys, "anthropic")
        params, warnings = validate_params(
            "anthropic", self.MODEL, {"max_tokens": 100_000})
        assert params["max_tokens"] == 64000 and warnings
        response = _corralled_call(
            litellm_mod, "anthropic", self.MODEL,
            LLMParams(temperature=0.0, max_tokens=100_000), api_key)
        assert response.choices[0].message.content


# --- OpenAI: reasoning models (gpt-5.x) --------------------------------------

class TestOpenAIReasoning:
    MODEL = "gpt-5.6-luna"  # nano tier — cheapest of the family

    def test_raw_nondefault_temperature_rejected(self, litellm_mod, keys):
        api_key = _need(keys, "openai")
        with pytest.raises(litellm_mod.BadRequestError, match="temperature"):
            _raw_call(litellm_mod, model=self.MODEL, messages=_MSGS,
                      temperature=0.5, max_completion_tokens=32,
                      api_key=api_key)

    def test_corralled_succeeds_with_renamed_tokens(self, litellm_mod, keys):
        api_key = _need(keys, "openai")
        params, warnings = validate_params(
            "openai", self.MODEL,
            {"temperature": 0.5, "max_tokens": 256, "reasoning_effort": "low"})
        assert "temperature" not in params
        assert params["max_completion_tokens"] == 256
        assert params["reasoning_effort"] == "low"
        assert warnings
        response = _corralled_call(
            litellm_mod, "openai", self.MODEL,
            LLMParams(temperature=0.5, max_tokens=256, reasoning_effort="low"),
            api_key)
        assert response.choices  # reasoning may consume tokens; call must succeed


class TestOpenAIClassic:
    MODEL = "gpt-4o-mini"

    def test_temperature_upper_bound_ok(self, litellm_mod, keys):
        api_key = _need(keys, "openai")
        response = _raw_call(litellm_mod, model=self.MODEL, messages=_MSGS,
                             temperature=2.0, max_tokens=32, api_key=api_key)
        assert response.choices

    def test_temperature_above_two_rejected_raw(self, litellm_mod, keys):
        api_key = _need(keys, "openai")
        with pytest.raises(litellm_mod.BadRequestError, match="temperature"):
            _raw_call(litellm_mod, model=self.MODEL, messages=_MSGS,
                      temperature=2.5, max_tokens=32, api_key=api_key)

    def test_temperature_above_two_corralled(self, litellm_mod, keys):
        api_key = _need(keys, "openai")
        response = _corralled_call(
            litellm_mod, "openai", self.MODEL,
            LLMParams(temperature=2.5, max_tokens=32), api_key)
        assert response.choices


# --- Gemini ------------------------------------------------------------------

class TestGemini:
    MODEL = "gemini-2.5-flash-lite"

    def test_temperature_upper_bound_ok(self, litellm_mod, keys):
        api_key = _need(keys, "google")
        response = _raw_call(litellm_mod, model=f"gemini/{self.MODEL}",
                             messages=_MSGS, temperature=2.0, max_tokens=32,
                             api_key=api_key)
        assert response.choices

    def test_temperature_above_two_rejected_raw(self, litellm_mod, keys):
        api_key = _need(keys, "google")
        with pytest.raises(litellm_mod.BadRequestError):
            _raw_call(litellm_mod, model=f"gemini/{self.MODEL}",
                      messages=_MSGS, temperature=2.5, max_tokens=32,
                      api_key=api_key)

    def test_temperature_above_two_corralled(self, litellm_mod, keys):
        api_key = _need(keys, "google")
        response = _corralled_call(
            litellm_mod, "gemini", self.MODEL,
            LLMParams(temperature=2.5, max_tokens=32), api_key)
        assert response.choices


# --- End-to-end regression: the style-analysis path --------------------------

class TestStyleAnalyzerRegression:
    """Replicates the exact failing path from imageai_current.log:
    core/styles/analyzer.py -> UnifiedLLMProvider.analyze_image with a
    Claude 5-line model and temperature=0.7 (previously a 400)."""

    @pytest.mark.parametrize("model", ["anthropic/claude-opus-5",
                                       "anthropic/claude-sonnet-5"])
    def test_analyze_image_claude5(self, keys, model):
        api_key = _need(keys, "anthropic")
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
