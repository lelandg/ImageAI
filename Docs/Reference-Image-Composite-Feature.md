# Reference Image Auto-Composite Feature

## Overview

The auto-composite feature allows you to use multiple reference images (people, characters, etc.) with AI models that have single-image limitations. Multiple images are automatically combined into a single "character design sheet" composite image.

## Key Changes

### 1. Strict Mode: Maximum 3 References
- **Previous**: Maximum 4 reference images
- **New**: Maximum 3 reference images
- Uses Imagen 3 Customization API for precise subject preservation

### 2. Flexible Mode: Unlimited References with Auto-Composite
- **Previous**: Single reference image only
- **New**: Unlimited reference images
- Multiple images are auto-composited into a single square (1:1) image
- Uses Google Gemini for style transformation

### 3. Mode Switching with Selection Dialog
- When switching from Flexible to Strict mode with more than 3 images:
  - A selection dialog appears
  - User chooses which 3 images to keep
  - Remaining images are removed

## How to Use

### Using Single Reference (Flexible Mode)
1. Select "Flexible" mode in the Reference Mode section
2. Click "+ Add Reference Image"
3. Select one image
4. Generate as normal (style transfer applied)

### Using Multiple References (Flexible Mode with Auto-Composite)
1. Select "Flexible" mode in the Reference Mode section
2. Click "+ Add Reference Image" multiple times to add images
3. A help banner appears when you have 2+ images with guidance
4. In the main **Prompt** field, enter a description like:
   - "These people as high resolution cartoon characters"
   - "These characters in anime style"
   - "Professional headshots of these individuals"
5. Click "Generate"
6. The system will:
   - Composite all images into a grid layout on a square canvas
   - Append arrangement instructions to your prompt automatically
   - Generate the image using the composite as reference

### Using Strict Mode (Subject Preservation)
1. Select "Strict" mode
2. Add up to 3 reference images
3. In your prompt, reference images using tags: [1], [2], [3]
   - Example: "A photo of [1] and [2] at the beach, [3] in background"
4. Generate with precise subject preservation

## Technical Details

### Compositor
- **Location**: `core/reference/image_compositor.py`
- **Canvas Size**: 1024x1024 pixels (square, 1:1 aspect ratio)
- **Arrangements**: Grid (auto-calculated), horizontal, or vertical
- **Output Format**: PNG with transparency support
- **Storage**: Composites saved to `<UserDataDir>/composites/`

### Prompt Enhancement
When using multiple images in flexible mode, the system:
1. Takes your prompt (e.g., "These people as cartoon characters")
2. Appends: "Place each in an equal part of the image, on a clean background, suitable as character design sheet."

Example:
- **Your prompt**: "These people as high resolution cartoon characters"
- **Final prompt**: "These people as high resolution cartoon characters. Place each in an equal part of the image, on a clean background, suitable as character design sheet."

**Note**: When using multiple references, your prompt should describe how to represent the people/characters, not a scene. The output will be a character design sheet with all subjects arranged in a grid.

### Selection Dialog
- **Location**: `gui/reference_selection_dialog.py`
- Shows thumbnail cards for all images
- Click to select/deselect
- Must select exactly N images (enforced by OK button)
- Used when switching to strict mode with too many images

## Video Tab Support

The same auto-composite feature is available in the Video Project tab:
- Reference Library widget updated with help text
- Multiple character references can be composited for video generation
- Extracted frames can be added as references

## Files Modified

### Core Components
- `core/reference/image_compositor.py` - New compositor class
- `gui/reference_selection_dialog.py` - New selection dialog

### UI Updates
- `gui/imagen_reference_widget.py`:
  - Changed strict mode max from 4 to 3
  - Removed 1-image limit in flexible mode
  - Added composite description field
  - Added mode switching with selection dialog
  - Updated tooltips and help text

- `gui/main_window.py`:
  - Updated flexible mode generation to support multiple images
  - Added compositor integration
  - Enhanced prompt generation for composites

- `gui/video/reference_library_widget.py`:
  - Updated help text to mention compositing

## Usage Tips

1. **Prompt Best Practices for Multiple References**:
   - Describe the desired style (cartoon, anime, realistic, etc.)
   - Mention "high resolution" for better quality
   - Keep it concise (one sentence)
   - Focus on how to represent the subjects, not a scene
   - Examples:
     - "These people as Disney-style cartoon characters"
     - "Professional portrait photos in watercolor style"
     - "High resolution anime character designs"

2. **Image Selection**:
   - Use images with similar lighting for best results
   - Ensure faces/subjects are clearly visible
   - Square or portrait orientation works best

3. **Aspect Ratio**:
   - Composites are always square (1:1)
   - Works best for both image and video generation
   - Ensures compatibility across different models

4. **Storage**:
   - Composites are saved to `<UserDataDir>/composites/`
   - Timestamped filenames prevent conflicts
   - Can be reused as regular reference images

## Examples

### Example 1: Three Characters
```
1. Add 3 reference photos to Flexible mode
2. Prompt: "These people as Disney-style cartoon characters"
3. System composites images and appends arrangement instructions
4. Result: Character design sheet with 3 Disney-style characters in a grid
5. (Optional) Use the generated design sheet as reference for scenes
```

### Example 2: Family Portrait
```
1. Add family photos to Flexible mode
2. Prompt: "Professional family portrait in watercolor style"
3. Result: Character design sheet with family members in watercolor style
```

### Example 3: Video Characters
```
1. In Video tab, add character photos to reference library
2. When generating scenes, the composited character sheet maintains consistency
3. Each video frame uses the character design sheet as reference
```

## Troubleshooting

### Generation with multiple references
- **What happens**: System composites your reference images and uses your prompt to describe the composite
- **Help text**: A yellow banner appears with guidance when you have 2+ images
- **Prompt guidance**: Enter something like "These people as high resolution cartoon characters"

### "Strict mode allows maximum 3 reference images"
- **Cause**: Trying to add more than 3 images in strict mode
- **Solution**: Switch to flexible mode or remove some images

### Selection dialog appears when switching modes
- **Cause**: Switching from flexible to strict with more than 3 images
- **Solution**: Select your 3 most important images and click OK

### Composite quality is poor
- **Cause**: Images may be too different in lighting/style
- **Solution**: Try using images with similar characteristics

## Future Enhancements

Potential improvements for future versions:
- Custom grid layouts (2x2, 3x1, etc.)
- Automatic image size equalization
- Background removal before compositing
- Label/name overlay on each character
- Preview of composite before generation
- Save/load composite presets
