# GA Endpoint Migration (June 30, 2026 Deprecation) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all references to Google Cloud AI image/video endpoints scheduled for discontinuation on **June 30, 2026**, replacing them with the GA successors so ImageAI keeps working past that date.

**Architecture:** The migration touches three independent surfaces: (1) the Google image-provider model registry — drop Imagen 3/4 model IDs and route them to `gemini-2.5-flash-image`; (2) the `ImagenCustomizationProvider` strict-mode multi-reference path — replace the dying `imagen-3.0-capability-001` Vertex predict call with a Gemini-based path that injects references via `gemini-2.5-flash-image`; (3) the Veo client — remove `veo-3.0-generate-001`, `veo-3.0-fast-generate-001`, `veo-2.0-generate-001` from the model enum, GUI dropdowns, cost tables, and config defaults, routing them to `veo-3.1-generate-001` / `veo-3.1-fast-generate-001`. Each surface is independently testable and committed separately.

**Tech Stack:** Python 3.12, PySide6, `google.genai`, `google.cloud.aiplatform`, pytest.

**Source email:** `G:\Downloads\[Action Required] Migrate to newly available Cloud AI Image and Video GA endpoints.eml` (received 2026-03-23).

**Migration table (from email):**

| Discontinued | Replacement |
|---|---|
| `imagegeneration@002…006`, `imagetext@001`, `imagen-3.0-*`, `imagen-4.0-*` | `gemini-2.5-flash-image` |
| `veo-2.0-generate-001` | `veo-3.1-generate-001` |
| `veo-3.0-generate-001` | `veo-3.1-generate-001` |
| `veo-3.0-fast-generate-001` | `veo-3.1-fast-generate-001` |

**Affected GCP project:** `gen-lang-client-0898520379`.

---

## File Structure

### Files to modify
- `core/constants.py` — remove Imagen 4/3 entries from `PROVIDER_MODELS["google"]`
- `providers/google.py` — remove Imagen 4/3 entries from `MODEL_AUTH_REQUIREMENTS`, `get_models()`, `get_models_with_details()`; add migration shim that maps legacy IDs to `gemini-2.5-flash-image`
- `providers/imagen_customization.py` — replace the Vertex `imagen-3.0-capability-001` predict call with a Gemini-based reference-image generation, OR delete the file entirely if Task 4 chooses replacement-via-Gemini at the call site
- `providers/__init__.py` — remove or update the `imagen_customization` registration depending on Task 4 outcome
- `gui/main_window.py` — collapse the strict-mode branch (lines ~5541-5570) into the flexible-mode flow; drop the `imagen_customization` filtering scattered across the file
- `core/video/veo_client.py` — remove `VEO_3_GENERATE`, `VEO_3_FAST`, `VEO_2_GENERATE` enum members; remove their `MODEL_CONSTRAINTS` entries; delete the doc comment block (lines 49-60) entries for the dropped models
- `core/video/config.py` — change `"veo_model"` default to `"veo-3.1-generate-001"`; remove the three legacy entries from `veo_settings.models`; add a load-time migration that rewrites legacy IDs in user config files
- `gui/video/workspace_widget.py` — remove the three legacy IDs from `veo_model_combo.addItems()` (lines 1644-1646), tooltip block, and both `pricing` dicts (lines 6332-6342); update the tooltip to reflect the new lineup
- `gui/video/video_project_tab.py` — change line 952 default from `VEO_3_GENERATE` to `VEO_3_1_GENERATE`
- `core/video/project.py` — update the docstring example on line 456
- `gui/video/video_project_tab_old.py` — `_old.py` file; verify it's truly orphaned, then delete in Task 8

### Files to create
- `tests/migration/test_legacy_model_migration.py` — covers the config-load migration shim and the Google provider's legacy-ID alias behavior
- `Notes/2026-04-08-GA-migration-notes.md` — running notes captured during execution (created at the end as part of the wrap-up commit)

### Verification commands
- `python -m pytest tests/migration/ -v` — runs the new migration tests
- `python -c "from core.video.veo_client import VeoModel; print([m.value for m in VeoModel])"` — sanity check of the surviving Veo enum
- `python -c "from core.constants import PROVIDER_MODELS; assert all('imagen' not in m for m in PROVIDER_MODELS['google']); print('OK')"`
- `Grep imagen-[34]\.0|imagegeneration@|imagetext@|veo-[23]\.0- providers core gui` — must return zero functional references after Task 8

---

## Pre-flight: Setup

### Task 0: Branch + plan commit

**Files:**
- Create: `Plans/2026-04-08-GA-endpoint-migration.md` (this file)

- [ ] **Step 1: Verify branch state**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && git status
```

Expected: `main` branch, plan file untracked.

- [ ] **Step 2: Commit the plan file**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && git add Plans/2026-04-08-GA-endpoint-migration.md && git commit -m "docs(plans): add GA endpoint migration plan for June 30 2026 deprecation"
```

Expected: one commit created.

---

## Phase 1 — Veo migration (smallest, mechanical)

### Task 1: Drop Veo 3.0/2.0 from `core/video/veo_client.py`

**Files:**
- Modify: `core/video/veo_client.py:45-69` (enum), `:165-214` (MODEL_CONSTRAINTS)

- [ ] **Step 1: Remove the deprecated enum members**

In `core/video/veo_client.py`, replace the `VeoModel` class body (currently lines 62-69) with:

```python
    # Veo 3.1 (Latest - production GA)
    VEO_3_1_GENERATE = "veo-3.1-generate-001"       # 1080p, 8s fixed, reference images, frame interpolation
    VEO_3_1_FAST = "veo-3.1-fast-generate-001"      # 720p, 4-8s variable, fast (11-60s generation)
```

Also update the docstring (lines 46-61) to remove the bullets for `veo-3.0-generate-001`, `veo-3.0-fast-generate-001`, and `veo-2.0-generate-001`, and add a single line to the deprecated section: `- veo-3.0-*, veo-2.0-* → discontinued June 30 2026, use 3.1 GA`.

- [ ] **Step 2: Remove constraint entries for the dropped models**

In the `MODEL_CONSTRAINTS` dict (lines 165-214), delete the three entries keyed by `VeoModel.VEO_3_GENERATE`, `VeoModel.VEO_3_FAST`, and `VeoModel.VEO_2_GENERATE`. Keep only `VEO_3_1_GENERATE` and `VEO_3_1_FAST`.

- [ ] **Step 3: Update `VeoGenerationConfig.__post_init__` validation**

The current validation at lines 92-97 references `VeoModel.VEO_3_GENERATE`. Replace with:

```python
        # Veo 3.1 Standard: ONLY supports 8-second clips
        if self.model == VeoModel.VEO_3_1_GENERATE:
            if self.duration != 8:
                raise ValueError(
                    f"Veo 3.1 Standard ONLY supports 8-second clips, got {self.duration}. "
                    f"All scenes must be batched to exactly 8 seconds."
                )
        # Veo 3.1 Fast: Supports 4, 6, or 8 seconds
        elif self.model == VeoModel.VEO_3_1_FAST:
            if self.duration not in [4, 6, 8]:
                raise ValueError(
                    f"Veo 3.1 Fast duration must be 4, 6, or 8 seconds, got {self.duration}. "
                    f"Use snap_duration_to_veo() to convert float durations."
                )
```

Also update the reference-image validation block (lines 107-112): the allowed-models list becomes `[VeoModel.VEO_3_1_GENERATE, VeoModel.VEO_3_1_FAST]` and the error message no longer mentions Veo 2.0.

- [ ] **Step 4: Update `to_dict` audio handling**

Line 129 currently special-cases `VeoModel.VEO_3_GENERATE` for `include_audio`. Both 3.1 models support audio, so change to:

```python
        if self.model in (VeoModel.VEO_3_1_GENERATE, VeoModel.VEO_3_1_FAST):
            config["include_audio"] = self.include_audio
```

- [ ] **Step 5: Change the dataclass default**

Line 75: `model: VeoModel = VeoModel.VEO_3_GENERATE` → `model: VeoModel = VeoModel.VEO_3_1_GENERATE`.

- [ ] **Step 6: Syntax-check the file**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && python3 -c "import ast; ast.parse(open('core/video/veo_client.py').read()); print('OK')"
```

Expected: `OK`.

- [ ] **Step 7: Import-check the module**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && source .venv_linux/bin/activate && python -c "from core.video.veo_client import VeoModel, VeoGenerationConfig; print(sorted(m.value for m in VeoModel))"
```

Expected: `['veo-3.1-fast-generate-001', 'veo-3.1-generate-001']`.

- [ ] **Step 8: Commit**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && git add core/video/veo_client.py && git commit -m "feat(veo): drop Veo 3.0/2.0 GA models ahead of June 30 2026 deprecation"
```

---

### Task 2: Update Veo config defaults + add migration shim

**Files:**
- Modify: `core/video/config.py:19,35-58,108-131`
- Test: `tests/migration/test_legacy_model_migration.py`

- [ ] **Step 1: Write the failing test**

Create `tests/migration/__init__.py` (empty) and `tests/migration/test_legacy_model_migration.py`:

```python
"""Tests for legacy model migration shims (June 30 2026 GA deprecation)."""

import json
from pathlib import Path

import pytest

from core.video.config import VideoConfig


@pytest.fixture
def tmp_video_config(tmp_path: Path) -> Path:
    """Write a video_config.json containing legacy Veo IDs."""
    cfg = {
        "veo_model": "veo-3.0-generate-001",
        "veo_settings": {
            "models": {
                "veo-3.0-generate-001": {"duration": 8},
                "veo-2.0-generate-001": {"duration": 5},
            }
        },
    }
    target = tmp_path / "video_config.json"
    target.write_text(json.dumps(cfg))
    return target


def test_video_config_migrates_legacy_veo_default(tmp_video_config: Path):
    cfg = VideoConfig(config_file=tmp_video_config)
    assert cfg.get("veo_model") == "veo-3.1-generate-001"


def test_video_config_drops_legacy_veo_model_entries(tmp_video_config: Path):
    cfg = VideoConfig(config_file=tmp_video_config)
    models = cfg.get("veo_settings.models") or {}
    assert "veo-3.0-generate-001" not in models
    assert "veo-3.0-fast-generate-001" not in models
    assert "veo-2.0-generate-001" not in models
    assert "veo-3.1-generate-001" in models


def test_video_config_persists_migration(tmp_video_config: Path):
    VideoConfig(config_file=tmp_video_config).save()
    on_disk = json.loads(tmp_video_config.read_text())
    assert on_disk["veo_model"] == "veo-3.1-generate-001"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && source .venv_linux/bin/activate && python -m pytest tests/migration/test_legacy_model_migration.py -v
```

Expected: 3 failures (default still `veo-3.0-generate-001`, legacy entries still present).

- [ ] **Step 3: Update `DEFAULT_CONFIG` in `core/video/config.py`**

Change line 19 from `"veo_model": "veo-3.0-generate-001",` to `"veo_model": "veo-3.1-generate-001",`.

Replace the `veo_settings.models` block (lines 36-58) with only the GA models:

```python
            "models": {
                "veo-3.1-generate-001": {
                    "duration": 8,
                    "fps": 24,
                    "resolutions": ["720p", "1080p"],
                    "aspect_ratios": ["16:9", "9:16", "1:1"],
                    "has_audio": True
                },
                "veo-3.1-fast-generate-001": {
                    "duration": 8,
                    "fps": 24,
                    "resolutions": ["720p"],
                    "aspect_ratios": ["16:9", "9:16"],
                    "has_audio": True
                }
            },
```

- [ ] **Step 4: Add the migration shim to `load()`**

In `core/video/config.py`, add a private helper above `load()`:

```python
    _LEGACY_VEO_MIGRATION = {
        "veo-3.0-generate-001": "veo-3.1-generate-001",
        "veo-3.0-fast-generate-001": "veo-3.1-fast-generate-001",
        "veo-2.0-generate-001": "veo-3.1-generate-001",
    }

    def _migrate_legacy_models(self) -> None:
        """Rewrite legacy Veo model IDs in self.config to their GA replacements.

        Called from load() so any user config saved before the June 30 2026
        deprecation continues to work after this code change.
        """
        legacy_default = self.config.get("veo_model")
        if legacy_default in self._LEGACY_VEO_MIGRATION:
            new_default = self._LEGACY_VEO_MIGRATION[legacy_default]
            self.logger.info(
                f"Migrating legacy veo_model '{legacy_default}' -> '{new_default}'"
            )
            self.config["veo_model"] = new_default

        models = self.config.get("veo_settings", {}).get("models")
        if isinstance(models, dict):
            for legacy_id in list(models.keys()):
                if legacy_id in self._LEGACY_VEO_MIGRATION:
                    self.logger.info(
                        f"Dropping legacy veo_settings.models entry '{legacy_id}'"
                    )
                    models.pop(legacy_id)
            # Make sure the GA models are present
            for ga_id in ("veo-3.1-generate-001", "veo-3.1-fast-generate-001"):
                if ga_id not in models:
                    models[ga_id] = self.DEFAULT_CONFIG["veo_settings"]["models"][ga_id]
```

Then in `load()`, immediately after `self._deep_merge(self.config, file_config)` (currently line 124), add:

```python
            self._migrate_legacy_models()
```

- [ ] **Step 5: Re-run the tests**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && source .venv_linux/bin/activate && python -m pytest tests/migration/test_legacy_model_migration.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 6: Commit**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && git add core/video/config.py tests/migration/ && git commit -m "feat(video-config): default to Veo 3.1 GA + migrate legacy user configs"
```

---

### Task 3: Update Veo GUI dropdowns, pricing, and dependent code

**Files:**
- Modify: `gui/video/workspace_widget.py:1641-1672` (combo + tooltip), `:6328-6343` (pricing dicts)
- Modify: `gui/video/video_project_tab.py:952`
- Modify: `core/video/project.py:456` (comment only)

- [ ] **Step 1: Trim the model combo and tooltip**

In `gui/video/workspace_widget.py`, replace the `addItems` block (lines 1641-1647) with:

```python
        self.veo_model_combo.addItems([
            "veo-3.1-generate-001",            # Veo 3.1 Standard - 1080p, 8s, ref images, audio
            "veo-3.1-fast-generate-001",       # Veo 3.1 Fast - 720p, 4-8s, 11-60s generation
        ])
```

Replace the tooltip string (lines 1652-1670) with the trimmed version below — keeping only the surviving models so users don't see the deprecated lineup:

```python
        self.veo_model_combo.setToolTip(
            "Veo Model Selection (post June 30 2026 GA):\n\n"
            "Veo 3.1 Standard ($0.40/sec audio, $0.20/sec video):\n"
            "  - 1080p resolution, 8 seconds fixed\n"
            "  - Reference images (up to 3), scene extension\n"
            "  - Frame-to-frame interpolation\n"
            "  - Generation time: 1-6 minutes\n\n"
            "Veo 3.1 Fast ($0.15/sec audio, $0.10/sec video):\n"
            "  - 720p resolution, 4-8 seconds variable\n"
            "  - Reference images, scene extension\n"
            "  - Generation time: 11-60 seconds (FAST!)"
        )
```

- [ ] **Step 2: Trim both pricing dicts**

In the same file, lines 6328-6343, the two `pricing` dicts inside `_update_cost_estimate` should each contain only the two surviving keys:

```python
        if include_audio:
            pricing = {
                "veo-3.1-generate-001": 0.40,
                "veo-3.1-fast-generate-001": 0.15,
            }
        else:
            pricing = {
                "veo-3.1-generate-001": 0.20,
                "veo-3.1-fast-generate-001": 0.10,
            }
```

- [ ] **Step 3: Update `video_project_tab.py` default**

Change line 952 from:

```python
            selected_model = VeoModel.VEO_3_GENERATE
```

to:

```python
            selected_model = VeoModel.VEO_3_1_GENERATE
```

- [ ] **Step 4: Update the docstring example in `core/video/project.py`**

Change line 456 from:

```python
    video_model: Optional[str] = None  # For Veo: 'veo-3.0-generate-001', etc.
```

to:

```python
    video_model: Optional[str] = None  # For Veo: 'veo-3.1-generate-001', etc.
```

- [ ] **Step 5: Syntax-check the modified files**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && python3 -c "import ast; [ast.parse(open(f).read()) for f in ['gui/video/workspace_widget.py','gui/video/video_project_tab.py','core/video/project.py']]; print('OK')"
```

Expected: `OK`.

- [ ] **Step 6: Verify zero functional Veo legacy references remain**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && grep -rn "veo-3\.0-\|veo-2\.0-\|VEO_3_GENERATE\|VEO_3_FAST\|VEO_2_GENERATE" core gui providers --include="*.py" | grep -v video_project_tab_old.py
```

Expected: no output (the `_old.py` file is dropped in Task 8).

- [ ] **Step 7: Commit**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && git add gui/video/workspace_widget.py gui/video/video_project_tab.py core/video/project.py && git commit -m "feat(video-ui): drop Veo 3.0/2.0 from dropdowns and pricing tables"
```

---

## Phase 2 — Imagen image-model removal

### Task 4: Decide and execute strict-mode replacement

**Decision:** Strict-mode (Imagen 3 Customization with `[1]/[2]/[3]/[4]` reference tags) cannot survive — `imagen-3.0-capability-001` is in the discontinuation list. The flexible-mode path (Gemini-based) already handles multi-reference via `reference_images` (a list of byte buffers passed straight to `gemini-2.5-flash-image`). The cleanest replacement is to **collapse strict mode into the existing direct-mode flexible path** and rewrite the `[N]` tags inline before sending the prompt to Gemini.

**Files:**
- Delete: `providers/imagen_customization.py`
- Modify: `providers/__init__.py:75-80` (drop the conditional import + registration)
- Modify: `gui/main_window.py:5541-5570` (strict-mode branch), and the four other places that filter `imagen_customization` out of the provider list (lines 589, 738-739, 1542-1543, 7535) plus the migration shim at lines 131-133 and the lowercase check at lines 5113, 5224-5225, 5413, 5555-5559, 5646
- Modify: `gui/video/reference_generation_dialog.py:258` (drop the same filter)

- [ ] **Step 1: Read the strict-mode branch in `gui/main_window.py`**

Skim lines 5541-5610 of `gui/main_window.py` so you understand what state it touches: it sets `use_imagen_customization = True`, swaps `self.current_provider`, stores the original provider in `self._imagen_original_provider`, and forwards `references` in `kwargs`. The replacement keeps the original provider and instead inlines the references into the existing direct-mode flexible path.

- [ ] **Step 2: Replace the strict-mode branch**

In `gui/main_window.py`, replace the entire `else:` block starting at line 5541 (`# Strict mode: Use Imagen 3 Customization (subject preservation)`) and ending at the matching block close (the line before the next sibling `if`/`elif`). The replacement preserves the `[N]`-tag UX but routes through Gemini:

```python
            else:
                # Strict mode: Use Gemini multi-reference (post June 30 2026 GA).
                # Imagen 3 Customization (imagen-3.0-capability-001) was discontinued;
                # we now satisfy strict-mode by passing references directly to Gemini
                # and rewriting the [N] tags into natural-language references in the prompt.
                import re
                ref_tags = re.findall(r'\[(\d+)\]', prompt)
                if not ref_tags:
                    msg = (f"Your prompt must reference the images using tags like [1], [2], etc.\n\n"
                           f"You have {len(references)} reference image(s).\n"
                           f"Example: 'A photo of [1] and [2] at the beach'")
                    self._append_to_console(f"ERROR: {msg}", "#ff6666")
                    QMessageBox.warning(self, APP_NAME, msg)
                    self.btn_generate.setEnabled(True)
                    return

                # Rewrite [N] tags into natural-language references the model can ground
                # against the corresponding reference image position in the list.
                rewritten_prompt = prompt
                for idx, ref in enumerate(references, start=1):
                    label = ref.subject_description or f"reference image {idx}"
                    rewritten_prompt = rewritten_prompt.replace(f"[{idx}]", label)
                prompt = rewritten_prompt

                reference_images = []
                for ref in references:
                    with open(ref.path, 'rb') as f:
                        reference_images.append(f.read())
                    self._append_to_console(
                        f"  Strict-mode reference [{ref.reference_id}]: {ref.path.name}",
                        "#66ccff"
                    )
                kwargs['reference_images'] = reference_images

                self._append_to_console(
                    f"Using Strict mode (Gemini multi-reference) with {len(references)} reference image(s)",
                    "#00ff00"
                )
                self._append_to_console(
                    f"Rewritten prompt: {prompt}",
                    "#888888"
                )
```

This deletes the `use_imagen_customization = True` / `self.current_provider = "imagen_customization"` swap. Search the rest of the function for any later use of `use_imagen_customization` and `self._imagen_original_provider` and remove those branches as well — they no longer have a purpose because the provider never switches.

- [ ] **Step 3: Remove the `imagen_customization` filtering and migration shim**

In `gui/main_window.py`, delete the now-dead code:

- Lines 131-133 (the `imagen_customization` → `google` migration shim — there's no longer any such selection to migrate from a fresh perspective; if user configs may still hold `"imagen_customization"`, leave the shim in place but add a comment that it's permanent and only fires once)
- Line 589: `available_providers = [p for p in available_providers if p != "imagen_customization"]`
- Lines 738-739, 1542-1543, 7535: same line, delete each
- Lines 5113, 5224-5225, 5413, 5646: any reference to the literal `"imagen_customization"` provider name — drop the OR-clause so the conditions only check for `"google"`
- Line 5413: `use_imagen_customization = False` — delete
- Lines 5555-5570: already covered by Step 2

After editing, run:

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && grep -n "imagen_customization" gui/main_window.py
```

The only acceptable surviving reference is the migration shim (lines ~131-133) if you decided to keep it. Everything else must be gone.

- [ ] **Step 4: Drop the provider registration**

In `providers/__init__.py`, delete lines 75-80 (the `try` block that imports `ImagenCustomizationProvider` and registers it under `"imagen_customization"`).

- [ ] **Step 5: Drop the same filter from the video reference dialog**

In `gui/video/reference_generation_dialog.py`, delete line 258.

- [ ] **Step 6: Delete the provider file**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && git rm providers/imagen_customization.py
```

- [ ] **Step 7: Syntax + import sanity check**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && python3 -c "import ast; [ast.parse(open(f).read()) for f in ['gui/main_window.py','providers/__init__.py','gui/video/reference_generation_dialog.py']]; print('OK')"
cd /mnt/d/Documents/Code/GitHub/ImageAI && source .venv_linux/bin/activate && python -c "from providers import list_providers; print(list_providers()); assert 'imagen_customization' not in list_providers()"
```

Expected: `OK`, then a list of providers that does NOT include `imagen_customization`.

- [ ] **Step 8: Commit**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && git add -u providers/__init__.py gui/main_window.py gui/video/reference_generation_dialog.py && git commit -m "feat(strict-mode): replace Imagen 3 Customization with Gemini multi-reference"
```

---

### Task 5: Drop Imagen 3/4 IDs from the Google provider model registry

**Files:**
- Modify: `core/constants.py:24-33`
- Modify: `providers/google.py:68-91, 1620-1684`
- Test: `tests/migration/test_legacy_model_migration.py` (extend)

- [ ] **Step 1: Extend the migration test to cover Imagen aliasing**

Append to `tests/migration/test_legacy_model_migration.py`:

```python
from core.constants import PROVIDER_MODELS
from providers.google import GoogleProvider


LEGACY_IMAGEN_IDS = [
    "imagen-3.0-generate-002",
    "imagen-4.0-generate-001",
    "imagegeneration@006",
    "imagetext@001",
    "imagen-3.0-capability-001",
]


def test_constants_no_longer_lists_imagen_models():
    google_models = PROVIDER_MODELS["google"]
    for legacy in LEGACY_IMAGEN_IDS:
        assert legacy not in google_models, f"{legacy} still in PROVIDER_MODELS"


def test_google_provider_aliases_legacy_imagen_to_gemini(monkeypatch):
    config = {"api_key": "test-key"}
    provider = GoogleProvider(config)
    for legacy in LEGACY_IMAGEN_IDS:
        resolved = provider.resolve_model_alias(legacy)
        assert resolved == "gemini-2.5-flash-image", (
            f"Expected {legacy} -> gemini-2.5-flash-image, got {resolved}"
        )
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && source .venv_linux/bin/activate && python -m pytest tests/migration/test_legacy_model_migration.py -v
```

Expected: failures — `imagen-*` keys still present in `PROVIDER_MODELS`, and `GoogleProvider.resolve_model_alias` does not exist yet.

- [ ] **Step 3: Remove the Imagen entries from `core/constants.py`**

In `core/constants.py`, the `"google"` block of `PROVIDER_MODELS` (lines 24-33) becomes:

```python
    "google": {
        # Gemini Image Generation (API key or gcloud) - newest first
        "gemini-3-pro-image-preview": "Gemini 3 Pro Image (Nano Banana Pro) - 4K",
        "gemini-3.1-flash-image-preview": "Gemini 3.1 Flash Image (Nano Banana 2) - 2K",
        "gemini-2.5-flash-image": "Gemini 2.5 Flash Image (Nano Banana)",
    },
```

- [ ] **Step 4: Remove the Imagen entries from `providers/google.py`**

Delete the `imagen-4.0-generate-001` and `imagen-3.0-generate-002` entries from `MODEL_AUTH_REQUIREMENTS` (lines 68-90), `get_models()` (lines 1626-1628), and `get_models_with_details()` (lines 1669-1684). Leave the surrounding Gemini entries intact.

- [ ] **Step 5: Add the alias resolver method**

Add a class-level constant and method to `GoogleProvider` in `providers/google.py` (place near `get_default_model`):

```python
    LEGACY_IMAGE_MODEL_ALIASES = {
        # All discontinued Vertex Image endpoints redirect to gemini-2.5-flash-image.
        # Source: Google Cloud deprecation notice, June 30 2026.
        "imagen-3.0-generate-001": "gemini-2.5-flash-image",
        "imagen-3.0-generate-002": "gemini-2.5-flash-image",
        "imagen-3.0-fast-generate-001": "gemini-2.5-flash-image",
        "imagen-3.0-capability-001": "gemini-2.5-flash-image",
        "imagen-3.0-capability-002": "gemini-2.5-flash-image",
        "imagen-4.0-generate-001": "gemini-2.5-flash-image",
        "imagen-4.0-fast-generate-001": "gemini-2.5-flash-image",
        "imagen-4.0-ultra-generate-001": "gemini-2.5-flash-image",
        "imagegeneration@002": "gemini-2.5-flash-image",
        "imagegeneration@003": "gemini-2.5-flash-image",
        "imagegeneration@004": "gemini-2.5-flash-image",
        "imagegeneration@005": "gemini-2.5-flash-image",
        "imagegeneration@006": "gemini-2.5-flash-image",
        "imagetext@001": "gemini-2.5-flash-image",
    }

    def resolve_model_alias(self, model: str) -> str:
        """Map a possibly-legacy model ID to the current GA equivalent.

        Returns the input unchanged if it isn't a known legacy ID.
        """
        return self.LEGACY_IMAGE_MODEL_ALIASES.get(model, model)
```

- [ ] **Step 6: Wire the alias into `generate_image`**

Find the entry point in `providers/google.py` where the model name is read off `kwargs` (search for `model = kwargs.get("model"` or the `def generate_image` definition). Immediately after the model is resolved, add:

```python
        model = self.resolve_model_alias(model)
```

This guarantees that any saved user project, template, or CLI argument carrying a legacy ID still produces an image after the deprecation date.

- [ ] **Step 7: Run the migration tests**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && source .venv_linux/bin/activate && python -m pytest tests/migration/test_legacy_model_migration.py -v
```

Expected: all tests pass (3 from Task 2 + 2 new ones = 5 total).

- [ ] **Step 8: Commit**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && git add core/constants.py providers/google.py tests/migration/test_legacy_model_migration.py && git commit -m "feat(google-provider): drop Imagen models, alias legacy IDs to gemini-2.5-flash-image"
```

---

## Phase 3 — Cleanup, smoke test, docs

### Task 6: Update `scripts/fetch_model_capabilities.py` and other helpers

**Files:**
- Modify: `scripts/fetch_model_capabilities.py`
- Modify: any other matches from the initial grep that turned out to be functional

- [ ] **Step 1: Inspect the script**

Read `scripts/fetch_model_capabilities.py` and identify whether it queries Vertex for the legacy Imagen / Veo IDs. If it does, replace each occurrence with the GA replacement from the migration table at the top of this plan.

- [ ] **Step 2: Re-run the global grep**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && grep -rn "imagen-[34]\.0\|imagegeneration@\|imagetext@\|veo-3\.0-\|veo-2\.0-" scripts core providers gui --include="*.py"
```

The only remaining hits should be inside `LEGACY_IMAGE_MODEL_ALIASES` in `providers/google.py`, the deprecation comment in `core/video/veo_client.py`, and the `_LEGACY_VEO_MIGRATION` map in `core/video/config.py`. Anything else is a real reference and must be fixed before continuing.

- [ ] **Step 3: Commit (only if changes were needed)**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && git add -u scripts/ && git commit -m "chore(scripts): refresh fetch_model_capabilities for GA endpoints"
```

If no edits were necessary, skip the commit and add a note in the wrap-up doc (Task 8).

---

### Task 7: GUI smoke test (manual but scripted)

**Files:** none (manual verification)

- [ ] **Step 1: Launch the GUI**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && source .venv_linux/bin/activate && python main.py
```

- [ ] **Step 2: Verify the Google provider model dropdown**

Open Settings → Provider: Google. The model dropdown must contain only the three Gemini entries (Nano Banana Pro / 2 / 1). No Imagen 3 / Imagen 4 rows.

- [ ] **Step 3: Verify the Veo dropdown**

Open the Video tab. The Veo model combobox must contain only `veo-3.1-generate-001` and `veo-3.1-fast-generate-001`. The cost-estimate label must show a non-`N/A` value when Gemini Veo is selected.

- [ ] **Step 4: Verify strict-mode references**

In the Generate tab, add 2 reference images and toggle the reference widget into strict mode. Enter a prompt like `A photo of [1] and [2] at the beach` and click Generate. Watch the status console — it should say `Using Strict mode (Gemini multi-reference)` and `Rewritten prompt: A photo of reference image 1 and reference image 2 at the beach`. The image should generate without ever switching providers.

- [ ] **Step 5: Verify the migration shim with a legacy config**

Quit the app, then edit `~/.config/ImageAI/video_config.json` (or the platform equivalent) and set `"veo_model": "veo-3.0-generate-001"`. Relaunch the app, open the Video tab, and confirm the dropdown defaults to `veo-3.1-generate-001` and the JSON file on disk has been rewritten.

- [ ] **Step 6: Capture findings**

Note any issues uncovered during the smoke test in `Notes/2026-04-08-GA-migration-notes.md` (created in Task 8). If a real bug is found, stop and fix it under a new commit before proceeding.

---

### Task 8: Final cleanup, dead code removal, wrap-up doc

**Files:**
- Delete: `gui/video/video_project_tab_old.py` (only if confirmed unused)
- Create: `Notes/2026-04-08-GA-migration-notes.md`
- Modify: `CHANGELOG.md`, `README.md` (if they reference the dropped models)

- [ ] **Step 1: Confirm `_old.py` is dead**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && grep -rn "video_project_tab_old" --include="*.py"
```

If the only matches are imports inside `video_project_tab_old.py` itself (no external import), the file is safe to delete:

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && git rm gui/video/video_project_tab_old.py
```

If something else imports it, leave it alone and update its model references to GA the same way you did the live tab.

- [ ] **Step 2: Update `CHANGELOG.md`**

Read the top of `CHANGELOG.md`, then add a new section above the latest entry:

```markdown
## [Unreleased]

### Removed
- Imagen 3 / Imagen 4 model selections from the Google provider (discontinued by Google on June 30 2026).
- Veo 3.0, Veo 3.0 Fast, and Veo 2.0 video models (same deprecation).
- `providers/imagen_customization.py` (`imagen-3.0-capability-001` Vertex predict endpoint discontinued).

### Changed
- Strict-mode multi-reference image generation now routes through `gemini-2.5-flash-image` with inlined `[N]` tag rewriting instead of the discontinued Imagen 3 Customization API.
- Default Veo model is now `veo-3.1-generate-001`.
- Legacy Veo IDs in saved video configs are auto-migrated on load.
- Legacy Imagen IDs (CLI arguments, saved projects, templates) are aliased to `gemini-2.5-flash-image` at generate time.
```

- [ ] **Step 3: Update `README.md` if needed**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && grep -n "imagen-[34]\.0\|veo-3\.0-\|veo-2\.0-\|imagen.*customization" README.md
```

Replace any user-facing mentions of the dropped models with the GA equivalents, or remove the section entirely if it's no longer relevant.

- [ ] **Step 4: Write the wrap-up notes**

Create `Notes/2026-04-08-GA-migration-notes.md` with the date, the GitHub issue/email reference, the list of commits in the migration, and any findings from Task 7's smoke test. Keep it short — this is for future-you to know what happened and why.

- [ ] **Step 5: Final global verification**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && grep -rn "imagen-[34]\.0\|imagegeneration@\|imagetext@\|veo-3\.0-\|veo-2\.0-" core providers gui scripts --include="*.py" | grep -v "LEGACY_\|_LEGACY_\|deprecated\|discontinued"
```

Expected: zero functional references.

- [ ] **Step 6: Run the full migration test suite**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && source .venv_linux/bin/activate && python -m pytest tests/migration/ -v
```

Expected: 5 passing.

- [ ] **Step 7: Commit and note completion**

```bash
cd /mnt/d/Documents/Code/GitHub/ImageAI && git add -A CHANGELOG.md README.md Notes/2026-04-08-GA-migration-notes.md && git commit -m "docs(migration): wrap up GA endpoint migration for June 30 2026"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Every legacy endpoint from the email's migration table is handled — Imagen 3.x/4.x and `imagegeneration@*`/`imagetext@*` IDs are removed from the registry and aliased at generate time (Task 5); `imagen-3.0-capability-001` is removed by deleting `imagen_customization.py` (Task 4); Veo 3.0 / 3.0 fast / 2.0 are removed from the enum, defaults, dropdowns, pricing, and user configs (Tasks 1-3).
- [x] **Placeholder scan:** No `TBD`, `add appropriate error handling`, or `similar to Task N` references — every step shows the exact code or command.
- [x] **Type consistency:** `VeoModel` member names (`VEO_3_1_GENERATE`, `VEO_3_1_FAST`) are used consistently across Tasks 1, 3 and the test in Task 2. `LEGACY_IMAGE_MODEL_ALIASES` and `_LEGACY_VEO_MIGRATION` are referenced under their declared names. `resolve_model_alias` is defined in Task 5 Step 5 and called in Task 5 Step 6.
- [x] **Execution order:** Phase 1 (Veo) is independent and ships first because the Veo deprecation is the more time-sensitive of the two surfaces (the preview deprecation already passed on April 2). Phase 2 (Imagen) follows. Phase 3 cleans up and smoke-tests.
