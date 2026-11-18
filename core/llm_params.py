"""
Unified LLM parameter population, validation, and corralling.

Single source of truth for which chat-completion parameters each provider/model
accepts. Every completion call site builds its kwargs through this module instead
of hand-rolling ``temperature``/``max_tokens`` dicts and per-model hacks.

Contract (see Plans/LLM-Params-Standardization.md):
  - validate values against curated per-family rules,
  - corral where possible (clamp to range, drop unsupported, cap tokens) with a
    logged warning,
  - raise ``LLMParamError`` for values that cannot be corralled (wrong type,
    nonsense values, unknown reasoning effort), or for *any* correction when
    ``strict=True``.

Why curated rules: third-party capability tables lag the live APIs (one
table claimed ``temperature`` was supported on ``anthropic/claude-opus-5``,
but the live API rejects it with a 400, "`temperature` is deprecated for this
model"). The rules below are verified by the live boundary tests in
``tests/test_live_llm_params.py``.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.llm_models import LLM_PROVIDERS, get_provider_prefix
from core.model_registry import FALLBACK_PATH

logger = logging.getLogger(__name__)

# Known route prefixes that may arrive glued onto a model id.
_ROUTE_PREFIXES = (
    "anthropic/", "gemini/", "vertex_ai/", "openai/", "ollama/", "ollama_chat/",
    "lm_studio/", "azure/", "bedrock/",
)

# Accepted reasoning-effort levels across providers (OpenAI o-series/gpt-5.x
# plus Anthropic-style effort names). Unknown strings cannot be corralled.
_REASONING_EFFORT_LEVELS = {
    "none", "minimal", "low", "medium", "high", "xhigh", "max",
}

_VERBOSITY_LEVELS = {"low", "medium", "high"}

# Display names / aliases -> canonical LLM provider id (LLM_PROVIDERS keys).
_PROVIDER_ALIASES = {
    "openai": "openai",
    "anthropic": "anthropic",
    "claude": "anthropic",
    "gemini": "gemini",
    "google": "gemini",
    "ollama": "ollama",
    "lmstudio": "lmstudio",
    "lm studio": "lmstudio",
    "lm_studio": "lmstudio",
}


class LLMParamError(ValueError):
    """A parameter value that cannot be corralled into a valid request."""


@dataclass
class LLMParams:
    """Provider-agnostic chat-completion parameters as the caller wants them.

    ``None`` means "do not send" — the provider default applies.
    """
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    reasoning_effort: Optional[str] = None
    verbosity: Optional[str] = None
    response_format: Optional[Dict[str, Any]] = None
    timeout: Optional[float] = None
    seed: Optional[int] = None
    stop: Optional[Any] = None

    @classmethod
    def from_dict(cls, values: Dict[str, Any]) -> "LLMParams":
        known = {f for f in cls.__dataclass_fields__}
        unknown = set(values) - known
        if unknown:
            # A typo here (e.g. 'max_completion_tokens' instead of 'max_tokens')
            # would otherwise silently drop the caller's constraint.
            logger.warning(f"ignoring unknown LLM params: {sorted(unknown)}")
        return cls(**{k: v for k, v in values.items() if k in known})


@dataclass
class ModelParamRules:
    """What one provider/model family actually accepts."""
    # (lo, hi) inclusive range; None means the parameter is rejected outright.
    temperature_range: Optional[Tuple[float, float]] = (0.0, 2.0)
    # If set, only this value is accepted (e.g. GPT-5 requires default 1.0);
    # corralling drops the parameter so the provider default applies.
    temperature_fixed: Optional[float] = None
    top_p_supported: bool = True
    top_k_supported: bool = False
    # Claude 4.x accepts temperature or top_p, not both.
    temp_top_p_exclusive: bool = False
    tokens_param: str = "max_tokens"  # or "max_completion_tokens"
    max_output_tokens: Optional[int] = None
    supports_reasoning_effort: bool = False
    supports_verbosity: bool = False
    supports_response_format: bool = True
    supports_seed: bool = True
    description: str = ""  # short label used in warnings


# --- Curated per-family rules (authoritative; verified by live tests) --------

@dataclass
class _FamilyRule:
    provider: str
    pattern: str  # regex matched against the unprefixed, lowercased model id
    rules: ModelParamRules = field(default_factory=ModelParamRules)


_FAMILY_RULES: List[_FamilyRule] = [
    # Anthropic — Claude Opus 4.7/4.8, every Opus/Sonnet/Haiku of generation
    # 5 and later, Fable/Mythos: sampling params removed entirely (400 if
    # sent; live: "temperature is deprecated for this model" on Haiku 5).
    # claude-haiku-4-5-*, claude-opus-4-2025* and claude-3-* do not match.
    _FamilyRule(
        provider="anthropic",
        pattern=r"^claude-(opus-4-[78]|(?:opus|sonnet|haiku)-(?:[5-9]|\d{2,})|fable|mythos)",
        rules=ModelParamRules(
            temperature_range=None,
            top_p_supported=False,
            top_k_supported=False,
            tokens_param="max_tokens",
            supports_reasoning_effort=False,
            supports_seed=False,
            description="Claude 5-line (no sampling params)",
        ),
    ),
    # Anthropic — dated releases the model registry snapshot has no output
    # ceiling for. Limits are Anthropic's published per-model maximum output.
    _FamilyRule(
        provider="anthropic",
        pattern=r"^claude-opus-4-2025",
        rules=ModelParamRules(
            temperature_range=(0.0, 1.0),
            top_p_supported=True,
            top_k_supported=True,
            temp_top_p_exclusive=True,
            tokens_param="max_tokens",
            max_output_tokens=32000,  # unconfirmed (not found in Context7 docs)
            supports_seed=False,
            description="Claude Opus 4 (temperature 0-1)",
        ),
    ),
    _FamilyRule(
        provider="anthropic",
        pattern=r"^claude-3-7-sonnet",
        rules=ModelParamRules(
            temperature_range=(0.0, 1.0),
            top_p_supported=True,
            top_k_supported=True,
            temp_top_p_exclusive=True,
            tokens_param="max_tokens",
            max_output_tokens=64000,  # unconfirmed (not found in Context7 docs)
            supports_seed=False,
            description="Claude 3.7 Sonnet (temperature 0-1)",
        ),
    ),
    # Anthropic — everything older: temperature 0..1, top_p exclusive with
    # temperature, top_k accepted.
    _FamilyRule(
        provider="anthropic",
        pattern=r"^claude-",
        rules=ModelParamRules(
            temperature_range=(0.0, 1.0),
            top_p_supported=True,
            top_k_supported=True,
            temp_top_p_exclusive=True,
            tokens_param="max_tokens",
            supports_seed=False,
            description="Claude 4.x/3.x (temperature 0-1)",
        ),
    ),
    # OpenAI — reasoning models (gpt-5 and every later generation, every
    # o-series number, chat-latest): max_completion_tokens required (the live
    # API rejects max_tokens for GPT-6), top_p rejected, temperature locked to
    # the default. The temperature lock is proven for gpt-5; for GPT-6 and
    # later it is assumed by analogy until the live tier proves it.
    _FamilyRule(
        provider="openai",
        pattern=r"^(gpt-(?:[5-9]|\d{2,})|o\d|chat-latest)",
        rules=ModelParamRules(
            temperature_range=(1.0, 1.0),
            temperature_fixed=1.0,
            top_p_supported=False,
            top_k_supported=False,
            tokens_param="max_completion_tokens",
            supports_reasoning_effort=True,
            supports_verbosity=True,
            description="OpenAI reasoning model (temperature fixed at 1)",
        ),
    ),
    # OpenAI — classic chat models.
    _FamilyRule(
        provider="openai",
        pattern=r"",
        rules=ModelParamRules(
            temperature_range=(0.0, 2.0),
            top_p_supported=True,
            tokens_param="max_tokens",
            description="OpenAI chat model (temperature 0-2)",
        ),
    ),
    # Google Gemini.
    _FamilyRule(
        provider="gemini",
        pattern=r"",
        rules=ModelParamRules(
            temperature_range=(0.0, 2.0),
            top_p_supported=True,
            top_k_supported=True,
            tokens_param="max_tokens",
            description="Gemini (temperature 0-2)",
        ),
    ),
    # Local servers — permissive; they ignore what they don't understand.
    _FamilyRule(
        provider="ollama",
        pattern=r"",
        rules=ModelParamRules(
            temperature_range=(0.0, 2.0),
            top_p_supported=True,
            top_k_supported=True,
            description="Ollama (local)",
        ),
    ),
    _FamilyRule(
        provider="lmstudio",
        pattern=r"",
        rules=ModelParamRules(
            temperature_range=(0.0, 2.0),
            top_p_supported=True,
            top_k_supported=True,
            description="LM Studio (local)",
        ),
    ),
]


# --- Registry capability metadata (max output tokens etc.) -------------------

def _load_registry_capabilities() -> Dict[str, Dict[str, Any]]:
    try:
        with open(FALLBACK_PATH, encoding="utf-8") as fh:
            return json.load(fh).get("capabilities", {})
    except Exception as e:  # pragma: no cover - snapshot bundled with the app
        logger.warning(f"model-registry capabilities unavailable: {e}")
        return {}


_REGISTRY_CAPABILITIES = _load_registry_capabilities()


def normalize_provider(provider: str) -> str:
    """Map any app alias/display name ('Google', 'claude', 'LM Studio') to the
    canonical LLM provider id used by LLM_PROVIDERS."""
    key = (provider or "").strip().lower()
    return _PROVIDER_ALIASES.get(key, key)


def strip_route_prefix(model: str) -> str:
    """Remove a route prefix ('anthropic/', 'gemini/', ...) if present."""
    for prefix in _ROUTE_PREFIXES:
        if model.startswith(prefix):
            return model[len(prefix):]
    return model


_PREFIX_TO_PROVIDER = {
    "anthropic/": "anthropic",
    "gemini/": "gemini",
    "vertex_ai/": "gemini",
    "openai/": "openai",
    "azure/": "openai",
    "ollama/": "ollama",
    "ollama_chat/": "ollama",
    "lm_studio/": "lmstudio",
}


# Open-weight OpenAI models (gpt-oss-20b, gpt-oss:120b). Local servers host
# them; the OpenAI API does not, so the name is not evidence of cloud OpenAI.
_OPEN_WEIGHT_GPT = re.compile(r"^gpt-oss(?:[-:._]|$)")


def infer_provider_from_model(model: str, default: str = "openai") -> str:
    """Best-effort provider id from a (possibly prefixed) model string.

    For call sites that only receive a model name (e.g. analyze_image).
    An open-weight ``gpt-oss`` id returns ``default``: it is a local model.
    """
    m = (model or "").strip().lower()
    bare = strip_route_prefix(m)
    if _OPEN_WEIGHT_GPT.match(bare) and (bare == m or m.startswith("openai/")):
        # Local servers list it as "gpt-oss-20b", "gpt-oss:20b" or
        # "openai/gpt-oss-20b" (publisher name, not a route).
        return normalize_provider(default)
    for prefix, provider in _PREFIX_TO_PROVIDER.items():
        if m.startswith(prefix):
            return provider
    if bare.startswith("claude"):
        return "anthropic"
    if bare.startswith("gemini"):
        return "gemini"
    if re.match(r"^(gpt|o\d|chat-latest|davinci)", bare):
        return "openai"
    return normalize_provider(default)


def _registry_max_output_tokens(model_id: str) -> Optional[int]:
    caps = _REGISTRY_CAPABILITIES.get(model_id)
    if caps:
        return caps.get("max_output_tokens")
    return None


def get_param_rules(provider: str, model: str) -> ModelParamRules:
    """Resolve the parameter rules for a provider/model.

    Curated family rules are authoritative; the model registry fills in
    ``max_output_tokens`` when a rule does not set one. Unknown providers get permissive
    defaults so local/custom endpoints keep working.
    """
    provider_id = normalize_provider(provider)
    model_id = strip_route_prefix((model or "").strip())
    model_lc = model_id.lower()

    rules = None
    for fam in _FAMILY_RULES:
        if fam.provider == provider_id and re.search(fam.pattern, model_lc):
            # Copy so per-call mutation (max_output_tokens) never leaks back.
            rules = ModelParamRules(**vars(fam.rules))
            break
    if rules is None:
        rules = ModelParamRules(description=f"unknown provider '{provider_id}' (permissive)")

    if rules.max_output_tokens is None:
        rules.max_output_tokens = _registry_max_output_tokens(model_id)
    return rules


# --- Validation / corralling -------------------------------------------------

def _require_number(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LLMParamError(f"{name} must be a number, got {value!r}")
    return float(value)


def validate_params(
    provider: str,
    model: str,
    params: "LLMParams | Dict[str, Any] | None",
    *,
    strict: bool = False,
    on_warning: Optional[Callable[[str], None]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """Validate and corral chat params for one provider/model.

    Returns ``(kwargs, warnings)`` where ``kwargs`` contains
    only parameters the model accepts (already renamed, clamped, capped).

    Corralling (logged + reported via ``on_warning``):
      - out-of-range numerics are clamped to the nearest bound,
      - unsupported parameters are dropped,
      - fixed-value parameters (GPT-5 temperature) are dropped unless equal,
      - ``max_tokens`` above the model's output ceiling is capped.

    Raises ``LLMParamError`` for values that cannot be corralled (wrong type,
    non-positive token counts, unknown reasoning effort/verbosity), or for any
    needed correction when ``strict=True``.
    """
    if params is None:
        params = LLMParams()
    elif isinstance(params, dict):
        params = LLMParams.from_dict(params)

    rules = get_param_rules(provider, model)
    model = strip_route_prefix((model or "").strip())
    warnings: List[str] = []
    out: Dict[str, Any] = {}

    def corral(message: str) -> None:
        if strict:
            raise LLMParamError(message)
        warnings.append(message)
        logger.warning(f"LLM param corralled for {provider}/{model}: {message}")
        if on_warning:
            on_warning(message)

    # temperature -------------------------------------------------------------
    if params.temperature is not None:
        temp = _require_number("temperature", params.temperature)
        if rules.temperature_range is None:
            corral(f"temperature={temp} not supported by {model} "
                   f"({rules.description}); dropped")
        elif rules.temperature_fixed is not None and temp != rules.temperature_fixed:
            corral(f"temperature={temp} not supported by {model} "
                   f"({rules.description}); only {rules.temperature_fixed} allowed — dropped")
        elif rules.temperature_fixed is not None:
            pass  # equals the only accepted value; provider default — omit
        else:
            lo, hi = rules.temperature_range
            if temp < lo or temp > hi:
                clamped = min(max(temp, lo), hi)
                corral(f"temperature={temp} outside [{lo}, {hi}] for {model}; "
                       f"clamped to {clamped}")
                temp = clamped
            out["temperature"] = temp

    # top_p / top_k -----------------------------------------------------------
    if params.top_p is not None:
        top_p = _require_number("top_p", params.top_p)
        if not rules.top_p_supported:
            corral(f"top_p={top_p} not supported by {model}; dropped")
        elif rules.temp_top_p_exclusive and "temperature" in out:
            corral(f"{model} accepts temperature or top_p, not both; top_p dropped")
        else:
            if top_p < 0.0 or top_p > 1.0:
                clamped = min(max(top_p, 0.0), 1.0)
                corral(f"top_p={top_p} outside [0, 1]; clamped to {clamped}")
                top_p = clamped
            out["top_p"] = top_p

    if params.top_k is not None:
        if isinstance(params.top_k, bool) or not isinstance(params.top_k, int):
            raise LLMParamError(f"top_k must be an integer, got {params.top_k!r}")
        if not rules.top_k_supported:
            corral(f"top_k={params.top_k} not supported by {model}; dropped")
        elif params.top_k < 1:
            raise LLMParamError(f"top_k must be >= 1, got {params.top_k}")
        else:
            out["top_k"] = params.top_k

    # max tokens --------------------------------------------------------------
    if params.max_tokens is not None:
        if isinstance(params.max_tokens, bool) or not isinstance(params.max_tokens, int):
            raise LLMParamError(f"max_tokens must be an integer, got {params.max_tokens!r}")
        if params.max_tokens <= 0:
            raise LLMParamError(f"max_tokens must be positive, got {params.max_tokens}")
        tokens = params.max_tokens
        ceiling = rules.max_output_tokens
        if ceiling and tokens > ceiling:
            corral(f"max_tokens={tokens} exceeds {model} output limit {ceiling}; capped")
            tokens = ceiling
        out[rules.tokens_param] = tokens

    # reasoning effort / verbosity -------------------------------------------
    if params.reasoning_effort is not None:
        effort = str(params.reasoning_effort).strip().lower()
        if effort not in _REASONING_EFFORT_LEVELS:
            raise LLMParamError(
                f"unknown reasoning_effort {params.reasoning_effort!r}; "
                f"expected one of {sorted(_REASONING_EFFORT_LEVELS)}")
        if rules.supports_reasoning_effort:
            out["reasoning_effort"] = effort
        else:
            corral(f"reasoning_effort={effort!r} not supported by {model}; dropped")

    if params.verbosity is not None:
        verbosity = str(params.verbosity).strip().lower()
        if verbosity not in _VERBOSITY_LEVELS:
            raise LLMParamError(
                f"unknown verbosity {params.verbosity!r}; "
                f"expected one of {sorted(_VERBOSITY_LEVELS)}")
        if rules.supports_verbosity:
            out["verbosity"] = verbosity
        else:
            corral(f"verbosity={verbosity!r} not supported by {model}; dropped")

    # passthrough parameters ---------------------------------------------------
    if params.response_format is not None:
        if rules.supports_response_format:
            out["response_format"] = params.response_format
        else:
            corral(f"response_format not supported by {model}; dropped")
    if params.timeout is not None:
        out["timeout"] = params.timeout
    if params.seed is not None:
        if rules.supports_seed:
            out["seed"] = params.seed
        else:
            corral(f"seed not supported by {model}; dropped")
    if params.stop is not None:
        out["stop"] = params.stop

    return out, warnings


def _is_api_key_mode(auth_mode: str) -> bool:
    """True for the API-key spellings of the Google auth mode; every other
    value (gcloud, adc, "Google Cloud Account") means Google Cloud login."""
    return auth_mode.strip().lower().replace("_", "-").replace(" ", "-") == "api-key"


def build_completion_kwargs(
    provider: str,
    model: str,
    messages: List[Dict[str, Any]],
    params: "LLMParams | Dict[str, Any] | None" = None,
    *,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    auth_mode: Optional[str] = None,
    vertex_project: Optional[str] = None,
    strict: bool = False,
    on_warning: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Build a complete, validated kwargs dict for ``chameleon_llm.completion()``.

    Handles route prefixing per provider (``anthropic/``, ``gemini/`` vs
    ``vertex_ai/`` by auth mode, bare model + ``api_base`` for LM Studio) and
    merges the corralled parameters from :func:`validate_params`.

    Gemini routing: ``auth_mode`` ('api-key' -> ``gemini/``, 'gcloud'/'adc' ->
    ``vertex_ai/``) wins when given, also over a ``gemini/`` or ``vertex_ai/``
    prefix already on the model id (the id is re-routed, with a warning), so
    Google Cloud login never sends a key. Without ``auth_mode`` a Google
    prefix is honoured, and for a bare id the presence of ``api_key`` decides
    (present -> Google AI Studio, absent -> Vertex AI/ADC). Callers relying on
    the ``GEMINI_API_KEY`` env var must pass ``auth_mode='api-key'``.

    ``api_key`` is the key of ``provider``. When ``model`` carries the route
    prefix of another provider (``ollama/...`` under Google, ``anthropic/...``
    under OpenAI), the prefix is honoured but the key is not sent (WARNING and
    ``on_warning``; ``LLMParamError`` when ``strict``). A local provider's own
    token still passes on its own route.

    ``vertex_project`` is the Google Cloud project saved in Settings (see
    :func:`saved_vertex_project`). It is sent on the ``vertex_ai/`` route only;
    without it the adapter falls back to ``GOOGLE_CLOUD_PROJECT`` and then to
    the project of the Application Default Credentials, which may be another
    project than the one the user configured.
    """
    if not model or not str(model).strip():
        raise LLMParamError(f"no model specified for provider {provider!r}")

    provider_id = normalize_provider(provider)
    model_id = str(model).strip()
    # Set when the model id carries the route prefix of another provider.
    foreign_route = None
    # Set when an explicit Google auth mode overrides a Google route prefix.
    reroute_message = None

    if provider_id == "lmstudio":
        # OpenAI-compatible local server via api_base. Checked before the
        # route-prefix test: LM Studio model ids often contain slashes
        # (e.g. 'lmstudio-community/Meta-Llama-3-8B-GGUF') that are not routes.
        routed_model = model_id
        if api_base is None:
            config = LLM_PROVIDERS.get("lmstudio")
            api_base = config.endpoint if config else None
    elif any(model_id.startswith(p) for p in _ROUTE_PREFIXES):
        routed_model = model_id  # caller already prefixed — honor it
        prefix = next(p for p in _ROUTE_PREFIXES if model_id.startswith(p))
        owner = _PREFIX_TO_PROVIDER.get(prefix)
        if owner and owner != provider_id:
            foreign_route = prefix
        elif provider_id == "gemini" and auth_mode:
            # An explicit auth mode decides between the two Google routes,
            # also for an id that already names one: "gemini/x" with Google
            # Cloud login is a Vertex request (and must not carry a key), and
            # "vertex_ai/x" in API-key mode is a Gemini API request.
            target = "gemini/" if _is_api_key_mode(auth_mode) else "vertex_ai/"
            if prefix != target:
                routed_model = target + model_id[len(prefix):]
                reroute_message = (
                    f"model '{model_id}' sent on the '{target}' route: the "
                    f"Google auth mode is '{auth_mode}'")
    elif provider_id == "gemini":
        if auth_mode:
            use_api_key_route = _is_api_key_mode(auth_mode)
        else:
            use_api_key_route = bool(api_key)
        routed_model = (f"gemini/{model_id}" if use_api_key_route
                        else f"vertex_ai/{model_id}")
    else:
        prefix = get_provider_prefix(provider_id)
        routed_model = f"{prefix}{model_id}" if prefix else model_id

    kwargs, _ = validate_params(
        provider_id, model_id, params, strict=strict, on_warning=on_warning)

    kwargs["model"] = routed_model
    kwargs["messages"] = messages
    if reroute_message:
        if strict:
            raise LLMParamError(reroute_message)
        logger.warning(f"LLM request re-routed: {reroute_message}")
        if on_warning:
            on_warning(reroute_message)
    if api_key and foreign_route:
        # The key belongs to ``provider_id``; the prefix sends the request to
        # another provider (a local server, or a different cloud). Sending it
        # would hand one provider's credential to another.
        message = (f"API key for provider '{provider_id}' not sent: the model "
                   f"id selects the '{foreign_route}' route, which belongs to "
                   f"another provider")
        if strict:
            raise LLMParamError(message)
        logger.warning(f"LLM request for {routed_model}: {message}")
        if on_warning:
            on_warning(message)
        api_key = None
    # The vertex_ai route signs in with the Google Cloud login; a stored API
    # key would only be dropped (with a warning) by the adapter.
    if api_key and not routed_model.startswith("vertex_ai/"):
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base
    if routed_model.startswith("vertex_ai/"):
        project = vertex_project.strip() if isinstance(vertex_project, str) else ""
        if project:
            kwargs["vertex_project"] = project
    return kwargs


def saved_vertex_project(config: Any) -> Optional[str]:
    """The Google Cloud project saved in Settings (``gcloud_project_id``).

    ``config`` is a ``ConfigManager`` or a plain dict; anything else, a
    missing entry or a non-string value gives ``None``.
    """
    getter = getattr(config, "get", None)
    if getter is None:
        return None
    try:
        value = getter("gcloud_project_id")
    except Exception:
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


_GCLOUD_AUTH_MODES = frozenset({"gcloud", "adc", "google cloud account"})


def _normalize_google_auth_mode(value: Any) -> Optional[str]:
    """'gcloud', 'api-key', or None when ``value`` is not a usable setting."""
    if not isinstance(value, str) or not value.strip():
        return None
    return "gcloud" if value.strip().lower() in _GCLOUD_AUTH_MODES else "api-key"


def _saved_settings() -> Any:
    """The app's saved Settings (a ``ConfigManager``), or None when they
    cannot be read. A separate function so tests can replace it."""
    try:
        from core.config import ConfigManager
        return ConfigManager()
    except Exception as exc:  # never let a settings problem break a request
        logger.debug(f"saved Settings unavailable for Google auth lookup: {exc}")
        return None


def _google_settings(config: Any, want_key: bool
                     ) -> Tuple[str, Optional[str], Optional[str]]:
    """``(auth_mode, api_key, project)``; the saved Settings are opened at
    most once. See :func:`google_auth_settings` and :func:`google_credentials`."""
    mode = None
    key = None
    getter = getattr(config, "get", None)
    if callable(getter):
        try:
            mode = _normalize_google_auth_mode(getter("auth_mode"))
        except Exception:
            mode = None
        if want_key:
            try:
                value = getter("google_api_key")
            except Exception:
                value = None
            key = value.strip() if isinstance(value, str) and value.strip() else None
    project = saved_vertex_project(config)

    needs_key = want_key and key is None and mode != "gcloud"
    if mode is None or project is None or needs_key:
        saved = _saved_settings()
        if saved is not None:
            try:
                saved_mode = _normalize_google_auth_mode(saved.get("auth_mode"))
            except Exception:
                saved_mode = None
            if mode is None:
                mode = saved_mode
            if project is None:
                project = saved_vertex_project(saved)
            # get_api_key is the only way keys are read. Never in Google
            # Cloud mode (ours or the saved one): there it answers with an
            # OAuth access token, which is not a Gemini API key.
            if (want_key and key is None and (mode or "api-key") == "api-key"
                    and saved_mode != "gcloud"):
                try:
                    value = saved.get_api_key("google")
                except Exception as exc:
                    logger.debug(f"Google API key lookup failed: {exc}")
                    value = None
                key = value.strip() if isinstance(value, str) and value.strip() else None
    mode = mode or "api-key"
    if mode == "gcloud":
        key = None
    return mode, key, project


def google_auth_settings(config: Any = None) -> Tuple[str, Optional[str]]:
    """``(auth_mode, project)`` for Google: 'gcloud' (Google Cloud login) or
    'api-key', and the Google Cloud project saved in Settings.

    ``config`` is whatever the caller holds: a ``ConfigManager`` or a
    provider-config dict. Values it carries (``auth_mode``,
    ``gcloud_project_id``) win. The provider-config dicts the GUI builds carry
    neither, so anything missing is read from the saved Settings.
    """
    mode, _key, project = _google_settings(config, want_key=False)
    return mode, project


def google_credentials(config: Any = None) -> Tuple[str, Optional[str], Optional[str]]:
    """``(auth_mode, api_key, project)`` for an object that sends Google
    requests and keeps its own settings.

    As :func:`google_auth_settings`, plus the Gemini API key. In 'api-key'
    mode the key is ``config``'s ``google_api_key`` when it has one, else the
    key saved in Settings, read once through ``ConfigManager.get_api_key``
    (a key kept in the OS keyring is in no config dict). In 'gcloud' mode the
    key is always None and no lookup is made.

    Callers pass the returned mode to the kwargs builder on every request, so
    'api-key' mode with no key stays on ``gemini/`` and fails with an
    authentication error; only 'gcloud' goes to ``vertex_ai/``.
    """
    return _google_settings(config, want_key=True)


def route_completion_kwargs(
    provider: str,
    model: str,
    messages: List[Dict[str, Any]],
    params: "LLMParams | Dict[str, Any] | None" = None,
    *,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    auth_mode: Optional[str] = None,
    vertex_project: Optional[str] = None,
    on_warning: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """:func:`build_completion_kwargs` for callers that hold a provider alias
    or display name ("Google", "Anthropic", "LM Studio") and may rely on a
    Gemini key in the environment.

    Without an explicit ``auth_mode``, a Gemini model uses the API-key route
    when a key is configured (``api_key`` or ``GEMINI_API_KEY`` /
    ``GOOGLE_API_KEY``), otherwise the Vertex AI (Google Cloud login) route.
    """
    provider_id = normalize_provider(provider)
    if provider_id == "gemini" and not auth_mode:
        has_key = bool(api_key or os.environ.get("GEMINI_API_KEY")
                       or os.environ.get("GOOGLE_API_KEY"))
        auth_mode = "api-key" if has_key else "gcloud"
    return build_completion_kwargs(
        provider_id, model, messages, params,
        api_key=api_key or None, api_base=api_base, auth_mode=auth_mode,
        vertex_project=vertex_project, on_warning=on_warning)
