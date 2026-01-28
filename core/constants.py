"""Constants and default values for ImageAI."""

import os
import platform
from pathlib import Path

# Application metadata
APP_NAME = "ImageAI"
VERSION = "0.33.0"
__version__ = VERSION
__author__ = "Leland Green"
__email__ = "contact@lelandgreen.com"
__license__ = "MIT"
__copyright__ = "Copyright 2025 Leland Green"

# Default provider settings
DEFAULT_PROVIDER = "google"
DEFAULT_MODEL = "gemini-2.5-flash-image"

# Provider model mappings
# NOTE: For comprehensive LLM models, see core/llm_models.py (LLM_PROVIDERS)
# This mapping is for image generation models shown in the main UI
# Models are ordered newest to oldest for UI display
PROVIDER_MODELS = {
    "google": {
        # Gemini Image Generation (API key or gcloud) - newest first
        "gemini-3-pro-image-preview": "Gemini 3 Pro Image (Nano Banana Pro) - 4K",
        "gemini-2.5-flash-image": "Gemini 2.5 Flash Image (Nano Banana)",
        # Imagen Models (Vertex AI - gcloud only) - newest first
        "imagen-4.0-generate-001": "Imagen 4 (Best Quality)",
        "imagen-3.0-generate-002": "Imagen 3 (General Purpose)",
    },
    "openai": {
        # GPT Image Series (December 2025) - newest first
        "gpt-image-1.5": "GPT Image 1.5 (Latest)",
        "gpt-image-1": "GPT Image 1",
        "gpt-image-1-mini": "GPT Image 1 Mini (Fast)",
        # DALL-E Series
        "dall-e-3": "DALL·E 3",
        "dall-e-2": "DALL·E 2",
    },
    "stability": {
        # Stable Diffusion models - SDXL is newest
        "stable-diffusion-xl-1024-v1-0": "Stable Diffusion XL 1.0",
        "stable-diffusion-xl-beta-v2-2-2": "Stable Diffusion XL Beta",
        "stable-diffusion-512-v2-1": "Stable Diffusion 2.1",
        "stable-diffusion-v1-6": "Stable Diffusion 1.6",
    },
    "local_sd": {
        # Local SD models - SDXL variants first
        "stabilityai/stable-diffusion-xl-base-1.0": "SDXL Base 1.0",
        "segmind/SSD-1B": "SSD-1B (Fast SDXL)",
        "stabilityai/stable-diffusion-2-1": "Stable Diffusion 2.1",
        "runwayml/stable-diffusion-v1-5": "Stable Diffusion 1.5",
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

# Discord Rich Presence
# To use: Create an application at https://discord.com/developers/applications
# and replace this with your Application ID
DISCORD_CLIENT_ID = "1456298602950561954"  # ImageAI Discord Application
DISCORD_UPDATE_INTERVAL = 15  # seconds (Discord's minimum rate limit)
DISCORD_GITHUB_URL = "https://github.com/lelandg/ImageAI"
DISCORD_SERVER_URL = "https://discord.gg/chameleonlabs"  # Chameleon Labs Discord

# Privacy levels for Discord presence
DISCORD_PRIVACY_LEVELS = {
    "full": "Show provider, model, and activity",
    "activity_only": "Show activity only (Generating, Idle)",
    "minimal": "Show only that ImageAI is running",
}

# Discord asset names (must match names uploaded to Discord Developer Portal)
# IMPORTANT: Assets must be uploaded to Rich Presence → Art Assets, NOT the App Icon!
# The App Icon (in General Information) is different from Rich Presence assets.
# Set large_image to "" or None to use the default App Icon instead of a custom asset.
DISCORD_ASSETS = {
    "large_image": "imageai_logo",  # Must match asset name in Discord Developer Portal → Rich Presence → Art Assets
    "large_text": f"{APP_NAME} v{VERSION}",
    # Activity-specific images (override large_image for certain states)
    "activities": {
        "character_generator": "character_gen",  # When in character animator/generator
        "chatting_with_ai": "imageai_robot",     # When using LLM dialogs
    },
    "providers": {
        "google": "provider_google",
        "openai": "provider_openai",
        "stability": "provider_stability",
        "local_sd": "provider_local",
    },
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