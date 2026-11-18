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
