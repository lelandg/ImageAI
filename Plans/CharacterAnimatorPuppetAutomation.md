# Character Animator Puppet Automation - Implementation Checklist

**Last Updated:** 2025-12-19 07:36
**Status:** In Progress
**Progress:** 33/35 tasks complete

## Overview

Automate the conversion of a single image into an Adobe Character Animator puppet with proper layer structure, including auto-generated mouth visemes (14 shapes) and eye blink states. Uses AI segmentation for body part separation and generative AI for creating facial expression variants.

---

## Adobe Character Animator Requirements Summary

### Supported Formats
| Format | Notes |
|--------|-------|
| **PSD** | Most common, best for photorealistic |
| **AI** | Vector-based, preserves layers |
| **SVG** | Groups map to layers, good for cartoons |

### Required Layer Structure
```
+[CharacterName]              (root, + = warp independence)
├── Body
│   ├── Torso
│   ├── Left Arm
│   ├── Right Arm
│   └── [Legs if full body]
└── Head                      (must be group)
    ├── +Left Eyebrow
    ├── +Right Eyebrow
    ├── Left Eye (group)
    │   ├── Left Pupil Range  (eyeball white)
    │   └── +Left Pupil
    ├── Right Eye (group)
    │   ├── Right Pupil Range
    │   └── +Right Pupil
    ├── Left Blink            (closed eyelid)
    ├── Right Blink
    └── Mouth (group)
        ├── Neutral
        ├── Ah, D, Ee, F, L, M, Oh, R, S, Uh, W-Oo
        ├── Smile             (camera-driven)
        └── Surprised         (camera-driven)
```

### 14 Mouth Visemes
| Viseme | Description | Prompt Hint |
|--------|-------------|-------------|
| Neutral | Resting mouth | "mouth at rest, lips together" |
| Ah | Open mouth | "mouth wide open saying 'ah'" |
| D | Tongue behind teeth | "tongue touching upper teeth" |
| Ee | Wide smile | "wide smile showing teeth" |
| F | Lower lip under teeth | "biting lower lip" |
| L | Tongue up | "tongue tip touching roof of mouth" |
| M | Closed lips | "lips pressed together" |
| Oh | Rounded open | "rounded 'O' shape mouth" |
| R | Slightly rounded | "slightly pursed lips" |
| S | Teeth together | "teeth together, slight smile" |
| Uh | Slightly open | "mouth slightly open" |
| W-Oo | Pursed lips | "lips pursed as if whistling" |
| Smile | Camera-driven | "happy smile" |
| Surprised | Camera-driven | "mouth open surprised expression" |

---

## Technology Stack

### Core Libraries
- **Segmentation**: `segment-anything` (SAM 2), `mediapipe`
- **Depth Estimation**: `depth-anything` or `midas`
- **Inpainting**: `diffusers` (Stable Diffusion + ControlNet)
- **Image Processing**: `opencv-python`, `pillow`, `scipy`
- **File Generation**: `psd-tools` (PSD), `svgwrite` (SVG)
- **Face Detection**: `mediapipe` Face Mesh (478 landmarks)

### External Options
- **ToLayers.com** - AI layer separation (free, web-based)
- **KomikoAI** - Layer splitter for animation
- **Cre8tiveAI Layer Decomposer** - Fills occluded regions

---

## Implementation Tasks

### Phase 1: Core Infrastructure & Lazy Installation

#### Package Structure
- [x] Create `core/character_animator/` package directory (`core/character_animator/__init__.py:1`) ✅
- [x] Create `__init__.py` with package exports (`core/character_animator/__init__.py`) ✅
- [x] Create `models.py` - Data classes for puppet structure (`core/character_animator/models.py`) ✅
  - [x] `PuppetLayer` dataclass (name, image, children, properties) ✅
  - [x] `PuppetStructure` dataclass (head, body, layers hierarchy) ✅
  - [x] `VisemeSet` dataclass (14 mouth shapes) ✅
  - [x] `ExportFormat` enum (PSD, SVG, AI) ✅
- [x] Create `constants.py` - Layer naming conventions (`core/character_animator/constants.py`) ✅
  - [x] `LAYER_NAMES` dict with standard names ✅
  - [x] `VISEME_PROMPTS` dict with generation prompts ✅
  - [x] `BODY_PART_ORDER` list for z-ordering ✅

#### Lazy Loading Infrastructure (follows Real-ESRGAN pattern)
- [x] Create `core/character_animator/installer.py` - Package installation (`core/character_animator/installer.py`) ✅
  - [x] `get_puppet_packages()` - Returns package list with GPU detection ✅
  - [x] `PUPPET_PACKAGES` dict with package groups (segmentation, inpainting, etc.) ✅
  - [x] `check_dependencies()` - Check which AI modules are installed ✅
  - [x] `get_missing_packages()` - Return list of uninstalled packages ✅
- [x] Create `core/character_animator/availability.py` - Availability checks (`core/character_animator/availability.py`) ✅
  - [x] `SEGMENTATION_AVAILABLE` flag (try import SAM/MediaPipe) ✅
  - [x] `INPAINTING_AVAILABLE` flag (try import diffusers) ✅
  - [x] `DEPTH_AVAILABLE` flag (try import depth-anything) ✅
  - [x] `check_all_dependencies()` - Returns dict of availability status ✅
  - [x] `get_install_status_message()` - Human-readable status ✅
- [x] Update `core/package_installer.py` - Add puppet-specific functions (`core/package_installer.py:478`) ✅
  - [x] `get_puppet_ai_packages()` - Similar to `get_realesrgan_packages()` ✅
  - [x] `get_puppet_model_info()` - Model URLs and sizes for download ✅

### Phase 2: Body Part Segmentation

- [x] Create `segmenter.py` - Body part detection and segmentation (`core/character_animator/segmenter.py`) ✅
  - [x] `BodyPartSegmenter` class ✅
  - [x] `detect_pose()` - MediaPipe pose detection (33 landmarks) ✅
  - [x] `detect_face()` - MediaPipe face mesh (478 landmarks) ✅
  - [x] `segment_body_parts()` - Separate head, torso, limbs ✅
  - [x] `estimate_depth()` - Depth-Anything for z-ordering ✅
  - [x] `handle_occlusions()` - Identify overlapping parts ✅
- [x] Integrate SAM 2 for precise segmentation masks ✅
- [x] Add fallback to simpler segmentation if SAM unavailable ✅

### Phase 3: Inpainting for Occluded Parts

- [x] Create `inpainter.py` - Generative fill for hidden regions (`core/character_animator/inpainter.py`) ✅
  - [x] `OcclusionInpainter` class ✅
  - [x] `setup_pipeline()` - Load Stable Diffusion + ControlNet ✅
  - [x] `inpaint_body_region()` - Fill occluded body parts ✅
  - [x] `generate_complete_layer()` - Create full layer from partial ✅
  - [x] Support both local models and API (if GPU unavailable) ✅
- [x] Add pose-guided inpainting (ControlNet OpenPose) ✅
- [x] Style consistency check using original image reference ✅

### Phase 4: Facial Variant Generation

- [x] Create `face_generator.py` - Mouth visemes and eye blinks (`core/character_animator/face_generator.py`) ✅
  - [x] `FaceVariantGenerator` class ✅
  - [x] `get_mouth_region()` - Extract mouth bounding box from landmarks ✅
  - [x] `get_eye_regions()` - Extract left/right eye regions ✅
  - [x] `generate_viseme()` - Create single mouth shape via inpainting ✅
  - [x] `generate_all_visemes()` - Create all 14 mouth shapes ✅
  - [x] `generate_blink_states()` - Create Left Blink, Right Blink ✅
  - [x] `generate_eyebrow_variants()` - Optional raised/lowered eyebrows ✅
- [x] Add quality validation for generated faces ✅
- [x] Caching to avoid regenerating same visemes ✅

### Phase 5: File Export (PSD)

- [x] Create `psd_exporter.py` - Photoshop file generation (`core/character_animator/psd_exporter.py`) ✅
  - [x] `PSDExporter` class ✅
  - [x] `create_layer_hierarchy()` - Build proper group structure ✅
  - [x] `add_layer()` - Add image layer with properties ✅
  - [x] `add_group()` - Create layer groups (Head, Mouth, Eyes) ✅
  - [x] `set_layer_properties()` - Visibility, blend mode, opacity ✅
  - [x] `export()` - Save final .psd file ✅
- [x] Use `psd-tools` for PSD creation ✅
- [x] Fallback: Generate script for Photoshop execution ✅

### Phase 6: File Export (SVG)

- [x] Create `svg_exporter.py` - Vector file generation (`core/character_animator/svg_exporter.py`) ✅
  - [x] `SVGExporter` class ✅
  - [x] `image_to_svg_path()` - Vectorize image regions ✅
  - [x] `create_group_hierarchy()` - Build SVG groups with correct IDs ✅
  - [x] `embed_raster_layers()` - Option to embed PNGs in SVG ✅
  - [x] `export()` - Save final .svg file ✅
- [x] Support both pure vector and hybrid (embedded raster) modes ✅
- [x] Add vectorization via potrace or AI tools ✅

### Phase 7: GUI Integration

#### Installation Dialog (follows Real-ESRGAN pattern)
- [x] Create `gui/character_animator/` package (`gui/character_animator/__init__.py`) ✅
- [x] Create `gui/character_animator/install_dialog.py` - Installation UI (`gui/character_animator/install_dialog.py`) ✅
  - [x] `PuppetInstallConfirmDialog` - Shows what will be installed ✅
    - [x] Display package list with sizes (~8-12GB total) ✅
    - [x] Show GPU detection status (CUDA vs CPU) ✅
    - [x] Check and display disk space requirements ✅
    - [x] List model weights to be downloaded ✅
  - [x] `PuppetInstallProgressDialog` - Installation progress ✅
    - [x] Package installation progress with timing ✅
    - [x] Model download progress with ETA ✅
    - [x] Elapsed time display ✅
    - [x] Background installation support ✅
    - [x] System notification on completion ✅

#### Puppet Creation Wizard
- [x] Create `puppet_wizard.py` - Multi-step wizard dialog (`gui/character_animator/puppet_wizard.py`) ✅
  - [x] Step 0: Dependency check with "Install AI Components" button ✅
  - [x] Step 1: Image selection and preview ✅
  - [x] Step 2: Body part detection preview (with manual adjustment) ✅
  - [x] Step 3: Viseme generation progress ✅
  - [x] Step 4: Export format selection and save ✅
- [x] Add to main window menu: Tools > Character Animator Puppet (`gui/main_window.py:761`) ✅
- [x] Progress feedback during generation (can take minutes) (`gui/character_animator/puppet_wizard.py:342`) ✅
- [x] Show install button if dependencies missing (`gui/character_animator/puppet_wizard.py:91`) ✅

### Phase 8: Testing & Documentation

- [ ] Create test images (simple cartoon, complex photo)
- [ ] Test import into Adobe Character Animator
- [x] Document usage in README (`README.md:1288`, `README.md:233`) ✅
- [x] Add example workflow to Help tab (via README.md, displayed in Help tab) ✅

---

## Files Created

| File | Description | Lines |
|------|-------------|-------|
| `core/character_animator/__init__.py` | Package exports | ~45 |
| `core/character_animator/models.py` | Data classes | ~320 |
| `core/character_animator/constants.py` | Layer names, prompts, landmarks | ~280 |
| `core/character_animator/installer.py` | Package installation | ~200 |
| `core/character_animator/availability.py` | Dependency checks | ~180 |
| `core/character_animator/segmenter.py` | Body part segmentation | ~450 |
| `core/character_animator/inpainter.py` | Occlusion inpainting | ~380 |
| `core/character_animator/face_generator.py` | Viseme/blink generation | ~420 |
| `core/character_animator/psd_exporter.py` | PSD file export | ~450 |
| `core/character_animator/svg_exporter.py` | SVG file export | ~380 |
| `gui/character_animator/__init__.py` | GUI package exports | ~15 |
| `gui/character_animator/install_dialog.py` | Installation dialogs | ~350 |
| `gui/character_animator/puppet_wizard.py` | Multi-step wizard | ~600 |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Input                                │
│                    (Single Image)                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   BodyPartSegmenter                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ MediaPipe    │  │ SAM 2        │  │ Depth-Anything     │    │
│  │ Pose + Face  │  │ Segmentation │  │ Z-Order Detection  │    │
│  └──────────────┘  └──────────────┘  └────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   OcclusionInpainter                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Stable Diffusion + ControlNet (OpenPose)                  │  │
│  │ Fill hidden body parts with style-consistent content      │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FaceVariantGenerator                           │
│  ┌──────────────────────┐  ┌────────────────────────────────┐  │
│  │ 14 Mouth Visemes     │  │ Eye Blink States               │  │
│  │ (SD Inpainting)      │  │ (Left Blink, Right Blink)      │  │
│  └──────────────────────┘  └────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      File Exporters                              │
│  ┌──────────────────────┐  ┌────────────────────────────────┐  │
│  │ PSDExporter          │  │ SVGExporter                    │  │
│  │ (psd-tools)          │  │ (svgwrite + optional vectorize)│  │
│  └──────────────────────┘  └────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Adobe Character Animator                      │
│            Import .psd or .svg → Auto-rig puppet                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Dependencies (Lazy Loading)

**IMPORTANT**: Heavy AI dependencies are installed on first use, not bundled with the application. This follows the pattern established for Real-ESRGAN upscaling (see `core/package_installer.py`).

### Always Installed (requirements.txt)
```txt
# Lightweight dependencies - always installed
psd-tools>=1.9.0        # PSD file creation
svgwrite>=1.4.0         # SVG file creation
scipy                   # Image processing utilities
```

### Install-on-First-Use (via GUI installer)
```txt
# Heavy AI dependencies - installed automatically on first use
# Total download: ~8-12GB depending on GPU/CPU choice

# Core AI frameworks (GPU detection determines CUDA vs CPU)
torch>=2.4.1
torchvision>=0.19.1

# Segmentation (~2.5GB model)
segment-anything-2

# Pose/Face detection (~200MB models)
mediapipe>=0.10.0

# Depth estimation (~1.5GB model)
depth-anything           # or transformers for MiDaS

# Inpainting (~5GB models)
diffusers>=0.25.0
controlnet-aux
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| GPU required for SD | High | High | Offer API fallback (Replicate, etc.) |
| Viseme quality varies | Medium | Medium | Quality check + manual override |
| Complex poses fail | Medium | High | Limit to front-facing initially |
| PSD library limitations | Low | Medium | Photoshop script fallback |
| SAM model size (2GB+) | Medium | Low | **Lazy loading on first use** |
| Large download size (~8-12GB) | High | Medium | **Install-on-first-use pattern** with progress dialog |
| No GPU available | Medium | Medium | **Auto-detect GPU, install CPU-only PyTorch if needed** |
| Installation interruption | Low | Medium | Partial install detection, resume capability |

---

## Installation Flow (First-Use Pattern)

```
User clicks "Tools > Character Animator Puppet"
                    │
                    ▼
        ┌───────────────────────┐
        │ Check dependencies    │
        │ (availability.py)     │
        └───────────────────────┘
                    │
           All installed? ─────Yes────▶ Open Puppet Wizard
                    │
                   No
                    │
                    ▼
        ┌───────────────────────┐
        │ Show Install Dialog   │
        │ - Package list        │
        │ - GPU detected?       │
        │ - Disk space check    │
        │ - Download sizes      │
        └───────────────────────┘
                    │
            User clicks Install
                    │
                    ▼
        ┌───────────────────────┐
        │ PackageInstaller      │
        │ (background thread)   │
        │ 1. Install PyTorch    │
        │ 2. Install SAM        │
        │ 3. Install MediaPipe  │
        │ 4. Install Diffusers  │
        └───────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ ModelDownloader       │
        │ (background thread)   │
        │ 1. SAM weights        │
        │ 2. ControlNet weights │
        │ 3. SD Inpaint weights │
        └───────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ System notification   │
        │ "Installation done"   │
        │ Show Puppet Wizard    │
        └───────────────────────┘
```

---

## Future Enhancements

- Support side-view and 3/4 view characters
- Full body puppet with legs and walk cycles
- Hand finger separation for detailed puppets
- Batch processing multiple characters
- Style transfer to maintain consistency
- Template-based puppet generation (define your own structure)

---

## References

### External Resources
- [Adobe Character Animator - Prepare Artwork](https://helpx.adobe.com/adobe-character-animator/using/prepare-artwork.html)
- [Meta AI - Segment Anything 2](https://github.com/facebookresearch/segment-anything-2)
- [Google - MediaPipe](https://ai.google.dev/edge/mediapipe)
- [ToLayers - AI Layer Separation](https://tolayers.com/)
- [OK Samurai Puppets](https://okaysamurai.com/puppets/)

### Internal References (Lazy Install Pattern)
Use these as templates for implementing the install-on-first-use pattern:
- `core/package_installer.py` - PackageInstaller, ModelDownloader, detect_nvidia_gpu()
- `gui/install_dialog.py` - InstallConfirmDialog, InstallProgressDialog
- `gui/upscaling_widget.py` - check_realesrgan_availability(), _on_install_clicked()
- `core/upscaling.py` - REALESRGAN_AVAILABLE flag pattern
