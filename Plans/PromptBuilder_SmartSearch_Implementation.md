# Prompt Builder Smart Search - Implementation Plan

**Project:** ImageAI
**Feature:** Intelligent Semantic Search for Prompt Builder
**Status:** 📋 PLANNING
**Created:** 2025-11-10
**Last Updated:** 2025-11-10

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

**Status:** Phase 1 is **0% complete**. Ready to start.

### Tasks

1. ⏸️ Create preset data structure - **PENDING**
   - File: `data/prompts/presets.json`
   - Schema: `{id, name, description, category, icon, settings, variations, tags, popularity}`
   - Initial presets: 5-10 for testing

2. ⏸️ Create PresetLoader class - **PENDING**
   - File: `core/preset_loader.py`
   - Methods: `get_presets()`, `save_custom_preset()`, `delete_preset()`
   - Category filtering support
   - Sort by popularity

3. ⏸️ Design preset UI layout - **PENDING**
   - Add preset panel above existing dropdowns
   - Flow layout with wrapped buttons (chips)
   - Icon + name for each preset
   - Tooltip shows description
   - Max height with scroll for many presets

4. ⏸️ Implement preset loading logic - **PENDING**
   - `_load_preset(preset: Dict)` method
   - Auto-populate all matching dropdowns
   - Visual feedback when preset loaded
   - Log preset usage

5. ⏸️ Add "Save as Preset" feature - **PENDING**
   - New button in button bar
   - Dialog: name, description, category, icon picker
   - Save current dropdown values
   - Add to preset list immediately

6. ⏸️ Curate 20-30 style presets - **PENDING**
   - Comics: MAD Magazine, Manga, Superhero, Underground
   - Photography: Portrait, Landscape, Street, Fashion
   - Fine Art: Renaissance, Impressionist, Cubist, Surrealist
   - Digital: Cyberpunk, Fantasy, Concept Art, Game Art
   - Illustration: Children's Book, Editorial, Technical
   - Vintage: 1950s Ad, Art Deco, Retro Poster

**Deliverables:** 📦
- ⏸️ `data/prompts/presets.json` with 20-30 curated presets
- ⏸️ `core/preset_loader.py` class
- ⏸️ Updated `gui/prompt_builder.py` with preset UI
- ⏸️ "Save Custom Preset" dialog
- ⏸️ User can click preset and all dropdowns auto-populate

**Acceptance Criteria:**
- [ ] User clicks "MAD Magazine" preset → Artist, Style, Mood auto-fill
- [ ] User can save current settings as custom preset
- [ ] Presets persist across sessions
- [ ] Preset panel scrolls if > 20 presets
- [ ] Works entirely offline

---

## Phase 2: Tag-Based Search ⏳ Week 2

**Goal:** Users can type "mad magazine" and see only relevant items in all dropdowns.

**Status:** Phase 2 is **0% complete**. Pending Phase 1 completion.

### Tasks

1. ⏸️ Create tag generation script - **PENDING**
   - File: `scripts/generate_tags.py`
   - Use LiteLLM with Gemini Flash (cheapest)
   - Generate tags for all 760 items
   - Progress bar with tqdm
   - Error handling and retry logic
   - Estimated cost: $0.50-$2.00 one-time

2. ⏸️ Run tag generation - **PENDING**
   - Execute: `python scripts/generate_tags.py`
   - Review sample output (first 10 items)
   - Validate tag quality
   - Save to `data/prompts/metadata.json`

3. ⏸️ Create TagSearcher class - **PENDING**
   - File: `core/tag_searcher.py`
   - Load metadata.json at init
   - `search(query, category=None)` method
   - Relevance scoring: name match (50) + tag (10) + keyword (20) + description (5)
   - Boost by popularity
   - Return top 10 per category

4. ⏸️ Add search bar UI - **PENDING**
   - QLineEdit above dropdowns
   - Placeholder: "🔍 Search artists, styles, moods... (e.g., 'Mad Magazine')"
   - Clear Filters button
   - Result count indicator

5. ⏸️ Implement search filtering - **PENDING**
   - Debouncing (300ms delay)
   - `_on_search_text_changed()` handler
   - `_perform_search(query)` method
   - `_filter_combo(combo, allowed_items)` to update dropdowns
   - Store original items for restore
   - Visual indicator: "filtered (4 of 116)"

6. ⏸️ Add clear filters functionality - **PENDING**
   - Restore all original dropdown items
   - Clear search input
   - Reset any visual indicators

**Deliverables:** 📦
- ⏸️ `scripts/generate_tags.py` tag generation script
- ⏸️ `data/prompts/metadata.json` with semantic tags for 760 items
- ⏸️ `core/tag_searcher.py` search class
- ⏸️ Search bar UI in Prompt Builder
- ⏸️ Real-time dropdown filtering

**Acceptance Criteria:**
- [ ] User types "mad magazine" → Artists show only Al Jaffee, Mort Drucker, Don Martin, Dave Berg
- [ ] User types "mad magazine" → Styles show Comic Art, Cartoon Art
- [ ] User types "mad magazine" → Moods show Satirical, Humorous
- [ ] Search results appear in <100ms
- [ ] Clear Filters restores all items
- [ ] Works offline (tags pre-generated)

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
