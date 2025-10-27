# 📖 ImageAI Layout/Books Module - Implementation Plan

**Last Updated:** 2025-10-27 15:25:56

**Goal:** Implement a comprehensive layout engine for children's books, comics, and magazine articles with template-driven intelligent placement, LLM integration, and professional export capabilities.

---

## Overview

Building on the starter bundle in `Plans/ImageAI_Layout_Starter/`, this plan outlines the full implementation of the Layout/Books module for ImageAI, integrating it seamlessly with the existing codebase while adding powerful new capabilities.

---

## Phase 1: Core Integration & Foundation ✅ **100% Complete**

**Goal:** Integrate the starter code into ImageAI's existing architecture and establish the foundation.

**Status:** Phase 1 is **100% complete**. All tasks finished successfully.

**Last Updated:** 2025-10-27 (current session)

### Tasks

1. ✅ **Directory Structure Setup** - **COMPLETED**
   - Created `core/layout/` package
   - Created `templates/layouts/` directory
   - Created `gui/layout/` for GUI components
   - Files created: All directories established at project root

2. ✅ **Move Starter Files** - **COMPLETED**
   - Moved and adapted `layout_engine.py` → `core/layout/engine.py` (237 lines)
   - Moved template JSONs → `templates/layouts/*.json` (3 templates)
   - Created `core/layout/__init__.py` with public API (36 lines)
   - Created `core/layout/models.py` for data classes (90 lines)

3. ✅ **Font System Integration** - **COMPLETED** (core/layout/font_manager.py:1)
   - Implemented `core/layout/font_manager.py` (185 lines)
   - System font discovery (platform-specific: Windows, macOS, Linux)
   - Font manifest building with TTF/OTF scanning
   - Font cache for quick lookups
   - Fallback chain support
   - Note: MyFonts repository scanning will be enhanced in Phase 2

4. ✅ **Configuration Integration** - **COMPLETED** (core/config.py:203)
   - Added layout settings to `ConfigManager`
   - `get_templates_dir()` - Auto-detects project templates directory
   - `get_fonts_dir()` - Custom fonts directory support
   - `get_layout_export_dpi()` / `set_layout_export_dpi()` - Export quality settings (default 300 DPI)
   - `get_layout_llm_provider()` / `set_layout_llm_provider()` - LLM provider for text generation

5. ✅ **Logging Integration** - **COMPLETED** (core/logging_config.py:173)
   - Created `LogManager` class for centralized logger access
   - Layout modules use 'imageai.layout.*' namespace
   - Font manager: `imageai.layout.fonts`
   - Layout engine: `imageai.layout.engine`
   - All logging goes to both file and console with appropriate levels

**Deliverables:** ✅
- ✅ Core layout package structure created (`core/layout/` with 4 modules)
- ✅ Font management system operational (FontManager with system font discovery)
- ✅ Settings integrated with ConfigManager (6 new layout-related methods)
- ✅ Logging properly configured (LogManager with layout-specific loggers)

**Files Created/Modified:**
- `core/layout/__init__.py` (36 lines)
- `core/layout/models.py` (90 lines)
- `core/layout/font_manager.py` (185 lines)
- `core/layout/engine.py` (237 lines)
- `core/config.py` (modified: added layout configuration methods)
- `core/logging_config.py` (modified: added LogManager class)
- `templates/layouts/children_single_illustration.json` (copied)
- `templates/layouts/comic_three_panel_grid.json` (copied)
- `templates/layouts/magazine_two_columns_pullquote.json` (copied)

---

## Phase 2: Enhanced Layout Engine 🎨 **0% Complete**

**Goal:** Improve the starter layout engine with advanced features and better rendering.

**Status:** Phase 2 is **0% complete**. Pending Phase 1.

**Last Updated:** 2025-10-27 12:30

### Tasks

1. **Improved Text Rendering** - **PENDING**
   - Better word wrapping algorithm
   - Hyphenation support (pyphen library)
   - Widow/orphan control
   - Justify text with word spacing
   - Letter spacing adjustment (±2%)
   - Multi-paragraph support with spacing

2. **Advanced Image Handling** - **PENDING**
   - Rounded corners with anti-aliasing
   - Image filters (blur, grayscale, sepia)
   - Border/stroke rendering
   - Alpha channel support
   - Image masks/clipping paths

3. **Template Variable Substitution** - **PENDING**
   - Runtime variable replacement (`{{variable}}` syntax)
   - Color palette support
   - Computed values (e.g., `{{accent_light}}`)
   - Per-page variable overrides

4. **Layout Algorithms** - **PENDING**
   - **Auto-fit text**: Binary search for optimal font size
   - **Text overflow**: Split across multiple pages
   - **Panel grids**: Compute gutter spacing for comics
   - **Column flow**: Magazine text reflow across columns
   - **Safe area**: Margin and bleed handling

5. **Block Constraints** - **PENDING**
   - Min/max font sizes
   - Aspect ratio preservation for images
   - Z-index/layering support
   - Block dependencies (e.g., "caption below image")

**Deliverables:** 🎨
- Production-quality text rendering
- Professional image handling
- Flexible template system
- Smart layout algorithms

---

## Phase 3: Template Management System 📋 **0% Complete**

**Goal:** Build a robust template management system with discovery, validation, and preview generation.

**Status:** Phase 3 is **0% complete**. Pending Phase 2.

**Last Updated:** 2025-10-27 12:30

### Tasks

1. **Template Schema Validation** - **PENDING**
   - JSON schema for templates
   - Validation on load
   - Error reporting with line numbers
   - Schema version compatibility

2. **Template Discovery** - **PENDING**
   - Scan `templates/layouts/` directory
   - Load template metadata (name, description, category, tags)
   - Build template registry
   - Watch for new templates (file system monitoring)

3. **Template Preview Generation** - **PENDING**
   - Generate thumbnail images (256x256)
   - Cache previews in `~/.config/ImageAI/template_cache/`
   - Regenerate on template change
   - Show sample text/images in previews

4. **Template Categories** - **PENDING**
   - Category system: Children's Books, Comics, Magazines, Custom
   - Tag-based filtering
   - Search by name/description
   - Sort by popularity/recent

5. **Template Inheritance** - **PENDING**
   - Base template + variations
   - Override specific blocks
   - Shared style definitions
   - Template composition

6. **User Templates** - **PENDING**
   - Save custom templates
   - User templates directory in AppData
   - Template export/import
   - Template sharing format

**Deliverables:** 📋
- Template validation system
- Template discovery and registry
- Preview generation and caching
- User template support

---

## Phase 4: GUI Implementation 🖥️ **0% Complete**

**Goal:** Create a comprehensive GUI tab for the Layout/Books module with intuitive controls and live preview.

**Status:** Phase 4 is **0% complete**. Pending Phase 3.

**Last Updated:** 2025-10-27 12:30

### Tasks

1. **Main Layout Tab** - **PENDING**
   - Create `gui/layout/layout_tab.py`
   - Add tab to `MainWindow` (after Help tab)
   - Three-panel layout: Templates (left), Canvas (center), Inspector (right)
   - Use splitters for resizable panels

2. **Template Selector Widget** - **PENDING**
   - Create `gui/layout/template_selector.py`
   - Grid view with thumbnails
   - List view with details
   - Category/tag filters
   - Search bar
   - Template preview on hover

3. **Canvas Widget** - **PENDING**
   - Create `gui/layout/canvas_widget.py`
   - Scrollable, zoomable page preview
   - Show block boundaries in edit mode
   - Click to select blocks
   - Drag to reposition (future)
   - Multi-page navigation (previous/next)

4. **Inspector Panel** - **PENDING**
   - Create `gui/layout/inspector_widget.py`
   - Block-specific properties
   - Text editing for TextBlocks
   - Image selection for ImageBlocks
   - Style overrides (font, size, color, alignment)
   - Live preview updates

5. **Document Properties Dialog** - **PENDING**
   - Create `gui/layout/document_dialog.py`
   - Document title, author, metadata
   - Page size selection
   - Theme/palette configuration
   - Global variables

6. **Text Generation Dialog** - **PENDING**
   - Create `gui/layout/text_gen_dialog.py`
   - LLM provider selection
   - Prompt for text generation
   - Target block selection
   - Generate button with progress
   - Preview before applying

7. **Image Source Integration** - **PENDING**
   - Use existing generated images from history
   - Browse file system for images
   - Generate new images inline (use existing providers)
   - Drag-and-drop support

8. **Export Dialog** - **PENDING**
   - Create `gui/layout/export_dialog.py`
   - Output format selection (PNG sequence, PDF, JSON)
   - Quality/DPI settings
   - Page range selection
   - Progress bar for multi-page export

9. **Status Console Integration** - **PENDING**
   - Use existing `DialogStatusConsole` pattern
   - Show template loading status
   - Show rendering progress
   - Show LLM generation status
   - Error messages with details

**Deliverables:** 🖥️
- Complete Layout/Books tab in GUI
- Template browser with previews
- Interactive canvas with live preview
- Block inspector for editing
- Text generation integration
- Export functionality

---

## Phase 5: LLM Integration for Content Generation 🤖 **0% Complete**

**Goal:** Leverage LLMs to auto-generate text content, enhance prompts, and suggest layouts.

**Status:** Phase 5 is **0% complete**. Pending Phase 4.

**Last Updated:** 2025-10-27 12:30

### Tasks

1. **Text Content Generation** - **PENDING**
   - Create `core/layout/llm_content.py`
   - Generate narration for children's books
   - Generate dialogue for comics
   - Generate articles for magazines
   - Per-block content generation
   - Context-aware generation (previous pages)

2. **Prompt Enhancement** - **PENDING**
   - Enhance user prompts for layout-appropriate imagery
   - Add style keywords based on template type
   - Suggest aspect ratios matching block dimensions
   - Generate cohesive image series for multi-page

3. **Layout Suggestions** - **PENDING**
   - Analyze content and suggest templates
   - Recommend block assignments
   - Suggest color palettes
   - Font pairing recommendations

4. **Story Generation** - **PENDING**
   - Generate complete children's book stories
   - Chapter/page breakdown
   - Character consistency
   - Plot progression

5. **LLM Provider Configuration** - **PENDING**
   - Use existing LiteLLM integration
   - Provider selection in settings
   - Model selection (e.g., gpt-4, claude-3.5-sonnet)
   - Temperature/creativity settings

6. **Error Handling & Fallbacks** - **PENDING**
   - Use `LLMResponseParser` from `gui/llm_utils.py`
   - Handle empty responses
   - Provide default content on failure
   - Log all LLM interactions comprehensively

**Deliverables:** 🤖
- LLM-powered text generation
- Prompt enhancement for images
- Layout recommendation system
- Story generation capabilities

---

## Phase 6: Advanced Export & Rendering 📤 **0% Complete**

**Goal:** Professional-quality export with multiple formats and print-ready output.

**Status:** Phase 6 is **0% complete**. Pending Phase 5.

**Last Updated:** 2025-10-27 12:30

### Tasks

1. **High-Resolution PNG Export** - **PENDING**
   - DPI selection (72, 150, 300, 600)
   - Proper scaling for print (300+ DPI)
   - Anti-aliased text rendering
   - Color profile embedding (sRGB, Adobe RGB)

2. **Professional PDF Export** - **PENDING**
   - Vector text rendering (ReportLab)
   - Embedded fonts
   - Proper page sizes (A4, Letter, custom)
   - Margins and bleed marks
   - Print-ready CMYK support (future)

3. **JSON Sidecar Files** - **PENDING**
   - Save resolved layout with absolute positions
   - Include all content (text, image paths)
   - Round-trip editing support
   - Version metadata

4. **Project File Format** - **PENDING**
   - `.layout.json` project files
   - Save entire document state
   - Template references
   - Work-in-progress support
   - Auto-save functionality

5. **Batch Export** - **PENDING**
   - Export multiple documents
   - Parallel rendering for performance
   - Progress reporting
   - Error recovery

6. **Export Presets** - **PENDING**
   - Web-optimized (72 DPI PNG)
   - Print-ready (300 DPI PDF)
   - Presentation (150 DPI PDF)
   - Custom presets

**Deliverables:** 📤
- High-quality PNG export
- Professional PDF output
- JSON sidecar for editing
- Project file format
- Batch export capabilities

---

## Phase 7: Advanced Features & Polish ✨ **0% Complete**

**Goal:** Add advanced features, polish the UI, and optimize performance.

**Status:** Phase 7 is **0% complete**. Pending Phase 6.

**Last Updated:** 2025-10-27 12:30

### Tasks

1. **Performance Optimization** - **PENDING**
   - Font cache implementation
   - Template preview cache
   - Async page rendering with QThread
   - Progress callbacks for long operations
   - Memory management for large documents

2. **Advanced Text Features** - **PENDING**
   - Multi-language support (unicode, RTL)
   - Advanced typography (ligatures, kerning)
   - Text effects (shadow, outline, gradient)
   - Custom text paths (curved text)

3. **Advanced Image Features** - **PENDING**
   - Image editing (crop, rotate, filters)
   - Blend modes
   - Image masks
   - Background removal integration

4. **Interactive Editing** - **PENDING**
   - Drag blocks to reposition
   - Resize blocks with handles
   - Visual guides and snap-to-grid
   - Undo/redo system
   - Keyboard shortcuts

5. **Template Editor** - **PENDING**
   - Visual template creation
   - Block placement with mouse
   - Style editor
   - Save as custom template

6. **Collaboration Features** - **PENDING**
   - Export template packs
   - Share project files
   - Import community templates

7. **CLI Enhancements** - **PENDING**
   - Create `cli/layout.py` for CLI mode
   - Batch processing from command line
   - Scriptable workflows
   - Watch mode for auto-regeneration

**Deliverables:** ✨
- Optimized performance
- Advanced typography
- Interactive editing
- Template editor
- Enhanced CLI

---

## Phase 8: Documentation & Testing 📚 **0% Complete**

**Goal:** Comprehensive documentation and testing for the Layout module.

**Status:** Phase 8 is **0% complete**. Pending Phase 7.

**Last Updated:** 2025-10-27 12:30

### Tasks

1. **User Documentation** - **PENDING**
   - Update `README.md` with Layout features
   - Create `Docs/Layout_User_Guide.md`
   - Template creation guide
   - LLM integration guide
   - Export guide with examples

2. **Developer Documentation** - **PENDING**
   - Update `Docs/CodeMap.md` with layout modules
   - Architecture documentation
   - API reference
   - Extension guide (custom blocks, renderers)

3. **Example Templates** - **PENDING**
   - 10+ professional templates
   - Various categories (children's, comics, magazines)
   - Different page sizes and layouts
   - Comprehensive documentation in each template

4. **Example Projects** - **PENDING**
   - Sample children's book project
   - Sample comic project
   - Sample magazine article
   - Include source images and text

5. **Unit Tests** - **PENDING**
   - Test font manager
   - Test layout algorithms
   - Test template validation
   - Test rendering pipeline
   - Test export functions

6. **Integration Tests** - **PENDING**
   - End-to-end rendering tests
   - Template loading tests
   - LLM integration tests
   - Export format tests

7. **Manual Testing** - **PENDING**
   - GUI workflow testing
   - Cross-platform testing (Windows, macOS, Linux)
   - Performance testing with large documents
   - Font rendering on different platforms

**Deliverables:** 📚
- Complete user documentation
- Developer documentation
- Example templates and projects
- Comprehensive test suite

---

## Technical Architecture

### Directory Structure
```
ImageAI/
├── core/
│   └── layout/
│       ├── __init__.py           # Public API
│       ├── models.py             # Data classes (PageSpec, DocumentSpec, etc.)
│       ├── engine.py             # Layout and rendering engine
│       ├── font_manager.py       # Font discovery and loading
│       ├── template_manager.py   # Template discovery and validation
│       ├── llm_content.py        # LLM-powered content generation
│       └── exporters.py          # PNG, PDF, JSON exporters
├── gui/
│   └── layout/
│       ├── __init__.py
│       ├── layout_tab.py         # Main Layout tab
│       ├── template_selector.py  # Template browser widget
│       ├── canvas_widget.py      # Canvas with page preview
│       ├── inspector_widget.py   # Block properties inspector
│       ├── document_dialog.py    # Document settings dialog
│       ├── text_gen_dialog.py    # Text generation dialog
│       └── export_dialog.py      # Export settings dialog
├── cli/
│   └── layout.py                 # CLI interface for layout
├── templates/
│   └── layouts/
│       ├── children/             # Children's book templates
│       ├── comics/               # Comic templates
│       ├── magazines/            # Magazine templates
│       └── custom/               # User custom templates
├── assets/
│   └── fonts/                    # Optional font storage
└── Plans/
    ├── ImageAI_Layout_Starter/   # Original starter bundle
    └── ImageAI_Layout_Implementation_Plan.md  # This file
```

### Key Classes

```python
# core/layout/models.py
@dataclass
class TextStyle:
    family: List[str]
    weight: str = "regular"
    italic: bool = False
    size_px: int = 32
    line_height: float = 1.3
    color: str = "#111111"
    align: str = "left"
    # ... more properties

@dataclass
class ImageStyle:
    fit: str = "cover"
    border_radius_px: int = 0
    stroke_px: int = 0
    stroke_color: str = "#000000"
    # ... more properties

@dataclass
class TextBlock:
    id: str
    rect: Rect
    text: str = ""
    style: TextStyle = field(default_factory=TextStyle)

@dataclass
class ImageBlock:
    id: str
    rect: Rect
    image_path: Optional[str] = None
    style: ImageStyle = field(default_factory=ImageStyle)

@dataclass
class PageSpec:
    page_size_px: Size
    margin_px: int = 64
    bleed_px: int = 0
    background: Optional[str] = None
    blocks: List[Union[TextBlock, ImageBlock]] = field(default_factory=list)
    variables: Dict[str, str] = field(default_factory=dict)

@dataclass
class DocumentSpec:
    title: str
    author: Optional[str] = None
    pages: List[PageSpec] = field(default_factory=list)
    theme: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)
```

### Integration Points

1. **ConfigManager** (`core/config.py`)
   - Add layout settings section
   - Template directory path
   - Fonts directory path
   - Default LLM provider for text generation
   - Export quality settings

2. **LogManager** (`core/logging_config.py`)
   - Add layout logger
   - Log template operations
   - Log rendering pipeline
   - Log LLM interactions

3. **MainWindow** (`gui/main_window.py`)
   - Add Layout/Books tab after Help tab
   - Wire up to layout_tab.LayoutTab widget

4. **LiteLLM Integration** (`gui/llm_utils.py`)
   - Use existing LLMResponseParser
   - Use existing LiteLLMHandler
   - Leverage existing provider configuration

5. **Image Providers** (`providers/`)
   - Integrate with existing image generation
   - Use generated images as layout sources
   - Generate images with layout-appropriate prompts

---

## Dependencies

### New Dependencies to Add

```
# Layout rendering
Pillow>=10.0.0           # Already present
reportlab>=4.0.0         # For PDF export

# Advanced text handling
pyphen>=0.14.0           # Hyphenation
fonttools>=4.40.0        # Font introspection

# Template validation
jsonschema>=4.0.0        # JSON schema validation

# Performance
aiofiles>=23.0.0         # Async file operations (optional)
```

### Existing Dependencies to Leverage
- PySide6 (GUI)
- google-generativeai (LLM for text generation)
- openai (LLM alternative)
- litellm (LLM abstraction)

---

## Implementation Priority

### MVP (Minimum Viable Product) - Phases 1-4
- Core integration
- Basic layout engine
- Template system
- Simple GUI

**Estimated Time:** 2-3 weeks

### Production Ready - Phases 5-6
- LLM integration
- Professional export
- Advanced features

**Estimated Time:** 2-3 weeks

### Full Feature Set - Phases 7-8
- Polish and optimization
- Documentation and testing

**Estimated Time:** 1-2 weeks

**Total Estimated Time:** 5-8 weeks

---

## Success Criteria

### Phase 1-4 (MVP)
- [ ] Can load and display templates
- [ ] Can fill templates with text and images
- [ ] Can export to PNG
- [ ] Basic GUI functional

### Phase 5-6 (Production)
- [ ] LLM generates appropriate content
- [ ] PDF export is print-ready
- [ ] Multi-page documents work seamlessly

### Phase 7-8 (Complete)
- [ ] Interactive editing works smoothly
- [ ] Performance is excellent (< 2s per page render)
- [ ] Documentation is comprehensive
- [ ] Test coverage > 80%

---

## Risk Mitigation

### Technical Risks

1. **Font Rendering Inconsistencies**
   - Risk: Different platforms render fonts differently
   - Mitigation: Use Pillow with FreeType for consistent rendering
   - Fallback: Embed rendered text as images in PDF

2. **PDF Complexity**
   - Risk: ReportLab learning curve and limitations
   - Mitigation: Start with image-based PDFs, add vector text later
   - Fallback: PNG export always available

3. **Performance with Large Documents**
   - Risk: Slow rendering for 50+ page books
   - Mitigation: Async rendering, progress callbacks, caching
   - Fallback: Batch export in background

4. **LLM Reliability**
   - Risk: LLM may produce inappropriate or empty content
   - Mitigation: Use robust parsing with fallbacks (LLMResponseParser)
   - Fallback: User can always edit generated content

### UX Risks

1. **Complex UI Overwhelming Users**
   - Risk: Too many options confuse users
   - Mitigation: Progressive disclosure, sensible defaults
   - Fallback: Simple mode vs. advanced mode

2. **Template Creation Difficulty**
   - Risk: Users struggle to create custom templates
   - Mitigation: Visual template editor in Phase 7
   - Fallback: Comprehensive examples and documentation

---

## Future Enhancements (Beyond Phase 8)

1. **Animation Support**
   - Animated page transitions
   - Export to video (MP4)
   - Integration with existing video project system

2. **Collaborative Editing**
   - Real-time collaboration
   - Cloud storage integration
   - Version control

3. **AI-Powered Layout**
   - AI suggests optimal layouts for content
   - Auto-generates complete books from prompts
   - Style transfer from reference images

4. **Print Integration**
   - Direct integration with print-on-demand services
   - ISBN assignment
   - Distribution to platforms (Kindle, Apple Books)

5. **Extended Format Support**
   - ePub export for e-readers
   - Interactive HTML export
   - Augmented Reality previews

---

## Notes

- This plan builds on the excellent starter bundle in `Plans/ImageAI_Layout_Starter/`
- Integration with existing ImageAI systems is prioritized for consistency
- Modular design allows for incremental implementation
- Each phase has clear deliverables and success criteria
- Performance and user experience are key considerations throughout

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2025-10-27 | 1.0 | Initial plan created based on starter bundle |
