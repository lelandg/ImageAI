"""Constants and default values for ImageAI."""

import os
import platform
from pathlib import Path

# Application metadata
APP_NAME = "ImageAI"
VERSION = "0.30.0"
__version__ = VERSION
__author__ = "Leland Green"
__email__ = "contact@lelandgreen.com"
__license__ = "MIT"
__copyright__ = "Copyright 2025 Leland Green"

# Default provider settings
DEFAULT_PROVIDER = "google"
DEFAULT_MODEL = "gemini-2.5-flash-image-preview"

# Provider model mappings
PROVIDER_MODELS = {
    "google": {
        "gemini-2.5-flash-image-preview": "Gemini 2.5 Flash (Image Preview)",
        "gemini-2.5-flash": "Gemini 2.5 Flash",
        "gemini-2.5-pro": "Gemini 2.5 Pro",
    },
    "openai": {
        "dall-e-3": "DALL·E 3",
        "dall-e-2": "DALL·E 2",
    },
    "stability": {
        "stable-diffusion-xl-1024-v1-0": "Stable Diffusion XL 1.0",
        "stable-diffusion-v1-6": "Stable Diffusion 1.6",
        "stable-diffusion-512-v2-1": "Stable Diffusion 2.1",
        "stable-diffusion-xl-beta-v2-2-2": "Stable Diffusion XL Beta",
    },
    "local_sd": {
        "stabilityai/stable-diffusion-2-1": "Stable Diffusion 2.1",
        "runwayml/stable-diffusion-v1-5": "Stable Diffusion 1.5",
        "stabilityai/stable-diffusion-xl-base-1.0": "SDXL Base 1.0",
        "segmind/SSD-1B": "SSD-1B (Fast SDXL)",
        "CompVis/stable-diffusion-v1-4": "Stable Diffusion 1.4",
    },
}

# Provider API key URLs
PROVIDER_KEY_URLS = {
    "google": "https://aistudio.google.com/apikey",
    "openai": "https://platform.openai.com/api-keys",
    "stability": "https://platform.stability.ai/account/keys",
    "local_sd": "",  # No API key needed for local models
}

# File paths
README_PATH = Path(__file__).parent.parent / "README.md"
GEMINI_TEMPLATES_PATH = Path(__file__).parent.parent / "GEMINI.md"

# Image generation defaults
DEFAULT_IMAGE_SIZE = "1024x1024"
DEFAULT_NUM_IMAGES = 1
DEFAULT_QUALITY = "standard"

# UI defaults
DEFAULT_WINDOW_WIDTH = 1000
DEFAULT_WINDOW_HEIGHT = 700
PREVIEW_MAX_WIDTH = 512
PREVIEW_MAX_HEIGHT = 512

# Template categories
TEMPLATE_CATEGORIES = [
    "Art Style",
    "Photography",
    "Design",
    "Character",
    "Scene",
    "Product",
    "Marketing",
]

# Supported image formats
IMAGE_FORMATS = {
    "PNG": "*.png",
    "JPEG": "*.jpg *.jpeg",
    "WebP": "*.webp",
    "All Images": "*.png *.jpg *.jpeg *.webp",
}


def get_user_data_dir() -> Path:
    """Get platform-specific user data directory for ImageAI.

    Returns:
        Path to the user data directory where configuration, logs, and generated
        images are stored.
    """
    system = platform.system()
    home = Path.home()

    if system == "Windows":
        base = Path(os.getenv("APPDATA", home / "AppData" / "Roaming"))
        return base / APP_NAME
    elif system == "Darwin":  # macOS
        return home / "Library" / "Application Support" / APP_NAME
    else:  # Linux/Unix
        base = Path(os.getenv("XDG_CONFIG_HOME", home / ".config"))
        return base / APP_NAME