# Discord Post: Font Generator Options

**Posted:** 2026-01-26

---

## ImageAI Font Generator - Create Custom Fonts from Images

Transform your alphabet images into installable TTF/OTF fonts with ImageAI's Font Generator wizard.

### Character Set Options
- **Uppercase (A-Z)** - 26 characters
- **Lowercase (a-z)** - 26 characters
- **Uppercase + Lowercase** - 52 characters
- **Uppercase + Digits** - 36 characters
- **Full Set** - A-Z, a-z, 0-9 (62 characters)
- **Custom** - Define your own character set

### Segmentation Methods
- **Contour-based** - Best for irregular spacing, hand-drawn
- **Grid-based** - Best for uniform rows/columns
- **Auto Detect** - Tries both, picks best result

### Vectorization Quality
- **None** - Maximum detail (clean sources)
- **Low** - Slight cleanup
- **Medium** - Balanced (general purpose)
- **High** - Heavy smoothing (hand-drawn)
- **Maximum** - Aggressive (rough sketches)

### Export Settings

**Font Metadata Fields**
- **Font Family** *(required)* - Display name (e.g., "MyHandwriting")
- **Style** *(required)* - Regular, Bold, Italic, or Light
- **Version** *(required)* - Semantic version (e.g., "1.0")
- **Designer** *(optional)* - Creator's name
- **Copyright** *(optional)* - Copyright notice

**Export Formats:**
- **TrueType (.ttf)** - Maximum compatibility across all systems
- **OpenType (.otf)** - Advanced typography features

**Automatic Font Metrics:**
The generator calculates these automatically:
- Units Per Em (1000 standard)
- Ascender/Descender heights
- Baseline alignment
- Advance width (character spacing)
- Per-character bounding boxes

### Tips
1. Use high-res images (300+ DPI)
2. Dark text on light background works best
3. Keep consistent spacing between characters
4. Thin strokes may not render well
5. All settings persist between sessions

Access via **Tools > Font Generator** in ImageAI v0.32+

---

*ImageAI Font Generator - Turn any alphabet image into a working font*
