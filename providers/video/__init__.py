"""Video providers for ImageAI."""

from enum import Enum
from typing import Optional

from .base_lipsync import BaseLipSyncProvider


class LipSyncBackend(Enum):
    """Available lip-sync backends."""
    MUSETALK = "musetalk"
    DID = "did"  # Future: D-ID cloud API


def get_lipsync_provider(backend: LipSyncBackend = LipSyncBackend.MUSETALK) -> BaseLipSyncProvider:
    """
    Get a lip-sync provider instance.

    Args:
        backend: The backend to use

    Returns:
        A lip-sync provider instance

    Raises:
        ValueError: If the backend is not supported
    """
    if backend == LipSyncBackend.MUSETALK:
        from .musetalk_provider import MuseTalkProvider
        return MuseTalkProvider()
    elif backend == LipSyncBackend.DID:
        raise NotImplementedError("D-ID provider not yet implemented")
    else:
        raise ValueError(f"Unknown lip-sync backend: {backend}")


def get_available_lipsync_backends() -> list:
    """
    Get list of available (installed) lip-sync backends.

    Returns:
        List of available LipSyncBackend values
    """
    available = []

    # Check MuseTalk
    try:
        from .musetalk_provider import MuseTalkProvider
        provider = MuseTalkProvider()
        if provider.is_available():
            available.append(LipSyncBackend.MUSETALK)
    except Exception:
        pass

    # Future: Check D-ID
    # available.append(LipSyncBackend.DID)

    return available


__all__ = [
    'BaseLipSyncProvider',
    'LipSyncBackend',
    'get_lipsync_provider',
    'get_available_lipsync_backends',
]
