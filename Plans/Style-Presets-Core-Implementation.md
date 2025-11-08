# Style Presets - Core Implementation Checklist

**Goal:** Add comprehensive style presets to the Prompt Builder dialog with local import/export functionality.

**Status:** Not Started

**Last Updated:** 2025-11-08

---

## Phase 1: Data Model and Schema ⏸️

### 1.1 Create JSON Schema Definition

- [ ] Create `core/style_presets/schema.py` with preset data model
  - [ ] Define `StylePreset` dataclass with all required fields
  - [ ] Implement `Metadata` (id, name, description, author, timestamps)
  - [ ] Implement `Categorization` (category, subcategory, tags, era, region)
  - [ ] Implement `VisualMetadata` (color palette, mood, style attributes, complexity)
  - [ ] Implement `SearchMetadata` (keywords, aliases, related terms)
  - [ ] Implement `TechnicalMetadata` (compatibility, performance, constraints)
  - [ ] Implement `Parameters` (provider-specific generation params)
  - [ ] Implement `Relationships` (related styles, variations, influences)
  - [ ] Add JSON serialization/deserialization methods
  - [ ] Add schema validation

**Deliverables:**
- [ ] `core/style_presets/schema.py` - Complete data model
- [ ] Unit tests for serialization/validation

### 1.2 Create Sample Preset Data

- [ ] Create `data/style_presets/` directory structure
- [ ] Create initial 20 presets covering key categories:
  - [ ] **Historical Art** (5 presets): Impressionism, Post-Impressionism, Cubism, Surrealism, Art Deco
  - [ ] **Contemporary Digital** (5 presets): Vaporwave, Synthwave, Cyberpunk, Lo-fi, Cottagecore
  - [ ] **Cultural Traditions** (3 presets): Ukiyo-e, Aboriginal Dot Painting, Ndebele Geometric
  - [ ] **Cinematic** (4 presets): Film Noir, Wes Anderson Symmetry, Wong Kar-wai Neon, BBC Nature Documentary
  - [ ] **Artist Signatures** (3 presets): Monet, Van Gogh, Frida Kahlo
- [ ] Include cultural sensitivity guidelines for applicable presets
- [ ] Generate placeholder thumbnails (or mark as TBD)

**Deliverables:**
- [ ] 20 JSON preset files in `data/style_presets/`
- [ ] README with preset descriptions

---

## Phase 2: Preset Management System ⏸️

### 2.1 Create Preset Manager

- [ ] Create `core/style_presets/manager.py` with `StylePresetManager` class
  - [ ] Implement `load_presets()` - Load from JSON files
  - [ ] Implement `get_preset(id)` - Get single preset by ID
  - [ ] Implement `search_presets(query, filters)` - Search with filters
  - [ ] Implement `get_categories()` - Get category hierarchy
  - [ ] Implement `get_by_category(category)` - Filter by category
  - [ ] Implement `get_by_tags(tags)` - Filter by tags
  - [ ] Implement `get_related(preset_id)` - Get related presets
  - [ ] Add caching for performance
  - [ ] Add error handling for missing/corrupt files

**Deliverables:**
- [ ] `core/style_presets/manager.py` - Preset manager
- [ ] Unit tests for all operations

### 2.2 Implement Search and Filtering

- [ ] Create `core/style_presets/search.py` with search engine
  - [ ] Implement exact match search (name, slug, aliases)
  - [ ] Implement fuzzy match search (name, description, keywords)
  - [ ] Implement multi-faceted filtering:
    - [ ] By category (hierarchical)
    - [ ] By era/period
    - [ ] By mood/atmosphere
    - [ ] By color palette
    - [ ] By technical complexity
    - [ ] By media type (image/video)
    - [ ] By culture/region
    - [ ] By use case ("best for")
  - [ ] Implement autocomplete suggestions
  - [ ] Implement "related styles" recommendations

**Deliverables:**
- [ ] `core/style_presets/search.py` - Search engine
- [ ] Performance benchmarks (< 100ms for typical queries)

---

## Phase 3: Import/Export Functionality ⏸️

### 3.1 Export System

- [ ] Create `core/style_presets/export.py` with export functionality
  - [ ] Implement `export_preset(preset, format)` - Export single preset
  - [ ] Implement `export_collection(presets, format)` - Export multiple presets
  - [ ] Support export formats:
    - [ ] `complete` - Full preset with all metadata
    - [ ] `minimal` - Core parameters only
    - [ ] `parameters-only` - Just generation parameters
  - [ ] Include checksums (MD5, SHA256) for integrity
  - [ ] Add metadata (export timestamp, source application, version)
  - [ ] Generate `.stylepreset` files (JSON with .stylepreset extension)

**Deliverables:**
- [ ] `core/style_presets/export.py` - Export system
- [ ] Sample exported preset files for testing

### 3.2 Import System

- [ ] Create `core/style_presets/import.py` with import functionality
  - [ ] Implement `import_preset(file_path)` - Import single preset
  - [ ] Implement `import_collection(file_path)` - Import multiple presets
  - [ ] Validate imported presets against schema
  - [ ] Check for duplicates (by ID or name)
  - [ ] Handle merge conflicts (keep existing, replace, rename)
  - [ ] Verify checksums if present
  - [ ] Add imported presets to user's custom collection
  - [ ] Support both `.stylepreset` and `.json` files

**Deliverables:**
- [ ] `core/style_presets/import.py` - Import system
- [ ] Conflict resolution UI (if needed)
- [ ] Import validation report

---

## Phase 4: UI Integration with Prompt Builder ⏸️

### 4.1 Style Preset Browser Widget

- [ ] Create `gui/prompt_builder/style_preset_browser.py`
  - [ ] Create `StylePresetBrowserWidget` with:
    - [ ] **Left sidebar:** Category tree view
      - [ ] Hierarchical categories (Historical → Impressionism → Landscape)
      - [ ] Show preset count per category
      - [ ] Expand/collapse categories
    - [ ] **Center area:** Preset grid/list view
      - [ ] Thumbnail grid (default) with preset names
      - [ ] List view option with more details
      - [ ] Preset cards showing: name, thumbnail, tags, mood
      - [ ] Hover preview with full description
    - [ ] **Right sidebar:** Preset detail panel
      - [ ] Full metadata display
      - [ ] Color palette preview
      - [ ] Tags and keywords
      - [ ] "Apply" button to use preset
      - [ ] "Export" button to save preset
      - [ ] "Related Styles" section
    - [ ] **Top toolbar:** Search and filters
      - [ ] Search box with autocomplete
      - [ ] Filter dropdowns (mood, era, complexity, media type)
      - [ ] Sort options (alphabetical, popular, recent)
      - [ ] View toggle (grid/list)

**Deliverables:**
- [ ] `gui/prompt_builder/style_preset_browser.py` - Browser widget
- [ ] Integration with existing prompt builder dialog

### 4.2 Integrate with Prompt Builder Dialog

- [ ] Modify `gui/prompt_generation_dialog.py` to add style presets:
  - [ ] Add "Style Presets" tab or section
  - [ ] Embed `StylePresetBrowserWidget`
  - [ ] Add "Apply Style" action:
    - [ ] Append style keywords to prompt
    - [ ] Update color palette fields (if available)
    - [ ] Set recommended parameters (aspect ratio, etc.)
  - [ ] Add import/export buttons to toolbar:
    - [ ] "Import Presets" - Open file dialog for .stylepreset files
    - [ ] "Export Selected" - Export chosen preset to file
    - [ ] "Export All" - Export entire collection

**Deliverables:**
- [ ] Updated prompt builder dialog with style presets
- [ ] Seamless integration with existing prompt workflow

### 4.3 Visual Polish

- [ ] Generate or create thumbnail images for presets:
  - [ ] Use representative images for each style
  - [ ] Consistent thumbnail size (300x200px recommended)
  - [ ] Placeholder images for styles without thumbnails
- [ ] Implement color palette visualization:
  - [ ] Show dominant colors as color swatches
  - [ ] Display color hex codes on hover
- [ ] Add mood/atmosphere indicators:
  - [ ] Visual icons or badges for mood (peaceful, energetic, etc.)
  - [ ] Energy level indicator (calm/energetic)
- [ ] Style category icons:
  - [ ] Icons for Historical, Contemporary, Cultural, Cinematic, Artist

**Deliverables:**
- [ ] Thumbnail library or placeholder system
- [ ] Polished visual design matching ImageAI style

---

## Phase 5: Preset Application Logic ⏸️

### 5.1 Prompt Enhancement with Presets

- [ ] Create `core/style_presets/application.py` with preset application logic
  - [ ] Implement `apply_preset_to_prompt(prompt, preset, mode)`
    - [ ] **Mode: Append** - Add style keywords to end of prompt
    - [ ] **Mode: Prepend** - Add style keywords to beginning
    - [ ] **Mode: Replace** - Use preset as base, incorporate user's subject
  - [ ] Implement keyword integration:
    - [ ] Extract primary keywords from preset
    - [ ] Format as comma-separated additions
    - [ ] Avoid duplicate keywords
  - [ ] Implement parameter suggestions:
    - [ ] Extract recommended parameters (aspect ratio, etc.)
    - [ ] Return as dict for GUI to apply

**Deliverables:**
- [ ] `core/style_presets/application.py` - Application logic
- [ ] Unit tests for prompt integration

### 5.2 Provider Compatibility

- [ ] Implement provider-specific parameter mapping:
  - [ ] Map preset parameters to Google Gemini format
  - [ ] Map preset parameters to OpenAI DALL-E format
  - [ ] Handle unsupported parameters gracefully
  - [ ] Show warnings for incompatible settings
- [ ] Add compatibility indicators in UI:
  - [ ] Show which providers support each preset
  - [ ] Display limitations/warnings
  - [ ] Suggest alternatives if current provider incompatible

**Deliverables:**
- [ ] Provider compatibility mapping
- [ ] UI indicators for compatibility

---

## Phase 6: User Custom Presets ⏸️

### 6.1 Custom Preset Creation

- [ ] Create "New Preset" dialog:
  - [ ] Form for basic metadata (name, description, category)
  - [ ] Tag editor (add/remove tags)
  - [ ] Color palette picker
  - [ ] Mood/atmosphere selectors
  - [ ] "Save from Current" - Capture current prompt/settings as preset
  - [ ] Preview thumbnail upload
- [ ] Store custom presets separately:
  - [ ] User presets in `~/.config/ImageAI/custom_presets/`
  - [ ] Keep official presets read-only in `data/style_presets/`
  - [ ] Merge both collections in preset browser

**Deliverables:**
- [ ] Custom preset creation dialog
- [ ] User preset storage system

### 6.2 Custom Preset Management

- [ ] Add preset management features:
  - [ ] Edit existing custom presets
  - [ ] Delete custom presets (with confirmation)
  - [ ] Duplicate preset (fork/clone)
  - [ ] Reset to defaults (restore official presets)
- [ ] Add preset organization:
  - [ ] Create custom categories
  - [ ] Add to favorites
  - [ ] Recently used presets

**Deliverables:**
- [ ] Preset management UI
- [ ] Preset organization features

---

## Phase 7: Documentation and Testing ⏸️

### 7.1 User Documentation

- [ ] Add "Style Presets" section to README:
  - [ ] Explanation of style presets feature
  - [ ] How to browse and apply presets
  - [ ] How to create custom presets
  - [ ] Import/export instructions
  - [ ] Manual sharing workflow
- [ ] Create preset catalog document:
  - [ ] List all 65+ official presets
  - [ ] Descriptions and example use cases
  - [ ] Cultural sensitivity notes

**Deliverables:**
- [ ] Updated README with style presets documentation
- [ ] Preset catalog reference

### 7.2 Testing

- [ ] Unit tests:
  - [ ] Schema validation tests
  - [ ] Preset manager tests
  - [ ] Search/filter tests
  - [ ] Import/export tests
  - [ ] Prompt application tests
- [ ] Integration tests:
  - [ ] UI workflow tests
  - [ ] Provider compatibility tests
  - [ ] File I/O tests
- [ ] Manual testing:
  - [ ] Browse all presets
  - [ ] Apply presets to various prompts
  - [ ] Create custom presets
  - [ ] Import/export presets
  - [ ] Test with different providers

**Deliverables:**
- [ ] Comprehensive test suite
- [ ] Test coverage report

---

## Success Metrics

- [ ] **Coverage:** At least 50 official presets spanning all categories
- [ ] **Performance:** Search/filter operations < 100ms
- [ ] **Usability:** Users can find and apply presets in < 30 seconds
- [ ] **Compatibility:** Works with all supported providers (Google, OpenAI)
- [ ] **Portability:** Import/export works reliably for manual sharing

---

## Future Enhancements (Post-Phase 7)

These features are deferred to future versions:

- Visual similarity search (CLIP embeddings)
- Semantic search with embeddings
- Preset recommendations based on history
- Thumbnail generation from preset parameters
- Style mixing (combine multiple presets)
- Preset versioning and updates
- Community features (see separate checklist)
