"""scripts/generate_tags.py gives a bare --model override the provider's route."""

import importlib.util
import signal
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "generate_tags.py"


@pytest.fixture(scope="module")
def tags_module(tmp_path_factory):
    """Import the script without keeping its import-time side effects.

    The module opens a log file in the working directory and installs signal
    handlers; run the import in a temp dir and restore the handlers.
    """
    import os
    old_int = signal.getsignal(signal.SIGINT)
    old_term = signal.getsignal(signal.SIGTERM) if hasattr(signal, "SIGTERM") else None
    cwd = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("generate_tags"))
    try:
        spec = importlib.util.spec_from_file_location("generate_tags_under_test", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        os.chdir(cwd)
        signal.signal(signal.SIGINT, old_int)
        if old_term is not None:
            signal.signal(signal.SIGTERM, old_term)
    return mod


@pytest.fixture
def route_model(tags_module):
    return tags_module.route_model


def test_google_bare_id_api_key_auth_uses_gemini_route(route_model):
    assert route_model("google", "gemini-test-model", "api-key") == "gemini/gemini-test-model"


def test_google_bare_id_gcloud_auth_uses_vertex_route(route_model):
    assert route_model("google", "gemini-test-model", "gcloud") == "vertex_ai/gemini-test-model"


@pytest.mark.parametrize("provider,model", [
    ("google", "gemini/gemini-test-model"),
    ("google", "vertex_ai/gemini-test-model"),
    ("openai", "openai/gpt-test-model"),
    ("anthropic", "anthropic/claude-test-model"),
    ("ollama", "ollama/test-model"),
])
def test_prefixed_id_is_unchanged(route_model, provider, model):
    assert route_model(provider, model, "api-key") == model


def test_anthropic_bare_id_gets_anthropic_route(route_model):
    assert route_model("anthropic", "claude-test-model", "api-key") == "anthropic/claude-test-model"


def test_openai_bare_id_is_unchanged(route_model):
    assert route_model("openai", "gpt-test-model", "api-key") == "gpt-test-model"


# --- C2: generate_metadata builds its kwargs with build_completion_kwargs ------

@pytest.fixture
def completion():
    from types import SimpleNamespace
    from unittest import mock
    reply = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"tags": ["x"]}'),
                                 finish_reason="stop")],
        usage=None, model="fake")
    with mock.patch("core.chameleon_llm.completion", return_value=reply) as m:
        yield m


def _generator(tags_module, provider, model, api_key="stored-key"):
    from unittest import mock
    gen = tags_module.TagGenerator.__new__(tags_module.TagGenerator)
    gen.provider = provider
    gen.model = model
    gen.api_key = api_key
    gen.config = mock.MagicMock()
    gen.config.get_gcloud_project_id.return_value = "test-project"
    return gen


def test_reasoning_model_gets_completion_tokens_and_no_temperature(tags_module, completion):
    _generator(tags_module, "openai", "gpt-5-test").generate_metadata("Item", "styles")
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "gpt-5-test"
    assert kwargs["max_completion_tokens"] == 500
    assert "max_tokens" not in kwargs and "temperature" not in kwargs
    assert kwargs["api_key"] == "stored-key"


def test_classic_model_keeps_max_tokens_and_temperature(tags_module, completion):
    _generator(tags_module, "openai", "gpt-4-test").generate_metadata("Item", "styles")
    kwargs = completion.call_args.kwargs
    assert kwargs["max_tokens"] == 500 and "max_completion_tokens" not in kwargs
    assert kwargs["temperature"] == 0.3


@pytest.mark.parametrize("provider,model", [
    ("google", "gemini/gemini-test-model"),
    ("Google", "gemini/gemini-test-model"),
    ("openai", "anthropic/claude-test-model"),
    ("anthropic", "anthropic/claude-test-model"),
])
def test_prefixed_model_routes_unchanged(tags_module, completion, provider, model):
    _generator(tags_module, provider, model).generate_metadata("Item", "styles")
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == model
    assert kwargs["api_key"] == "stored-key"
    assert "vertex_project" not in kwargs


def test_vertex_route_gets_project_and_no_key(tags_module, completion):
    _generator(tags_module, "google", "vertex_ai/gemini-test-model",
               api_key="gcloud-token").generate_metadata("Item", "styles")
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "vertex_ai/gemini-test-model"
    assert "api_key" not in kwargs
    assert kwargs["vertex_project"] == "test-project"
    assert kwargs["vertex_location"] == "us-central1"
