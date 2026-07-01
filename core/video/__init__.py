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

# Gemini Omni client exports (lazy import; needs google-genai >= 2.3.0 for the
# Interactions API).
try:
    from .omni_client import (
        OmniClient,
        OmniModel,
        OmniGenerationConfig,
        OmniGenerationResult,
    )
    OMNI_AVAILABLE = True
except ImportError:
    OMNI_AVAILABLE = False
    OmniClient = None
    OmniModel = None
    OmniGenerationConfig = None
    OmniGenerationResult = None

__all__ = [
    # FFmpeg utilities
    'get_ffmpeg_manager',
    'get_ffmpeg_path',
    'is_ffmpeg_available',
    'ensure_ffmpeg',
    'install_ffmpeg',
    'get_ffmpeg_status',
    'FFmpegManager',
    # Gemini Omni client
    'OMNI_AVAILABLE',
    'OmniClient',
    'OmniModel',
    'OmniGenerationConfig',
    'OmniGenerationResult',
]
