# ImageAI v0.32 Discord Release Post

**Posted:** 2026-01-24

---

## ImageAI v0.32 Released!

Two major new features have landed:

### Character Animator Puppet Creator
Turn any image into an Adobe Character Animator puppet!
- **AI Body Segmentation** - MediaPipe + SAM 2 automatically detect body parts
- **Viseme Generation** - 14 mouth shapes generated via Gemini or OpenAI
- **Eye Blink States** - Natural animation with automatic blink generation
- **Export Options** - PSD or SVG with Adobe-compatible layer naming
- **Cost-Aware** - Real-time cost estimation before generation
- **Smart Caching** - Cached results avoid redundant API calls

Step-by-step wizard walks you through: Dependencies -> Image -> Body Parts -> Visemes -> Export

### Font Generator
Create custom fonts from alphabet images!
- **Auto Character Detection** - Contour or grid-based segmentation
- **Character Set Recognition** - Automatically detects uppercase, lowercase, digits
- **Vector Tracing** - Configurable smoothing for clean outlines
- **Proper Font Metrics** - Baseline, spacing, and kerning calculated
- **Multiple Formats** - Export to TTF or OTF
- **Live Preview** - See your font rendered in real-time

### Documentation
Full user guides added for both features in `Docs/`

---

Download: `git pull` or grab the latest from GitHub
Questions? Drop them below!
