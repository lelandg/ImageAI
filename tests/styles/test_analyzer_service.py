"""Transport-layer tests with UnifiedLLMProvider mocked out."""
import json
from unittest.mock import patch

import pytest
from PIL import Image

from core.styles.analyzer import (
    StyleAnalysisError, StyleAnalysisService, build_completion_fn,
    default_vision_model, normalize_llm_provider,
)
from core.styles.models import DESCRIPTOR_KEYS

DESC_JSON = json.dumps({k: "v" for k in DESCRIPTOR_KEYS})


class FakeConfig:
    def __init__(self, keys=None):
        self._keys = keys or {}
    def get_api_key(self, provider):
        return self._keys.get(provider)
    def get(self, key, default=None):
        return default


def test_normalize_llm_provider():
    assert normalize_llm_provider("gemini") == "google"
    assert normalize_llm_provider("claude") == "anthropic"
    assert normalize_llm_provider("OpenAI") == "openai"
    assert normalize_llm_provider(None) == "openai"


def test_default_vision_model_uses_registry():
    with patch("core.llm_models.resolve_model", return_value="resolved-x") as rm:
        assert default_vision_model("openai") == "resolved-x"
        assert rm.call_args.args[0] == "openai"


def test_build_completion_fn_requires_key():
    with pytest.raises(StyleAnalysisError, match="API key"):
        build_completion_fn(FakeConfig(), provider="openai")


def test_build_completion_fn_calls_unified_provider():
    cfg = FakeConfig({"openai": "sk-test"})
    with patch("core.video.prompt_engine.UnifiedLLMProvider") as MockLLM:
        MockLLM.return_value.analyze_image.return_value = "reply"
        fn, provider, model = build_completion_fn(cfg, provider="openai",
                                                  model="test-model")
        out = fn([{"role": "user", "content": "hi"}])
    assert out == "reply"
    assert provider == "openai"
    assert model == "test-model"  # openai prefix is ''
    assert MockLLM.call_args.args[0] == {"openai_api_key": "sk-test"}


def test_service_derive_end_to_end(tmp_path):
    img = tmp_path / "a.png"
    Image.new("RGB", (32, 32), (10, 10, 10)).save(img)
    cfg = FakeConfig({"openai": "sk-test"})
    with patch("core.video.prompt_engine.UnifiedLLMProvider") as MockLLM:
        MockLLM.return_value.analyze_image.return_value = DESC_JSON
        svc = StyleAnalysisService(cfg, provider="openai", model="test-model")
        result = svc.derive([img])
    assert result["prompt_text"]  # deterministic flatten of the single chunk
    assert set(result["descriptor"].keys()) == set(DESCRIPTOR_KEYS)


def test_analyze_image_forwards_max_retries(monkeypatch):
    """analyze_image passes its max_retries through to the retry wrapper."""
    from core.video.prompt_engine import UnifiedLLMProvider
    llm = UnifiedLLMProvider({})
    captured = {}

    def fake_retry(func, max_retries=3, **kw):
        captured["max_retries"] = max_retries
        return "ok"

    monkeypatch.setattr(llm, "_retry_with_backoff", fake_retry)
    out = llm.analyze_image(messages=[{"role": "user", "content": "hi"}],
                            model="gpt-4o", max_retries=0)
    assert out == "ok" and captured["max_retries"] == 0
