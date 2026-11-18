"""Fixtures for the ``local`` test tier: a real LM Studio or Ollama server.

A fixture skips (reason shown by ``pytest -v -rs``) only when there is nothing
to test: the server does not answer, or it has no chat model. Anything
unexpected from a server that DOES answer is a failure, never a skip, so a
contributor with a running server never gets a green run that tested nothing.
The parsing and the decisions live in ``local_logic.py``, which is tested
without a server in ``test_local_fixture_logic.py``.

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
  are NOT confirmed by the docs. ``local_logic.parse_listing`` accepts several
  spellings; a body it cannot read FAILS the test and names the keys it saw.
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
``local_logic.parse_listing``.
"""

from __future__ import annotations

import base64
import io
import os
import warnings
from dataclasses import dataclass
from typing import Optional

import pytest
import requests


from local_logic import (parse_listing, parse_ollama_tags, pick_lmstudio_model,
                         pick_ollama_model)

LIST_TIMEOUT = (2, 10)      # (connect, read) seconds for listing calls
LOAD_TIMEOUT = 120          # seconds for loading a model

_DEFAULT_LMSTUDIO = "http://localhost:1234"
_DEFAULT_OLLAMA = "http://localhost:11434"


@dataclass
class LocalServer:
    base_url: str               # OpenAI-compatible URL to pass as api_base
    model: str
    vision: Optional[bool]      # None = the server did not say


def _headers() -> dict:
    token = os.environ.get("LM_API_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _list_lmstudio(base: str):
    """Return (models, api_version). Newest path first; 404 falls back."""
    paths = (("v1", "/api/v1/models"), ("v0", "/api/v0/models"))
    for version, path in paths:
        try:
            resp = requests.get(base + path, headers=_headers(), timeout=LIST_TIMEOUT)
        except requests.RequestException:
            pytest.skip(f"LM Studio is not running at {base}")
        if resp.status_code == 404:
            continue
        if resp.status_code in (401, 403):
            pytest.fail(f"LM Studio at {base} answered HTTP {resp.status_code} on "
                        f"{path}: it needs a token. Set LM_API_TOKEN.")
        if resp.status_code != 200:
            pytest.fail(f"LM Studio at {base} answered HTTP {resp.status_code} on "
                        f"{path}: {resp.text[:200]}")
        try:
            payload = resp.json()
        except ValueError:
            pytest.fail(f"LM Studio at {base} returned a non-JSON body on {path}: "
                        f"{resp.text[:200]}")
        return parse_listing(payload), version
    pytest.fail(f"Something answers at {base} but it is not a recognised LM Studio "
                f"REST API: {paths[0][1]} and {paths[1][1]} both returned 404.")


@pytest.fixture(scope="session")
def lmstudio():
    base = os.environ.get("IMAGEAI_LMSTUDIO_URL", _DEFAULT_LMSTUDIO).rstrip("/")
    models, version = _list_lmstudio(base)
    pick = pick_lmstudio_model(models, os.environ.get("IMAGEAI_LMSTUDIO_MODEL"))

    loaded_here = None
    if pick.loaded:
        model_id = pick.loaded_ids[0]
    else:
        if version != "v1":
            pytest.skip("load a model in LM Studio first (this LM Studio only offers "
                        "the /api/v0 listing, which cannot load models)")
        try:
            resp = requests.post(base + "/api/v1/models/load",
                                 json={"model": pick.key}, headers=_headers(),
                                 timeout=LOAD_TIMEOUT)
        except requests.RequestException as exc:
            pytest.fail(f"loading {pick.key} in LM Studio failed: {exc}")
        if resp.status_code != 200:
            pytest.fail(f"loading {pick.key} in LM Studio failed: "
                        f"HTTP {resp.status_code} {resp.text[:300]}")
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {}
        status = body.get("status")
        model_id = body.get("instance_id") or pick.key
        loaded_here = model_id  # from here on, teardown unloads it

    try:
        # Verification runs inside the try so a failure still unloads the model.
        if loaded_here:
            if status is not None and status != "loaded":
                pytest.fail(f"LM Studio accepted the load of {pick.key} but "
                            f"reported status {status!r}, not 'loaded'")
            if status is None:  # no status field: confirm by listing again
                again, _ = _list_lmstudio(base)
                if not any(m.key == pick.key and m.loaded for m in again):
                    pytest.fail(f"LM Studio answered 200 to the load of {pick.key} "
                                "but the model does not show as loaded afterwards")
        yield LocalServer(base_url=base + "/v1", model=model_id, vision=pick.vision)
    finally:
        if loaded_here:  # only a model this fixture loaded
            try:
                resp = requests.post(base + "/api/v1/models/unload",
                                     json={"instance_id": loaded_here},
                                     headers=_headers(), timeout=LIST_TIMEOUT)
                if resp.status_code != 200:
                    warnings.warn(f"could not unload {loaded_here} from LM Studio: "
                                  f"HTTP {resp.status_code}; unload it by hand")
            except requests.RequestException as exc:
                warnings.warn(f"could not unload {loaded_here} from LM Studio: "
                              f"{exc}; unload it by hand")


def _ollama_capabilities(base: str, name: str) -> Optional[list]:
    """Capabilities from POST /api/show, or None when not reported."""
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
    wanted = os.environ.get("IMAGEAI_OLLAMA_MODEL")
    try:
        resp = requests.get(base + "/api/tags", timeout=LIST_TIMEOUT)
    except requests.RequestException:
        pytest.skip(f"Ollama is not running at {base}")
    if resp.status_code != 200:
        pytest.fail(f"Ollama at {base} answered HTTP {resp.status_code} on "
                    f"/api/tags: {resp.text[:200]}")
    try:
        payload = resp.json()
    except ValueError:
        pytest.fail(f"Ollama at {base} returned a non-JSON body on /api/tags: "
                    f"{resp.text[:200]}")
    names, sizes = parse_ollama_tags(payload, wanted)
    name, vision = pick_ollama_model(
        names, sizes, wanted,
        lambda n: _ollama_capabilities(base, n))
    return LocalServer(base_url=base, model=name, vision=vision)


@pytest.fixture(scope="session")
def red_png_data_url() -> str:
    """An 8x8 solid red PNG as a base64 data URL (built here, not committed)."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (255, 0, 0)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
