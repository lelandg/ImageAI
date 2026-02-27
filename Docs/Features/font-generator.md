# Font Generator

## Overview

The Font Generator tab turns any image containing alphabet characters into a working font file (TTF or OTF). Upload a photo of handwriting, a stylized alphabet, or an AI-generated character sheet, and the wizard segments, maps, and exports a fully usable font.

## Features

### Step 1 — Image Upload

Load your alphabet image:

- Supported formats: PNG, JPEG, WebP.
- Best results: a single image with all characters you want, arranged in rows or a grid, on a contrasting background.
- Select the character set the image contains:

| Character Set | Includes |
|---------------|---------|
| Uppercase | A–Z (26 characters) |
| Lowercase | a–z (26 characters) |
| Digits | 0–9 |
| Custom | Any characters you specify |

You can combine sets (e.g., Uppercase + Digits).

### Step 2 — Segmentation

ImageAI automatically finds and separates each character from the image.

Choose a segmentation method:

| Method | When to Use |
|--------|------------|
| Contour-based | Characters have visible outlines and clear gaps between them |
| Grid-based | Characters are arranged in a uniform grid — specify rows and columns |
| Auto Detect | Let ImageAI choose based on image analysis |

After segmentation, each detected character is shown in a preview grid. Adjust bounding boxes by dragging if any character was cut off or merged with a neighbor.

**Auto-Inversion:** If your image has light text on a dark background, ImageAI automatically inverts it so characters are processed as dark-on-light.

### Step 3 — Character Mapping

Review and correct the label assigned to each segmented character:

- ImageAI assigns labels in order based on your chosen character set.
- Click any character cell to reassign its label if the order is wrong.
- Skip characters you do not want to include in the font.

### Step 4 — Font Settings

Configure your font's metadata:

| Setting | Description |
|---------|-------------|
| Family Name | The name shown in app font menus |
| Style | Regular, Bold, Italic, etc. |
| Version | Font version number (e.g., 1.0) |
| Designer | Your name or credit |
| Copyright | Copyright notice text |
| Smoothing | Amount of vector smoothing applied to glyph outlines |

**Smoothing levels:**

- None — exact pixel outlines (sharp corners, best for pixel fonts)
- Low — slight smoothing (preserves detail)
- Medium — balanced smoothing (recommended for handwriting)
- High — aggressive smoothing (best for simple shapes)

### Step 5 — Preview and Export

A live preview shows your font rendering sample text. Adjust font settings and see changes instantly.

**Export formats:**

| Format | Notes |
|--------|-------|
| TTF (TrueType Font) | Most compatible — works on Windows, Mac, Linux, and all apps |
| OTF (OpenType Font) | Supports advanced OpenType features; choose if you know you need it |

After export, install the font on your system normally (double-click the file on Windows or Mac, or copy to ~/.fonts on Linux). It then appears in all applications including ImageAI's Layout/Books tab.

**Settings persistence:** All font settings are saved and restored the next time you open the Font Generator.

## Common Questions

**Q: My characters are not being detected correctly. What should I try?**
Try switching to Grid-based segmentation and manually enter the number of rows and columns your alphabet image uses. This method is most reliable for structured grids.

**Q: The generated font looks jagged. How do I fix it?**
Increase the smoothing level in Step 4. Medium or High smoothing works well for handwritten or artistic fonts.

**Q: Can I include special characters like punctuation?**
Yes — use the Custom character set option and type the characters you want. Make sure your image includes them in the same order.

**Q: After exporting, the font does not appear in other apps. Why?**
You need to install the font on your operating system. On Windows: double-click the TTF file and click Install. On Mac: double-click and click Install Font. On Linux: copy the file to ~/.fonts and run fc-cache -fv.

**Q: What is the difference between TTF and OTF?**
For most users, there is no practical difference. Choose TTF unless a specific application requires OTF.
