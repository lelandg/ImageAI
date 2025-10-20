# Reference Image System - Implementation Guide

**Last Updated**: 2025-10-20
**Status**: ✅ Implemented (Backend Complete, UI Pending)

---

## Overview

The Reference Image System provides character, object, and environment consistency across multiple video clips in a project. This is the **primary method** for achieving visual continuity in Veo 3 video generation.

### Key Concepts

- **Reference Images**: Up to 3 images that guide Veo 3 to maintain consistent appearance of characters, objects, or environments across ALL scenes
- **Global References**: Project-level references applied to all scenes by default
- **Per-Scene Overrides**: Individual scenes can override global references for specific needs
- **Reference Types**: CHARACTER, OBJECT, ENVIRONMENT, STYLE (for organization and smart selection)

---

## Architecture

### Data Models

#### `ReferenceImageType` Enum
```python
class ReferenceImageType(Enum):
    CHARACTER = "character"      # Person/face consistency
    OBJECT = "object"            # Props, items, products
    ENVIRONMENT = "environment"  # Locations, settings
    STYLE = "style"             # Visual style (Veo 2.0 only)
```

#### `ReferenceImage` Class
```python
@dataclass
class ReferenceImage:
    path: Path                                  # Path to reference image
    ref_type: ReferenceImageType               # Type of reference
    name: Optional[str]                        # User-friendly name
    description: Optional[str]                 # What this provides
    auto_linked: bool                          # Auto-linked from last frame?
    metadata: Dict[str, Any]                   # Additional metadata
```

#### `VideoProject` - Global References
```python
@dataclass
class VideoProject:
    # ... other fields ...
    global_reference_images: List[ReferenceImage]  # Max 3

    # Helper methods:
    def add_global_reference(ref_image: ReferenceImage) -> bool
    def remove_global_reference(ref_path: Path) -> bool
    def get_references_by_type(ref_type: ReferenceImageType) -> List[ReferenceImage]
    def get_references_by_name(name: str) -> List[ReferenceImage]
    def get_effective_references_for_scene(scene: Scene) -> List[ReferenceImage]
```

#### `Scene` - Per-Scene Overrides
```python
@dataclass
class Scene:
    # ... other fields ...
    reference_images: List[ReferenceImage]      # Scene-specific (max 3)
    use_global_references: bool                 # Use global or scene-specific?

    # Helper methods:
    def add_reference_image(ref_image: ReferenceImage) -> bool
    def get_effective_reference_images(global_refs) -> List[ReferenceImage]
    def clear_reference_images()
```

---

## Usage Patterns

### Pattern 1: Project-Wide Character Consistency (RECOMMENDED)

**Use Case**: Same character appears across multiple scenes in different locations

```python
from core.video.reference_manager import ReferenceManager, ReferenceImageType, ReferenceImageValidator
from core.video.project import ReferenceImage

# 1. Generate or load character reference images
character_refs = [
    Path("project/refs/sarah_front.png"),
    Path("project/refs/sarah_side.png"),
    Path("project/refs/sarah_full.png")
]

# 2. Validate references
validator = ReferenceImageValidator()
for ref_path in character_refs:
    info = validator.validate_reference_image(ref_path)
    if not info.is_valid:
        print(f"Invalid: {info.validation_errors}")
    else:
        print(f"Valid: {validator.get_validation_summary(info)}")

# 3. Add to project as global references
for ref_path in character_refs:
    ref_image = ReferenceImage(
        path=ref_path,
        ref_type=ReferenceImageType.CHARACTER,
        name="Sarah",
        description="Main character - young woman, dark hair"
    )
    project.add_global_reference(ref_image)

# 4. Generate videos for all scenes (automatically uses global refs)
for scene in project.scenes:
    # Scene will use global references by default
    refs = project.get_effective_references_for_scene(scene)
    print(f"Scene {scene.order}: Using {len(refs)} reference(s)")

    # Generate video with references
    veo_config = VeoGenerationConfig(
        prompt=scene.video_prompt,
        reference_images=[ref.path for ref in refs],  # Convert to paths
        duration=scene.duration_sec
    )
    result = veo_client.generate_video(veo_config)
```

### Pattern 2: Per-Scene Reference Override

**Use Case**: Most scenes use global references, but one scene needs different references

```python
# Scene 5 needs a different object reference
car_ref = ReferenceImage(
    path=Path("project/refs/vintage_car.png"),
    ref_type=ReferenceImageType.OBJECT,
    name="Vintage Car",
    description="1960s red convertible"
)

scene5 = project.scenes[4]  # Index 4 = scene 5
scene5.add_reference_image(car_ref)  # This disables global references

# Scene 5 now uses only its scene-specific references
refs = project.get_effective_references_for_scene(scene5)
# refs = [car_ref] (no global references)
```

### Pattern 3: Hybrid (References + Last-Frame Continuity)

**Use Case**: Sequential scenes in same location with continuous action

```python
from core.video.reference_manager import ReferenceManager

ref_manager = ReferenceManager(project.project_dir)

# Check if last-frame continuity makes sense
prev_scene = project.scenes[3]
current_scene = project.scenes[4]

should_use, reason = ref_manager.should_use_last_frame_continuity(
    prev_scene, current_scene
)

if should_use:
    print(f"Using last-frame continuity: {reason}")

    # Use BOTH references and last frame
    refs = project.get_effective_references_for_scene(current_scene)
    veo_config = VeoGenerationConfig(
        prompt=current_scene.video_prompt,
        reference_images=[ref.path for ref in refs],  # Character consistency
        image=prev_scene.last_frame,                   # Motion continuity
        duration=current_scene.duration_sec
    )
else:
    print(f"NOT using last-frame continuity: {reason}")

    # Use ONLY references (different location/scene break)
    refs = project.get_effective_references_for_scene(current_scene)
    veo_config = VeoGenerationConfig(
        prompt=current_scene.video_prompt,
        reference_images=[ref.path for ref in refs],
        duration=current_scene.duration_sec
    )
```

### Pattern 4: Auto-Generate Character References

**Use Case**: Creating reference sheet for new character

```python
from core.video.reference_manager import ReferenceManager

ref_manager = ReferenceManager(project.project_dir)

# Define character
character_desc = "Sarah - young woman, 25, long dark hair, green eyes, blue jacket"
style = "cinematic lighting, high detail, photorealistic"

# Generate 3 reference images
def image_generator(prompt, output_dir, filename_prefix):
    # Your image generation logic here
    # Return path to generated image
    pass

refs_dir = project.project_dir / "references"
ref_paths = ref_manager.generate_character_references(
    character_description=character_desc,
    style=style,
    image_generator=image_generator,
    output_dir=refs_dir
)

# Add to project
for i, ref_path in enumerate(ref_paths):
    ref_image = ReferenceImage(
        path=ref_path,
        ref_type=ReferenceImageType.CHARACTER,
        name="Sarah",
        description=f"Character reference {i+1}/3"
    )
    project.add_global_reference(ref_image)

print(f"✓ Generated {len(ref_paths)}/3 character references")
```

### Pattern 5: Smart Reference Selection

**Use Case**: Auto-select relevant references based on scene content

```python
from core.video.reference_manager import ReferenceManager

ref_manager = ReferenceManager(project.project_dir)

# Auto-select references for a scene
scene = project.scenes[10]
selected_refs = ref_manager.select_references_for_scene(
    scene_prompt=scene.video_prompt,
    available_refs=project.global_reference_images,
    max_refs=3
)

# Apply selected references to scene
scene.reference_images = selected_refs
scene.use_global_references = False
```

---

## Validation

### Veo 3 Requirements

| Requirement | Min | Max | Recommended |
|-------------|-----|-----|-------------|
| **Resolution** | 720p | - | 1080p+ |
| **Format** | PNG, JPEG | - | PNG (lossless) |
| **File Size** | - | 50MB | < 10MB |
| **Aspect Ratio** | Any | - | 16:9, 9:16, 1:1 |
| **Count** | 0 | 3 | 2-3 for best results |

### Validation Example

```python
from core.video.reference_manager import ReferenceImageValidator

validator = ReferenceImageValidator()

# Validate a reference image
info = validator.validate_reference_image(Path("refs/sarah_front.png"))

if info.is_valid:
    print(f"✓ Valid: {info.width}×{info.height}, {info.format}, {info.file_size_mb:.1f}MB")
    if info.validation_warnings:
        for warning in info.validation_warnings:
            print(f"  ⚠️ {warning}")
else:
    print(f"✗ Invalid:")
    for error in info.validation_errors:
        print(f"  • {error}")
```

---

## Integration with Video Generation

### Current Implementation (veo_client.py)

The `VeoClient` already supports reference images via the `VeoGenerationConfig`:

```python
@dataclass
class VeoGenerationConfig:
    # ... other fields ...
    reference_images: Optional[List[Path]] = None  # Up to 3 reference images

# In veo_client.py lines 279-327, references are loaded and passed to API
```

### Usage in Video Generation

```python
from core.video.veo_client import VeoClient, VeoGenerationConfig, VeoModel

# Initialize client
veo = VeoClient(api_key=your_api_key)

# Get effective references for scene
refs = project.get_effective_references_for_scene(scene)
ref_paths = [ref.path for ref in refs]

# Configure video generation
config = VeoGenerationConfig(
    model=VeoModel.VEO_3_GENERATE,
    prompt=scene.video_prompt,
    reference_images=ref_paths,  # ← PRIMARY continuity mechanism
    image=scene.approved_image if use_start_frame else None,  # ← OPTIONAL
    duration=scene.duration_sec,
    aspect_ratio=project.style["aspect_ratio"]
)

# Generate video
result = veo.generate_video(config)
```

---

## Decision Tree: When to Use What

```
Scene Generation Decision Tree
├─ Is this the first scene in project?
│  ├─ YES → Use global references only (no image/last_frame)
│  └─ NO → Continue...
│
├─ Does scene have per-scene reference override?
│  ├─ YES → Use scene.reference_images
│  └─ NO → Use project.global_reference_images
│
├─ Is previous scene sequential and compatible?
│  ├─ YES → Add image=prev_scene.last_frame (hybrid approach)
│  └─ NO → References only (scene break/location change)
│
└─ Generate with selected configuration
```

### Compatibility Check (Automated)

```python
from core.video.reference_manager import ReferenceManager

ref_manager = ReferenceManager()

should_use_continuity, reason = ref_manager.should_use_last_frame_continuity(
    prev_scene, current_scene, check_prompts=True
)

# Detects:
# - Sequential order (scene.order)
# - Transition keywords ("fade to", "cut to", etc.)
# - Location changes (basic heuristics)
```

---

## Migration Guide

### For Existing Projects

Existing projects will automatically migrate when loaded:

```python
# Old project file (pre-reference-types):
{
  "global_reference_images": [
    {
      "path": "/path/to/ref.png",
      "label": "character",       # ← Legacy string label
      "description": "Sarah"
    }
  ]
}

# Loaded as:
ReferenceImage(
    path=Path("/path/to/ref.png"),
    ref_type=ReferenceImageType.CHARACTER,  # ← Parsed from label
    name="Sarah",                            # ← Extracted from description
    label="character"                        # ← Kept for backward compat
)
```

---

## UI Integration (TODO)

### Planned UI Components

1. **Reference Library Panel** (Project-level)
   - Grid view of all global references
   - Add/remove/reorder references
   - Type selector dropdown (CHARACTER, OBJECT, ENVIRONMENT, STYLE)
   - Name input field
   - Validation status indicators

2. **Reference Generation Wizard**
   - "Generate Character References" button
   - Character description input
   - Style/quality settings
   - Auto-generates 3-angle reference sheet

3. **Per-Scene Reference Override**
   - Toggle: "Use Global References" / "Use Scene-Specific"
   - When scene-specific: Mini reference selector
   - Visual indicator when scene uses overrides

4. **Smart Reference Preview**
   - Hover over scene → show which references will be used
   - Visual diff when scene overrides globals

---

## Best Practices

### DO ✅

1. **Generate character references at project start**
   - 3 angles: front, 3/4 side, full body
   - Same lighting and style across all 3
   - Use project's visual style

2. **Use global references for main characters**
   - Apply to all scenes automatically
   - Override only when truly necessary

3. **Validate all references before adding**
   - Check resolution (≥720p)
   - Verify format (PNG/JPEG)
   - Confirm file size (<50MB)

4. **Combine with last-frame for smooth motion**
   - Use references for character/environment
   - Add last-frame for motion continuity
   - Only for compatible sequential scenes

5. **Name references clearly**
   - "Sarah" not "character_1"
   - "Vintage Car" not "object_ref"
   - Helps with smart selection

### DON'T ❌

1. **Don't use image-to-video for scene changes**
   - Last-frame can't transform scenes
   - Use references instead

2. **Don't exceed 3 references per generation**
   - Veo 3 API limit
   - Prioritize: character > environment > objects

3. **Don't mix incompatible styles**
   - All references should match project style
   - Consistent lighting, color grading

4. **Don't use low-resolution references**
   - Minimum 720p
   - Higher is better for quality

5. **Don't forget to validate**
   - Always use ReferenceImageValidator
   - Handle validation errors gracefully

---

## Troubleshooting

### Issue: "Reference image validation failed"
**Solution**: Use `ReferenceImageValidator` to check specific errors:
```python
info = validator.validate_reference_image(path)
print(info.validation_errors)  # See specific issues
```

### Issue: "Veo 3 ignoring references"
**Possible causes**:
- References not passed to `VeoGenerationConfig.reference_images`
- Scene has `use_global_references=False` but no scene-specific refs
- Reference file paths invalid/missing

**Solution**:
```python
refs = project.get_effective_references_for_scene(scene)
print(f"Using {len(refs)} refs: {[r.path for r in refs]}")
# Verify all paths exist
assert all(r.path.exists() for r in refs)
```

### Issue: "Character looks different across scenes"
**Possible causes**:
- Different references used per scene
- References not high quality enough
- Prompt contradicts reference appearance

**Solution**:
- Verify all scenes use same global references
- Check reference image quality (1080p+)
- Ensure prompts don't contradict (e.g., don't say "blonde hair" if ref shows dark hair)

---

## API Reference

See:
- `/core/video/reference_manager.py` - Validation, management, generation
- `/core/video/project.py` - Data models (ReferenceImage, Scene, VideoProject)
- `/core/video/veo_client.py` - Video generation with references

---

## Next Steps (Implementation)

- [ ] Update `video_project_tab.py` to use reference system
- [ ] Create UI for reference library management
- [ ] Create reference generation wizard dialog
- [ ] Add per-scene reference override UI
- [ ] Update video generation workflow to use references-first
- [ ] Add validation indicators in UI
- [ ] Create user guide/tutorial

---

**Status**: Backend complete ✅ | UI integration pending ⏳
