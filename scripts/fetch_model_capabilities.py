#!/usr/bin/env python3
"""
Fetch and compile model capabilities from provider APIs and documentation.

This script creates a comprehensive data file containing all available models
and their capabilities from supported providers (OpenAI, Google, etc.).

Usage:
    python scripts/fetch_model_capabilities.py [--output path/to/output.json]

Output:
    Creates/updates data/model_capabilities.json with structured model data.
"""

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Set

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

class ModelCategory(str, Enum):
    """Categories of AI models."""
    LLM = "llm"                    # Text/chat models
    IMAGE_GEN = "image_generation" # Image generation
    IMAGE_EDIT = "image_editing"   # Image editing/inpainting
    VIDEO_GEN = "video_generation" # Video generation
    AUDIO_TTS = "audio_tts"        # Text-to-speech
    AUDIO_STT = "audio_stt"        # Speech-to-text
    AUDIO_REALTIME = "audio_realtime"  # Realtime audio
    EMBEDDING = "embedding"        # Text embeddings
    MODERATION = "moderation"      # Content moderation
    REASONING = "reasoning"        # Reasoning models (o1, o3, o4)
    CODE = "code"                  # Code-specific models


class ModelStatus(str, Enum):
    """Model availability status."""
    PRODUCTION = "production"
    PREVIEW = "preview"
    BETA = "beta"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


@dataclass
class ModelCapabilities:
    """Capabilities of a model."""
    text_input: bool = False
    text_output: bool = False
    image_input: bool = False      # Vision/multimodal
    image_output: bool = False     # Image generation
    audio_input: bool = False
    audio_output: bool = False
    video_input: bool = False
    video_output: bool = False
    function_calling: bool = False
    structured_output: bool = False
    streaming: bool = False
    json_mode: bool = False
    system_prompt: bool = True
    # Image-specific
    transparent_background: bool = False
    reference_images: bool = False
    inpainting: bool = False
    outpainting: bool = False
    # Video-specific
    frame_interpolation: bool = False
    audio_generation: bool = False


@dataclass
class ModelLimits:
    """Resource limits for a model."""
    context_window: Optional[int] = None      # Max input tokens
    max_output_tokens: Optional[int] = None   # Max output tokens
    max_images: Optional[int] = None          # Max images per request
    supported_sizes: List[str] = field(default_factory=list)  # Image sizes
    supported_aspects: List[str] = field(default_factory=list)  # Aspect ratios
    max_duration_seconds: Optional[int] = None  # Video duration
    supported_resolutions: List[str] = field(default_factory=list)  # Video res


@dataclass
class ModelPricing:
    """Pricing information (per 1M tokens or per image/video)."""
    input_per_million: Optional[float] = None
    output_per_million: Optional[float] = None
    per_image: Optional[float] = None
    per_second_video: Optional[float] = None
    currency: str = "USD"


@dataclass
class ModelInfo:
    """Complete information about a model."""
    id: str
    display_name: str
    provider: str
    category: ModelCategory
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)
    limits: ModelLimits = field(default_factory=ModelLimits)
    pricing: Optional[ModelPricing] = None
    status: ModelStatus = ModelStatus.PRODUCTION
    description: Optional[str] = None
    nickname: Optional[str] = None  # e.g., "Nano Banana"
    requires_api_key: bool = True
    requires_gcloud: bool = False
    knowledge_cutoff: Optional[str] = None
    release_date: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class ProviderInfo:
    """Information about a model provider."""
    id: str
    display_name: str
    api_key_url: Optional[str] = None
    docs_url: Optional[str] = None
    models: Dict[str, ModelInfo] = field(default_factory=dict)


@dataclass
class ModelDatabase:
    """Complete database of all models."""
    last_updated: str = ""
    version: str = "1.0.0"
    providers: Dict[str, ProviderInfo] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "last_updated": self.last_updated,
            "version": self.version,
            "providers": {
                pid: {
                    "id": p.id,
                    "display_name": p.display_name,
                    "api_key_url": p.api_key_url,
                    "docs_url": p.docs_url,
                    "models": {
                        mid: self._model_to_dict(m)
                        for mid, m in p.models.items()
                    }
                }
                for pid, p in self.providers.items()
            }
        }

    def _model_to_dict(self, model: ModelInfo) -> Dict[str, Any]:
        """Convert ModelInfo to dict."""
        return {
            "id": model.id,
            "display_name": model.display_name,
            "provider": model.provider,
            "category": model.category.value if isinstance(model.category, ModelCategory) else model.category,
            "capabilities": asdict(model.capabilities),
            "limits": asdict(model.limits),
            "pricing": asdict(model.pricing) if model.pricing else None,
            "status": model.status.value if isinstance(model.status, ModelStatus) else model.status,
            "description": model.description,
            "nickname": model.nickname,
            "requires_api_key": model.requires_api_key,
            "requires_gcloud": model.requires_gcloud,
            "knowledge_cutoff": model.knowledge_cutoff,
            "release_date": model.release_date,
            "aliases": model.aliases,
            "tags": model.tags,
        }


# =============================================================================
# OpenAI Model Fetcher
# =============================================================================

class OpenAIModelFetcher:
    """Fetch and categorize OpenAI models."""

    # Model categorization patterns
    PATTERNS = {
        ModelCategory.IMAGE_GEN: [r'^gpt-image', r'^dall-e', r'^chatgpt-image'],
        ModelCategory.REASONING: [r'^o1', r'^o3', r'^o4'],
        ModelCategory.AUDIO_TTS: [r'^tts-', r'-tts$', r'-tts-'],
        ModelCategory.AUDIO_STT: [r'^whisper', r'-transcribe'],
        ModelCategory.AUDIO_REALTIME: [r'-realtime', r'^gpt-audio'],
        ModelCategory.EMBEDDING: [r'^text-embedding'],
        ModelCategory.MODERATION: [r'^omni-moderation', r'^text-moderation'],
        ModelCategory.CODE: [r'-codex'],
        ModelCategory.LLM: [r'^gpt-', r'^chatgpt-'],  # Fallback for GPT models
    }

    # Known model capabilities (from documentation and API research)
    # Sources: https://github.com/taylorwilsdon/llm-context-limits
    #          https://platform.openai.com/docs/models
    KNOWN_CAPABILITIES = {
        # GPT-5 series (December 2025)
        'gpt-5.2-pro': {
            'context': 400000, 'output': 128000,
            'vision': True, 'function_calling': True, 'structured': True, 'json_mode': True,
            'description': 'Most capable GPT-5 model for coding and agentic tasks',
            'knowledge_cutoff': '2025-06',
        },
        'gpt-5.2': {
            'context': 400000, 'output': 128000,
            'vision': True, 'function_calling': True, 'structured': True, 'json_mode': True,
            'description': 'Latest stable GPT-5 model',
            'knowledge_cutoff': '2025-06',
        },
        'gpt-5.1': {
            'context': 400000, 'output': 128000,
            'vision': True, 'function_calling': True, 'structured': True, 'json_mode': True,
            'knowledge_cutoff': '2025-03',
        },
        'gpt-5.1-codex-max': {
            'context': 400000, 'output': 128000,
            'vision': True, 'function_calling': True, 'structured': True,
            'description': 'Extended code generation model',
            'knowledge_cutoff': '2025-03',
        },
        'gpt-5.1-codex': {
            'context': 400000, 'output': 128000,
            'vision': True, 'function_calling': True,
            'description': 'Optimized for code generation',
            'knowledge_cutoff': '2025-03',
        },
        'gpt-5-codex': {
            'context': 400000, 'output': 128000,
            'function_calling': True,
            'description': 'Code-focused GPT-5 variant',
            'knowledge_cutoff': '2025-01',
        },
        'gpt-5-pro': {
            'context': 400000, 'output': 128000,
            'vision': True, 'function_calling': True, 'structured': True, 'json_mode': True,
            'knowledge_cutoff': '2025-01',
        },
        'gpt-5': {
            'context': 400000, 'output': 128000,
            'vision': True, 'function_calling': True, 'structured': True, 'json_mode': True,
            'knowledge_cutoff': '2025-01',
        },
        'gpt-5-mini': {
            'context': 400000, 'output': 128000,
            'vision': True, 'function_calling': True, 'structured': True,
            'description': 'Balanced performance and cost',
            'knowledge_cutoff': '2025-01',
        },
        'gpt-5-nano': {
            'context': 400000, 'output': 128000,
            'vision': True, 'function_calling': True,
            'description': 'Fastest GPT-5 variant',
            'knowledge_cutoff': '2025-01',
        },
        # Reasoning models (o-series)
        'o4-mini': {
            'context': 200000, 'output': 100000,
            'vision': True, 'function_calling': True,
            'description': 'Fast, cost-efficient reasoning model',
            'knowledge_cutoff': '2024-06',
        },
        'o3-pro': {
            'context': 200000, 'output': 100000,
            'vision': True, 'function_calling': True,
            'description': 'Advanced reasoning with extended thinking',
            'knowledge_cutoff': '2024-06',
        },
        'o3': {
            'context': 200000, 'output': 100000,
            'vision': True, 'function_calling': True,
            'description': 'State-of-the-art for math, science, and coding',
            'knowledge_cutoff': '2024-06',
        },
        'o3-mini': {
            'context': 200000, 'output': 100000,
            'vision': True, 'function_calling': True,
            'description': 'Faster, smaller reasoning model',
            'knowledge_cutoff': '2024-06',
        },
        'o1-pro': {
            'context': 200000, 'output': 100000,
            'vision': True, 'function_calling': True,
            'knowledge_cutoff': '2024-03',
        },
        'o1': {
            'context': 200000, 'output': 100000,
            'vision': True,
            'description': 'Original reasoning model',
            'knowledge_cutoff': '2024-03',
        },
        'o1-mini': {
            'context': 128000, 'output': 65536,
            'vision': True,
            'description': 'Smaller, faster o1 variant',
            'knowledge_cutoff': '2024-03',
        },
        'o1-preview': {
            'context': 128000, 'output': 32768,
            'vision': True,
            'description': 'Preview version of o1',
            'knowledge_cutoff': '2024-03',
        },
        # GPT-4.1 series (1M context)
        'gpt-4.1': {
            'context': 1047576, 'output': 32768,
            'vision': True, 'function_calling': True, 'structured': True, 'json_mode': True,
            'description': 'Major gains in coding and instruction following',
            'knowledge_cutoff': '2024-12',
        },
        'gpt-4.1-mini': {
            'context': 1047576, 'output': 32768,
            'vision': True, 'function_calling': True, 'structured': True,
            'description': 'Smaller, faster 4.1 variant',
            'knowledge_cutoff': '2024-12',
        },
        'gpt-4.1-nano': {
            'context': 1047576, 'output': 32768,
            'function_calling': True,
            'description': 'Fastest 4.1 variant for simple tasks',
            'knowledge_cutoff': '2024-12',
        },
        # GPT-4o series
        'gpt-4o': {
            'context': 128000, 'output': 16384,
            'vision': True, 'function_calling': True, 'structured': True, 'json_mode': True,
            'description': 'Multimodal GPT-4 with vision and audio',
            'knowledge_cutoff': '2023-10',
        },
        'gpt-4o-mini': {
            'context': 128000, 'output': 16384,
            'vision': True, 'function_calling': True, 'structured': True, 'json_mode': True,
            'description': 'Smaller, faster GPT-4o',
            'knowledge_cutoff': '2023-10',
        },
        # GPT-4 series (legacy)
        'gpt-4-turbo': {
            'context': 128000, 'output': 4096,
            'vision': True, 'function_calling': True,
            'description': 'Previous generation turbo model',
            'knowledge_cutoff': '2023-12',
        },
        'gpt-4': {
            'context': 8192, 'output': 8192,
            'function_calling': True,
            'description': 'Original GPT-4',
            'knowledge_cutoff': '2021-09',
        },
        # GPT-3.5 series (legacy)
        'gpt-3.5-turbo': {
            'context': 16385, 'output': 4096,
            'function_calling': True,
            'description': 'Fast, efficient for simple tasks',
            'knowledge_cutoff': '2021-09',
        },
        # Image models
        'gpt-image-1.5': {
            'sizes': ['1024x1024', '1536x1024', '1024x1536'],
            'max_images': 10,
            'transparent': True, 'reference': True,
            'description': 'Latest image model, 4x faster, better instruction following'
        },
        'gpt-image-1': {
            'sizes': ['1024x1024', '1536x1024', '1024x1536'],
            'max_images': 1,
            'transparent': True, 'reference': True,
            'description': 'High quality with transparent background support'
        },
        'gpt-image-1-mini': {
            'sizes': ['1024x1024', '1536x1024', '1024x1536'],
            'max_images': 1,
            'transparent': True,
            'description': 'Fast, lower cost image generation'
        },
        'dall-e-3': {
            'sizes': ['1024x1024', '1024x1792', '1792x1024'],
            'max_images': 1,
            'description': 'Highest quality DALL-E model'
        },
        'dall-e-2': {
            'sizes': ['256x256', '512x512', '1024x1024'],
            'max_images': 10,
            'inpainting': True, 'outpainting': True,
            'description': 'Previous generation, supports editing'
        },
        # Audio models
        'whisper-1': {
            'description': 'Speech-to-text transcription'
        },
        'tts-1': {
            'description': 'Text-to-speech, optimized for speed'
        },
        'tts-1-hd': {
            'description': 'Text-to-speech, high definition quality'
        },
        # Embeddings
        'text-embedding-3-large': {
            'context': 8191,
            'description': 'Most capable embedding model'
        },
        'text-embedding-3-small': {
            'context': 8191,
            'description': 'Efficient embedding model'
        },
    }

    def __init__(self, api_key: Optional[str] = None):
        """Initialize with optional API key."""
        self.api_key = api_key
        self.client = None

    def _ensure_client(self):
        """Ensure OpenAI client is initialized."""
        if self.client is None:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")

    def fetch_model_list(self) -> List[str]:
        """Fetch list of available models from OpenAI API."""
        self._ensure_client()
        models = self.client.models.list()
        return [m.id for m in models.data]

    def categorize_model(self, model_id: str) -> ModelCategory:
        """Determine the category of a model based on its ID."""
        model_lower = model_id.lower()

        for category, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, model_lower):
                    return category

        return ModelCategory.LLM  # Default

    def get_model_info(self, model_id: str) -> ModelInfo:
        """Get complete information for a model."""
        category = self.categorize_model(model_id)
        known = self.KNOWN_CAPABILITIES.get(model_id, {})

        # Build capabilities
        caps = ModelCapabilities(
            text_input=category in [ModelCategory.LLM, ModelCategory.REASONING, ModelCategory.CODE],
            text_output=category in [ModelCategory.LLM, ModelCategory.REASONING, ModelCategory.CODE, ModelCategory.AUDIO_TTS],
            image_input=known.get('vision', False),
            image_output=category == ModelCategory.IMAGE_GEN,
            audio_input=category in [ModelCategory.AUDIO_STT, ModelCategory.AUDIO_REALTIME],
            audio_output=category in [ModelCategory.AUDIO_TTS, ModelCategory.AUDIO_REALTIME],
            function_calling=known.get('function_calling', False),
            structured_output=known.get('structured', False),
            streaming=category in [ModelCategory.LLM, ModelCategory.REASONING],
            json_mode=known.get('json_mode', False),
            transparent_background=known.get('transparent', False),
            reference_images=known.get('reference', False),
            inpainting=known.get('inpainting', False),
            outpainting=known.get('outpainting', False),
        )

        # Build limits
        limits = ModelLimits(
            context_window=known.get('context'),
            max_output_tokens=known.get('output'),
            max_images=known.get('max_images'),
            supported_sizes=known.get('sizes', []),
        )

        # Determine status from model ID
        status = ModelStatus.PRODUCTION
        if 'preview' in model_id.lower():
            status = ModelStatus.PREVIEW
        elif 'beta' in model_id.lower():
            status = ModelStatus.BETA
        elif 'exp' in model_id.lower():
            status = ModelStatus.EXPERIMENTAL

        # Generate display name
        display_name = self._generate_display_name(model_id)

        return ModelInfo(
            id=model_id,
            display_name=display_name,
            provider="openai",
            category=category,
            capabilities=caps,
            limits=limits,
            status=status,
            description=known.get('description'),
            knowledge_cutoff=known.get('knowledge_cutoff'),
            tags=self._get_tags(model_id, category),
        )

    def _generate_display_name(self, model_id: str) -> str:
        """Generate a human-readable display name."""
        # Special cases
        special_names = {
            'dall-e-3': 'DALL·E 3',
            'dall-e-2': 'DALL·E 2',
            'gpt-image-1.5': 'GPT Image 1.5',
            'gpt-image-1': 'GPT Image 1',
            'gpt-image-1-mini': 'GPT Image 1 Mini',
            'whisper-1': 'Whisper',
            'tts-1': 'TTS',
            'tts-1-hd': 'TTS HD',
        }

        if model_id in special_names:
            return special_names[model_id]

        # Convert model ID to display name
        name = model_id.replace('-', ' ').replace('_', ' ')
        # Capitalize appropriately
        words = name.split()
        display_words = []
        for word in words:
            if word.lower() in ['gpt', 'tts', 'stt']:
                display_words.append(word.upper())
            elif word.lower() in ['mini', 'nano', 'pro', 'turbo', 'hd']:
                display_words.append(word.capitalize())
            elif re.match(r'^[ov]\d', word.lower()):
                display_words.append(word.upper())
            else:
                display_words.append(word.capitalize())

        return ' '.join(display_words)

    def _get_tags(self, model_id: str, category: ModelCategory) -> List[str]:
        """Get relevant tags for a model."""
        tags = [category.value]

        if 'mini' in model_id.lower():
            tags.append('fast')
            tags.append('efficient')
        if 'nano' in model_id.lower():
            tags.append('fastest')
        if 'pro' in model_id.lower():
            tags.append('advanced')
        if 'turbo' in model_id.lower():
            tags.append('fast')
        if 'hd' in model_id.lower():
            tags.append('high-quality')
        if 'search' in model_id.lower():
            tags.append('web-search')
        if 'realtime' in model_id.lower():
            tags.append('realtime')
        if 'deep-research' in model_id.lower():
            tags.append('research')

        return tags

    def fetch_all(self) -> ProviderInfo:
        """Fetch all OpenAI model information."""
        logger.info("Fetching OpenAI models...")

        try:
            model_ids = self.fetch_model_list()
            logger.info(f"Found {len(model_ids)} models from API")
        except Exception as e:
            logger.warning(f"Could not fetch from API: {e}")
            logger.info("Using known model list...")
            model_ids = list(self.KNOWN_CAPABILITIES.keys())

        # Filter to relevant models (skip fine-tuned, deprecated variants)
        filtered_ids = []
        for mid in model_ids:
            # Skip fine-tuned models
            if ':ft-' in mid or mid.startswith('ft:'):
                continue
            # Skip old dated variants unless it's a specific version
            if re.search(r'-\d{4}-\d{2}-\d{2}$', mid) and mid not in self.KNOWN_CAPABILITIES:
                continue
            filtered_ids.append(mid)

        logger.info(f"Processing {len(filtered_ids)} relevant models")

        models = {}
        for model_id in filtered_ids:
            try:
                info = self.get_model_info(model_id)
                models[model_id] = info
            except Exception as e:
                logger.warning(f"Error processing {model_id}: {e}")

        return ProviderInfo(
            id="openai",
            display_name="OpenAI",
            api_key_url="https://platform.openai.com/api-keys",
            docs_url="https://platform.openai.com/docs/models",
            models=models,
        )


# =============================================================================
# Google Model Fetcher
# =============================================================================

class GoogleModelFetcher:
    """Fetch and compile Google model information."""

    # Hardcoded model data based on documentation research
    MODELS = {
        # Gemini LLM Models
        'gemini-3-pro-preview': {
            'category': ModelCategory.LLM,
            'display_name': 'Gemini 3 Pro',
            'description': 'State-of-the-art reasoning, 1M context window',
            'context': 1048576, 'output': 65536,
            'vision': True, 'audio': True, 'video': True,
            'function_calling': True, 'structured': True,
            'status': ModelStatus.PREVIEW,
            'tags': ['reasoning', 'multimodal', 'long-context'],
        },
        'gemini-3-flash-preview': {
            'category': ModelCategory.LLM,
            'display_name': 'Gemini 3 Flash',
            'description': 'Frontier intelligence with fast inference, 1M context',
            'context': 1048576, 'output': 65536,
            'vision': True, 'audio': True, 'video': True,
            'function_calling': True, 'structured': True,
            'status': ModelStatus.PREVIEW,
            'tags': ['fast', 'multimodal', 'long-context'],
        },
        'gemini-2.5-pro': {
            'category': ModelCategory.LLM,
            'display_name': 'Gemini 2.5 Pro',
            'description': 'Complex reasoning for code, math, STEM',
            'context': 1048576, 'output': 65536,
            'vision': True, 'audio': True, 'video': True,
            'function_calling': True, 'structured': True,
            'tags': ['reasoning', 'code', 'math'],
        },
        'gemini-2.5-flash': {
            'category': ModelCategory.LLM,
            'display_name': 'Gemini 2.5 Flash',
            'description': 'Price-performance optimized, 1M context',
            'context': 1048576, 'output': 65536,
            'vision': True, 'audio': True, 'video': True,
            'function_calling': True, 'structured': True,
            'tags': ['fast', 'efficient'],
        },
        'gemini-2.5-flash-lite': {
            'category': ModelCategory.LLM,
            'display_name': 'Gemini 2.5 Flash Lite',
            'description': 'Cost-efficient, high throughput',
            'context': 1048576, 'output': 65536,
            'vision': True, 'audio': True, 'video': True,
            'tags': ['fastest', 'cheapest'],
        },
        'gemini-2.0-flash': {
            'category': ModelCategory.LLM,
            'display_name': 'Gemini 2.0 Flash',
            'description': 'Previous generation multimodal',
            'context': 1048576, 'output': 8192,
            'vision': True, 'audio': True, 'video': True,
            'function_calling': True,
        },
        'gemini-2.0-flash-lite': {
            'category': ModelCategory.LLM,
            'display_name': 'Gemini 2.0 Flash Lite',
            'context': 1048576, 'output': 8192,
            'vision': True,
        },

        # Gemini Image Generation Models
        'gemini-2.5-flash-image': {
            'category': ModelCategory.IMAGE_GEN,
            'display_name': 'Gemini 2.5 Flash Image',
            'nickname': 'Nano Banana',
            'description': 'Production image generation with aspect ratio support',
            'aspects': ['1:1', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '21:9'],
            'max_resolution': '1K',
            'requires_gcloud': False,
            'tags': ['fast', 'production'],
        },
        'gemini-3.1-flash-image-preview': {
            'category': ModelCategory.IMAGE_GEN,
            'display_name': 'Gemini 3.1 Flash Image',
            'nickname': 'Nano Banana 2',
            'description': '2K output, next-gen flash image generation',
            'aspects': ['1:1', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '21:9'],
            'max_resolution': '2K',
            'requires_gcloud': False,
            'status': ModelStatus.PREVIEW,
            'tags': ['fast', 'preview'],
        },
        'gemini-3-pro-image-preview': {
            'category': ModelCategory.IMAGE_GEN,
            'display_name': 'Gemini 3 Pro Image',
            'nickname': 'Nano Banana Pro',
            'description': '4K output, superior text rendering, up to 14 reference images',
            'aspects': ['1:1', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '21:9'],
            'sizes': ['1K', '2K', '4K'],
            'max_resolution': '4K',
            'max_reference': 14,
            'requires_gcloud': False,
            'status': ModelStatus.PREVIEW,
            'tags': ['high-quality', 'text-rendering', 'reference-images'],
        },

        # Imagen Models (Vertex AI)
        'imagen-4.0-generate-001': {
            'category': ModelCategory.IMAGE_GEN,
            'display_name': 'Imagen 4',
            'description': 'Best quality, low latency, near-real-time performance',
            'max_resolution': '2K',
            'requires_gcloud': True,
            'tags': ['best-quality', 'fast'],
        },
        'imagen-3.0-generate-002': {
            'category': ModelCategory.IMAGE_GEN,
            'display_name': 'Imagen 3',
            'description': 'General purpose generation, inpainting, outpainting',
            'max_resolution': '2K',
            'requires_gcloud': True,
            'inpainting': True, 'outpainting': True,
            'tags': ['versatile', 'editing'],
        },

        # Veo Video Models
        'veo-3.1-generate-001': {
            'category': ModelCategory.VIDEO_GEN,
            'display_name': 'Veo 3.1',
            'description': 'Full quality, 1080p, reference images, frame interpolation',
            'resolutions': ['720p', '1080p'],
            'aspects': ['16:9', '9:16'],
            'duration': 8,
            'fps': 24,
            'reference_images': True,
            'frame_interpolation': True,
            'requires_gcloud': False,
            'tags': ['high-quality', 'reference-images'],
        },
        'veo-3.1-fast-generate-001': {
            'category': ModelCategory.VIDEO_GEN,
            'display_name': 'Veo 3.1 Fast',
            'description': 'Fast generation (11-60s), 720p, variable duration',
            'resolutions': ['720p'],
            'aspects': ['16:9', '9:16'],
            'durations': [4, 6, 8],
            'fps': 24,
            'reference_images': True,
            'frame_interpolation': True,
            'requires_gcloud': False,
            'tags': ['fast', 'reference-images'],
        },
        'veo-3.0-generate-001': {
            'category': ModelCategory.VIDEO_GEN,
            'display_name': 'Veo 3',
            'description': 'Standard quality with audio generation',
            'resolutions': ['720p', '1080p'],
            'aspects': ['16:9', '9:16', '1:1'],
            'duration': 8,
            'fps': 24,
            'audio_generation': True,
            'requires_gcloud': False,
            'tags': ['audio', 'standard'],
        },
        'veo-3.0-fast-generate-001': {
            'category': ModelCategory.VIDEO_GEN,
            'display_name': 'Veo 3 Fast',
            'description': 'Fast generation, 720p, variable duration',
            'resolutions': ['720p'],
            'aspects': ['16:9', '9:16'],
            'durations': [4, 6, 8],
            'fps': 24,
            'requires_gcloud': False,
            'tags': ['fast'],
        },
        'veo-2.0-generate-001': {
            'category': ModelCategory.VIDEO_GEN,
            'display_name': 'Veo 2',
            'description': 'Legacy model, reference images supported',
            'resolutions': ['720p'],
            'aspects': ['16:9'],
            'durations': [5, 6, 7, 8],
            'fps': 24,
            'reference_images': True,
            'requires_gcloud': False,
            'tags': ['legacy', 'reference-images'],
        },
    }

    def get_model_info(self, model_id: str, data: dict) -> ModelInfo:
        """Convert model data dict to ModelInfo."""
        category = data.get('category', ModelCategory.LLM)

        # Build capabilities
        caps = ModelCapabilities(
            text_input=category == ModelCategory.LLM,
            text_output=category == ModelCategory.LLM,
            image_input=data.get('vision', False),
            image_output=category == ModelCategory.IMAGE_GEN,
            audio_input=data.get('audio', False),
            audio_output=data.get('audio_generation', False),
            video_input=data.get('video', False),
            video_output=category == ModelCategory.VIDEO_GEN,
            function_calling=data.get('function_calling', False),
            structured_output=data.get('structured', False),
            streaming=category == ModelCategory.LLM,
            reference_images=data.get('reference_images', False) or data.get('max_reference', 0) > 0,
            inpainting=data.get('inpainting', False),
            outpainting=data.get('outpainting', False),
            frame_interpolation=data.get('frame_interpolation', False),
            audio_generation=data.get('audio_generation', False),
        )

        # Build limits
        limits = ModelLimits(
            context_window=data.get('context'),
            max_output_tokens=data.get('output'),
            supported_sizes=data.get('sizes', []),
            supported_aspects=data.get('aspects', []),
            max_duration_seconds=data.get('duration') or (max(data.get('durations', [8])) if 'durations' in data else None),
            supported_resolutions=data.get('resolutions', []),
        )

        status = data.get('status', ModelStatus.PRODUCTION)

        return ModelInfo(
            id=model_id,
            display_name=data.get('display_name', model_id),
            provider="google",
            category=category,
            capabilities=caps,
            limits=limits,
            status=status,
            description=data.get('description'),
            nickname=data.get('nickname'),
            requires_api_key=not data.get('requires_gcloud', False),
            requires_gcloud=data.get('requires_gcloud', False),
            tags=data.get('tags', []),
        )

    def fetch_all(self) -> ProviderInfo:
        """Compile all Google model information."""
        logger.info("Compiling Google models...")

        models = {}
        for model_id, data in self.MODELS.items():
            try:
                info = self.get_model_info(model_id, data)
                models[model_id] = info
            except Exception as e:
                logger.warning(f"Error processing {model_id}: {e}")

        logger.info(f"Compiled {len(models)} Google models")

        return ProviderInfo(
            id="google",
            display_name="Google",
            api_key_url="https://aistudio.google.com/apikey",
            docs_url="https://ai.google.dev/gemini-api/docs/models",
            models=models,
        )


# =============================================================================
# Anthropic Model Fetcher
# =============================================================================

class AnthropicModelFetcher:
    """Fetch and compile Anthropic Claude model information."""

    # Hardcoded model data based on documentation research
    # Sources: https://www.anthropic.com/claude/opus
    #          https://www.anthropic.com/claude/sonnet
    #          https://www.anthropic.com/news/claude-4
    MODELS = {
        # Claude 4.5 Series (Latest - November 2025)
        'claude-opus-4-5-20251101': {
            'category': ModelCategory.LLM,
            'display_name': 'Claude Opus 4.5',
            'description': 'Most intelligent model, best for coding, agents, and computer use',
            'context': 200000, 'output': 64000,
            'vision': True, 'function_calling': True, 'structured': True,
            'extended_thinking': True, 'computer_use': True,
            'knowledge_cutoff': '2025-04',
            'release_date': '2025-11-24',
            'pricing_input': 5.0, 'pricing_output': 25.0,
            'tags': ['flagship', 'coding', 'agents', 'computer-use'],
        },
        'claude-sonnet-4-5-20250514': {
            'category': ModelCategory.LLM,
            'display_name': 'Claude Sonnet 4.5',
            'description': 'Best for complex agents and coding, 1M context available',
            'context': 200000, 'output': 64000,
            'extended_context': 1000000,  # Beta with header
            'vision': True, 'function_calling': True, 'structured': True,
            'extended_thinking': True, 'computer_use': True,
            'knowledge_cutoff': '2025-04',
            'release_date': '2025-05-14',
            'pricing_input': 3.0, 'pricing_output': 15.0,
            'tags': ['agents', 'coding', 'long-context'],
        },

        # Claude 4 Series (May 2025)
        'claude-opus-4-20250514': {
            'category': ModelCategory.LLM,
            'display_name': 'Claude Opus 4',
            'description': 'World\'s best coding model, sustained performance on complex tasks',
            'context': 200000, 'output': 64000,
            'vision': True, 'function_calling': True, 'structured': True,
            'extended_thinking': True,
            'knowledge_cutoff': '2025-03',
            'release_date': '2025-05-14',
            'pricing_input': 15.0, 'pricing_output': 75.0,
            'tags': ['coding', 'reasoning', 'agentic'],
        },
        'claude-sonnet-4-20250514': {
            'category': ModelCategory.LLM,
            'display_name': 'Claude Sonnet 4',
            'description': 'Excellent coding performance, balanced speed and capability',
            'context': 200000, 'output': 64000,
            'extended_context': 1000000,  # Beta with header
            'vision': True, 'function_calling': True, 'structured': True,
            'extended_thinking': True,
            'knowledge_cutoff': '2025-03',
            'release_date': '2025-05-14',
            'pricing_input': 3.0, 'pricing_output': 15.0,
            'tags': ['coding', 'balanced'],
        },

        # Claude 3.7 Series
        'claude-3-7-sonnet-20250219': {
            'category': ModelCategory.LLM,
            'display_name': 'Claude 3.7 Sonnet',
            'description': 'Enhanced reasoning with extended thinking',
            'context': 200000, 'output': 16384,
            'vision': True, 'function_calling': True, 'structured': True,
            'extended_thinking': True,
            'knowledge_cutoff': '2024-11',
            'release_date': '2025-02-19',
            'pricing_input': 3.0, 'pricing_output': 15.0,
            'tags': ['reasoning', 'balanced'],
        },

        # Claude 3.5 Series
        'claude-3-5-sonnet-20241022': {
            'category': ModelCategory.LLM,
            'display_name': 'Claude 3.5 Sonnet',
            'description': 'Best combination of speed and intelligence for most tasks',
            'context': 200000, 'output': 8192,
            'vision': True, 'function_calling': True, 'structured': True,
            'knowledge_cutoff': '2024-04',
            'release_date': '2024-10-22',
            'pricing_input': 3.0, 'pricing_output': 15.0,
            'tags': ['balanced', 'general-purpose'],
        },
        'claude-3-5-haiku-20241022': {
            'category': ModelCategory.LLM,
            'display_name': 'Claude 3.5 Haiku',
            'description': 'Fastest model with near-instant responses',
            'context': 200000, 'output': 8192,
            'vision': True, 'function_calling': True,
            'knowledge_cutoff': '2024-04',
            'release_date': '2024-10-22',
            'pricing_input': 0.80, 'pricing_output': 4.0,
            'tags': ['fast', 'efficient'],
        },

        # Claude 3 Series (Legacy)
        'claude-3-opus-20240229': {
            'category': ModelCategory.LLM,
            'display_name': 'Claude 3 Opus',
            'description': 'Previous generation flagship model',
            'context': 200000, 'output': 4096,
            'vision': True, 'function_calling': True,
            'knowledge_cutoff': '2023-08',
            'release_date': '2024-02-29',
            'pricing_input': 15.0, 'pricing_output': 75.0,
            'status': ModelStatus.DEPRECATED,
            'tags': ['legacy', 'powerful'],
        },
        'claude-3-sonnet-20240229': {
            'category': ModelCategory.LLM,
            'display_name': 'Claude 3 Sonnet',
            'description': 'Previous generation balanced model',
            'context': 200000, 'output': 4096,
            'vision': True, 'function_calling': True,
            'knowledge_cutoff': '2023-08',
            'release_date': '2024-02-29',
            'pricing_input': 3.0, 'pricing_output': 15.0,
            'status': ModelStatus.DEPRECATED,
            'tags': ['legacy', 'balanced'],
        },
        'claude-3-haiku-20240307': {
            'category': ModelCategory.LLM,
            'display_name': 'Claude 3 Haiku',
            'description': 'Previous generation fast model',
            'context': 200000, 'output': 4096,
            'vision': True, 'function_calling': True,
            'knowledge_cutoff': '2023-08',
            'release_date': '2024-03-07',
            'pricing_input': 0.25, 'pricing_output': 1.25,
            'status': ModelStatus.DEPRECATED,
            'tags': ['legacy', 'fast'],
        },
    }

    def get_model_info(self, model_id: str, data: dict) -> ModelInfo:
        """Convert model data dict to ModelInfo."""
        category = data.get('category', ModelCategory.LLM)

        # Build capabilities
        caps = ModelCapabilities(
            text_input=True,
            text_output=True,
            image_input=data.get('vision', False),
            image_output=False,
            audio_input=False,
            audio_output=False,
            function_calling=data.get('function_calling', False),
            structured_output=data.get('structured', False),
            streaming=True,
            json_mode=True,  # Claude supports JSON mode
            system_prompt=True,
        )

        # Build limits
        limits = ModelLimits(
            context_window=data.get('context'),
            max_output_tokens=data.get('output'),
        )

        # Build pricing
        pricing = None
        if 'pricing_input' in data:
            pricing = ModelPricing(
                input_per_million=data.get('pricing_input'),
                output_per_million=data.get('pricing_output'),
            )

        status = data.get('status', ModelStatus.PRODUCTION)

        return ModelInfo(
            id=model_id,
            display_name=data.get('display_name', model_id),
            provider="anthropic",
            category=category,
            capabilities=caps,
            limits=limits,
            pricing=pricing,
            status=status,
            description=data.get('description'),
            knowledge_cutoff=data.get('knowledge_cutoff'),
            release_date=data.get('release_date'),
            tags=data.get('tags', []),
        )

    def fetch_all(self) -> ProviderInfo:
        """Compile all Anthropic model information."""
        logger.info("Compiling Anthropic Claude models...")

        models = {}
        for model_id, data in self.MODELS.items():
            try:
                info = self.get_model_info(model_id, data)
                models[model_id] = info
            except Exception as e:
                logger.warning(f"Error processing {model_id}: {e}")

        logger.info(f"Compiled {len(models)} Anthropic models")

        return ProviderInfo(
            id="anthropic",
            display_name="Anthropic",
            api_key_url="https://console.anthropic.com/settings/keys",
            docs_url="https://docs.anthropic.com/en/docs/about-claude/models",
            models=models,
        )


# =============================================================================
# Main Script
# =============================================================================

def load_api_key(provider: str) -> Optional[str]:
    """Load API key from config files."""
    # Try Windows config location (from WSL)
    win_config = Path('/mnt/c/Users/aboog/AppData/Roaming/ImageAI/config.json')
    if win_config.exists():
        try:
            with open(win_config) as f:
                data = json.load(f)
            key = data.get(f'{provider}_api_key')
            if key:
                return key
        except Exception:
            pass

    # Try Linux config
    linux_config = Path.home() / '.config' / 'ImageAI' / 'config.json'
    if linux_config.exists():
        try:
            with open(linux_config) as f:
                data = json.load(f)
            return data.get(f'{provider}_api_key')
        except Exception:
            pass

    return None


def main():
    parser = argparse.ArgumentParser(
        description='Fetch and compile model capabilities from AI providers'
    )
    parser.add_argument(
        '--output', '-o',
        default=str(PROJECT_ROOT / 'data' / 'model_capabilities.json'),
        help='Output file path'
    )
    parser.add_argument(
        '--providers', '-p',
        nargs='+',
        default=['openai', 'google', 'anthropic'],
        choices=['openai', 'google', 'anthropic', 'stability'],
        help='Providers to fetch'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create database
    db = ModelDatabase(
        last_updated=datetime.now().isoformat(),
        version="1.0.0",
    )

    # Fetch from each provider
    for provider in args.providers:
        try:
            if provider == 'openai':
                api_key = load_api_key('openai')
                if not api_key:
                    logger.warning("No OpenAI API key found, using known model list")
                fetcher = OpenAIModelFetcher(api_key)
                db.providers['openai'] = fetcher.fetch_all()

            elif provider == 'google':
                fetcher = GoogleModelFetcher()
                db.providers['google'] = fetcher.fetch_all()

            elif provider == 'anthropic':
                fetcher = AnthropicModelFetcher()
                db.providers['anthropic'] = fetcher.fetch_all()

            else:
                logger.warning(f"Provider {provider} not yet implemented")

        except Exception as e:
            logger.error(f"Error fetching {provider}: {e}")

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(db.to_dict(), f, indent=2, ensure_ascii=False)

    logger.info(f"Wrote model capabilities to {output_path}")

    # Print summary
    total_models = sum(len(p.models) for p in db.providers.values())
    print(f"\n{'='*60}")
    print(f"Model Capabilities Database Generated")
    print(f"{'='*60}")
    print(f"Output: {output_path}")
    print(f"Providers: {len(db.providers)}")
    print(f"Total Models: {total_models}")
    for pid, pinfo in db.providers.items():
        print(f"  - {pinfo.display_name}: {len(pinfo.models)} models")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
