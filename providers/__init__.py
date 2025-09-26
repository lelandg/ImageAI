"""Image generation providers for ImageAI."""

import sys
import os
import warnings
from typing import Dict, Type, Optional, Any

# Suppress warnings before importing providers
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
warnings.filterwarnings('ignore', message='.*GetPrototype.*')
warnings.filterwarnings('ignore', category=FutureWarning)

# Ensure protobuf is patched if not already done by main.py
if 'google.protobuf.message_factory' in sys.modules:
    try:
        _mf = sys.modules['google.protobuf.message_factory']
        if hasattr(_mf, 'MessageFactory'):
            mf_class = _mf.MessageFactory
            if not hasattr(mf_class, 'GetPrototype') and hasattr(mf_class, 'GetMessageClass'):
                mf_class.GetPrototype = lambda self, desc: self.GetMessageClass(desc)
    except:
        pass

if 'google.protobuf.symbol_database' in sys.modules:
    try:
        _sdb = sys.modules['google.protobuf.symbol_database']
        if hasattr(_sdb, 'Default'):
            db = _sdb.Default()
            if not hasattr(db.__class__, 'GetPrototype') and hasattr(db.__class__, 'GetMessageClass'):
                db.__class__.GetPrototype = lambda self, desc: self.GetMessageClass(desc)
    except:
        pass

from .base import ImageProvider

# Lazy load providers to avoid import errors when dependencies are missing
_PROVIDERS = None

# Cache for loaded provider instances
_PROVIDER_CACHE = {}

def _get_providers() -> Dict[str, Type[ImageProvider]]:
    """Lazy load provider classes."""
    global _PROVIDERS
    if _PROVIDERS is None:
        import sys
        import io
        import contextlib
        
        _PROVIDERS = {}
        
        # Create a context manager to suppress stderr during imports
        @contextlib.contextmanager
        def suppress_stderr():
            """Temporarily suppress stderr to hide protobuf errors."""
            old_stderr = sys.stderr
            sys.stderr = io.StringIO()
            try:
                yield
            finally:
                sys.stderr = old_stderr
        
        import logging

        # Try to import Google provider
        try:
            with suppress_stderr():
                from .google import GoogleProvider
                _PROVIDERS["google"] = GoogleProvider
        except Exception as e:
            logging.debug(f"Could not load Google provider: {e}")
        
        # Try to import OpenAI provider
        try:
            with suppress_stderr():
                from .openai import OpenAIProvider
                _PROVIDERS["openai"] = OpenAIProvider
        except Exception as e:
            logging.debug(f"Could not load OpenAI provider: {e}")
        
        # Try to import Stability AI provider (may have protobuf issues)
        try:
            with suppress_stderr():
                from .stability import StabilityProvider
                _PROVIDERS["stability"] = StabilityProvider
        except (ImportError, AttributeError) as e:
            # AttributeError can occur with protobuf conflicts
            import logging
            logging.debug(f"Could not load Stability provider: {e}")
            pass
        
        # Try to import Local SD provider (may have TensorFlow/protobuf issues)
        try:
            with suppress_stderr():
                from .local_sd import LocalSDProvider
                _PROVIDERS["local_sd"] = LocalSDProvider
        except (ImportError, AttributeError) as e:
            # AttributeError can occur with protobuf/TensorFlow conflicts
            import logging
            logging.debug(f"Could not load Local SD provider: {e}")
            pass

        # Try to import Midjourney provider
        try:
            with suppress_stderr():
                from .midjourney_provider import MidjourneyProvider
                _PROVIDERS["midjourney"] = MidjourneyProvider
        except Exception as e:
            import logging
            logging.debug(f"Could not load Midjourney provider: {e}")
            pass

    return _PROVIDERS


def get_provider(name: str, config: Optional[Dict[str, Any]] = None, use_cache: bool = True) -> ImageProvider:
    """
    Get a provider instance by name.
    
    Args:
        name: Provider name (google, openai, etc.)
        config: Provider configuration including API keys
        use_cache: If True, return cached provider if available
    
    Returns:
        Provider instance
    
    Raises:
        ValueError: If provider name is unknown
    """
    global _PROVIDER_CACHE
    
    providers = _get_providers()
    name = name.lower().strip()
    
    if name not in providers:
        available = ', '.join(providers.keys()) if providers else 'none (no providers available)'
        raise ValueError(f"Unknown provider: {name}. Available: {available}")
    
    # Check cache first
    if use_cache and name in _PROVIDER_CACHE:
        # Update config if provided
        if config:
            cached = _PROVIDER_CACHE[name]
            cached.api_key = config.get('api_key', cached.api_key)
            cached.auth_mode = config.get('auth_mode', cached.auth_mode)
        return _PROVIDER_CACHE[name]
    
    # Create new provider instance
    provider_class = providers[name]
    provider_instance = provider_class(config or {})
    
    # Cache it
    if use_cache:
        _PROVIDER_CACHE[name] = provider_instance
    
    return provider_instance


def list_providers() -> list[str]:
    """Get list of available provider names."""
    providers = _get_providers()
    return list(providers.keys())


def clear_provider_cache():
    """Clear the provider cache."""
    global _PROVIDER_CACHE
    _PROVIDER_CACHE = {}


def preload_provider(name: str, config: Optional[Dict[str, Any]] = None) -> None:
    """
    Preload a provider into cache.
    
    Args:
        name: Provider name to preload
        config: Provider configuration
    """
    print(f"Loading provider: {name}...")
    get_provider(name, config, use_cache=True)


__all__ = [
    "ImageProvider",
    "get_provider",
    "list_providers",
    "clear_provider_cache",
    "preload_provider",
]
