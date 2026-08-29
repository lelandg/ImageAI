"""The generation package re-exports its public surface."""
import core.sprite.generation as gen


def test_public_exports():
    expected = {
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
    }
    assert expected <= set(gen.__all__)
    for name in expected:
        assert getattr(gen, name) is not None
