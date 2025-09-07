"""Core functionality for ImageAI."""

from .config import ConfigManager, get_api_key_url
from .constants import (
    APP_NAME,
    VERSION,
    __version__,
    __author__,
    __email__,
    __license__,
    __copyright__,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    PROVIDER_MODELS,
    PROVIDER_KEY_URLS,
)
from .utils import (
    sanitize_filename,
    read_key_file,
    extract_api_key_help,
    read_readme_text,
    images_output_dir,
    sidecar_path,
    write_image_sidecar,
    read_image_sidecar,
    detect_image_extension,
    sanitize_stub_from_prompt,
    auto_save_images,
    scan_disk_history,
    find_cached_demo,
    default_model_for_provider,
)

# Export metadata at package level
__version__ = __version__
__author__ = __author__
__email__ = __email__
__license__ = __license__
__copyright__ = __copyright__

__all__ = [
    "ConfigManager",
    "get_api_key_url",
    "APP_NAME",
    "VERSION",
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__copyright__",
    "DEFAULT_MODEL",
    "DEFAULT_PROVIDER",
    "PROVIDER_MODELS",
    "PROVIDER_KEY_URLS",
    "sanitize_filename",
    "read_key_file",
    "extract_api_key_help",
    "read_readme_text",
    "images_output_dir",
    "sidecar_path",
    "write_image_sidecar",
    "read_image_sidecar",
    "detect_image_extension",
    "sanitize_stub_from_prompt",
    "auto_save_images",
    "scan_disk_history",
    "find_cached_demo",
    "default_model_for_provider",
]