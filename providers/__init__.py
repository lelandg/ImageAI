"""Image generation providers for ImageAI."""

from typing import Dict, Type, Optional, Any
from .base import ImageProvider

# Lazy load providers to avoid import errors when dependencies are missing
_PROVIDERS = None

def _get_providers() -> Dict[str, Type[ImageProvider]]:
    """Lazy load provider classes."""
    global _PROVIDERS
    if _PROVIDERS is None:
        _PROVIDERS = {}
        
        # Try to import Google provider
        try:
            from .google import GoogleProvider
            _PROVIDERS["google"] = GoogleProvider
        except ImportError:
            pass
        
        # Try to import OpenAI provider
        try:
            from .openai import OpenAIProvider
            _PROVIDERS["openai"] = OpenAIProvider
        except ImportError:
            pass
        
        # Try to import Stability AI provider
        try:
            from .stability import StabilityProvider
            _PROVIDERS["stability"] = StabilityProvider
        except (ImportError, AttributeError) as e:
            # AttributeError can occur with protobuf conflicts
            import logging
            logging.debug(f"Could not load Stability provider: {e}")
            pass
        
        # Try to import Local SD provider
        try:
            from .local_sd import LocalSDProvider
            _PROVIDERS["local_sd"] = LocalSDProvider
        except (ImportError, AttributeError) as e:
            # AttributeError can occur with protobuf/TensorFlow conflicts
            import logging
            logging.debug(f"Could not load Local SD provider: {e}")
            pass
    
    return _PROVIDERS


def get_provider(name: str, config: Optional[Dict[str, Any]] = None) -> ImageProvider:
    """
    Get a provider instance by name.
    
    Args:
        name: Provider name (google, openai, etc.)
        config: Provider configuration including API keys
    
    Returns:
        Provider instance
    
    Raises:
        ValueError: If provider name is unknown
    """
    providers = _get_providers()
    name = name.lower().strip()
    
    if name not in providers:
        available = ', '.join(providers.keys()) if providers else 'none (no providers available)'
        raise ValueError(f"Unknown provider: {name}. Available: {available}")
    
    provider_class = providers[name]
    return provider_class(config or {})


def list_providers() -> list[str]:
    """Get list of available provider names."""
    providers = _get_providers()
    return list(providers.keys())


__all__ = [
    "ImageProvider",
    "get_provider",
    "list_providers",
]