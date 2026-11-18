"""Fixtures for the ``local`` test tier: a real LM Studio or Ollama server.

Each fixture skips (with the reason shown by ``pytest -v -rs``) when its
server does not answer, so the tier is safe to run on any machine.

Environment variables (all optional):

* ``IMAGEAI_LMSTUDIO_URL``    LM Studio base URL, default ``http://localhost:1234``
* ``IMAGEAI_LMSTUDIO_MODEL``  LM Studio model key to use
* ``IMAGEAI_OLLAMA_URL``      Ollama base URL, default ``http://localhost:11434``
* ``IMAGEAI_OLLAMA_MODEL``    Ollama model name to use
* ``LM_API_TOKEN``            LM Studio's own token variable; sent as a Bearer
                              header when LM Studio has authentication on.

LM Studio REST API (confirmed 2026-11-18)
-----------------------------------------
Source: LM Studio developer docs (https://lmstudio.ai/docs/developer/rest),
read through the Context7 documentation tool. No LM Studio server was running
on the build machine, so nothing below was probed live.

Documented and used (newest form, tried first):

* ``GET  /api/v1/models`` lists models. The docs name the endpoint but print no
  response example. The fields used here (``models`` array; ``key``, ``type``,
  ``size_bytes``, ``loaded_instances`` with an ``id``, ``capabilities.vision``)
  are NOT confirmed by the docs. ``_parse_listing`` therefore accepts several
  spellings and treats a missing field as "unknown".
* ``POST /api/v1/models/load`` with ``{"model": <key>}`` loads a model; the
  response carries ``instance_id`` and ``status: "loaded"`` (documented).
* ``POST /api/v1/models/unload`` with ``{"instance_id": <id>}`` unloads it;
  the response echoes ``instance_id`` (documented).

Documented older form, used when ``/api/v1/models`` answers 404:

* ``GET /api/v0/models`` returns ``{"object": "list", "data": [...]}``; each
  entry has ``id``, ``type`` (``llm``, ``vlm`` or ``embeddings``) and
  ``state`` (``loaded`` or ``not-loaded``). ``vlm`` means vision-capable.
  There is no size field and the docs list no load or unload endpoint for
  ``/api/v0``, so on that form the fixture never loads: it uses a model that is
  already loaded, or skips with "load a model in LM Studio first".

If the live server disagrees with this docstring, the live server wins; adjust
``_parse_listing``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import pytest
import requests

from core.llm_models import fetch_ollama_models

LIST_TIMEOUT = (2, 10)      # (connect, read) seconds for listing calls
LOAD_TIMEOUT = 120          # seconds for loading a model

_DEFAULT_LMSTUDIO = "http://localhost:1234"
_DEFAULT_OLLAMA = "http://localhost:11434"


@dataclass
class LocalServer:
    base_url: str   # OpenAI-compatible URL to pass as api_base
    model: str
    vision: bool


# --- LM Studio ----------------------------------------------------------------

@dataclass
class _LMModel:
    key: str
    kind: str                     # "llm", "vlm", "embedding", ...
    size: Optional[float]
    loaded_ids: list
    vision: bool

    @property
    def is_chat(self) -> bool:
        return self.kind in ("llm", "vlm")

    @property
    def loaded(self) -> bool:
        return bool(self.loaded_ids)


def _headers() -> dict:
    token = os.environ.get("LM_API_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _parse_listing(payload: dict) -> list:
    """Normalize a /api/v1/models or /api/v0/models payload."""
    items = payload.get("models")
    if items is None:
        items = payload.get("data") or []
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key = item.get("key") or item.get("id")
        if not key:
            continue
        kind = str(item.get("type") or "").lower()
        instances = item.get("loaded_instances")
        if instances is None:
            instances = [key] if item.get("state") == "loaded" else []
        ids = [i.get("id", key) if isinstance(i, dict) else i for i in instances]
        caps = item.get("capabilities")
        vision = (bool(caps.get("vision")) if isinstance(caps, dict) else False) \
            or kind == "vlm"
        size = item.get("size_bytes", item.get("size"))
        out.append(_LMModel(key=key, kind=kind,
                            size=float(size) if isinstance(size, (int, float)) else None,
                            loaded_ids=ids, vision=vision))
    return out


def _list_lmstudio(base: str):
    """Return (models, api_version) or skip. Newest path first, 404 falls back."""
    for version, path in (("v1", "/api/v1/models"), ("v0", "/api/v0/models")):
        try:
            resp = requests.get(base + path, headers=_headers(), timeout=LIST_TIMEOUT)
        except requests.RequestException:
            pytest.skip(f"LM Studio is not running at {base}")
        if resp.status_code == 404:
            continue
        if resp.status_code in (401, 403):
            pytest.skip(f"LM Studio at {base} requires a token: set LM_API_TOKEN")
        if resp.status_code != 200:
            pytest.skip(f"LM Studio at {base} answered HTTP {resp.status_code} "
                        f"on {path}")
        try:
            return _parse_listing(resp.json()), version
        except ValueError:
            pytest.skip(f"LM Studio at {base} returned non-JSON on {path}")
    pytest.skip(f"LM Studio at {base} has no REST model listing "
                "(/api/v1/models and /api/v0/models both answered 404)")


@pytest.fixture(scope="session")
def lmstudio():
    base = os.environ.get("IMAGEAI_LMSTUDIO_URL", _DEFAULT_LMSTUDIO).rstrip("/")
    models, version = _list_lmstudio(base)
    chat = [m for m in models if m.is_chat]

    wanted = os.environ.get("IMAGEAI_LMSTUDIO_MODEL")
    if wanted:
        pick = next((m for m in chat if m.key == wanted or wanted in m.loaded_ids),
                    None)
        if pick is None:
            pytest.skip(f"IMAGEAI_LMSTUDIO_MODEL={wanted!r} is not a chat model "
                        "in LM Studio")
    else:
        pick = next((m for m in chat if m.loaded), None)
        if pick is None:
            if not chat:
                pytest.skip("no chat model downloaded in LM Studio")
            pick = min(chat, key=lambda m: (m.size is None, m.size or 0))

    loaded_here = None
    if not pick.loaded:
        if version != "v1":
            pytest.skip("load a model in LM Studio first "
                        "(this LM Studio only offers the /api/v0 listing, "
                        "which cannot load models)")
        try:
            resp = requests.post(base + "/api/v1/models/load",
                                 json={"model": pick.key}, headers=_headers(),
                                 timeout=LOAD_TIMEOUT)
        except requests.RequestException as exc:
            pytest.skip(f"could not load {pick.key} in LM Studio: {exc}")
        if resp.status_code != 200:
            pytest.skip(f"could not load {pick.key} in LM Studio: "
                        f"HTTP {resp.status_code} {resp.text[:200]}")
        try:
            loaded_here = resp.json().get("instance_id") or pick.key
        except ValueError:
            loaded_here = pick.key
        model_id = loaded_here
    else:
        model_id = pick.loaded_ids[0]

    try:
        yield LocalServer(base_url=base + "/v1", model=model_id, vision=pick.vision)
    finally:
        if loaded_here:  # only a model this fixture loaded
            try:
                requests.post(base + "/api/v1/models/unload",
                              json={"instance_id": loaded_here},
                              headers=_headers(), timeout=LIST_TIMEOUT)
            except requests.RequestException:
                pass


# --- Ollama -------------------------------------------------------------------

def _ollama_capabilities(base: str, name: str) -> Optional[list]:
    """Capabilities reported by POST /api/show, or None when not reported."""
    try:
        resp = requests.post(base + "/api/show", json={"model": name},
                             timeout=LIST_TIMEOUT)
        resp.raise_for_status()
        caps = resp.json().get("capabilities")
    except (requests.RequestException, ValueError):
        return None
    return caps if isinstance(caps, list) else None


@pytest.fixture(scope="session")
def ollama():
    base = os.environ.get("IMAGEAI_OLLAMA_URL", _DEFAULT_OLLAMA).rstrip("/")
    names = fetch_ollama_models(base)
    if not names:
        pytest.skip(f"Ollama is not running at {base}, or has no models installed")

    wanted = os.environ.get("IMAGEAI_OLLAMA_MODEL")
    if wanted:
        if wanted not in names:
            pytest.skip(f"IMAGEAI_OLLAMA_MODEL={wanted!r} is not installed in Ollama")
        candidates = [wanted]
    else:
        try:
            tags = requests.get(base + "/api/tags", timeout=LIST_TIMEOUT).json()
            sizes = {m.get("name"): m.get("size") or 0 for m in tags.get("models", [])}
        except (requests.RequestException, ValueError):
            sizes = {}
        candidates = sorted(names, key=lambda n: sizes.get(n, 0))

    for name in candidates:
        caps = _ollama_capabilities(base, name)
        # Older Ollama reports no capabilities; then trust the name.
        if caps is None or "completion" in caps:
            return LocalServer(base_url=base, model=name,
                               vision=bool(caps) and "vision" in caps)
    pytest.skip("no Ollama model that can complete text is installed")


# --- Shared test data -----------------------------------------------------------

@pytest.fixture(scope="session")
def red_png_data_url() -> str:
    """An 8x8 red PNG as a base64 data URL, built in memory (no binary file)."""
    import base64
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (255, 0, 0)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.fixture(scope="session")
def red_png_data_url() -> str:
    """An 8x8 solid red PNG as a base64 data URL (built here, not committed)."""
    import base64
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (255, 0, 0)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
