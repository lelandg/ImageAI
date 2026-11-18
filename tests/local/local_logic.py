"""Pure parsing and decision logic for the ``local`` tier fixtures.

No network access happens here, so ``test_local_fixture_logic.py`` can test it
without a server. The rule: ``pytest.skip`` only when there is genuinely
nothing to test; anything unexpected from a server that IS answering is
``pytest.fail``, so a contributor never gets a green run that tested nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import pytest

CHAT_KINDS = ("llm", "vlm")
EMBEDDING_KINDS = ("embedding", "embeddings", "embedder")


@dataclass
class LMModel:
    key: str
    kind: str                       # raw "type" value, lower-cased
    size: Optional[float]
    loaded_ids: list
    vision: Optional[bool]          # None = the server did not say
    fields: list = field(default_factory=list)   # raw keys, for failure messages

    @property
    def is_chat(self) -> bool:
        return self.kind in CHAT_KINDS

    @property
    def loaded(self) -> bool:
        return bool(self.loaded_ids)


def parse_listing(payload) -> list:
    """Normalize a /api/v1/models (``models``) or /api/v0/models (``data``) body."""
    is_v0 = isinstance(payload, dict) and "models" not in payload
    items = None
    if isinstance(payload, dict):
        items = payload.get("models")
        if items is None:
            items = payload.get("data")
    if not isinstance(items, list):
        keys = sorted(payload) if isinstance(payload, dict) else type(payload).__name__
        pytest.fail("LM Studio answered 200 but the body has no recognisable model "
                    f"list (expected a 'models' or 'data' array). Top-level keys: {keys}")
    out = []
    unreadable = []
    for item in items:
        key = item.get("key") or item.get("id") if isinstance(item, dict) else None
        if not key:
            unreadable.append(sorted(item) if isinstance(item, dict)
                              else type(item).__name__)
            continue
        kind = str(item.get("type") or "").lower()
        instances = item.get("loaded_instances")
        if instances is None:
            instances = [key] if item.get("state") == "loaded" else []
        ids = [i.get("id", key) if isinstance(i, dict) else i for i in instances]
        caps = item.get("capabilities")
        if kind == "vlm":
            vision = True
        elif isinstance(caps, dict) and "vision" in caps:
            vision = bool(caps["vision"])
        elif is_v0 and kind == "llm":
            vision = False          # /api/v0 marks vision models as "vlm"
        else:
            vision = None
        size = item.get("size_bytes", item.get("size"))
        out.append(LMModel(key=key, kind=kind,
                           size=float(size) if isinstance(size, (int, float)) else None,
                           loaded_ids=ids, vision=vision, fields=sorted(item)))
    if items and not out:
        pytest.fail(f"LM Studio lists {len(items)} entries but none has a 'key' or "
                    f"'id' field. Entry keys seen: {unreadable[:3]}")
    return out


def pick_lmstudio_model(models: list, wanted: Optional[str] = None) -> LMModel:
    """Choose the model to test: named, else loaded chat, else smallest chat."""
    chat = [m for m in models if m.is_chat]
    if wanted and not any(m.key == wanted or wanted in m.loaded_ids for m in chat):
        pytest.fail(f"IMAGEAI_LMSTUDIO_MODEL={wanted!r} is not a chat model in "
                    f"LM Studio. Chat models: {[m.key for m in chat]}")
    if not models:
        pytest.skip("no chat model downloaded in LM Studio (the model list is empty)")
    if not chat:
        if all(m.kind in EMBEDDING_KINDS for m in models):
            pytest.skip("no chat model downloaded in LM Studio (only embedding models)")
        pytest.fail(
            "LM Studio lists models but none is recognised as a chat model. "
            f"'type' values seen: {sorted({m.kind for m in models})}; "
            f"keys on the first entry: {models[0].fields}. If these are real chat "
            "models, the field names in tests/local/local_logic.py are wrong.")
    if wanted:  # present in ``chat``: the check at the top fails otherwise
        return next(m for m in chat if m.key == wanted or wanted in m.loaded_ids)
    for m in chat:
        if m.loaded:
            return m
    return min(chat, key=lambda m: (m.size is None, m.size or 0))


def fail_or_skip_request_error(server: str, base: str, path: str, exc) -> None:
    """Skip when nothing accepted the connection; fail on anything else.

    Only a refused connection or a connect timeout means the server is not
    running. A read timeout or any other request error comes from a server
    that answered, so the test fails instead of reporting a green skip.
    """
    import requests
    if isinstance(exc, (requests.ConnectionError, requests.ConnectTimeout)):
        pytest.skip(f"{server} is not running at {base}")
    pytest.fail(f"{server} at {base} accepted the connection but the request to "
                f"{path} failed: {type(exc).__name__}: {exc}")


def parse_ollama_tags(payload, wanted: Optional[str] = None) -> tuple:
    """Parse a GET /api/tags body into (names, sizes). Skips when empty."""
    items = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        keys = sorted(payload) if isinstance(payload, dict) else type(payload).__name__
        pytest.fail("Ollama answered 200 but the body has no 'models' list. "
                    f"Top-level keys: {keys}")
    names, sizes = [], {}
    for item in items:
        name = (item.get("name") or item.get("model")) if isinstance(item, dict) else None
        if not name:
            pytest.fail("Ollama lists a model entry with no 'name'. Entry: "
                        f"{sorted(item) if isinstance(item, dict) else type(item).__name__}")
        names.append(name)
        sizes[name] = item.get("size") or 0
    if wanted and wanted not in names:
        pytest.fail(f"IMAGEAI_OLLAMA_MODEL={wanted!r} is not installed in "
                    f"Ollama. Installed: {names}")
    if not names:
        pytest.skip("Ollama has no models installed")
    return names, sizes


def pick_ollama_model(names: list, sizes: dict, wanted: Optional[str],
                      capabilities: Callable[[str], Optional[list]]):
    """Return (name, vision). ``capabilities(name)`` is None when unreadable."""
    if wanted:
        if wanted not in names:
            pytest.fail(f"IMAGEAI_OLLAMA_MODEL={wanted!r} is not installed in "
                        f"Ollama. Installed: {names}")
        candidates = [wanted]
    else:
        candidates = sorted(names, key=lambda n: sizes.get(n, 0))
    for name in candidates:
        caps = capabilities(name)
        # Older Ollama reports no capabilities: trust the name, vision unknown.
        if caps is None:
            return name, None
        if "completion" in caps:
            return name, "vision" in caps
    pytest.skip("no Ollama model that can complete text is installed "
                "(capabilities were read for every model)")
