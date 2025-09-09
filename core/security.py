"""
Security utilities for ImageAI application.

This module provides security-related functionality including:
- Path traversal validation
- API key encryption/decryption
- Rate limiting for API calls
"""

import hashlib
import hmac
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Dict, Optional, Any

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

logger = logging.getLogger(__name__)


class PathValidator:
    """Validates file paths to prevent directory traversal attacks."""
    
    @staticmethod
    def is_safe_path(path: Path, base_dir: Path) -> bool:
        """
        Check if a path is safe (doesn't escape base directory).
        
        Args:
            path: Path to validate
            base_dir: Base directory that path should not escape
            
        Returns:
            True if path is safe, False otherwise
        """
        try:
            # Resolve both paths to absolute paths
            resolved_path = path.resolve()
            resolved_base = base_dir.resolve()
            
            # Check if the resolved path is within the base directory
            resolved_path.relative_to(resolved_base)
            return True
        except (ValueError, RuntimeError):
            # Path is outside base directory or resolution failed
            return False
    
    @staticmethod
    def validate_filename(filename: str) -> bool:
        """
        Validate that a filename doesn't contain dangerous characters.
        
        Args:
            filename: Filename to validate
            
        Returns:
            True if filename is safe, False otherwise
        """
        # List of characters that shouldn't be in filenames
        dangerous_chars = ['..', '/', '\\', '\x00', ':', '*', '?', '"', '<', '>', '|']
        
        for char in dangerous_chars:
            if char in filename:
                return False
        
        # Check for control characters
        if any(ord(c) < 32 for c in filename):
            return False
        
        return True


class SecureKeyStorage:
    """Manages secure storage of API keys using system keyring when available."""
    
    SERVICE_NAME = "ImageAI"
    
    def __init__(self):
        """Initialize secure key storage."""
        self.keyring_available = KEYRING_AVAILABLE
        if not self.keyring_available:
            logger.info("Keyring library not available. Using file-based storage.")
    
    def store_key(self, provider: str, key: str) -> bool:
        """
        Store an API key securely.
        
        Args:
            provider: Provider name (e.g., 'google', 'openai')
            key: API key to store
            
        Returns:
            True if stored successfully, False otherwise
        """
        if not self.keyring_available:
            return False
        
        try:
            keyring.set_password(
                self.SERVICE_NAME,
                f"{provider}_api_key",
                key
            )
            logger.info(f"API key for {provider} stored in system keyring")
            return True
        except Exception as e:
            logger.warning(f"Failed to store key in keyring: {e}")
            return False
    
    def retrieve_key(self, provider: str) -> Optional[str]:
        """
        Retrieve an API key from secure storage.
        
        Args:
            provider: Provider name (e.g., 'google', 'openai')
            
        Returns:
            API key if found, None otherwise
        """
        if not self.keyring_available:
            return None
        
        try:
            key = keyring.get_password(
                self.SERVICE_NAME,
                f"{provider}_api_key"
            )
            if key:
                logger.debug(f"Retrieved API key for {provider} from keyring")
            return key
        except Exception as e:
            logger.debug(f"Failed to retrieve key from keyring: {e}")
            return None
    
    def delete_key(self, provider: str) -> bool:
        """
        Delete an API key from secure storage.
        
        Args:
            provider: Provider name (e.g., 'google', 'openai')
            
        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.keyring_available:
            return False
        
        try:
            keyring.delete_password(
                self.SERVICE_NAME,
                f"{provider}_api_key"
            )
            logger.info(f"API key for {provider} deleted from keyring")
            return True
        except Exception as e:
            logger.warning(f"Failed to delete key from keyring: {e}")
            return False


class RateLimiter:
    """Implements rate limiting for API calls."""
    
    def __init__(self):
        """Initialize rate limiter."""
        self._call_history: Dict[str, list] = defaultdict(list)
        self._lock = Lock()
        
        # Default rate limits per provider
        self._limits = {
            'google': {'calls': 60, 'window': 60},  # 60 calls per minute
            'openai': {'calls': 50, 'window': 60},  # 50 calls per minute
            'stability': {'calls': 150, 'window': 10},  # 150 calls per 10 seconds
            'default': {'calls': 100, 'window': 60}  # Default: 100 calls per minute
        }
    
    def set_limit(self, provider: str, calls: int, window: int):
        """
        Set custom rate limit for a provider.
        
        Args:
            provider: Provider name
            calls: Maximum number of calls
            window: Time window in seconds
        """
        self._limits[provider] = {'calls': calls, 'window': window}
    
    def check_rate_limit(self, provider: str, wait: bool = True) -> bool:
        """
        Check if an API call is within rate limits.
        
        Args:
            provider: Provider name
            wait: If True, wait until rate limit allows the call
            
        Returns:
            True if call is allowed, False if rate limited
        """
        with self._lock:
            now = time.time()
            
            # Get limits for this provider
            limits = self._limits.get(provider, self._limits['default'])
            max_calls = limits['calls']
            window = limits['window']
            
            # Clean old entries
            cutoff = now - window
            self._call_history[provider] = [
                t for t in self._call_history[provider] if t > cutoff
            ]
            
            # Check if we're at the limit
            if len(self._call_history[provider]) >= max_calls:
                if not wait:
                    return False
                
                # Calculate wait time
                oldest_call = min(self._call_history[provider])
                wait_time = window - (now - oldest_call) + 0.1
                
                if wait_time > 0:
                    logger.info(f"Rate limit reached for {provider}. Waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    
                    # Clean again after waiting
                    now = time.time()
                    cutoff = now - window
                    self._call_history[provider] = [
                        t for t in self._call_history[provider] if t > cutoff
                    ]
            
            # Record this call
            self._call_history[provider].append(now)
            return True
    
    def get_remaining_calls(self, provider: str) -> tuple[int, float]:
        """
        Get remaining calls and time until reset.
        
        Args:
            provider: Provider name
            
        Returns:
            Tuple of (remaining calls, seconds until reset)
        """
        with self._lock:
            now = time.time()
            
            # Get limits for this provider
            limits = self._limits.get(provider, self._limits['default'])
            max_calls = limits['calls']
            window = limits['window']
            
            # Clean old entries
            cutoff = now - window
            self._call_history[provider] = [
                t for t in self._call_history[provider] if t > cutoff
            ]
            
            remaining = max_calls - len(self._call_history[provider])
            
            if self._call_history[provider]:
                oldest_call = min(self._call_history[provider])
                reset_time = window - (now - oldest_call)
            else:
                reset_time = 0
            
            return remaining, max(0, reset_time)


# Global instances
path_validator = PathValidator()
secure_storage = SecureKeyStorage()
rate_limiter = RateLimiter()