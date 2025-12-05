"""Video generation and processing module."""

from .ffmpeg_utils import (
    get_ffmpeg_manager,
    get_ffmpeg_path,
    is_ffmpeg_available,
    ensure_ffmpeg,
    install_ffmpeg,
    get_ffmpeg_status,
    FFmpegManager,
)

# Sora client exports (lazy import to avoid ImportError if openai not installed)
try:
    from .sora_client import (
        SoraClient,
        SoraModel,
        SoraGenerationConfig,
        SoraGenerationResult,
        SoraErrorType,
    )
    SORA_AVAILABLE = True
except ImportError:
    SORA_AVAILABLE = False
    SoraClient = None
    SoraModel = None
    SoraGenerationConfig = None
    SoraGenerationResult = None
    SoraErrorType = None

__all__ = [
    # FFmpeg utilities
    'get_ffmpeg_manager',
    'get_ffmpeg_path',
    'is_ffmpeg_available',
    'ensure_ffmpeg',
    'install_ffmpeg',
    'get_ffmpeg_status',
    'FFmpegManager',
    # Sora client
    'SORA_AVAILABLE',
    'SoraClient',
    'SoraModel',
    'SoraGenerationConfig',
    'SoraGenerationResult',
    'SoraErrorType',
]
