"""Sprite generation routes: chroma plate, turnaround, action cards, video clips.

Route A (video) of the sprite pipeline — design §4.2. Everything here is
pure Python with injected provider clients and an injected ``log`` sink.
"""
from core.sprite.generation.action_cards import (
    ActionCardDraft,
    GENRE_CHECKLISTS,
    build_messages,
    draft_to_card,
    generate_action_cards,
    parse_action_cards,
)
from core.sprite.generation.cost import (
    PRICE_TABLE_VERIFIED,
    estimate_action,
    estimate_project,
    price_per_second,
    record_actual,
)
from core.sprite.generation.errors import (
    ProviderError,
    QuotaExceeded,
    SafetyRefusal,
    SpriteGenerationError,
    classify_provider_error,
)
from core.sprite.generation.plate import make_chroma_plate
from core.sprite.generation.prompts import (
    CHROMA_SUFFIX,
    FORBIDDEN_WORDS,
    LOOP_SUFFIX,
    color_name,
    inject_chroma,
)
from core.sprite.generation.queue import ActionQueue
from core.sprite.generation.turnaround import VIEWS, generate_turnaround
from core.sprite.generation.video_route import (
    RenderRequest,
    build_omni_config,
    build_veo_config,
    refine_action,
    render_action,
    trim_to_loop,
)

__all__ = [
    "SpriteGenerationError", "SafetyRefusal", "QuotaExceeded", "ProviderError",
    "classify_provider_error",
    "inject_chroma", "color_name", "CHROMA_SUFFIX", "LOOP_SUFFIX", "FORBIDDEN_WORDS",
    "make_chroma_plate",
    "generate_turnaround", "VIEWS",
    "ActionCardDraft", "GENRE_CHECKLISTS", "build_messages", "parse_action_cards",
    "generate_action_cards", "draft_to_card",
    "RenderRequest", "build_omni_config", "build_veo_config", "render_action",
    "refine_action", "trim_to_loop",
    "PRICE_TABLE_VERIFIED", "price_per_second", "estimate_action", "estimate_project",
    "record_actual",
    "ActionQueue",
]
