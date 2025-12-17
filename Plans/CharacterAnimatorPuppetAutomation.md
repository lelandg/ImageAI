# Character Animator Puppet Automation - Implementation Checklist

**Last Updated:** 2025-12-17 10:24
**Status:** Not Started
**Progress:** 0/28 tasks complete

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

### Phase 1: Core Infrastructure

- [ ] Create `core/character_animator/` package directory
- [ ] Create `__init__.py` with package exports
- [ ] Create `models.py` - Data classes for puppet structure
  - [ ] `PuppetLayer` dataclass (name, image, children, properties)
  - [ ] `PuppetStructure` dataclass (head, body, layers hierarchy)
  - [ ] `VisemeSet` dataclass (14 mouth shapes)
  - [ ] `ExportFormat` enum (PSD, SVG, AI)
- [ ] Create `constants.py` - Layer naming conventions
  - [ ] `LAYER_NAMES` dict with standard names
  - [ ] `VISEME_PROMPTS` dict with generation prompts
  - [ ] `BODY_PART_ORDER` list for z-ordering

### Phase 2: Body Part Segmentation

- [ ] Create `segmenter.py` - Body part detection and segmentation
  - [ ] `BodyPartSegmenter` class
  - [ ] `detect_pose()` - MediaPipe pose detection (33 landmarks)
  - [ ] `detect_face()` - MediaPipe face mesh (478 landmarks)
  - [ ] `segment_body_parts()` - Separate head, torso, limbs
  - [ ] `estimate_depth()` - Depth-Anything for z-ordering
  - [ ] `handle_occlusions()` - Identify overlapping parts
- [ ] Integrate SAM 2 for precise segmentation masks
- [ ] Add fallback to simpler segmentation if SAM unavailable

### Phase 3: Inpainting for Occluded Parts

- [ ] Create `inpainter.py` - Generative fill for hidden regions
  - [ ] `OcclusionInpainter` class
  - [ ] `setup_pipeline()` - Load Stable Diffusion + ControlNet
  - [ ] `inpaint_body_region()` - Fill occluded body parts
  - [ ] `generate_complete_layer()` - Create full layer from partial
  - [ ] Support both local models and API (if GPU unavailable)
- [ ] Add pose-guided inpainting (ControlNet OpenPose)
- [ ] Style consistency check using original image reference

### Phase 4: Facial Variant Generation

- [ ] Create `face_generator.py` - Mouth visemes and eye blinks
  - [ ] `FaceVariantGenerator` class
  - [ ] `get_mouth_region()` - Extract mouth bounding box from landmarks
  - [ ] `get_eye_regions()` - Extract left/right eye regions
  - [ ] `generate_viseme()` - Create single mouth shape via inpainting
  - [ ] `generate_all_visemes()` - Create all 14 mouth shapes
  - [ ] `generate_blink_states()` - Create Left Blink, Right Blink
  - [ ] `generate_eyebrow_variants()` - Optional raised/lowered eyebrows
- [ ] Add quality validation for generated faces
- [ ] Caching to avoid regenerating same visemes

### Phase 5: File Export (PSD)

- [ ] Create `psd_exporter.py` - Photoshop file generation
  - [ ] `PSDExporter` class
  - [ ] `create_layer_hierarchy()` - Build proper group structure
  - [ ] `add_layer()` - Add image layer with properties
  - [ ] `add_group()` - Create layer groups (Head, Mouth, Eyes)
  - [ ] `set_layer_properties()` - Visibility, blend mode, opacity
  - [ ] `export()` - Save final .psd file
- [ ] Use `psd-tools` for PSD creation
- [ ] Fallback: Generate script for Photoshop execution

### Phase 6: File Export (SVG)

- [ ] Create `svg_exporter.py` - Vector file generation
  - [ ] `SVGExporter` class
  - [ ] `image_to_svg_path()` - Vectorize image regions
  - [ ] `create_group_hierarchy()` - Build SVG groups with correct IDs
  - [ ] `embed_raster_layers()` - Option to embed PNGs in SVG
  - [ ] `export()` - Save final .svg file
- [ ] Support both pure vector and hybrid (embedded raster) modes
- [ ] Add vectorization via potrace or AI tools

### Phase 7: GUI Integration

- [ ] Create `gui/character_animator/` package
- [ ] Create `puppet_wizard.py` - Multi-step wizard dialog
  - [ ] Step 1: Image selection and preview
  - [ ] Step 2: Body part detection preview (with manual adjustment)
  - [ ] Step 3: Viseme generation progress
  - [ ] Step 4: Export format selection and save
- [ ] Add to main window menu: Tools > Character Animator Puppet
- [ ] Progress feedback during generation (can take minutes)

### Phase 8: Testing & Documentation

- [ ] Create test images (simple cartoon, complex photo)
- [ ] Test import into Adobe Character Animator
- [ ] Document usage in README
- [ ] Add example workflow to Help tab

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

## Dependencies to Add

```txt
# requirements.txt additions
segment-anything-2      # SAM 2 for segmentation
mediapipe>=0.10.0       # Pose and face detection
depth-anything          # Depth estimation (or transformers for MiDaS)
diffusers>=0.25.0       # Stable Diffusion + ControlNet
controlnet-aux          # ControlNet preprocessors
psd-tools>=1.9.0        # PSD file creation
svgwrite>=1.4.0         # SVG file creation
scipy                   # Image processing utilities
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| GPU required for SD | High | High | Offer API fallback (Replicate, etc.) |
| Viseme quality varies | Medium | Medium | Quality check + manual override |
| Complex poses fail | Medium | High | Limit to front-facing initially |
| PSD library limitations | Low | Medium | Photoshop script fallback |
| SAM model size (2GB+) | Medium | Low | Lazy loading, optional download |

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

- [Adobe Character Animator - Prepare Artwork](https://helpx.adobe.com/adobe-character-animator/using/prepare-artwork.html)
- [Meta AI - Segment Anything 2](https://github.com/facebookresearch/segment-anything-2)
- [Google - MediaPipe](https://ai.google.dev/edge/mediapipe)
- [ToLayers - AI Layer Separation](https://tolayers.com/)
- [OK Samurai Puppets](https://okaysamurai.com/puppets/)
