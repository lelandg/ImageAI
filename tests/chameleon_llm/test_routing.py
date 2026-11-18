import pytest

from core.chameleon_llm.errors import BadRequestError, UnsupportedRouteError
from core.chameleon_llm.routing import Route, resolve_route


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
def test_resolve_route(model, api_base, expected):
    assert resolve_route(model, api_base) == expected


@pytest.mark.parametrize("model", ["azure/x", "bedrock/x"])
def test_unsupported_routes_raise(model):
    with pytest.raises(UnsupportedRouteError) as info:
        resolve_route(model)
    assert model.split("/")[0] in str(info.value)


@pytest.mark.parametrize("model", ["", "   "])
def test_empty_model_raises_bad_request(model):
    with pytest.raises(BadRequestError):
        resolve_route(model)


# --- I1: refuse an id that would silently reach OpenAI ----------------------

@pytest.mark.parametrize("model,hint", [
    ("claude-test-model", "anthropic/"),
    ("Claude-Test-Model", "anthropic/"),
    ("gemini-test-model", "gemini/"),
    ("GEMINI-test-model", "vertex_ai/"),
])
def test_bare_claude_or_gemini_id_without_api_base_raises(model, hint):
    with pytest.raises(BadRequestError) as info:
        resolve_route(model)
    assert hint in str(info.value)
    assert model in str(info.value)


@pytest.mark.parametrize("model,hint", [
    ("claude/test-model", "anthropic/"),
    ("Claude/test-model", "anthropic/"),
    ("google/test-model", "gemini/"),
    ("vertex/test-model", "vertex_ai/"),
    ("vertexai/test-model", "vertex_ai/"),
    ("lmstudio/test-model", "lm_studio/"),
    ("lm-studio/test-model", "lm_studio/"),
    ("OpenAI/test-model", "openai/"),
    ("Anthropic/test-model", "anthropic/"),
    ("Gemini/test-model", "gemini/"),
])
def test_misnamed_or_miscased_prefix_without_api_base_raises(model, hint):
    with pytest.raises(BadRequestError) as info:
        resolve_route(model)
    assert hint in str(info.value)


@pytest.mark.parametrize("model", [
    "claude-test-model", "gemini-test-model", "google/gemma-test",
    "lmstudio/test-model", "Claude/test-model", "OpenAI/test-model",
])
def test_with_api_base_any_name_goes_to_the_local_server(model):
    # A local server may host any model name, including ids with slashes.
    assert resolve_route(model, "http://localhost:1234/v1") == Route(
        "openai", "openai", model)


@pytest.mark.parametrize("model", [
    "gpt-test-model", "o-test-model", "local-test-model",
    "meta-llama/Llama-test",  # unknown first segment: not a known misname
    "test-claude-model",      # only a leading claude/gemini counts
])
def test_other_bare_ids_still_route_to_openai(model):
    assert resolve_route(model) == Route("openai", "openai", model)


def test_dispatch_refuses_before_any_client_is_built(fake_openai, monkeypatch):
    from core.chameleon_llm import completion
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    with pytest.raises(BadRequestError):
        completion(model="claude-test-model", messages=[{"role": "user", "content": "x"}])
    assert fake_openai.clients_built == 0


def test_dispatch_passes_api_base_to_routing(fake_openai):
    from core.chameleon_llm import completion
    completion(model="claude-test-model", messages=[{"role": "user", "content": "x"}],
               api_base="http://localhost:1234/v1")
    assert fake_openai.chat_calls[0]["model"] == "claude-test-model"
    assert fake_openai.client_kwargs[0]["base_url"] == "http://localhost:1234/v1"
