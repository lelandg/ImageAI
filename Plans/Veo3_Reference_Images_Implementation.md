# Veo 3 Reference Images Implementation Summary

**Status**: Core Implementation Complete - UI Integration Pending
**Created**: 2025-10-18
**Feature**: Support for up to 3 reference images in Veo 3 video generation for visual continuity

## Overview

Veo 3 supports up to 3 reference images for maintaining visual consistency across scenes. Reference images guide the AI in maintaining character appearance, environment style, and lighting/mood throughout video generation.

## What Was Implemented

### 1. Data Model (`core/video/project.py`)

#### New `ReferenceImage` Dataclass (Lines 147-176)
```python
@dataclass
class ReferenceImage:
    """A reference image for style/character/environment consistency"""
    path: Path
    label: Optional[str] = None  # e.g., "character", "environment", "lighting"
    description: Optional[str] = None
    auto_linked: bool = False  # True if from previous scene's last frame
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Features**:
- Flexible labeling system (typed or generic)
- Auto-linking support for continuity
- Full JSON serialization

#### Enhanced `Scene` Class (Lines 241-355)
```python
# New fields
reference_images: List[ReferenceImage] = field(default_factory=list)  # Scene-specific (max 3)
use_global_references: bool = True  # Toggle between global and scene-specific

# New helper methods
def add_reference_image(ref_image: ReferenceImage, max_refs: int = 3) -> bool
def get_effective_reference_images(global_refs: Optional[List[ReferenceImage]] = None) -> List[ReferenceImage]
def clear_reference_images()
```

**Features**:
- Per-scene reference images (up to 3)
- Global vs scene-specific toggle
- Automatic max-3 enforcement
- Full serialization support

#### Enhanced `VideoProject` Class (Line 386)
```python
# New field
global_reference_images: List[ReferenceImage] = field(default_factory=list)  # Max 3 global
```

**Features**:
- Project-wide reference images
- Shared across all scenes by default
- Full serialization support

### 2. Storyboard Generator (`core/video/storyboard_v2.py`)

#### New Auto-Linking Method (Lines 507-545)
```python
def apply_reference_image_auto_linking(scenes: List[Scene]) -> List[Scene]
```

**Features**:
- Automatically uses previous scene's `last_frame` as first reference for next scene
- Creates properly labeled ReferenceImage objects
- Tracks source scene metadata
- Can be enabled/disabled via `enable_auto_link_references` flag

**How It Works**:
```
Scene 1 generates video → extracts last_frame
                           ↓
Scene 2 receives last_frame as reference_images[0] (auto-linked=True)
                           ↓
Scene 2 uses this for visual continuity during generation
```

### 3. Veo Client Integration (`core/video/veo_client.py`)

#### Enhanced `VeoGenerationConfig` (Line 52)
```python
reference_images: Optional[List[Path]] = None  # Up to 3 references
```

**Validation**:
- Max 3 references enforced in `__post_init__`
- Clear error message if exceeded

#### Updated `VeoClient.generate_video_async()` (Lines 279-350)

**Reference Image Loading** (Lines 279-300):
```python
# Load reference images (max 3)
reference_image_list = []
if config.reference_images:
    for idx, ref_path in enumerate(config.reference_images[:3]):
        # Load and encode each reference image
        ref_image = {
            'imageBytes': ref_bytes,
            'mimeType': 'image/png'
        }
        reference_image_list.append(ref_image)
```

**API Integration** (Lines 324-327):
```python
# Add to video config
if reference_image_list:
    video_config_params["reference_images"] = reference_image_list
```

**Enhanced Logging**:
- Logs each reference image loaded
- Shows total count of references being used
- Indicates visual consistency mode

### 4. UI Widget (`gui/video/reference_images_widget.py`)

#### New `ReferenceImagesWidget` Class
Manages up to 3 reference images with button-based interface.

**Features**:
- 3 reference image slots (using `FrameButton` components)
- Each slot supports:
  - Generate new reference image
  - Load from disk
  - Select from existing images
  - Clear reference
  - Auto-link from previous scene
- Hover previews (200x200px thumbnails)
- Right-click context menus

**API**:
```python
# Set a reference
set_reference_image(index: int, path: Path, auto_linked: bool = False)

# Get a specific reference
get_reference_image(index: int) -> Optional[Path]

# Get all valid references
get_valid_references() -> List[Path]

# Clear all
clear_all()
```

## Integration Points

### Scene Table Integration (workspace_widget.py)

**TODO**: Add reference images column to scene table

Current table columns:
```
| # | Start Frame | End Frame | 🎬 | Time | ⤵️ | Start Prompt | End Prompt | Lyrics/Text |
```

Proposed with references:
```
| # | Start Frame | End Frame | Ref Images [1][2][3] | 🎬 | Time | ⤵️ | Start Prompt | End Prompt | Lyrics/Text |
```

**Implementation Steps**:
1. Import `ReferenceImagesWidget` in workspace_widget.py
2. Add "Ref Images" column to table header (after End Frame)
3. Create `ReferenceImagesWidget` for each row
4. Wire up signals:
   - `reference_changed` → update scene.reference_images
   - Connect to image generation system
   - Connect to file dialog for loading
   - Connect to variant selector

### Global Reference Images (Project Settings)

**TODO**: Add global reference images section

Proposed location: Video Tab settings area (near audio tracks)

**UI Layout**:
```
┌─────────────────────────────────────────────────────────────────┐
│ Global Reference Images (used by all scenes by default)         │
├─────────────────────────────────────────────────────────────────┤
│ [Ref 1] [Ref 2] [Ref 3]  [Clear All]                           │
│                                                                  │
│ These images guide visual consistency across your entire video. │
│ Scenes can override with their own reference images.            │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation Steps**:
1. Add global_reference_images widget to settings panel
2. Wire up to `VideoProject.global_reference_images`
3. Save/load with project JSON
4. Allow scenes to toggle `use_global_references`

### Video Generation Integration

**TODO**: Pass reference images to Veo during video generation

Current generation flow:
```python
# In video generation worker
config = VeoGenerationConfig(
    prompt=prompt,
    image=start_frame,
    last_frame=end_frame,
    # ADD THIS:
    reference_images=scene.get_effective_reference_images(project.global_reference_images)
)
```

**Implementation Steps**:
1. In video generation code, get effective references for scene
2. Convert `ReferenceImage` objects to `List[Path]`
3. Pass to `VeoGenerationConfig`
4. VeoClient handles the rest (already implemented!)

## Usage Workflows

### Workflow 1: Global References for Entire Project

**Use Case**: Consistent character/style throughout video

1. Set 3 global reference images in project settings:
   - Ref 1: Character portrait
   - Ref 2: Environment style
   - Ref 3: Lighting/mood reference

2. All scenes automatically use these references

3. Generate all videos with consistent visual style

### Workflow 2: Auto-Linked Scene Continuity

**Use Case**: Smooth scene transitions using previous frames

1. Enable auto-link references in storyboard generator

2. Generate Scene 1 video → extracts last_frame

3. Scene 2 automatically receives Scene 1's last_frame as reference

4. Scene 2 video maintains visual continuity from Scene 1

5. Repeat for all scenes → seamless visual flow

### Workflow 3: Per-Scene Custom References

**Use Case**: Different visual styles per scene

1. Set global references (optional baseline)

2. For specific scenes:
   - Toggle "Use Scene-Specific References"
   - Set custom references for that scene only
   - Override global references

3. Mix global and custom references throughout video

### Workflow 4: Hybrid Approach

**Use Case**: Best of all worlds

1. Set 1-2 global references (character, environment)

2. Enable auto-link for scene transitions

3. Auto-linked frames become 3rd reference slot

4. Each scene has:
   - Global reference 1 (character)
   - Global reference 2 (environment)
   - Auto-linked reference (previous scene's last frame)

5. Maximum visual continuity + flexibility

## API Integration

### Veo API Call Format

When reference images are provided, the Veo API call includes:

```python
response = client.models.generate_videos(
    model="veo-3.0-generate-001",
    prompt="Your prompt here",
    image=start_frame,  # Optional start frame
    config=types.GenerateVideosConfig(
        aspect_ratio="16:9",
        duration_seconds=8,
        last_frame=end_frame,  # Optional end frame (Veo 3.1)
        reference_images=[ref1, ref2, ref3]  # NEW: Up to 3 references
    )
)
```

Each reference image is encoded as:
```python
{
    'imageBytes': <PNG bytes>,
    'mimeType': 'image/png'
}
```

## File Locations

### Modified Files
1. `core/video/project.py` - Data models
2. `core/video/storyboard_v2.py` - Auto-linking
3. `core/video/veo_client.py` - API integration

### New Files
1. `gui/video/reference_images_widget.py` - UI widget

### Pending Integration
1. `gui/video/workspace_widget.py` - Scene table integration
2. `gui/video/workspace_widget.py` - Global references UI

## Testing Checklist

- [ ] Data model serialization (save/load project with references)
- [ ] Scene-specific references (add, get, clear)
- [ ] Global references (add, get, clear)
- [ ] Auto-linking (previous last_frame → next reference)
- [ ] VeoClient validation (max 3 references enforced)
- [ ] Reference image loading (file I/O)
- [ ] API call includes reference_images parameter
- [ ] UI widget (3 slots, buttons work)
- [ ] Scene table integration
- [ ] Global references UI
- [ ] End-to-end video generation with references

## Next Steps

1. **UI Integration** (workspace_widget.py):
   - Add reference images column to scene table
   - Add global references section to project settings
   - Wire up all signals and event handlers

2. **Video Generation Integration**:
   - Update video generation worker to pass references
   - Extract effective references for each scene
   - Handle auto-linking during generation

3. **Testing**:
   - Unit tests for data model
   - Integration tests for auto-linking
   - End-to-end test with Veo API

4. **Documentation**:
   - Update user guide with reference images workflow
   - Add examples to inspirational continuity guide
   - Create video tutorial

## Known Limitations

1. **Max 3 References**: Veo 3 API limit, enforced at multiple levels
2. **PNG Only**: Current implementation assumes PNG format (can be extended)
3. **Auto-linking**: Only links last_frame, not other frame types
4. **UI Incomplete**: Table integration and global references UI pending

## Future Enhancements

1. **Smart Reference Selection**: AI suggests which images to use as references
2. **Reference Categories**: Enforce character/environment/lighting slots
3. **Reference Preview**: Show all references in a panel during generation
4. **Reference Templates**: Preset reference combinations for common use cases
5. **Reference Extraction**: Auto-extract reference-worthy frames from videos

---

**Implementation Status**: ✅ Core Complete | ⏳ UI Integration Pending
**Next Milestone**: Complete workspace_widget integration and test end-to-end
