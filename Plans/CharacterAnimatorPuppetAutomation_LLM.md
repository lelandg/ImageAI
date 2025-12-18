# Character Animator Puppet Automation (LLM-First, No Depth-Anything) - Plan

**Last Updated:** 2025-12-18 15:18
**Status:** Not Started
**Progress:** 0/36 tasks complete

## Overview
Automate the conversion of a single image into an Adobe Character Animator puppet with proper layer structure, including auto-generated mouth visemes (14 shapes) and eye blink states. This plan removes depth estimation models and uses a vision-capable LLM for semantic planning, occlusion reasoning, and prompt generation.

## Key Approach (No Depth)
- LLM-first layer planning: parts, bounding boxes, occlusion pairs, and z-order suggestions
- Segmentation via SAM/SAM2 (or fallback) using LLM-provided prompts/boxes
- Z-order inference from overlap graph + heuristics + LLM tie-breaks
- Optional inpainting for occluded regions and visemes; provide a no-inpaint mode

## Non-Goals (Initial Version)
- Side or 3/4 view characters
- Full-body legs and walk cycle rigging
- Perfect photorealistic inpainting in heavy occlusions

## Adobe Character Animator Requirements Summary

### Supported Formats
| Format | Notes |
|--------|-------|
| PSD | Most common, best for photorealistic |
| AI | Vector-based, preserves layers |
| SVG | Groups map to layers, good for cartoons |

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
| Neutral | Resting mouth | mouth at rest, lips together |
| Ah | Open mouth | mouth wide open saying "ah" |
| D | Tongue behind teeth | tongue touching upper teeth |
| Ee | Wide smile | wide smile showing teeth |
| F | Lower lip under teeth | biting lower lip |
| L | Tongue up | tongue tip touching roof of mouth |
| M | Closed lips | lips pressed together |
| Oh | Rounded open | rounded "O" shape mouth |
| R | Slightly rounded | slightly pursed lips |
| S | Teeth together | teeth together, slight smile |
| Uh | Slightly open | mouth slightly open |
| W-Oo | Pursed lips | lips pursed as if whistling |
| Smile | Camera-driven | happy smile |
| Surprised | Camera-driven | mouth open surprised expression |

## Data Contracts (Structured Outputs)
- LayerPlan JSON: parts list (name, label, bbox), occlusion pairs, z-order list, confidence, notes
- MaskSpec JSON: SAM prompt points/boxes per part
- ExportSpec JSON: output format, layer hierarchy, naming

## Dependencies (Proposed)
- Vision LLM: Gemini or OpenAI (structured JSON output)
- Segmentation: segment-anything-2 (SAM2) or SAM + opencv-python + pillow
- Face/Pose: mediapipe
- Inpainting: diffusers + optional ControlNet (or API fallback)
- Export: psd-tools, svgwrite

---

## Phase 1: LLM-Oriented Core Models ⏳ 0%
**Last Updated:** 2025-12-18 15:18

### Tasks
1. ⬜ Define `LayerPlan`, `MaskSpec`, `OcclusionGraph`, and `ExportSpec` data classes - **NOT STARTED**
2. ⬜ Create `constants.py` for layer names, viseme names, and ordering heuristics - **NOT STARTED**
3. ⬜ Add JSON schema validators for LLM outputs (strict mode) - **NOT STARTED**
4. ⬜ Add config switches: `llm_only_depth=true`, `inpaint_mode=optional` - **NOT STARTED**

## Phase 2: LLM Vision Analysis and Layer Planning ⏳ 0%
**Last Updated:** 2025-12-18 15:18

### Tasks
1. ⬜ Implement `llm_layer_planner.py` (vision prompt + schema output) - **NOT STARTED**
2. ⬜ Provide prompts for parts list, occlusion pairs, and confidence - **NOT STARTED**
3. ⬜ Add fallback prompt for unknown parts to reduce failure modes - **NOT STARTED**
4. ⬜ Build an LLM critique pass to self-check inconsistencies - **NOT STARTED**
5. ⬜ Cache LLM results keyed by image hash + model + prompt version - **NOT STARTED**

## Phase 3: Mask Generation and Occlusion Graph ⏳ 0%
**Last Updated:** 2025-12-18 15:18

### Tasks
1. ⬜ Implement `mask_builder.py` using SAM2 with LLM-provided points/boxes - **NOT STARTED**
2. ⬜ Add contour cleanup (hole fill, smoothing, simplification) - **NOT STARTED**
3. ⬜ Build `occlusion_graph.py` from overlapping masks - **NOT STARTED**
4. ⬜ Add heuristic z-order rules (face > hair > eyes > mouth, arms in front) - **NOT STARTED**
5. ⬜ Use LLM to resolve ambiguous overlaps (tie-break only) - **NOT STARTED**
6. ⬜ Provide manual override hooks for GUI adjustment - **NOT STARTED**

## Phase 4: Occlusion Completion (Optional Inpainting) ⏳ 0%
**Last Updated:** 2025-12-18 15:18

### Tasks
1. ⬜ Implement `occlusion_inpainter.py` (diffusers or API fallback) - **NOT STARTED**
2. ⬜ Use LLM to generate part-specific prompts (style-consistent) - **NOT STARTED**
3. ⬜ Add a no-inpaint mode that keeps partial layers - **NOT STARTED**
4. ⬜ Add a quality gate to avoid inpaint mismatch (histogram or SSIM check) - **NOT STARTED**

## Phase 5: Facial Variants (Visemes and Blinks) ⏳ 0%
**Last Updated:** 2025-12-18 15:18

### Tasks
1. ⬜ Implement `face_variant_generator.py` using mediapipe landmarks - **NOT STARTED**
2. ⬜ Use LLM for viseme prompt generation and guardrails - **NOT STARTED**
3. ⬜ Generate 14 visemes via inpainting on the mouth region only - **NOT STARTED**
4. ⬜ Generate Left and Right blink via eyelid inpainting - **NOT STARTED**
5. ⬜ Add cache keyed by viseme + image hash - **NOT STARTED**

## Phase 6: Exporters (PSD and SVG) ⏳ 0%
**Last Updated:** 2025-12-18 15:18

### Tasks
1. ⬜ Implement `psd_exporter.py` with correct layer hierarchy and names - **NOT STARTED**
2. ⬜ Implement `svg_exporter.py` (raster-embedded option) - **NOT STARTED**
3. ⬜ Add validation to ensure required layers exist before export - **NOT STARTED**
4. ⬜ Add CLI command `imageai puppet --input --format` - **NOT STARTED**

## Phase 7: GUI Integration ⏳ 0%
**Last Updated:** 2025-12-18 15:18

### Tasks
1. ⬜ Create `gui/character_animator_llm/` wizard - **NOT STARTED**
2. ⬜ Steps: image select, LLM plan preview, mask review, visemes, export - **NOT STARTED**
3. ⬜ Add manual re-order and visibility toggles for layers - **NOT STARTED**
4. ⬜ Add progress feedback and cancel handling - **NOT STARTED**

## Phase 8: Testing and Documentation ⏳ 0%
**Last Updated:** 2025-12-18 15:18

### Tasks
1. ⬜ Add test images (cartoon and photo) with golden exports - **NOT STARTED**
2. ⬜ Add unit tests for layer plan schema validation - **NOT STARTED**
3. ⬜ Add integration test: plan to mask to export (no inpaint) - **NOT STARTED**
4. ⬜ Document workflow and limitations in README or Docs - **NOT STARTED**

---

## Risks and Mitigations
- LLM mislabels parts: schema validation + critique pass + manual edit UI
- Z-order errors without depth: occlusion graph + heuristics + user override
- Inpainting mismatch: no-inpaint mode and review step
- LLM cost and latency: caching and offline heuristic fallback

## Success Criteria
- A front-facing character image exports to PSD with required Character Animator layers
- Mouth visemes and eye blinks import cleanly in Adobe Character Animator
- Z-order is reasonable without depth estimation in 80 percent of tests

## Open Questions
- Preferred LLM provider(s) for vision planning?
- Acceptable output quality for no-inpaint mode?
- Should SVG export embed raster layers by default?
