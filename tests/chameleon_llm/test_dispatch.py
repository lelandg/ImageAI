import ast
import importlib
import logging
import sys
import types
from pathlib import Path

import pytest

import core.chameleon_llm as pkg
from core.chameleon_llm import completion
from core.chameleon_llm.errors import (
    BadRequestError, MissingSDKError, UnsupportedRouteError,
)
from core.chameleon_llm.types import Choice, Completion, Message, Usage

MSGS = [{"role": "user", "content": "hi"}]
ADAPTER_MOD = "core.chameleon_llm.anthropic_adapter"


@pytest.fixture
def fake_adapter(monkeypatch):
    """Register a fake anthropic adapter; returns the dict of captured calls."""
    seen = {}

    def complete(route, messages, *, api_key, api_base, params, timeout, max_retries):
        seen.update(route=route, messages=messages, api_key=api_key,
                    api_base=api_base, params=params, timeout=timeout,
                    max_retries=max_retries)
        return Completion(
            model=route.model,
            choices=[Choice(0, Message("assistant", "ok"), "stop")],
            usage=Usage(1, 1, 2),
        )

    mod = types.ModuleType(ADAPTER_MOD)
    mod.ACCEPTED_PARAMS = frozenset({"temperature", "max_tokens"})
    mod.complete = complete
    monkeypatch.setitem(sys.modules, ADAPTER_MOD, mod)
    return seen


def _fail_adapter_import(monkeypatch, missing):
    monkeypatch.delitem(sys.modules, ADAPTER_MOD, raising=False)
    real = importlib.import_module

    def fake_import(name, *a, **k):
        if name == ADAPTER_MOD:
            raise ModuleNotFoundError(f"No module named '{missing}'", name=missing)
        return real(name, *a, **k)

    monkeypatch.setattr(importlib, "import_module", fake_import)


def test_returns_adapter_completion(fake_adapter):
    resp = completion(model="anthropic/test-model", messages=MSGS)
    assert resp.choices[0].message.content == "ok"
    assert fake_adapter["route"].model == "test-model"
    assert fake_adapter["messages"] == MSGS


def test_none_params_removed_silently(fake_adapter, caplog):
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        completion(model="anthropic/test-model", messages=MSGS,
                   temperature=None, seed=None, max_tokens=5)
    assert fake_adapter["params"] == {"max_tokens": 5}
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_unaccepted_param_dropped_with_warning(fake_adapter, caplog):
    with caplog.at_level(logging.WARNING, logger="chameleon_llm"):
        completion(model="anthropic/test-model", messages=MSGS, seed=7, temperature=0.5)
    assert fake_adapter["params"] == {"temperature": 0.5}
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "seed" in warnings[0].getMessage()


def test_timeout_defaults_to_600(fake_adapter):
    completion(model="anthropic/test-model", messages=MSGS)
    assert fake_adapter["timeout"] == 600


def test_explicit_timeout_is_kept(fake_adapter):
    completion(model="anthropic/test-model", messages=MSGS, timeout=12.5)
    assert fake_adapter["timeout"] == 12.5


def test_max_retries_defaults_to_zero(fake_adapter):
    completion(model="anthropic/test-model", messages=MSGS)
    assert fake_adapter["max_retries"] == 0


def test_debug_line_and_no_api_key_in_logs(fake_adapter, caplog):
    with caplog.at_level(logging.DEBUG, logger="chameleon_llm"):
        completion(model="anthropic/test-model", messages=MSGS,
                   api_key="sk-secret-value", temperature=0.1)
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "test-model" in text and "temperature" in text
    assert "sk-secret-value" not in text
    assert fake_adapter["api_key"] == "sk-secret-value"


def test_unsupported_route_raises():
    with pytest.raises(UnsupportedRouteError):
        completion(model="azure/x", messages=MSGS)


def test_empty_model_raises_bad_request():
    with pytest.raises(BadRequestError):
        completion(model=" ", messages=MSGS)


@pytest.mark.parametrize("missing,pip_name", [
    ("anthropic", "anthropic"), ("openai", "openai"),
    ("google.genai", "google-genai"), ("google", "google-genai"),
])
def test_missing_sdk_becomes_missing_sdk_error(monkeypatch, missing, pip_name):
    _fail_adapter_import(monkeypatch, missing)
    with pytest.raises(MissingSDKError) as info:
        completion(model="anthropic/test-model", messages=MSGS)
    assert pip_name in str(info.value)


def test_unrelated_import_error_propagates(monkeypatch):
    _fail_adapter_import(monkeypatch, "zzz")
    with pytest.raises(ModuleNotFoundError):
        completion(model="anthropic/test-model", messages=MSGS)


def test_public_names_exported():
    for name in ("completion", "Completion", "Choice", "Message", "Usage", "Route",
                 "resolve_route", "LLMError", "AuthError", "RateLimitError",
                 "BadRequestError", "TimeoutError_", "ConnectionError_",
                 "ServerError", "UnsupportedRouteError", "MissingSDKError"):
        assert hasattr(pkg, name), name
    assert pkg.__version__ == "0.1.0"


def test_package_imports_nothing_from_imageai():
    root = Path(pkg.__file__).parent
    banned = ("core", "gui", "cli", "providers", "PySide6")
    bad = []
    for path in root.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            else:
                continue
            for n in names:
                if n.split(".")[0] in banned:
                    bad.append((path.name, n))
    assert not bad
