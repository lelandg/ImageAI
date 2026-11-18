"""scripts/generate_tags.py gives a bare --model override the provider's route."""

import importlib.util
import signal
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "generate_tags.py"


@pytest.fixture(scope="module")
def route_model(tmp_path_factory):
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
    return mod.route_model


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
