"""Regression tests for video-provider save/restore label consistency.

The provider combo emits labels like "Gemini Veo" / "OpenAI Sora" /
"Gemini Omni", and persistence saves ``combo.currentText().lower()`` then
restores via ``findText(<label>)``. A drift between the saved label and the
``findText`` label silently drops the provider to the default (this is the
"Google Veo" vs "Gemini Veo" bug fixed alongside the Omni work).

These tests scan the workspace-widget source so they run without a display
(the GUI is not headless-constructable), and assert the label contract holds.
"""

import re
from pathlib import Path

WIDGET_SRC = (
    Path(__file__).resolve().parents[2] / "gui" / "video" / "workspace_widget.py"
).read_text(encoding="utf-8")

# Labels the provider combo actually offers (must match findText() targets).
COMBO_LABELS = ["FFmpeg Slideshow", "Gemini Veo", "OpenAI Sora", "Gemini Omni"]


def test_combo_offers_all_four_providers():
    m = re.search(r"video_provider_combo\.addItems\(\[(.*?)\]\)", WIDGET_SRC, re.S)
    assert m, "could not find video_provider_combo.addItems(...)"
    items = m.group(1)
    for label in COMBO_LABELS:
        assert f'"{label}"' in items, f"combo missing provider label {label!r}"


def test_no_stale_google_veo_label():
    # The combo emits "Gemini Veo"; the old save/restore checked "Google Veo",
    # which never matched and dropped saved Veo projects to slideshow.
    assert '"Google Veo"' not in WIDGET_SRC, (
        'stale "Google Veo" label present — save/restore must use "Gemini Veo"'
    )


def test_restore_uses_correct_findtext_labels():
    # Each restorable provider label must be looked up by its real combo text.
    for label in ("Gemini Veo", "OpenAI Sora", "Gemini Omni"):
        assert f'findText("{label}")' in WIDGET_SRC, (
            f"restore is missing findText({label!r})"
        )


def test_restore_accepts_lowercased_saved_values():
    # Saved values are combo text lower-cased. Restore must accept them.
    for saved in ("gemini veo", "openai sora", "gemini omni", "ffmpeg slideshow"):
        assert f'"{saved}"' in WIDGET_SRC, (
            f"restore does not handle saved provider value {saved!r}"
        )


def test_save_persists_omni_model():
    assert 'omni_model_combo.currentText()' in WIDGET_SRC, (
        "save path does not persist the selected Omni model"
    )
