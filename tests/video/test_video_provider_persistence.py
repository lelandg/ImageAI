"""Regression tests for video-provider save/restore label consistency.

The provider combo emits labels like "Gemini Veo" / "Gemini Omni", and
persistence saves ``combo.currentText().lower()`` then restores via
``findText(<label>)``. A drift between the saved label and the ``findText``
label silently drops the provider to the default (this is the "Google Veo" vs
"Gemini Veo" bug fixed alongside the Omni work).

These tests scan the workspace-widget and config source so they run without a
display (the GUI is not headless-constructable), and assert the label contract
holds as well as the Sora→Omni back-compat coercions.
"""

import re
from pathlib import Path

WIDGET_SRC = (
    Path(__file__).resolve().parents[2] / "gui" / "video" / "workspace_widget.py"
).read_text(encoding="utf-8")

CONFIG_SRC = (
    Path(__file__).resolve().parents[2] / "core" / "video" / "config.py"
).read_text(encoding="utf-8")

TAB_SRC = (
    Path(__file__).resolve().parents[2] / "gui" / "video" / "video_project_tab.py"
).read_text(encoding="utf-8")

# Labels the provider combo actually offers (must match findText() targets).
COMBO_LABELS = ["FFmpeg Slideshow", "Gemini Veo", "Gemini Omni"]


def test_combo_offers_three_providers():
    """Combo must list exactly the three supported providers (Sora removed)."""
    m = re.search(r"video_provider_combo\.addItems\(\[(.*?)\]\)", WIDGET_SRC, re.S)
    assert m, "could not find video_provider_combo.addItems(...)"
    items = m.group(1)
    for label in COMBO_LABELS:
        assert f'"{label}"' in items, f"combo missing provider label {label!r}"


def test_sora_not_in_combo():
    """OpenAI Sora must no longer appear in addItems."""
    m = re.search(r"video_provider_combo\.addItems\(\[(.*?)\]\)", WIDGET_SRC, re.S)
    assert m, "could not find video_provider_combo.addItems(...)"
    assert '"OpenAI Sora"' not in m.group(1), (
        '"OpenAI Sora" should not be in the provider combo (provider removed)'
    )


def test_no_stale_google_veo_label():
    # The combo emits "Gemini Veo"; the old save/restore checked "Google Veo",
    # which never matched and dropped saved Veo projects to slideshow.
    assert '"Google Veo"' not in WIDGET_SRC, (
        'stale "Google Veo" label present — save/restore must use "Gemini Veo"'
    )


def test_restore_uses_correct_findtext_labels():
    # Each restorable provider label must be looked up by its real combo text.
    for label in ("Gemini Veo", "Gemini Omni"):
        assert f'findText("{label}")' in WIDGET_SRC, (
            f"restore is missing findText({label!r})"
        )


def test_restore_accepts_lowercased_saved_values():
    # Saved values are combo text lower-cased. Restore must accept them.
    for saved in ("gemini veo", "gemini omni", "ffmpeg slideshow"):
        assert f'"{saved}"' in WIDGET_SRC, (
            f"restore does not handle saved provider value {saved!r}"
        )


def test_save_persists_omni_model():
    assert 'omni_model_combo.currentText()' in WIDGET_SRC, (
        "save path does not persist the selected Omni model"
    )


# ── Back-compat coercion tests ────────────────────────────────────────────────

def test_workspace_widget_coerces_sora_to_omni():
    """workspace_widget must detect saved 'sora'/'openai sora' and coerce to Omni."""
    assert '"sora"' in WIDGET_SRC or "'sora'" in WIDGET_SRC, (
        "workspace_widget does not handle the legacy 'sora' saved value"
    )
    assert '"openai sora"' in WIDGET_SRC or "'openai sora'" in WIDGET_SRC, (
        "workspace_widget does not handle the legacy 'openai sora' saved value"
    )
    # The coercion must redirect to Gemini Omni
    assert 'findText("Gemini Omni")' in WIDGET_SRC, (
        "workspace_widget coercion of Sora must call findText(\"Gemini Omni\")"
    )


def test_workspace_widget_shows_warning_on_sora_coercion():
    """workspace_widget must show a user-facing warning when coercing Sora→Omni."""
    assert 'show_warning' in WIDGET_SRC, (
        "workspace_widget must call show_warning when coercing Sora to Omni"
    )
    assert 'Provider Removed' in WIDGET_SRC, (
        "warning dialog must mention 'Provider Removed'"
    )


def test_video_project_tab_coerces_sora_to_omni():
    """video_project_tab must coerce 'OpenAI Sora' provider to 'Gemini Omni' at runtime."""
    assert "'OpenAI Sora'" in TAB_SRC or '"OpenAI Sora"' in TAB_SRC, (
        "video_project_tab does not check for the legacy 'OpenAI Sora' provider"
    )
    assert "Gemini Omni" in TAB_SRC, (
        "video_project_tab coercion must redirect to 'Gemini Omni'"
    )


def test_config_migrates_sora_default_provider():
    """VideoConfig._migrate_legacy_models must coerce 'sora' default_video_provider to 'omni'."""
    assert '"sora"' in CONFIG_SRC or "'sora'" in CONFIG_SRC, (
        "config does not check for legacy 'sora' default_video_provider"
    )
    assert '"omni"' in CONFIG_SRC or "'omni'" in CONFIG_SRC, (
        "config does not coerce legacy 'sora' to 'omni'"
    )
    # Ensure the migration is inside _migrate_legacy_models
    assert "_migrate_legacy_models" in CONFIG_SRC, (
        "_migrate_legacy_models method not found in config"
    )
