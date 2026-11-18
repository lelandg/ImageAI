"""Shared fixtures for the chameleon_llm tests."""

from types import SimpleNamespace

import pytest


class FakeOpenAIState:
    """Records what the adapter did to the fake ``openai.OpenAI`` client."""

    def __init__(self):
        self.client_kwargs = []    # one dict per OpenAI(...) construction
        self.chat_calls = []       # kwargs of each chat.completions.create
        self.responses_calls = []  # kwargs of each responses.create (Responses API)
        self.chat_reply = make_chat_reply()
        self.responses_reply = None
        self.raises = None         # exception instance raised by any create()
        self.chat_raises = None    # raised by chat.completions.create only
        self.responses_raises = None  # raised by responses.create only

    @property
    def clients_built(self):
        return len(self.client_kwargs)


def make_chat_reply(content="hello", finish_reason="stop", usage=(3, 4, 7)):
    """Build an object shaped like an OpenAI ChatCompletion."""
    use = None
    if usage is not None:
        use = SimpleNamespace(prompt_tokens=usage[0], completion_tokens=usage[1],
                              total_tokens=usage[2])
    choice = SimpleNamespace(
        index=0, finish_reason=finish_reason,
        message=SimpleNamespace(role="assistant", content=content))
    return SimpleNamespace(model="echoed-model", choices=[choice], usage=use)


@pytest.fixture
def fake_openai(monkeypatch):
    openai = pytest.importorskip("openai")
    state = FakeOpenAIState()

    class _Chat:
        def __init__(self):
            self.completions = SimpleNamespace(create=self._create)

        def _create(self, **kwargs):
            state.chat_calls.append(kwargs)
            if state.raises is not None:
                raise state.raises
            if state.chat_raises is not None:
                raise state.chat_raises
            return state.chat_reply

    class _Responses:
        def create(self, **kwargs):
            state.responses_calls.append(kwargs)
            if state.raises is not None:
                raise state.raises
            if state.responses_raises is not None:
                raise state.responses_raises
            return state.responses_reply

    class FakeOpenAI:
        def __init__(self, **kwargs):
            state.client_kwargs.append(kwargs)
            self.chat = _Chat()
            self.responses = _Responses()

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    for var in ("OPENAI_API_KEY", "OPENAI_API_BASE", "OLLAMA_API_BASE"):
        monkeypatch.delenv(var, raising=False)
    return state


class FakeAnthropicState:
    """Records what the adapter did to the fake ``anthropic.Anthropic`` client."""

    def __init__(self):
        self.client_kwargs = []   # one dict per Anthropic(...) construction
        self.calls = []           # kwargs of each messages.create
        self.reply = make_anthropic_reply()
        self.raises = None        # exception instance raised by create()

    @property
    def clients_built(self):
        return len(self.client_kwargs)


def make_anthropic_reply(text="hello", stop_reason="end_turn", usage=(3, 4)):
    """Build an object shaped like an Anthropic Message."""
    use = None
    if usage is not None:
        use = SimpleNamespace(input_tokens=usage[0], output_tokens=usage[1])
    content = [SimpleNamespace(type="text", text=text)] if text is not None else []
    return SimpleNamespace(model="echoed-model", content=content,
                           stop_reason=stop_reason, usage=use)


@pytest.fixture
def fake_anthropic(monkeypatch):
    anthropic = pytest.importorskip("anthropic")
    state = FakeAnthropicState()

    class _Messages:
        def create(self, **kwargs):
            state.calls.append(kwargs)
            if state.raises is not None:
                raise state.raises
            return state.reply

    class FakeAnthropic:
        def __init__(self, **kwargs):
            state.client_kwargs.append(kwargs)
            self.messages = _Messages()

    monkeypatch.setattr(anthropic, "Anthropic", FakeAnthropic)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return state


class FakeGenaiState:
    """Records what the adapter did to the fake ``google.genai.Client``."""

    def __init__(self):
        self.client_kwargs = []   # one dict per Client(...) construction
        self.calls = []           # kwargs of each models.generate_content
        self.reply = make_genai_reply()
        self.raises = None        # exception instance raised by generate_content()

    @property
    def clients_built(self):
        return len(self.client_kwargs)


def make_genai_reply(text="hello", finish_reason="STOP", usage=(3, 4, 7)):
    """Build an object shaped like a google-genai GenerateContentResponse."""
    use = None
    if usage is not None:
        use = SimpleNamespace(prompt_token_count=usage[0],
                              candidates_token_count=usage[1],
                              total_token_count=usage[2])
    parts = [SimpleNamespace(text=text)] if text is not None else []
    candidate = SimpleNamespace(
        content=SimpleNamespace(role="model", parts=parts),
        finish_reason=finish_reason)
    return SimpleNamespace(candidates=[candidate], usage_metadata=use)


@pytest.fixture
def fake_genai(monkeypatch):
    genai = pytest.importorskip("google.genai")
    state = FakeGenaiState()

    class _Models:
        def generate_content(self, **kwargs):
            state.calls.append(kwargs)
            if state.raises is not None:
                raise state.raises
            return state.reply

    class FakeClient:
        def __init__(self, **kwargs):
            state.client_kwargs.append(kwargs)
            self.models = _Models()

    monkeypatch.setattr(genai, "Client", FakeClient)
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_CLOUD_PROJECT",
                "GOOGLE_CLOUD_LOCATION"):
        monkeypatch.delenv(var, raising=False)
    return state
