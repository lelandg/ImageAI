# Google Imagen 3 Multiple Reference Images - Implementation Plan

**Status:** PHASE 3 COMPLETE ✅ + PERSISTENCE COMPLETE ✅
**Priority:** HIGH
**Last Updated:** 2025-10-30 08:35 (Persistence feature added - references now auto-save)

## Executive Summary

Google's Imagen 3 API supports **up to 4 reference images simultaneously** through the Imagen 3 Customization capability (`imagen-3.0-capability-001` model). This feature enables advanced use cases like:
- Multi-character consistency (e.g., two people in one scene)
- Subject + style combination (e.g., specific person in watercolor style)
- Product composition with multiple items
- Scene composition with multiple reference elements

**Key Finding:** The current implementation uses `gemini-2.5-flash-image` which does NOT support multiple reference images. We need to implement the Imagen 3 Customization API separately.

---

## Table of Contents

1. [API Capabilities Overview](#api-capabilities-overview)
2. [Current Implementation Analysis](#current-implementation-analysis)
3. [Technical Architecture](#technical-architecture)
4. [Implementation Phases](#implementation-phases)
5. [API Integration Details](#api-integration-details)
6. [UI/UX Design](#uiux-design)
7. [Code Structure](#code-structure)
8. [Testing Strategy](#testing-strategy)
9. [Documentation Requirements](#documentation-requirements)

---

## API Capabilities Overview

### Supported Features

| Feature | Details |
|---------|---------|
| **Max References** | 4 images per generation request |
| **Reference Types** | SUBJECT, STYLE, CONTROL, RAW (edit mode), MASK (edit mode) |
| **Reference ID System** | Each image has referenceId (1-4), multiple images can share same ID |
| **Prompt Syntax** | Use `[1]`, `[2]`, `[3]`, `[4]` to reference images in text prompt |
| **Subject Types** | PERSON, ANIMAL, PRODUCT, DEFAULT |
| **Control Types** | FACE_MESH, CANNY (edge detection), SCRIBBLE |
| **Model** | `imagen-3.0-capability-001` (NOT `imagen-3.0-generate-002`) |

### API Endpoint

**Vertex AI (Google Cloud):**
```
https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/imagen-3.0-capability-001:predict
```

**Authentication:** Requires Application Default Credentials (ADC) or service account

---

## Current Implementation Analysis

### Existing Code Review

**File: `providers/google.py:452-568`**
- ✅ Single reference image support exists
- ✅ Handles aspect ratio and canvas composition
- ✅ PIL Image integration
- ❌ No Imagen 3 Customization API integration
- ❌ Uses `gemini-2.5-flash-image` (different API)
- ❌ No multi-reference image handling

**File: `gui/reference_image_dialog.py`**
- Purpose: Analyzes images with LLM vision to generate descriptions
- NOT for image generation reference (different use case)

**File: `core/video/reference_manager.py:1-200`**
- ✅ Reference image types: CHARACTER, OBJECT, ENVIRONMENT, STYLE
- ✅ Validation system for Veo 3 requirements
- 🔄 Can be adapted for Imagen 3 reference types

### Gap Analysis

| Needed | Status | Priority |
|--------|--------|----------|
| Imagen 3 Customization API client | ❌ Missing | **HIGH** |
| Multi-reference image upload | ❌ Missing | **HIGH** |
| Reference type selection (SUBJECT/STYLE) | ❌ Missing | **HIGH** |
| Prompt generation with [N] syntax | ❌ Missing | **HIGH** |
| Reference ID management | ❌ Missing | MEDIUM |
| Subject description for references | ❌ Missing | MEDIUM |
| Control-based customization UI | ❌ Missing | LOW |

---

## Technical Architecture

### Component Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                    Generate Tab (Main UI)                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Reference Images Section (NEW)                      │    │
│  │  - Add Reference button                             │    │
│  │  - Reference list with type badges                  │    │
│  │  - Drag to reorder (sets reference IDs)             │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Prompt Editor                                       │    │
│  │  - Auto-insert [1], [2] tags when referencing       │    │
│  │  - Syntax highlighting for reference tags           │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              ImagenCustomizationProvider                     │
│  - upload_references()                                       │
│  - build_customization_request()                            │
│  - generate_with_references()                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│           Google Vertex AI - Imagen 3 API                   │
│  Model: imagen-3.0-capability-001                           │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Action                    System Processing
──────────                     ─────────────────
1. Load reference images  ──►  Validate format/size
                               Store in ReferenceImage objects

2. Set reference types    ──►  Map to API types (SUBJECT/STYLE)
                               Assign reference IDs (1-4)

3. Write prompt           ──►  Parse [N] tags
   with [1], [2]               Validate reference IDs exist

4. Click Generate         ──►  Build API request:
                               - Upload images to inline_data
                               - Set referenceType for each
                               - Add subject descriptions
                               - Include prompt with [N] tags

5. API Response           ──►  Download generated image
                               Display in UI
```

---

## Implementation Phases

### Phase 1: Core API Integration ✅ COMPLETED

**Status:** ✅ COMPLETE (2025-10-29)

**Goal:** Get basic multi-reference working with Imagen 3 Customization API

#### Tasks:
- [x] Create `providers/imagen_customization.py` with new provider class
- [x] Implement authentication (ADC/Service Account)
- [x] Implement `generate_with_references()` with up to 4 images
- [x] Add basic error handling and logging
- [x] Create comprehensive test script

**Files Created:**
- ✅ `core/reference/__init__.py` - Reference package
- ✅ `core/reference/imagen_reference.py` - Data models (195 lines)
- ✅ `providers/imagen_customization.py` - API provider (456 lines)
- ✅ `test_imagen_customization.py` - Test script (448 lines)
- ✅ `Plans/Phase1-Completion-Summary.md` - Completion details

**Files Modified:**
- ✅ `providers/__init__.py` - Registered new provider

**Deliverables:**
- ✅ Working API client that can send 1-4 reference images
- ✅ Full prompt validation with [N] tag support
- ✅ Test script with multiple scenarios (single, double, style transfer)
- ✅ Reference data models with validation
- ✅ Comprehensive logging and error handling

**See:** `Plans/Phase1-Completion-Summary.md` for full details

---

### Phase 2: Reference Management System ✅ COMPLETED

**Status:** ✅ COMPLETE (2025-10-29) - Delivered as part of Phase 1

**Goal:** Robust reference image handling with types and validation

#### Tasks:
- [x] Create `core/reference/imagen_reference.py` - Reference image model
- [x] Implement reference type enum (SUBJECT, STYLE, CONTROL)
- [x] Implement subject type enum (PERSON, ANIMAL, PRODUCT)
- [x] Add validation for Imagen 3 requirements
- [x] Create reference ID assignment logic (1-4)
- [x] Implement reference ordering/reordering (via `auto_assign_reference_ids()`)
- [x] Add subject description support

**Data Model:**
```python
@dataclass
class ImagenReference:
    """Reference image for Imagen 3 customization"""
    path: Path
    reference_type: ImagenReferenceType  # SUBJECT, STYLE, CONTROL
    reference_id: int  # 1-4
    subject_type: Optional[ImagenSubjectType] = None  # PERSON, ANIMAL, PRODUCT
    subject_description: Optional[str] = None
    control_type: Optional[str] = None  # FACE_MESH, CANNY, SCRIBBLE
    image_data: Optional[bytes] = None
    mime_type: str = "image/png"
```

**Files Created:**
- ✅ `core/reference/imagen_reference.py` - Reference data model (240 lines)
  - Includes: ImagenReference dataclass, all enums, validation helpers
  - `validate_references()` function for API submission validation
  - `auto_assign_reference_ids()` for automatic ID assignment

**Deliverables:**
- ✅ Reference image data structure - Complete
- ✅ Validation against Imagen 3 specs - Complete
- ✅ Reference ID management (auto-assign, reorder) - Complete

**Notes:**
- Phase 2 was completed as part of Phase 1 implementation
- All planned data models and validation logic delivered
- No additional validation file needed - integrated into main module

---

### Phase 3: UI Components ✅ COMPLETED

**Status:** ✅ COMPLETE (2025-10-29 21:30)

**Goal:** User-friendly interface for managing multiple reference images in Generate tab

**Important Note:** This is for **image generation** (Generate tab), NOT video generation. Do not confuse with `gui/video/reference_images_widget.py` which is for Veo 3 video projects.

#### Tasks:
- [x] Create `gui/imagen_reference_widget.py` - Reference list widget for Generate tab (540 lines)
- [x] Implement automatic reference ID assignment (1-4)
- [x] Add reference type selector (SUBJECT/STYLE/CONTROL)
- [x] Add subject type selector (for SUBJECT references)
- [x] Add "Add Reference" button with file picker
- [x] Display reference thumbnails with type badges
- [x] Show reference ID numbers [1], [2], [3], [4]
- [x] Implement reference removal (clear button)
- [x] Add subject description editor (optional text field)
- [x] Integrate widget into `gui/main_window.py` Generate tab
- [x] Wire up to ImagenCustomizationProvider for generation
- [x] Add reference tag insertion buttons [1], [2], [3], [4]
- [x] Implement prompt validation (requires [N] tags when references exist)
- [x] Auto-update prompt placeholder with reference hints

**UI Mockup:**
```
┌─────────────────────────────────────────────────────┐
│ Reference Images (0/4)                [+ Add Image] │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────────────────────────────────────┐       │
│  │ [1] 🖼️ portrait.jpg              [SUBJECT]│  [×]  │
│  │     PERSON • "young woman, brown hair"   │       │
│  └─────────────────────────────────────────┘       │
│                                                      │
│  ┌─────────────────────────────────────────┐       │
│  │ [2] 🎨 watercolor.jpg              [STYLE]│  [×]  │
│  │     "soft watercolor painting style"     │       │
│  └─────────────────────────────────────────┘       │
│                                                      │
│  💡 Use [1] and [2] in your prompt to reference    │
│     these images                                    │
└─────────────────────────────────────────────────────┘
```

**Files Created:**
- ✅ `gui/imagen_reference_widget.py` - Reference list UI component (540 lines)
  - `ImagenReferenceItemWidget` - Individual reference item display with thumbnail, type selectors, description
  - `ImagenReferenceWidget` - Main container managing up to 4 references

**Files Modified:**
- ✅ `gui/main_window.py` - Multiple additions:
  - Line 627-633: Added ImagenReferenceWidget to Generate tab layout
  - Line 658-686: Added reference tag insertion buttons [1], [2], [3], [4] in prompt header
  - Line 3543-3555: Added `_update_imagen_reference_visibility()` method
  - Line 3589-3613: Added `_on_imagen_references_changed()` callback
  - Line 3615-3621: Added `_insert_reference_tag()` helper method
  - Line 4788-4834: Added Imagen customization routing in `_generate()` with validation

**Deliverables:**
- ✅ Working reference management UI - Complete
- ✅ Visual feedback for reference IDs and types - Complete with color-coded badges
- ✅ Intuitive reference ordering - Automatic ID assignment
- ✅ Integration with image generation flow - Complete with validation
- ✅ Reference tag insertion buttons - One-click [1], [2], [3], [4] insertion
- ✅ Prompt validation - Ensures [N] tags present when references exist
- ✅ Smart UI visibility - Shows/hides based on Google provider selection

**Code Metrics:**
- Widget: ~540 lines
- Main window modifications: ~150 lines
- Total Phase 3 code: ~690 lines

**Testing Requirements:**
- **Note:** gcloud authentication is configured for PowerShell only
- Full API testing must be done via PowerShell environment
- WSL/bash can be used for UI development and testing without API calls
- UI can be tested by launching the app and selecting Google provider

---

### Phase 3.5: Reference Persistence ✅ COMPLETED

**Status:** ✅ COMPLETE (2025-10-30 08:35)

**Goal:** Save and restore reference images across sessions and in project files

#### Tasks:
- [x] Add `to_dict()` and `from_dict()` methods to `ImagenReferenceWidget`
- [x] Create `_save_imagen_references_to_config()` in main_window
- [x] Create `_load_imagen_references_from_config()` in main_window
- [x] Hook auto-save to `references_changed` signal
- [x] Load references on application startup
- [x] Save references to project files (*.imgai)
- [x] Load references from project files

**Files Modified:**
- ✅ `gui/imagen_reference_widget.py` - Added serialization methods (lines 444-506)
  - `to_dict()` - Serialize all references to list of dictionaries
  - `from_dict()` - Restore references from list of dictionaries
- ✅ `gui/main_window.py` - Added persistence integration:
  - Line 1239: Load references on startup
  - Line 3440: Auto-save when references change
  - Lines 6863-6896: Save/load methods for config
  - Line 5788: Save to project files
  - Line 5901: Load from project files

**Deliverables:**
- ✅ References persist in global config file - Complete
- ✅ References auto-save when selected/changed - Complete
- ✅ References included in project save/load - Complete
- ✅ All reference settings (type, subject, description) preserved - Complete

**Behavior:**
- When user selects a reference image, it's **immediately saved** to config
- When user changes reference type/subject/description, changes are **auto-saved**
- When user saves a project (*.imgai), references are **included**
- When app starts, references from last session are **automatically restored**
- When user loads a project, references from that project are **restored**

---

### Phase 4: Prompt Integration (Week 2-3)

**Goal:** Smart prompt editing with reference tag support

#### Tasks:
- [ ] Add syntax highlighting for [1], [2], [3], [4] tags
- [ ] Implement auto-complete for reference tags
- [ ] Add validation: warn if [N] used without N references
- [ ] Add "Insert Reference" dropdown menu
- [ ] Show reference preview tooltip on hover over [N]
- [ ] Generate example prompts with references

**Prompt Examples to Generate:**
```python
EXAMPLES = {
    "2_person_scene": {
        "references": [
            {"type": "SUBJECT", "subject_type": "PERSON", "id": 1},
            {"type": "SUBJECT", "subject_type": "PERSON", "id": 2}
        ],
        "prompt": "A photograph of [1] and [2] having coffee at a cafe"
    },
    "person_with_style": {
        "references": [
            {"type": "SUBJECT", "subject_type": "PERSON", "id": 1},
            {"type": "STYLE", "id": 2}
        ],
        "prompt": "Portrait of [1] in the style of [2]"
    }
}
```

**Files to Modify:**
- `gui/generate_tab.py` - Enhance prompt editor

**Deliverables:**
- ✅ Smart prompt editing with reference awareness
- ✅ Validation and helpful warnings
- ✅ Example prompt templates

---

### Phase 5: Advanced Features (Week 3)

**Goal:** Polish and advanced capabilities

#### Tasks:
- [ ] Subject description auto-generation (LLM vision)
- [ ] Reference library/favorites system
- [ ] Control-based customization (Canny edge, scribble)
- [ ] Batch generation with different reference combinations
- [ ] Reference image templates/presets
- [ ] Export/import reference sets

**Optional Enhancements:**
- Reference image cropping/editing inline
- Face detection for PERSON subjects
- Style extraction from images
- Reference compatibility checker

**Files to Create:**
- `gui/reference_library_dialog.py` - Reference library manager
- `core/reference/control_generator.py` - Generate control images

**Deliverables:**
- ✅ Production-ready feature set
- ✅ Enhanced user experience
- ✅ Advanced customization options

---

## API Integration Details

### Request Format

**Endpoint:**
```
POST https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{LOCATION}/publishers/google/models/imagen-3.0-capability-001:predict
```

**Authentication:**
```python
from google.auth import default
from google.cloud import aiplatform

credentials, project = default()
aiplatform.init(project=project, location="us-central1")
```

**Request Body Structure:**
```json
{
  "instances": [
    {
      "prompt": "A photograph of [1] and [2] at the beach",
      "referenceImages": [
        {
          "referenceType": "SUBJECT",
          "referenceId": 1,
          "referenceImage": {
            "bytesBase64Encoded": "<base64_image_data>"
          },
          "referenceConfig": {
            "referenceType": "SUBJECT",
            "subjectType": "PERSON",
            "subjectDescription": "young woman with long brown hair"
          }
        },
        {
          "referenceType": "SUBJECT",
          "referenceId": 2,
          "referenceImage": {
            "bytesBase64Encoded": "<base64_image_data>"
          },
          "referenceConfig": {
            "referenceType": "SUBJECT",
            "subjectType": "PERSON",
            "subjectDescription": "man with short black hair and glasses"
          }
        }
      ]
    }
  ],
  "parameters": {
    "sampleCount": 1,
    "aspectRatio": "16:9",
    "negativePrompt": "blurry, low quality",
    "seed": 42
  }
}
```

**Response Format:**
```json
{
  "predictions": [
    {
      "bytesBase64Encoded": "<generated_image_base64>",
      "mimeType": "image/png"
    }
  ],
  "metadata": {
    "generateTime": "2025-10-29T12:34:56Z"
  }
}
```

### Python Implementation

```python
import base64
from typing import List, Dict, Any, Optional
from pathlib import Path
from PIL import Image
import io

class ImagenCustomizationProvider:
    """Provider for Imagen 3 Customization API with multiple reference images"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.project_id = None
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize Google Cloud AI Platform client"""
        from google.auth import default
        from google.cloud import aiplatform

        credentials, project = default()
        self.project_id = project
        aiplatform.init(project=project, location="us-central1")

    def generate_with_references(
        self,
        prompt: str,
        references: List['ImagenReference'],
        aspect_ratio: str = "16:9",
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        **kwargs
    ) -> bytes:
        """
        Generate image with multiple reference images.

        Args:
            prompt: Text prompt with [1], [2], etc. for references
            references: List of ImagenReference objects (max 4)
            aspect_ratio: Output aspect ratio
            negative_prompt: Things to avoid in the image
            seed: Random seed for reproducibility

        Returns:
            Generated image as bytes
        """
        if len(references) > 4:
            raise ValueError("Maximum 4 reference images allowed")

        if len(references) == 0:
            raise ValueError("At least 1 reference image required")

        # Validate prompt has reference tags
        self._validate_prompt_references(prompt, len(references))

        # Build reference images array
        reference_images = []
        for ref in references:
            ref_dict = self._build_reference_dict(ref)
            reference_images.append(ref_dict)

        # Build request
        request = {
            "instances": [{
                "prompt": prompt,
                "referenceImages": reference_images
            }],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": aspect_ratio,
            }
        }

        if negative_prompt:
            request["parameters"]["negativePrompt"] = negative_prompt

        if seed is not None:
            request["parameters"]["seed"] = seed

        # Call API
        from google.cloud import aiplatform_v1

        endpoint = (
            f"projects/{self.project_id}/locations/us-central1/"
            f"publishers/google/models/imagen-3.0-capability-001"
        )

        prediction_client = aiplatform_v1.PredictionServiceClient()
        response = prediction_client.predict(
            endpoint=endpoint,
            instances=request["instances"],
            parameters=request["parameters"]
        )

        # Extract image from response
        prediction = response.predictions[0]
        image_base64 = prediction["bytesBase64Encoded"]
        image_bytes = base64.b64decode(image_base64)

        return image_bytes

    def _build_reference_dict(self, ref: 'ImagenReference') -> Dict[str, Any]:
        """Build API reference dictionary from ImagenReference object"""
        # Load image if not already loaded
        if ref.image_data is None:
            with open(ref.path, 'rb') as f:
                ref.image_data = f.read()

        # Encode to base64
        image_base64 = base64.b64encode(ref.image_data).decode('utf-8')

        ref_dict = {
            "referenceType": ref.reference_type.value.upper(),
            "referenceId": ref.reference_id,
            "referenceImage": {
                "bytesBase64Encoded": image_base64
            }
        }

        # Add type-specific config
        if ref.reference_type == ImagenReferenceType.SUBJECT:
            ref_dict["referenceConfig"] = {
                "referenceType": "SUBJECT"
            }

            if ref.subject_type:
                ref_dict["referenceConfig"]["subjectType"] = ref.subject_type.value.upper()

            if ref.subject_description:
                ref_dict["referenceConfig"]["subjectDescription"] = ref.subject_description

        elif ref.reference_type == ImagenReferenceType.STYLE:
            ref_dict["referenceConfig"] = {
                "referenceType": "STYLE"
            }

            if ref.subject_description:  # Can be style description
                ref_dict["referenceConfig"]["styleDescription"] = ref.subject_description

        elif ref.reference_type == ImagenReferenceType.CONTROL:
            ref_dict["referenceConfig"] = {
                "referenceType": "CONTROL",
                "controlType": ref.control_type or "CANNY"
            }

        return ref_dict

    def _validate_prompt_references(self, prompt: str, num_references: int):
        """Validate that prompt references match available references"""
        import re

        # Find all [N] tags in prompt
        tags = re.findall(r'\[(\d+)\]', prompt)
        tag_nums = [int(t) for t in tags]

        # Check if any tag exceeds available references
        max_tag = max(tag_nums) if tag_nums else 0
        if max_tag > num_references:
            raise ValueError(
                f"Prompt references [{max_tag}] but only {num_references} "
                f"reference image(s) provided"
            )
```

---

## UI/UX Design

### Main Generate Tab Layout

**Before (Current):**
```
┌─────────────────────────────────────────┐
│ Prompt:                                 │
│ ┌─────────────────────────────────────┐ │
│ │                                     │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ [Generate] [Settings...] [Reference...] │
└─────────────────────────────────────────┘
```

**After (With Multi-Reference):**
```
┌──────────────────────────────────────────────────────┐
│ Reference Images (2/4)             [+ Add Reference] │
├──────────────────────────────────────────────────────┤
│ [1] 👤 sarah.jpg         [SUBJECT] [PERSON] [×]     │
│     "young woman with long brown hair"               │
│                                                       │
│ [2] 🎨 watercolor.jpg    [STYLE]           [×]      │
│     "soft watercolor painting style"                 │
├──────────────────────────────────────────────────────┤
│ Prompt:                                              │
│ ┌─────────────────────────────────────────────────┐ │
│ │ A portrait of [1] in the style of [2]          │ │
│ └─────────────────────────────────────────────────┘ │
│                                                       │
│ [Generate] [Settings...] [Examples...]              │
└──────────────────────────────────────────────────────┘
```

### Reference Image Item Design

```
┌──────────────────────────────────────────────────────┐
│ [1] 🖼️ portrait.jpg                      [SUBJECT] [×]│
│     ┌────────┐  PERSON                               │
│     │        │  "A description of the subject..."    │
│     │  📷   │  720×1280 • PNG • 2.1 MB              │
│     └────────┘                                        │
└──────────────────────────────────────────────────────┘
       │
       └──── Drag handle for reordering
```

### Settings Panel Addition

Add new section to Settings tab:
```
┌────────────────────────────────────────┐
│ Imagen 3 Customization                 │
├────────────────────────────────────────┤
│ □ Enable multi-reference support       │
│                                         │
│ Default Subject Type: [PERSON ▼]       │
│                                         │
│ Auto-generate descriptions: [✓]        │
│                                         │
│ Max reference images: [4 ▼]            │
└────────────────────────────────────────┘
```

---

## Code Structure

### New Files

```
ImageAI/
├── providers/
│   └── imagen_customization.py          # NEW: Imagen 3 API client
│
├── core/
│   └── reference/
│       ├── __init__.py                   # NEW: Package init
│       ├── imagen_reference.py           # NEW: Reference data model
│       ├── reference_validator.py        # NEW: Validation logic
│       └── control_generator.py          # NEW: Control image generation
│
├── gui/
│   ├── imagen_reference_widget.py        # NEW: Reference list UI
│   ├── imagen_reference_item_widget.py   # NEW: Reference item display
│   └── reference_examples_dialog.py      # NEW: Example prompts
│
└── tests/
    ├── test_imagen_customization.py      # NEW: API tests
    └── test_imagen_reference.py          # NEW: Reference model tests
```

### Modified Files

```
ImageAI/
├── providers/
│   ├── __init__.py                       # MODIFY: Register new provider
│   └── google.py                         # MODIFY: Add note about customization
│
├── gui/
│   ├── generate_tab.py                   # MODIFY: Add reference widget
│   └── settings_tab.py                   # MODIFY: Add Imagen settings
│
└── core/
    └── config.py                         # MODIFY: Add Imagen config options
```

---

## Testing Strategy

### Unit Tests

**Test: `test_imagen_customization.py`**
```python
def test_single_reference_generation():
    """Test generation with single reference image"""
    pass

def test_multi_reference_generation():
    """Test generation with 2-4 reference images"""
    pass

def test_reference_id_assignment():
    """Test automatic reference ID assignment"""
    pass

def test_prompt_validation():
    """Test prompt reference tag validation"""
    pass

def test_subject_description_handling():
    """Test subject descriptions in API requests"""
    pass

def test_error_handling():
    """Test API error handling and retries"""
    pass
```

**Test: `test_imagen_reference.py`**
```python
def test_reference_creation():
    """Test creating reference objects"""
    pass

def test_reference_validation():
    """Test image validation"""
    pass

def test_reference_ordering():
    """Test reference ID reordering"""
    pass

def test_reference_type_enum():
    """Test reference type enumerations"""
    pass
```

### Integration Tests

1. **Single SUBJECT reference**
   - Load 1 person image
   - Generate with "[1] at the beach"
   - Verify person consistency

2. **Two SUBJECT references**
   - Load 2 person images
   - Generate with "[1] and [2] together"
   - Verify both people appear

3. **SUBJECT + STYLE combination**
   - Load 1 person + 1 style reference
   - Generate with "[1] in the style of [2]"
   - Verify style transfer

4. **Maximum 4 references**
   - Load 4 different references
   - Generate complex scene
   - Verify all references used

### Manual Testing Checklist

- [ ] Add/remove reference images
- [ ] Reorder references (drag-and-drop)
- [ ] Change reference types
- [ ] Add subject descriptions
- [ ] Generate with [N] tags in prompt
- [ ] Error handling for missing references
- [ ] Error handling for invalid images
- [ ] Performance with large images
- [ ] UI responsiveness during generation
- [ ] Result quality comparison

---

## Documentation Requirements

### User Documentation

**File: `Docs/Imagen3-Multi-Reference-Guide.md`**
- Feature overview
- Step-by-step tutorial
- Reference type explanations
- Prompt writing tips
- Example use cases
- Troubleshooting guide

### Developer Documentation

**File: `Docs/Imagen3-API-Integration.md`**
- API endpoint details
- Authentication setup
- Request/response formats
- Error codes and handling
- Rate limits and quotas
- Code examples

### Code Documentation

**Inline Documentation:**
- Docstrings for all public methods
- Type hints for parameters and returns
- Usage examples in docstrings
- API reference comments

---

## Migration Path

### Backward Compatibility

**Option 1: Separate Provider**
- Keep existing `GoogleProvider` for simple single-reference
- New `ImagenCustomizationProvider` for multi-reference
- Users choose provider in settings

**Option 2: Unified Provider** (Recommended)
- Detect number of references
- Route to appropriate API automatically
- 0-1 references → `gemini-2.5-flash-image` (current)
- 2+ references → `imagen-3.0-capability-001` (customization)

### Settings Migration

```python
# Old config
{
    "provider": "google",
    "model": "gemini-2.5-flash-image",
    "reference_image": "/path/to/single.jpg"  # Single reference
}

# New config (backward compatible)
{
    "provider": "google",
    "model": "gemini-2.5-flash-image",  # Or "imagen-3.0-capability-001"
    "references": [  # New: multiple references
        {
            "path": "/path/to/ref1.jpg",
            "type": "SUBJECT",
            "subject_type": "PERSON",
            "description": "young woman",
            "reference_id": 1
        },
        {
            "path": "/path/to/ref2.jpg",
            "type": "STYLE",
            "description": "watercolor style",
            "reference_id": 2
        }
    ]
}
```

---

## Cost Considerations

### Imagen 3 Customization Pricing

**As of October 2025:**
- Image generation: ~$0.04 per image (1024x1024)
- Multi-reference customization: Same price per image
- No additional charge for using multiple references
- Storage costs if using GCS for reference images

**Monthly Estimates:**
```
100 generations/day × 30 days = 3,000 images
3,000 × $0.04 = $120/month
```

### Optimization Recommendations

1. **Cache Reference Images**: Don't re-upload same references
2. **Batch Requests**: Generate multiple variations in one session
3. **Use Smaller References**: Resize to 1024px max dimension
4. **Monitor Quotas**: Set up billing alerts

---

## Security Considerations

### Authentication

**Required:**
- Google Cloud Application Default Credentials (ADC)
- IAM permissions: `aiplatform.predictions.create`
- Project-level API enablement

**Security Best Practices:**
1. Use service accounts for production
2. Rotate credentials regularly
3. Implement rate limiting
4. Validate all uploaded images
5. Sanitize user prompts
6. Log all API requests

### Privacy

**Reference Image Handling:**
- Images sent to Google Cloud (not stored long-term)
- Subject descriptions are metadata (no facial recognition)
- Generated images may be used for service improvement (opt-out available)

**Recommendations:**
- Add privacy notice for reference images
- Allow users to delete reference history
- Don't log reference images in plaintext logs
- Implement local reference caching with encryption

---

## Success Metrics

### Phase 1 (API Integration)
- ✅ Successfully generate with 2+ references
- ✅ <5% API error rate
- ✅ <10 second generation time (P95)

### Phase 2 (Reference Management)
- ✅ Support 4 simultaneous references
- ✅ Reference validation <100ms
- ✅ 100% coverage for reference types

### Phase 3 (UI Components)
- ✅ <3 clicks to add reference
- ✅ Drag-and-drop ordering works 100%
- ✅ Responsive UI (no freezing)

### Phase 4 (Prompt Integration)
- ✅ Auto-complete reference tags
- ✅ Zero invalid reference errors in prompts
- ✅ 90% user satisfaction with prompt editing

### Phase 5 (Polish)
- ✅ Auto-generate descriptions for 80% of subjects
- ✅ Reference library with >10 saved references
- ✅ Production-ready performance

---

## Risk Mitigation

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| API quota limits | HIGH | Implement request queuing, retry logic |
| Large image uploads | MEDIUM | Resize images client-side to max 1024px |
| Slow generation times | MEDIUM | Show progress, allow cancellation |
| Reference ID conflicts | LOW | Strict ID validation, auto-assign |

### UX Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Complex UI | HIGH | Provide templates, examples, tutorials |
| Reference ordering confusion | MEDIUM | Clear visual indicators, undo/redo |
| Prompt syntax errors | HIGH | Validation, auto-complete, examples |

---

## Timeline Summary

| Phase | Duration | Start | End | Deliverables |
|-------|----------|-------|-----|--------------|
| **Phase 1** | 1 week | W1 D1 | W1 D7 | Working API client |
| **Phase 2** | 1 week | W1 D5 | W2 D4 | Reference system |
| **Phase 3** | 1 week | W2 D1 | W2 D7 | UI components |
| **Phase 4** | 1 week | W2 D5 | W3 D4 | Prompt integration |
| **Phase 5** | 1 week | W3 D1 | W3 D7 | Polish & testing |

**Total:** ~3 weeks with overlapping phases

---

## Next Steps

### Immediate Actions (This Week)

1. **Validate API Access**
   - [ ] Confirm Google Cloud project has Imagen 3 API enabled
   - [ ] Test authentication with `gcloud auth application-default login`
   - [ ] Make test API call with sample reference image

2. **Create Project Structure**
   - [ ] Create `providers/imagen_customization.py` stub
   - [ ] Create `core/reference/` package
   - [ ] Set up test files

3. **Prototype Core Functionality**
   - [ ] Implement basic 2-reference generation
   - [ ] Test with sample images
   - [ ] Document findings

### Questions to Answer

1. **API Access**: Do we have Imagen 3 Customization API access?
2. **Quota Limits**: What are the request limits for the project?
3. **Design Review**: Does the UI mockup meet requirements?
4. **Integration Point**: Add to main Generate tab or separate tool?

---

## References

### Official Documentation

- [Imagen 3 Customization API](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/imagen-api-customization)
- [Subject Customization](https://cloud.google.com/vertex-ai/generative-ai/docs/image/subject-customization)
- [Style Customization](https://cloud.google.com/vertex-ai/generative-ai/docs/image/style-customization)
- [Control-based Customization](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/imagen-api-edit)

### Code Examples

- [Vertex AI Python SDK](https://cloud.google.com/vertex-ai/docs/python-sdk/use-vertex-ai-python-sdk)
- [Image Generation Samples](https://github.com/GoogleCloudPlatform/python-docs-samples/tree/main/generative_ai/imagen)

---

## Appendix A: API Request Examples

### Example 1: Two Character Scene

```json
{
  "instances": [{
    "prompt": "A photograph of [1] and [2] having coffee at a modern cafe, smiling and talking",
    "referenceImages": [
      {
        "referenceType": "SUBJECT",
        "referenceId": 1,
        "referenceImage": {"bytesBase64Encoded": "..."},
        "referenceConfig": {
          "referenceType": "SUBJECT",
          "subjectType": "PERSON",
          "subjectDescription": "young woman with long brown hair wearing glasses"
        }
      },
      {
        "referenceType": "SUBJECT",
        "referenceId": 2,
        "referenceImage": {"bytesBase64Encoded": "..."},
        "referenceConfig": {
          "referenceType": "SUBJECT",
          "subjectType": "PERSON",
          "subjectDescription": "man with short black hair and beard"
        }
      }
    ]
  }],
  "parameters": {
    "sampleCount": 1,
    "aspectRatio": "16:9"
  }
}
```

### Example 2: Person with Style Transfer

```json
{
  "instances": [{
    "prompt": "A portrait of [1] in the artistic style of [2], dramatic lighting",
    "referenceImages": [
      {
        "referenceType": "SUBJECT",
        "referenceId": 1,
        "referenceImage": {"bytesBase64Encoded": "..."},
        "referenceConfig": {
          "referenceType": "SUBJECT",
          "subjectType": "PERSON",
          "subjectDescription": "elderly man with grey hair"
        }
      },
      {
        "referenceType": "STYLE",
        "referenceId": 2,
        "referenceImage": {"bytesBase64Encoded": "..."},
        "referenceConfig": {
          "referenceType": "STYLE",
          "styleDescription": "impressionist oil painting style with visible brushstrokes"
        }
      }
    ]
  }],
  "parameters": {
    "sampleCount": 1,
    "aspectRatio": "4:3"
  }
}
```

### Example 3: Product Composition

```json
{
  "instances": [{
    "prompt": "A professional product photo featuring [1] and [2] on a minimalist white background, studio lighting",
    "referenceImages": [
      {
        "referenceType": "SUBJECT",
        "referenceId": 1,
        "referenceImage": {"bytesBase64Encoded": "..."},
        "referenceConfig": {
          "referenceType": "SUBJECT",
          "subjectType": "PRODUCT",
          "subjectDescription": "red leather handbag with gold hardware"
        }
      },
      {
        "referenceType": "SUBJECT",
        "referenceId": 2,
        "referenceImage": {"bytesBase64Encoded": "..."},
        "referenceConfig": {
          "referenceType": "SUBJECT",
          "subjectType": "PRODUCT",
          "subjectDescription": "matching red leather wallet"
        }
      }
    ]
  }],
  "parameters": {
    "sampleCount": 1,
    "aspectRatio": "1:1",
    "negativePrompt": "blurry, low quality, cluttered"
  }
}
```

---

## Appendix B: Error Codes

| Code | Description | Resolution |
|------|-------------|------------|
| 400 | Invalid request format | Check JSON structure |
| 401 | Authentication failed | Verify ADC credentials |
| 403 | Permission denied | Check IAM permissions |
| 404 | Model not found | Verify model ID |
| 429 | Rate limit exceeded | Implement backoff |
| 500 | Server error | Retry with exponential backoff |

---

## Appendix C: Glossary

- **ADC**: Application Default Credentials - Google Cloud auth method
- **Reference ID**: Numeric identifier (1-4) for reference images in prompts
- **Reference Type**: Category of reference (SUBJECT, STYLE, CONTROL, etc.)
- **Subject Type**: Subcategory for SUBJECT references (PERSON, ANIMAL, PRODUCT)
- **Subject Description**: Text description of reference image content
- **Control Image**: Edge map, face mesh, or scribble for structural guidance
- **Customization**: Imagen 3 feature for reference-based generation

---

**End of Implementation Plan**

*This document will be updated as implementation progresses.*
