"""Constants and default values for ImageAI."""

from pathlib import Path

# Application metadata
APP_NAME = "ImageAI"
VERSION = "0.7.0"

# Default provider settings
DEFAULT_PROVIDER = "google"
DEFAULT_MODEL = "gemini-2.5-flash-image-preview"

# Provider model mappings
PROVIDER_MODELS = {
    "google": {
        "gemini-2.5-flash-image-preview": "Gemini 2.5 Flash (Image Preview)",
        "gemini-2.5-flash": "Gemini 2.5 Flash",
        "gemini-2.5-pro": "Gemini 2.5 Pro",
        "imagen-3": "Imagen 3 (Coming Soon)",
        "imagen-3-fast": "Imagen 3 Fast (Coming Soon)",
    },
    "openai": {
        "dall-e-3": "DALL·E 3",
        "dall-e-2": "DALL·E 2",
    },
}

# Provider API key URLs
PROVIDER_KEY_URLS = {
    "google": "https://aistudio.google.com/apikey",
    "openai": "https://platform.openai.com/api-keys",
    "stability": "https://platform.stability.ai/account/keys",
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