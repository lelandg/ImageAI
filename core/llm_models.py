"""
Centralized LLM provider and model definitions.
Single source of truth for all LLM model lists across the application.

When adding new models or providers, update this file ONLY.
All UI components and configuration will automatically use the updated lists.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import logging
import requests

logger = logging.getLogger(__name__)


@dataclass
class LLMProvider:
    """Represents an LLM provider with available models and configuration."""
    id: str
    display_name: str
    models: List[str]
    enabled_by_default: bool = True
    requires_api_key: bool = True
    endpoint: Optional[str] = None
    prefix: str = ''  # LiteLLM prefix (e.g., 'gemini/', 'ollama/')


# Define all LLM providers and their models
# Models are ordered from newest/most capable to older/smaller
LLM_PROVIDERS = {
    'openai': LLMProvider(
        id='openai',
        display_name='OpenAI',
        models=[
            # GPT-5 Series (Latest - December 2025)
            'gpt-5.2-pro',                     # GPT 5.2 Pro (newest flagship)
            'gpt-5.2',                         # GPT 5.2 (latest stable)
            'gpt-5.1',                         # GPT 5.1
            'gpt-5-pro',                       # GPT 5 Pro
            'gpt-5',                           # GPT 5
            'gpt-5-mini',                      # GPT 5 Mini (balanced)
            'gpt-5-nano',                      # GPT 5 Nano (fastest)
            # Reasoning Models (o-series)
            'o4-mini',                         # O4 Mini (fast reasoning)
            'o3-pro',                          # O3 Pro (advanced reasoning)
            'o3',                              # O3 (reasoning)
            'o3-mini',                         # O3 Mini (fast reasoning)
            'o1-pro',                          # O1 Pro (original reasoning)
            'o1',                              # O1 (original reasoning)
            # GPT-4 Series (Previous Generation)
            'gpt-4.1',                         # GPT 4.1 (stable)
            'gpt-4.1-mini',                    # GPT 4.1 Mini
            'gpt-4.1-nano',                    # GPT 4.1 Nano
            'gpt-4o',                          # GPT-4o (multimodal)
            'gpt-4o-mini',                     # GPT-4o Mini
            'gpt-4-turbo',                     # GPT-4 Turbo
        ],
        enabled_by_default=True,
        requires_api_key=True,
        prefix=''  # No prefix for OpenAI
    ),

    'anthropic': LLMProvider(
        id='anthropic',
        display_name='Anthropic',
        models=[
            # Claude 4.5 Series (Latest - November 2025)
            'claude-opus-4-5-20251101',      # Opus 4.5: Most intelligent, $5/$25 per 1M
            'claude-sonnet-4-5-20250514',    # Sonnet 4.5: Best for agents, $3/$15 per 1M
            # Claude 4 Series (May 2025)
            'claude-opus-4-20250514',        # Opus 4: Best coding model, $15/$75 per 1M
            'claude-sonnet-4-20250514',      # Sonnet 4: Balanced coding, $3/$15 per 1M
            # Claude 3.7 Series
            'claude-3-7-sonnet-20250219',    # Extended thinking, $3/$15 per 1M
            # Claude 3.5 Series
            'claude-3-5-sonnet-20241022',    # Best speed/intelligence balance
            'claude-3-5-haiku-20241022',     # Fastest, $0.80/$4 per 1M
        ],
        enabled_by_default=True,
        requires_api_key=True,
        prefix='anthropic/'  # LiteLLM requires "anthropic/" prefix
    ),

    'gemini': LLMProvider(
        id='gemini',
        display_name='Google',
        models=[
            # Gemini 3 Series (Latest - December 2025)
            'gemini-3-pro-preview',            # Gemini 3 Pro (state-of-the-art reasoning, 1M context)
            'gemini-3-flash-preview',          # Gemini 3 Flash (frontier intelligence, fast, 1M context)
            # Gemini 2.5 Series (Stable - June 2025)
            'gemini-2.5-pro',                  # Gemini 2.5 Pro (complex reasoning, 1M context)
            'gemini-2.5-flash',                # Gemini 2.5 Flash (price-performance, 1M context)
            'gemini-2.5-flash-lite',           # Gemini 2.5 Flash Lite (cost-efficient, 1M context)
            # Gemini 2.0 Series (Previous Generation)
            'gemini-2.0-flash',                # Gemini 2.0 Flash (1M context, 8K output)
            'gemini-2.0-flash-lite',           # Gemini 2.0 Flash Lite
        ],
        enabled_by_default=True,
        requires_api_key=True,
        prefix='gemini/'
    ),

    'ollama': LLMProvider(
        id='ollama',
        display_name='Ollama',
        models=[
            'llama3.2:latest',
            'llama3.1:8b',
            'mistral:7b',
            'mixtral:8x7b',
            'phi3:medium'
        ],
        enabled_by_default=False,
        requires_api_key=False,
        endpoint='http://localhost:11434',
        prefix='ollama/'
    ),

    'lmstudio': LLMProvider(
        id='lmstudio',
        display_name='LM Studio',
        models=[
            'local-model',
            'custom-model'
        ],
        enabled_by_default=False,
        requires_api_key=False,
        endpoint='http://localhost:1234/v1',
        prefix='openai/'  # LM Studio uses OpenAI-compatible API
    )
}


# Helper functions for easy access

def get_provider_models(provider_id: str) -> List[str]:
    """
    Get model list for a provider.

    Args:
        provider_id: Provider identifier (e.g., 'openai', 'anthropic')

    Returns:
        List of model names for the provider
    """
    provider_id_lower = provider_id.lower()
    return LLM_PROVIDERS[provider_id_lower].models if provider_id_lower in LLM_PROVIDERS else []


def get_all_provider_ids() -> List[str]:
    """
    Get all provider IDs.

    Returns:
        List of provider identifiers
    """
    return list(LLM_PROVIDERS.keys())


def get_provider_display_name(provider_id: str) -> str:
    """
    Get display name for a provider.

    Args:
        provider_id: Provider identifier

    Returns:
        Human-readable display name
    """
    provider_id_lower = provider_id.lower()
    return LLM_PROVIDERS[provider_id_lower].display_name if provider_id_lower in LLM_PROVIDERS else provider_id


def get_provider_config(provider_id: str) -> Optional[LLMProvider]:
    """
    Get full provider configuration.

    Args:
        provider_id: Provider identifier

    Returns:
        LLMProvider object or None if not found
    """
    provider_id_lower = provider_id.lower()
    return LLM_PROVIDERS.get(provider_id_lower)


def get_provider_prefix(provider_id: str) -> str:
    """
    Get LiteLLM prefix for a provider.

    Args:
        provider_id: Provider identifier

    Returns:
        LiteLLM prefix string (e.g., 'gemini/', 'ollama/')
    """
    provider_id_lower = provider_id.lower()
    return LLM_PROVIDERS[provider_id_lower].prefix if provider_id_lower in LLM_PROVIDERS else ''


def get_enabled_providers() -> List[str]:
    """
    Get list of providers enabled by default.

    Returns:
        List of provider IDs that are enabled by default
    """
    return [pid for pid, provider in LLM_PROVIDERS.items() if provider.enabled_by_default]


def format_provider_dict() -> Dict[str, Dict[str, any]]:
    """
    Format providers as dictionary for VideoConfig compatibility.

    Returns:
        Dictionary in VideoConfig.DEFAULT_CONFIG format
    """
    result = {}
    for provider_id, provider in LLM_PROVIDERS.items():
        result[provider_id] = {
            'enabled': provider.enabled_by_default,
            'models': provider.models.copy()
        }
        if provider.endpoint:
            result[provider_id]['endpoint'] = provider.endpoint
    return result


def fetch_ollama_models(endpoint: str = "http://localhost:11434") -> List[str]:
    """
    Fetch installed Ollama models from the Ollama server.

    Args:
        endpoint: Ollama server endpoint

    Returns:
        List of model names (e.g., ['llama3.2:latest', 'dolphin-mixtral:8x7b'])
    """
    try:
        response = requests.get(f"{endpoint}/api/tags", timeout=1)
        response.raise_for_status()
        data = response.json()

        models = []
        if "models" in data:
            for model_info in data["models"]:
                model_name = model_info.get("name", "")
                if model_name:
                    models.append(model_name)
                    logger.debug(f"Found Ollama model: {model_name}")

        logger.info(f"Detected {len(models)} Ollama models")
        return models

    except requests.exceptions.ConnectionError:
        logger.debug(f"Could not connect to Ollama at {endpoint}")
        return []
    except Exception as e:
        logger.debug(f"Error fetching Ollama models: {e}")
        return []


def update_ollama_models(endpoint: str = "http://localhost:11434") -> bool:
    """
    Update the Ollama provider's model list with dynamically detected models.

    Args:
        endpoint: Ollama server endpoint

    Returns:
        True if models were updated, False otherwise
    """
    detected_models = fetch_ollama_models(endpoint)

    if detected_models:
        # Update the LLM_PROVIDERS dictionary
        LLM_PROVIDERS['ollama'].models = detected_models
        logger.info(f"Updated Ollama models: {len(detected_models)} models")
        return True
    else:
        logger.debug("No Ollama models detected, keeping default list")
        return False
