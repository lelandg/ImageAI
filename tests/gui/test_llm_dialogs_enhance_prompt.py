"""Enhance Prompt worker, with a fake completion (C1, final review).

The dialog hands its provider combo's display text ("Anthropic", "Google",
"LM Studio", ...) to ``EnhanceWorker``; each must reach the right route.
``FakeCompletion`` also fails on a wrong route or an unaccepted parameter.
"""
import json

import pytest

from core.prompt_enhancer import EnhancementLevel
from gui.enhanced_prompt_dialog import EnhanceWorker

CANNED = json.dumps({"unified": {"prompt": "a cat, golden hour"}})

# (display name, api key, model, expected model)
BRANCHES = [
    pytest.param("OpenAI", "test-key", "gpt-test-model", "gpt-test-model", id="openai"),
    pytest.param("Anthropic", "test-key", "claude-test-model",
                 "anthropic/claude-test-model", id="anthropic"),
    pytest.param("Google", "test-key", "gemini-test-model",
                 "gemini/gemini-test-model", id="google-api-key"),
    pytest.param("Google", None, "gemini-test-model",
                 "vertex_ai/gemini-test-model", id="google-gcloud"),
    pytest.param("Ollama", None, "local-test-model", "ollama/local-test-model",
                 id="ollama"),
    pytest.param("LM Studio", None, "local-test-model", "local-test-model",
                 id="lm-studio"),
]


def _run(provider, api_key, model, temperature=0.7, max_tokens=500):
    worker = EnhanceWorker("a cat", provider, model, api_key, EnhancementLevel.MEDIUM,
                           temperature=temperature, max_tokens=max_tokens)
    results, errors = [], []
    worker.finished.connect(results.append)
    worker.error.connect(errors.append)
    worker.run()
    return results, errors


@pytest.mark.parametrize("provider, api_key, model, expected_model", BRANCHES)
def test_display_names_route(qapp, fake_completion, provider, api_key, model,
                             expected_model):
    fake_completion.reply = CANNED
    results, errors = _run(provider, api_key, model)
    assert fake_completion.kwargs["model"] == expected_model
    assert results == ["a cat, golden hour"] and errors == []


def test_reasoning_model_params_are_corralled(qapp, fake_completion):
    fake_completion.reply = CANNED
    _run("OpenAI", "test-key", "gpt-5-test", max_tokens=1000)
    kwargs = fake_completion.kwargs
    assert kwargs["max_completion_tokens"] == 1000
    assert "max_tokens" not in kwargs and "temperature" not in kwargs
