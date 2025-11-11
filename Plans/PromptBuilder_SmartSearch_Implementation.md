# Prompt Builder Smart Search - Implementation Plan

**Project:** ImageAI
**Feature:** Intelligent Semantic Search for Prompt Builder
**Status:** 🚀 READY - Phase 1 Complete ✅ | Phase 2 Complete ✅
**Created:** 2025-11-10
**Last Updated:** 2025-11-11 (Phase 2 completed)

---

## Executive Summary

Transform the Prompt Builder from a simple dropdown tool into an intelligent discovery system that helps users find relevant artists, styles, and moods using high-level concepts like "Mad Magazine" or "1960s Psychedelic."

**Approach:** Hybrid Preset + Tag Search + Optional LLM
**Timeline:** 2-3 weeks (65-95 hours)
**Cost:** $0.50-$2.00 (one-time tag generation)
**Priority:** High - Significantly improves user experience

---

## Problem Statement

Current Prompt Builder (`gui/prompt_builder.py`) has **760 items** across 6 categories:
- 117 artists (Al Jaffee, Mort Drucker, Don Martin, etc.)
- 114 art styles (Comic Art, Cartoon Art, Pop Art, etc.)
- 202 mediums
- 90 colors
- 78 lighting options
- 228 moods

**Pain Points:**
1. Users don't know which artists work together
2. No way to search by concept ("Mad Magazine style")
3. Hard to discover related options across categories
4. Overwhelming number of choices without guidance

---

## Solution Overview

### Three-Phase Progressive Enhancement

**Phase 1: Preset System** ⏱️ Week 1 (30-40h)
- Add 20-30 curated style presets (e.g., "MAD Magazine Style", "Cyberpunk Neon")
- Click preset → auto-populate all relevant dropdowns
- Save custom presets for personal workflow
- **Works without internet or LLM**

**Phase 2: Tag-Based Search** ⏱️ Week 2 (20-30h)
- One-time LLM pass to generate semantic tags for all 760 items
- Smart search bar filters dropdowns in real-time
- Type "mad magazine" → shows only relevant artists, styles, moods
- **Fast (<100ms), works offline after tag generation**

**Phase 3: Optional LLM Enhancement** ⏱️ Week 3 (15-25h)
- Settings toggle for "AI-Powered Smart Search"
- Handle complex queries: "moody cyberpunk with neon but not too dark"
- Query caching for performance
- **Optional power-user feature**

---

## Detailed Implementation Plan

## Phase 1: Preset System ✅ Week 1

**Goal:** Users can click pre-made style combinations instead of manually selecting dropdowns.

**Status:** Phase 1 is **100% complete** ✅ (Completed: 2025-11-10)

### Tasks

1. ✅ Create preset data structure - **COMPLETED** (gui/prompt_builder.py:1045)
   - File: `data/prompts/presets.json` (25 presets)
   - Schema: `{id, name, description, category, icon, settings, variations, tags, popularity}`
   - Created 8 initial test presets, expanded to 25 production-ready

2. ✅ Create PresetLoader class - **COMPLETED** (core/preset_loader.py:1-436)
   - File: `core/preset_loader.py` (436 lines)
   - Methods: `get_presets()`, `save_custom_preset()`, `delete_preset()`, `get_categories()`, `get_preset_by_id()`
   - Category filtering support ✓
   - Sort by popularity ✓
   - Export/import functionality ✓

3. ✅ Design preset UI layout - **COMPLETED** (gui/prompt_builder.py:637-711)
   - Added preset panel above existing dropdowns ✓
   - FlowLayout with wrapped buttons (gui/flow_layout.py:1-169)
   - Icon + name for each preset ✓
   - Tooltip shows description ✓
   - Scrollable area with max height 150px ✓

4. ✅ Implement preset loading logic - **COMPLETED** (gui/prompt_builder.py:713-745)
   - `_load_preset(preset: Dict)` method ✓
   - `_on_preset_clicked()` handler ✓
   - Auto-populate all matching dropdowns ✓
   - Uses existing `_apply_settings()` method ✓
   - Log preset usage ✓

5. ✅ Add "Save as Preset" feature - **COMPLETED** (gui/prompt_builder.py:26-171, 895-958)
   - SavePresetDialog class with full UI (gui/prompt_builder.py:26-171)
   - Dialog fields: name, description, category, icon picker, tags ✓
   - Save current dropdown values ✓
   - Persists to custom_presets.json ✓
   - User feedback on success/failure ✓

6. ✅ Curate 25 production-ready style presets - **COMPLETED** (data/prompts/presets.json)
   - Comics (5): MAD Magazine, Manga Action, Superhero, Underground, ✓
   - Photography (5): Portrait, Street, Fashion, Film Noir ✓
   - Fine Art (6): Renaissance, Impressionist, Cubist, Surrealist, Expressionist ✓
   - Digital (5): Cyberpunk, Fantasy, Stylized Game, Cinematic Concept ✓
   - Illustration (3): Children's Book, Editorial, Technical ✓
   - Vintage (3): 1950s Ad, Art Deco, Retro Poster ✓
   - Modern (1): Pop Art Portrait ✓
   - Anime (1): Anime Character ✓

**Deliverables:** 📦
- ✅ `data/prompts/presets.json` with 25 curated presets
- ✅ `core/preset_loader.py` class (436 lines)
- ✅ `gui/flow_layout.py` helper widget (169 lines)
- ✅ Updated `gui/prompt_builder.py` with preset UI (+325 lines)
- ✅ "Save Custom Preset" dialog (SavePresetDialog class)
- ✅ User can click preset and all dropdowns auto-populate

**Acceptance Criteria:**
- [✓] User clicks "MAD Magazine" preset → Artist, Style, Mood auto-fill
- [✓] User can save current settings as custom preset
- [✓] Presets persist across sessions (custom_presets.json)
- [✓] Preset panel scrolls if > 20 presets (max height: 150px)
- [✓] Works entirely offline (no external dependencies)

---

## Phase 2: Tag-Based Search ✅ Week 2

**Goal:** Users can type "mad magazine" and see only relevant items in all dropdowns.

**Status:** Phase 2 is **100% complete** ✅ (Completed: 2025-11-11)

**Last Updated:** 2025-11-11 (Phase 2 completed)

### Tasks

1. ✅ Create tag generation script - **COMPLETED** (scripts/generate_tags.py:1-605)
   - File: `scripts/generate_tags.py` (605 lines) ✓
   - Uses LiteLLM with Gemini 1.5 Flash or OpenAI (stable, good quotas) ✓
   - Generates comprehensive metadata: tags, related items, descriptions, era, popularity ✓
   - Progress bar with tqdm ✓
   - Error handling and retry logic (3 attempts) ✓
   - Exponential backoff for rate limit errors (5s, 10s, 20s) ✓
   - Fallback metadata for failed items ✓
   - Command-line options: --test, --limit, --provider, --model ✓
   - **Authentication**: Supports both API key and gcloud auth (auto-detects from main app config) ✓
   - **Smart endpoint selection**: Uses Vertex AI for gcloud auth, Gemini API for API keys ✓
   - **Project ID support**: Auto-detects and uses Google Cloud project ID for Vertex AI ✓
   - **Resume capability**: Automatically skips already-processed items, can be run multiple times ✓
   - **Logging**: Saves timestamped log to current directory, persists even on Ctrl+C abort ✓
   - **Interrupt handling**: Graceful shutdown with progress saved, resume on next run ✓
   - Rate limiting: 1.5s delay between requests (~40/min, safe for free tier) ✓
   - Estimated cost: $0.50-$2.00 one-time

2. ✅ Run tag generation - **COMPLETED**
   - Executed: `python scripts/generate_tags.py` ✓
   - Generated metadata for 740 items (Artists: 116, Styles: 113, Mediums: 200, Lighting: 77, Moods: 214) ✓
   - Validated tag quality ✓
   - Saved to `data/prompts/metadata.json` (19,757 lines) ✓

3. ✅ Create TagSearcher class - **COMPLETED** (core/tag_searcher.py:1-437)
   - File: `core/tag_searcher.py` (437 lines) ✓
   - Load metadata.json at init ✓
   - `search(query, category=None, max_results=10)` method ✓
   - `search_by_category(query, max_per_category=10)` method for multi-category search ✓
   - Relevance scoring implemented:
     - Exact name match: 100 points
     - Partial name match: 50 points
     - Tag match: 20 points (partial: 15, term: 10)
     - Keyword match: 15 points (term: 10)
     - Description match: 10 points (term: 5)
     - Related items: 5 points
     - Era match: 8 points
     - Popularity boost: 0-10 points
   - Returns SearchResult dataclass with item, category, score, matched_on ✓
   - Helper methods: `get_related_items()`, `get_item_tags()`, `get_all_tags()` ✓

4. ✅ Add search bar UI - **COMPLETED** (gui/prompt_builder.py:860-911)
   - Added `_create_search_panel()` method ✓
   - QLineEdit with placeholder: "Search artists, styles, moods... (e.g., 'Mad Magazine', 'cyberpunk', '1960s')" ✓
   - Clear Filters button with enable/disable state ✓
   - Result count indicator label ✓
   - Search panel inserted between presets and instructions ✓

5. ✅ Implement search filtering - **COMPLETED** (gui/prompt_builder.py:1323-1416)
   - No debouncing (instant search, fast enough <100ms) ✓
   - `_on_search_text_changed()` handler ✓
   - `_perform_search(query)` method ✓
   - Filters all relevant combos (artists, styles, mediums, lighting, moods) ✓
   - `_save_combo_items()` stores original items for restoration ✓
   - Visual indicator: "✓ Found 43 items: Artists (14), Styles (2), Moods (5), etc." ✓

6. ✅ Add clear filters functionality - **COMPLETED** (gui/prompt_builder.py:1418-1462)
   - `_clear_search_filters()` method ✓
   - Restores all original dropdown items ✓
   - Clears search input ✓
   - Resets result indicator label ✓
   - Preserves current selections when possible ✓

**Deliverables:** 📦
- ✅ `scripts/generate_tags.py` tag generation script (605 lines)
- ✅ `data/prompts/metadata.json` with semantic tags for 740 items (19,757 lines)
- ✅ `core/tag_searcher.py` search class (437 lines)
- ✅ Search bar UI in Prompt Builder (gui/prompt_builder.py:860-911)
- ✅ Real-time dropdown filtering (gui/prompt_builder.py:1305-1462)

**Acceptance Criteria:**
- [✓] User types "mad magazine" → Artists show Mort Drucker, Don Martin, Dave Berg, and 11 other MAD artists
- [✓] User types "cyberpunk" → Styles show Cyberpunk (exact match, score: 118)
- [✓] User types "cyberpunk" → Shows relevant artists (Katsuhiro Otomo, etc.)
- [✓] Search results appear in <100ms (instant, no debouncing needed)
- [✓] Clear Filters restores all items and clears search
- [✓] Works offline (tags pre-generated, no LLM calls during search)

---

## Phase 3: Optional LLM Enhancement 🚀 Week 3

**Goal:** Power users can enable real-time LLM queries for complex searches.

**Status:** Phase 3 is **0% complete**. Optional feature.

### Tasks

1. ⏸️ Add Smart Search settings toggle - **PENDING**
   - Checkbox to "Enable AI-Powered Smart Search (requires API key)"
   - Tooltip explains benefits and requirements
   - Select provider/model 
   
2. ⏸️ Implement LLM search function - **PENDING**
   - File: `core/llm_searcher.py`
   - `llm_search(query, timeout=2.0)` method
   - Build prompt with all 760 items
   - Use Gemini Flash for cost (~$0.002 per query)
   - Parse JSON response
   - Error handling

3. ⏸️ Create search cache system - **PENDING**
   - File: `core/search_cache.py`
   - SQLite or JSON storage
   - `get(query)` and `set(query, results)`
   - TTL: 30 days
   - Pre-populate common queries

4. ⏸️ Implement fallback hierarchy - **PENDING**
   - `search_with_fallback(query)` function
   - Try: LLM (if enabled) → Cached tags → Fuzzy match → Substring
   - Log which method succeeded
   - Graceful degradation

5. ⏸️ Add loading indicators - **PENDING**
   - Show spinner for LLM queries >300ms
   - Status message: "Searching with AI..."
   - Cancel button for long queries

6. ⏸️ Testing and refinement - **PENDING**
   - Test complex queries
   - Measure latency
   - Validate fallback behavior
   - User feedback

**Deliverables:** 📦
- ⏸️ `core/llm_searcher.py` LLM integration
- ⏸️ `core/search_cache.py` caching system
- ⏸️ Settings toggle for Smart Search
- ⏸️ Fallback hierarchy implementation
- ⏸️ Loading indicators

**Acceptance Criteria:**
- [ ] User enables Smart Search in settings
- [ ] Complex query "moody cyberpunk with neon but not too dark" returns relevant items
- [ ] LLM queries cached for 30 days
- [ ] Fallback to tag search if LLM fails
- [ ] Loading indicator for queries >300ms
- [ ] Works without API key (falls back to tags)

---

## Technical Details

### File Structure

```
ImageAI/
├── gui/
│   └── prompt_builder.py         # Add preset UI, search bar, filtering
├── core/
│   ├── preset_loader.py          # NEW: Load/save presets
│   ├── tag_searcher.py           # NEW: Tag-based search
│   ├── llm_searcher.py           # NEW: LLM-powered search (Phase 3)
│   └── search_cache.py           # NEW: Cache search results (Phase 3)
├── data/
│   └── prompts/
│       ├── presets.json          # NEW: Curated style presets
│       └── metadata.json         # NEW: Semantic tags for 760 items
└── scripts/
    └── generate_tags.py          # NEW: One-time tag generation
```

### Preset Schema

```json
{
  "presets": [
    {
      "id": "mad_magazine",
      "name": "MAD Magazine Style",
      "description": "Classic satirical comic art from MAD Magazine",
      "category": "Comics",
      "icon": "🎭",
      "settings": {
        "artist": "Al Jaffee",
        "transformation": "as caricature",
        "style": "Comic Art",
        "medium": "Ink",
        "mood": "Satirical",
        "technique": "use line work and cross-hatching"
      },
      "variations": [
        {"artist": "Mort Drucker", "description": "Movie parody style"},
        {"artist": "Don Martin", "description": "Visual gag style"}
      ],
      "tags": ["comics", "satire", "vintage", "1960s"],
      "popularity": 8
    }
  ]
}
```

### Metadata Schema

```json
{
  "artists": {
    "Al Jaffee": {
      "tags": ["mad_magazine", "caricature", "satire", "1960s", "comics"],
      "related_styles": ["Comic Art", "Cartoon Art"],
      "related_moods": ["Satirical", "Humorous"],
      "cultural_keywords": ["MAD Magazine", "fold-in", "satirical cartoons"],
      "description": "Legendary MAD Magazine cartoonist",
      "era": "1960s-2010s",
      "popularity": 9
    }
  }
}
```

---

## UI Mockup

```
┌────────────────────────────────────────────────────┐
│ Prompt Builder                              [X]    │
├────────────────────────────────────────────────────┤
│                                                     │
│ 🎨 Style Presets: Quick-start combinations         │
│ ┌────────────────────────────────────────────────┐ │
│ │ [🎭 MAD Magazine] [🌃 Cyberpunk] [🖼️ Renaissance]│ │
│ │ [📸 Film Noir] [🌸 Anime] [+ Custom Preset]    │ │
│ └────────────────────────────────────────────────┘ │
│                                                     │
│ 🔍 Search: [mad magazine___] [Clear Filters]       │
│    Found 7 items: Artists (4), Styles (2), Moods (1)│
│                                                     │
│ Subject:      [Headshot of attached              ▼]│
│ Transform:    [as caricature                     ▼]│
│ Art Style:    [Comic Art                         ▼]│
│               ^filtered (2 of 114 items)            │
│ Artist:       [Al Jaffee                         ▼]│
│               ^filtered (4 of 117 items)            │
│ Mood:         [Satirical                         ▼]│
│               ^filtered (1 of 228 items)            │
│                                                     │
│ Preview: Headshot of attached, as caricature,      │
│ in Comic Art style, in the style of Al Jaffee...   │
│                                                     │
│     [Load Example] [Clear] [Save Preset] [Use]     │
└────────────────────────────────────────────────────┘
```

---

## Success Metrics

**Usability:**
- 80% of users find relevant artists within 3 clicks
- 60%+ users try at least one preset
- Average time to build prompt: <30 seconds (vs. 2+ minutes)

**Performance:**
- Tag-based search: <100ms response time
- LLM search (cached): <100ms response time
- LLM search (uncached): <2000ms response time
- Preset load: <10ms

**Adoption:**
- Preset usage: 60%+ of sessions
- Search usage: 40%+ of sessions
- Custom preset creation: 10%+ of users

---

## Risk Assessment

**Low Risk:**
- Backward compatible (existing dropdowns still work)
- Progressive enhancement (works without LLM)
- Graceful degradation (fallback to tags if LLM fails)
- No breaking changes

**Risks & Mitigations:**
- **Risk:** Tag quality may be poor → **Mitigation:** Manual validation of top 30 items
- **Risk:** LLM costs add up → **Mitigation:** Aggressive caching, optional feature
- **Risk:** Users confused by presets → **Mitigation:** Tooltips, clear descriptions
- **Risk:** Search performance slow → **Mitigation:** Debouncing, client-side filtering

---

## Dependencies

**Phase 1:**
- None (pure Python/Qt)

**Phase 2:**
- LiteLLM (already installed)
- Gemini API key for tag generation (one-time)

**Phase 3:**
- LiteLLM
- User API key for real-time search

---

## Testing Plan

**Phase 1 Tests:**
- [ ] Preset loads all matching fields correctly
- [ ] Custom preset saves and persists
- [ ] Preset panel scrolls with many items
- [ ] Preset tooltips show descriptions

**Phase 2 Tests:**
- [ ] "mad magazine" finds Al Jaffee, Mort Drucker, Don Martin
- [ ] "cyberpunk" finds relevant styles, moods, lighting
- [ ] Search responds in <100ms
- [ ] Clear filters restores all items
- [ ] Works offline

**Phase 3 Tests:**
- [ ] LLM query returns relevant results
- [ ] Cache works (second query is instant)
- [ ] Fallback to tags when LLM fails
- [ ] Loading indicator shows for slow queries
- [ ] Works without API key (falls back)

---

## Related Files

- **Research:** `/mnt/d/Documents/Code/GitHub/ImageAI/Notes/PromptBuilder_SemanticSearch_Research.md`
- **Code Map:** `/mnt/d/Documents/Code/GitHub/ImageAI/Docs/CodeMap.md` (line refs for prompt_builder.py)
- **Existing Implementation:** `gui/prompt_builder.py:24-914`
- **Data Loader:** `core/prompt_data_loader.py:11-151`

---

## Next Steps

1. **Review this plan** with team/stakeholders
2. **Start Phase 1** - Implement preset system
3. **User testing** after Phase 1 - Get feedback on preset UX
4. **Generate tags** - Run one-time LLM pass for Phase 2
5. **Iterate** - Add Phase 2 and 3 based on feedback

---

**Status Legend:**
- ⏸️ Pending
- ⏳ In Progress
- ✅ Completed
- ❌ Blocked
- 🚀 Ready for Release

**Last Updated:** 2025-11-10
