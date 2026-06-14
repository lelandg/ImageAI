"""Project wrapper around the vendored ChameleonLabs model-registry client.

Resolves current LLM model IDs at runtime instead of hardcoding IDs that go stale.
Every call auto-defaults ``fallback_path`` to the snapshot bundled beside this package
(``core/model-registry.fallback.json``), so resolution never raises even fully offline:

    fetch live registry -> in-memory cache (even expired) -> bundled fallback snapshot

Usage::

    from core.model_registry import resolve

    model_id = resolve("anthropic", "opus")   # -> current Opus ID
    model_id = resolve("openai", "gpt")        # -> current flagship GPT ID

Refreshing the bundled fallback (do this periodically / before a release)::

    /model-registry refresh-fallback
    # or manually:
    curl -sf "https://chameleonlabs-model-registry.s3.us-east-1.amazonaws.com/models/latest.json" \
        -o core/model-registry.fallback.json
"""

from pathlib import Path

from . import client as _client
from .client import RegistryError

__all__ = [
    "resolve",
    "get_registry",
    "context_window",
    "available",
    "RegistryError",
    "FALLBACK_PATH",
]

# Snapshot bundled beside the central models module (core/llm_models.py).
FALLBACK_PATH = str(Path(__file__).resolve().parent.parent / "model-registry.fallback.json")


def resolve(provider: str, family: str, channel: str = "active", **kwargs):
    """Resolve (provider, family) to the current model ID, bundled-fallback wired."""
    kwargs.setdefault("fallback_path", FALLBACK_PATH)
    return _client.resolve(provider, family, channel=channel, **kwargs)


def get_registry(**kwargs):
    """Return the parsed registry dict, bundled-fallback wired."""
    kwargs.setdefault("fallback_path", FALLBACK_PATH)
    return _client.get_registry(**kwargs)


def context_window(model_id: str, **kwargs):
    """Return a model's context window in tokens (or None), bundled-fallback wired."""
    kwargs.setdefault("fallback_path", FALLBACK_PATH)
    return _client.context_window(model_id, **kwargs)


def available(provider: str, **kwargs):
    """Return the full curated model-ID list for a provider, bundled-fallback wired."""
    kwargs.setdefault("fallback_path", FALLBACK_PATH)
    return _client.available(provider, **kwargs)
