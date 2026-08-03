"""
Unified LLM parameter population, validation, and corralling.

Single source of truth for which chat-completion parameters each provider/model
accepts. Every LiteLLM call site builds its kwargs through this module instead
of hand-rolling ``temperature``/``max_tokens`` dicts and per-model hacks.

Contract (see Plans/LLM-Params-Standardization.md):
  - validate values against curated per-family rules,
  - corral where possible (clamp to range, drop unsupported, cap tokens) with a
    logged warning,
  - raise ``LLMParamError`` for values that cannot be corralled (wrong type,
    nonsense values, unknown reasoning effort), or for *any* correction when
    ``strict=True``.

Why curated rules instead of LiteLLM's tables: LiteLLM 1.89.0 claims
``temperature`` is supported on ``anthropic/claude-opus-5``, but the live API
rejects it with a 400 ("`temperature` is deprecated for this model"), so
``litellm.drop_params`` does not protect us. The rules below are verified by
the live boundary tests in ``tests/test_live_llm_params.py``.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.llm_models import LLM_PROVIDERS, get_provider_prefix
from core.model_registry import FALLBACK_PATH

logger = logging.getLogger(__name__)

# Known LiteLLM route prefixes that may arrive glued onto a model id.
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
    description: str = ""  # short label used in warnings


# --- Curated per-family rules (authoritative; verified by live tests) --------

@dataclass
class _FamilyRule:
    provider: str
    pattern: str  # regex matched against the unprefixed, lowercased model id
    rules: ModelParamRules = field(default_factory=ModelParamRules)


_FAMILY_RULES: List[_FamilyRule] = [
    # Anthropic — Claude Opus 4.7/4.8, Opus/Sonnet 5, Fable/Mythos: sampling
    # params removed entirely (400 if sent).
    _FamilyRule(
        provider="anthropic",
        pattern=r"^claude-(opus-4-[78]|opus-5|sonnet-5|fable|mythos)",
        rules=ModelParamRules(
            temperature_range=None,
            top_p_supported=False,
            top_k_supported=False,
            tokens_param="max_tokens",
            supports_reasoning_effort=False,
            description="Claude 5-line (no sampling params)",
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
            description="Claude 4.x/3.x (temperature 0-1)",
        ),
    ),
    # OpenAI — reasoning models (gpt-5.x, o-series, chat-latest): temperature
    # locked to the default, top_p rejected, max_completion_tokens required.
    _FamilyRule(
        provider="openai",
        pattern=r"^(gpt-5|o1|o3|o4|chat-latest)",
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
    """Remove a LiteLLM route prefix ('anthropic/', 'gemini/', ...) if present."""
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


def infer_provider_from_model(model: str, default: str = "openai") -> str:
    """Best-effort provider id from a (possibly prefixed) model string.

    For call sites that only receive a model name (e.g. analyze_image).
    """
    m = (model or "").strip().lower()
    for prefix, provider in _PREFIX_TO_PROVIDER.items():
        if m.startswith(prefix):
            return provider
    bare = strip_route_prefix(m)
    if bare.startswith("claude"):
        return "anthropic"
    if bare.startswith("gemini"):
        return "gemini"
    if re.match(r"^(gpt|o[134]|chat-latest|davinci)", bare):
        return "openai"
    return normalize_provider(default)


def _registry_max_output_tokens(model_id: str) -> Optional[int]:
    caps = _REGISTRY_CAPABILITIES.get(model_id)
    if caps:
        return caps.get("max_output_tokens")
    return None


def _litellm_max_output_tokens(provider_id: str, model_id: str) -> Optional[int]:
    try:
        import litellm
        prefix = get_provider_prefix(provider_id)
        info = litellm.get_model_info(f"{prefix}{model_id}" if prefix else model_id)
        return info.get("max_output_tokens") or info.get("max_tokens")
    except Exception:
        return None


def get_param_rules(provider: str, model: str) -> ModelParamRules:
    """Resolve the parameter rules for a provider/model.

    Curated family rules are authoritative; the model registry (then LiteLLM's
    tables) fill in ``max_output_tokens``. Unknown providers get permissive
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
        rules.max_output_tokens = (
            _registry_max_output_tokens(model_id)
            or _litellm_max_output_tokens(provider_id, model_id)
        )
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

    Returns ``(litellm_kwargs, warnings)`` where ``litellm_kwargs`` contains
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
        out["seed"] = params.seed
    if params.stop is not None:
        out["stop"] = params.stop

    return out, warnings


def build_completion_kwargs(
    provider: str,
    model: str,
    messages: List[Dict[str, Any]],
    params: "LLMParams | Dict[str, Any] | None" = None,
    *,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    strict: bool = False,
    on_warning: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Build a complete, validated kwargs dict for ``litellm.completion()``.

    Handles route prefixing per provider (``anthropic/``, ``gemini/`` vs
    ``vertex_ai/`` by auth mode, bare model + ``api_base`` for LM Studio) and
    merges the corralled parameters from :func:`validate_params`.
    """
    if not model or not str(model).strip():
        raise LLMParamError(f"no model specified for provider {provider!r}")

    provider_id = normalize_provider(provider)
    model_id = str(model).strip()

    if "/" in model_id:
        routed_model = model_id  # caller already prefixed — honor it
    elif provider_id == "gemini":
        # API-key auth -> Google AI Studio; otherwise gcloud/ADC -> Vertex AI.
        routed_model = f"gemini/{model_id}" if api_key else f"vertex_ai/{model_id}"
    elif provider_id == "lmstudio":
        routed_model = model_id  # OpenAI-compatible local server via api_base
        if api_base is None:
            config = LLM_PROVIDERS.get("lmstudio")
            api_base = config.endpoint if config else None
    else:
        prefix = get_provider_prefix(provider_id)
        routed_model = f"{prefix}{model_id}" if prefix else model_id

    kwargs, _ = validate_params(
        provider_id, model_id, params, strict=strict, on_warning=on_warning)

    kwargs["model"] = routed_model
    kwargs["messages"] = messages
    if api_key:
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base
    return kwargs
