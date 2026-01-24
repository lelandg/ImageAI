# Font Generator Guide

> Create custom fonts from alphabet images with automatic character segmentation and vector tracing.

## Overview

The Font Generator wizard transforms alphabet images into installable font files (TTF/OTF). It automatically segments individual characters, converts them to vector outlines, and builds a complete font with proper metrics.

## Quick Start

1. Open ImageAI and go to **Tools > Font Generator**
2. Upload an image containing your alphabet characters
3. Review and adjust character segmentation
4. Verify character mappings
5. Configure font settings
6. Preview and export to TTF/OTF

## Wizard Steps

### Step 1: Image Upload

Upload an image containing your alphabet characters. The wizard supports various arrangements:

**Supported Formats:** PNG, JPEG, BMP, TIFF

**Image Requirements:**
- Characters arranged in rows with clear spacing
- Dark characters on light background (or enable Invert)
- Consistent character sizing works best
- Higher resolution produces better quality fonts

**Character Set Selection:**
- Uppercase (A-Z) - 26 characters
- Lowercase (a-z) - 26 characters
- Uppercase + Lowercase - 52 characters
- Uppercase + Digits - 36 characters
- Full (A-Z, a-z, 0-9) - 62 characters
- Custom - Enter your own character set

### Step 2: Character Segmentation

The wizard detects individual characters using one of three methods:

**Segmentation Methods:**

| Method | Best For | Description |
|--------|----------|-------------|
| Contour-based | Irregular spacing | Detects character outlines automatically |
| Grid-based | Uniform grids | Divides image into rows and columns |
| Auto Detect | Unknown layouts | Tries both and selects best result |

**Adjustment Options:**
- **Invert** - Toggle for light text on dark background
- **Padding** - Add spacing around detected characters
- **Grid Rows/Cols** - Manual grid specification (grid mode only)
- **Re-analyze** - Rerun detection with current settings

**Visual Feedback:**
- Red bounding boxes show detected characters
- Status displays found vs expected character count
- Warnings highlight potential issues

### Step 3: Character Mapping

Review and correct the automatic character assignments:

- Each detected character is shown with its image and label
- Click the label field to change the assigned character
- Scroll through all detected characters to verify accuracy
- Fix any misidentified characters before proceeding

**Common Issues:**
- Similar characters confused (I/l/1, O/0, etc.)
- Wrong order due to detection sequence
- Missing characters from unclear source image

### Step 4: Font Settings

Configure your font's metadata and quality settings:

**Font Information:**
- **Font Family** - The name users will see (e.g., "MyCustomFont")
- **Style** - Regular, Bold, Italic, or Light
- **Version** - Semantic version (e.g., "1.0")
- **Designer** - Your name (optional)
- **Copyright** - Copyright notice (optional)

**Vectorization Quality:**

| Smoothing | Effect | Best For |
|-----------|--------|----------|
| None | Maximum detail | Already smooth source images |
| Low | Slight cleanup | Clean source with minor noise |
| Medium | Balanced | General purpose |
| High | Heavy smoothing | Rough or hand-drawn sources |
| Maximum | Aggressive | Very rough sources |

**Export Format:**
- **TrueType (.ttf)** - Most compatible across systems
- **OpenType (.otf)** - Advanced typography features

### Step 5: Preview & Export

Preview your font with sample text and export:

**Preview:**
- Enter custom sample text to preview
- Font is rendered using the actual generated font
- Check character spacing and visual quality

**Export:**
- Click **Export Font...** to save
- Choose destination folder and filename
- Both TTF and OTF can be exported simultaneously

## Technical Details

### Vector Tracing

Characters are converted from bitmap to vector using:

1. **Contour Detection** - OpenCV finds character outlines
2. **Path Simplification** - Reduces point count while preserving shape
3. **Bezier Fitting** - Converts to smooth curves
4. **Smoothing** - Applies selected smoothing level

### Font Metrics

The generator automatically calculates:

- **Units Per Em** - Standard 1000 units
- **Ascender/Descender** - Vertical bounds
- **Baseline** - Character alignment
- **Advance Width** - Character spacing
- **Bounding Boxes** - Per-character dimensions

### Dependencies

The Font Generator requires **fonttools** for font building:

```bash
pip install fonttools
```

If fonttools is not installed, export will be disabled with a warning.

## Best Practices

### Source Image Quality

1. **Use high resolution** - 300 DPI or higher
2. **Maintain consistency** - Same size and style for all characters
3. **Clean backgrounds** - Solid white or transparent works best
4. **Sufficient spacing** - Characters shouldn't touch
5. **Clear forms** - Avoid very thin strokes

### Character Arrangement

**Recommended Layout:**
```
A B C D E F G
H I J K L M N
O P Q R S T U
V W X Y Z
```

**For Grid-based Segmentation:**
- Use exact rows and columns
- Equal spacing between characters
- No extra margins or decorations

### Smoothing Selection

| Source Type | Recommended Smoothing |
|-------------|----------------------|
| Clean vector-style | None or Low |
| High-res photograph | Low or Medium |
| Hand-drawn/scanned | Medium or High |
| Rough sketch | High or Maximum |

## Troubleshooting

### Wrong Character Count

**Symptoms:** "Found X of Y characters" shows mismatch

**Solutions:**
1. Adjust **Invert** setting if text is light on dark
2. Increase **Padding** if characters are merging
3. Switch to **Grid-based** method with explicit rows/cols
4. Verify source image has all expected characters

### Poor Quality Output

**Symptoms:** Jagged edges, missing details, distorted shapes

**Solutions:**
1. Use higher resolution source image
2. Reduce **Smoothing** level to preserve detail
3. Check that source characters have clear edges
4. Ensure sufficient contrast in source image

### Export Fails

**Symptoms:** Error message on export

**Solutions:**
1. Install fonttools: `pip install fonttools`
2. Check write permissions for output directory
3. Ensure filename doesn't contain special characters
4. Try exporting to a different location

### Characters Not Detected

**Symptoms:** Some characters missing from segmentation

**Solutions:**
1. Check image has sufficient contrast
2. Try **Invert** if using light-on-dark text
3. Reduce **Padding** if it's excluding small characters
4. Use **Grid-based** method for uniform layouts

## File Locations

**Default Export Directory:**
- Windows: `%APPDATA%\ImageAI\Fonts\`
- macOS: `~/Library/Application Support/ImageAI/Fonts/`
- Linux: `~/.config/ImageAI/Fonts/`

**Settings Persistence:**
All wizard settings are saved and restored between sessions.

## Example Workflow

1. **Prepare Image:** Create alphabet in image editor with consistent styling
2. **Upload:** Select image and choose "Uppercase (A-Z)"
3. **Segment:** Use Contour-based with Invert OFF, Padding 2
4. **Verify:** Check all 26 characters are correctly labeled
5. **Configure:** Name "MyHandwriting", Style "Regular", Smoothing "Low"
6. **Preview:** Type sample text to verify appearance
7. **Export:** Save as "MyHandwriting.ttf"

## Related Documentation

- [ImageAI Features](ImageAI_Features.md)

---

*Part of ImageAI v0.32.0 | [GitHub Repository](https://github.com/lelandg/ImageAI)*
