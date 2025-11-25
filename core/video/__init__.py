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

__all__ = [
    'get_ffmpeg_manager',
    'get_ffmpeg_path',
    'is_ffmpeg_available',
    'ensure_ffmpeg',
    'install_ffmpeg',
    'get_ffmpeg_status',
    'FFmpegManager',
]
