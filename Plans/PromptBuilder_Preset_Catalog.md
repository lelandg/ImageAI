# Prompt Builder Preset Catalog

**Project:** ImageAI
**Purpose:** Curated collection of style presets for various creative fields
**Status:** 📋 DRAFT CATALOG
**Created:** 2025-11-10

---

## Overview

This document catalogs 30+ style presets spanning comics, photography, fine art, digital art, illustration, and vintage aesthetics. Each preset is designed to appeal to different creative fields and interests.

**Goal:** Enable users to quickly discover and apply professionally curated style combinations without deep knowledge of art history or specific artist names.

---

## Preset Categories

### 📚 Comics & Sequential Art (6 presets)

#### 1. MAD Magazine Style 🎭
```json
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
    "background": "on a clean white background",
    "pose": "facing forward",
    "technique": "use line work and cross-hatching",
    "mood": "Satirical"
  },
  "variations": [
    {"artist": "Mort Drucker", "description": "Movie parody style"},
    {"artist": "Don Martin", "description": "Visual gag style"},
    {"artist": "Dave Berg", "description": "Everyday life satire"},
    {"artist": "Sergio Aragonés", "description": "Dense visual humor"}
  ],
  "tags": ["comics", "satire", "vintage", "1960s", "humor"],
  "popularity": 8
}
```

#### 2. Modern Manga 🌸
```json
{
  "id": "modern_manga",
  "name": "Modern Manga",
  "description": "Contemporary Japanese manga/anime art style",
  "category": "Comics",
  "icon": "🌸",
  "settings": {
    "artist": "Hayao Miyazaki",
    "style": "Anime",
    "medium": "Digital Art",
    "background": "with gradient background",
    "lighting": "Soft lighting",
    "mood": "Dreamy"
  },
  "tags": ["anime", "manga", "japanese", "modern"],
  "popularity": 10
}
```

#### 3. Classic Superhero 🦸
```json
{
  "id": "classic_superhero",
  "name": "Classic Superhero",
  "description": "Golden Age comic book superhero style",
  "category": "Comics",
  "icon": "🦸",
  "settings": {
    "style": "Comic Art",
    "medium": "Ink",
    "background": "with abstract background",
    "pose": "dynamic pose",
    "technique": "with bold outlines",
    "lighting": "Dramatic lighting",
    "mood": "Heroic"
  },
  "tags": ["superhero", "comics", "action", "vintage"],
  "popularity": 9
}
```

#### 4. Underground Comix 🌀
```json
{
  "id": "underground_comix",
  "name": "Underground Comix",
  "description": "1960s-70s counterculture comic art",
  "category": "Comics",
  "icon": "🌀",
  "settings": {
    "artist": "Robert Crumb",
    "style": "Comic Art",
    "medium": "Ink",
    "technique": "with bold outlines",
    "mood": "Psychedelic"
  },
  "tags": ["underground", "psychedelic", "counterculture", "1960s"],
  "popularity": 6
}
```

#### 5. Graphic Novel Noir 🌙
```json
{
  "id": "graphic_novel_noir",
  "name": "Graphic Novel Noir",
  "description": "Dark, moody graphic novel aesthetic",
  "category": "Comics",
  "icon": "🌙",
  "settings": {
    "style": "Comic Art",
    "medium": "Ink",
    "background": "on a solid black background",
    "lighting": "Chiaroscuro lighting",
    "technique": "with bold outlines",
    "mood": "Dark"
  },
  "tags": ["noir", "dark", "graphic_novel", "moody"],
  "popularity": 7
}
```

#### 6. Webcomic Casual 💻
```json
{
  "id": "webcomic_casual",
  "name": "Webcomic Casual",
  "description": "Modern simplified webcomic style",
  "category": "Comics",
  "icon": "💻",
  "settings": {
    "style": "Cartoon Art",
    "medium": "Digital Art",
    "technique": "minimalist",
    "mood": "Playful"
  },
  "tags": ["webcomic", "modern", "simple", "casual"],
  "popularity": 8
}
```

---

### 📸 Photography & Realism (6 presets)

#### 7. Classic Portrait 👤
```json
{
  "id": "classic_portrait",
  "name": "Classic Portrait",
  "description": "Professional studio portrait photography",
  "category": "Photography",
  "icon": "👤",
  "settings": {
    "transformation": "as realistic portrait",
    "style": "Photorealism",
    "background": "with studio lighting background",
    "pose": "three-quarter view",
    "lighting": "Soft lighting",
    "technique": "photorealistic"
  },
  "tags": ["portrait", "photography", "professional", "realistic"],
  "popularity": 9
}
```

#### 8. Film Noir 🎬
```json
{
  "id": "film_noir",
  "name": "Film Noir",
  "description": "High-contrast black and white cinematic style",
  "category": "Photography",
  "icon": "🎬",
  "settings": {
    "style": "Cinematic Art",
    "medium": "Black and White Photography",
    "background": "in urban setting",
    "lighting": "Chiaroscuro lighting",
    "mood": "Dark"
  },
  "tags": ["noir", "cinematic", "vintage", "dramatic"],
  "popularity": 8
}
```

#### 9. Golden Hour Portrait 🌅
```json
{
  "id": "golden_hour",
  "name": "Golden Hour Portrait",
  "description": "Warm sunset/sunrise natural lighting",
  "category": "Photography",
  "icon": "🌅",
  "settings": {
    "style": "Photorealism",
    "background": "in natural setting",
    "lighting": "Golden hour lighting",
    "mood": "Warm"
  },
  "tags": ["golden_hour", "natural", "warm", "sunset"],
  "popularity": 9
}
```

#### 10. Street Photography 🏙️
```json
{
  "id": "street_photography",
  "name": "Street Photography",
  "description": "Candid urban documentary style",
  "category": "Photography",
  "icon": "🏙️",
  "settings": {
    "style": "Photorealism",
    "background": "in urban setting",
    "lighting": "Natural light",
    "mood": "Gritty"
  },
  "tags": ["street", "documentary", "urban", "candid"],
  "popularity": 7
}
```

#### 11. Fashion Editorial 💃
```json
{
  "id": "fashion_editorial",
  "name": "Fashion Editorial",
  "description": "High-fashion magazine photography",
  "category": "Photography",
  "icon": "💃",
  "settings": {
    "style": "Photorealism",
    "background": "with studio lighting background",
    "pose": "dynamic pose",
    "lighting": "Studio lighting",
    "technique": "photorealistic",
    "mood": "Glamorous"
  },
  "tags": ["fashion", "editorial", "glamour", "magazine"],
  "popularity": 8
}
```

#### 12. Product Photography 📦
```json
{
  "id": "product_photo",
  "name": "Product Photography",
  "description": "Clean commercial product shot",
  "category": "Photography",
  "icon": "📦",
  "settings": {
    "style": "Photorealism",
    "background": "on a clean white background",
    "lighting": "Studio lighting",
    "technique": "photorealistic"
  },
  "tags": ["product", "commercial", "clean", "minimal"],
  "popularity": 7
}
```

---

### 🎨 Fine Art & Classical (5 presets)

#### 13. Renaissance Portrait 🖼️
```json
{
  "id": "renaissance_portrait",
  "name": "Renaissance Portrait",
  "description": "Classical oil painting in Renaissance style",
  "category": "Fine Art",
  "icon": "🖼️",
  "settings": {
    "artist": "Leonardo da Vinci",
    "style": "Renaissance",
    "medium": "Oil Painting",
    "lighting": "Chiaroscuro lighting",
    "technique": "with soft shading"
  },
  "tags": ["classical", "renaissance", "oil", "historical"],
  "popularity": 7
}
```

#### 14. Impressionist Landscape 🌊
```json
{
  "id": "impressionist",
  "name": "Impressionist Landscape",
  "description": "Soft, light-focused Impressionist painting",
  "category": "Fine Art",
  "icon": "🌊",
  "settings": {
    "artist": "Claude Monet",
    "style": "Impressionism",
    "medium": "Oil Painting",
    "lighting": "Natural light",
    "mood": "Serene"
  },
  "tags": ["impressionism", "landscape", "classical", "soft"],
  "popularity": 8
}
```

#### 15. Cubist Abstract 🔲
```json
{
  "id": "cubist",
  "name": "Cubist Abstract",
  "description": "Geometric fragmented Cubist style",
  "category": "Fine Art",
  "icon": "🔲",
  "settings": {
    "artist": "Pablo Picasso",
    "style": "Cubism",
    "medium": "Oil Painting",
    "mood": "Abstract"
  },
  "tags": ["cubism", "abstract", "geometric", "modern"],
  "popularity": 6
}
```

#### 16. Surrealist Dream 🌀
```json
{
  "id": "surrealist",
  "name": "Surrealist Dream",
  "description": "Dreamlike surrealist composition",
  "category": "Fine Art",
  "icon": "🌀",
  "settings": {
    "artist": "Salvador Dalí",
    "style": "Surrealism",
    "medium": "Oil Painting",
    "lighting": "Dramatic lighting",
    "mood": "Dreamy"
  },
  "tags": ["surrealism", "dreamlike", "bizarre", "fantasy"],
  "popularity": 8
}
```

#### 17. Pop Art Bold 💥
```json
{
  "id": "pop_art",
  "name": "Pop Art Bold",
  "description": "Vibrant Pop Art style with bold colors",
  "category": "Fine Art",
  "icon": "💥",
  "settings": {
    "artist": "Roy Lichtenstein",
    "style": "Pop Art",
    "medium": "Screen Print",
    "technique": "with bold outlines",
    "mood": "Energetic"
  },
  "tags": ["pop_art", "bold", "colorful", "1960s"],
  "popularity": 9
}
```

---

### 🌃 Digital Art & Sci-Fi (5 presets)

#### 18. Cyberpunk Neon 🌃
```json
{
  "id": "cyberpunk_neon",
  "name": "Cyberpunk Neon",
  "description": "Futuristic sci-fi with neon lighting",
  "category": "Sci-Fi",
  "icon": "🌃",
  "settings": {
    "style": "Cyberpunk",
    "medium": "Digital Art",
    "background": "in urban setting",
    "lighting": "Neon lighting",
    "mood": "Moody",
    "technique": "photorealistic"
  },
  "tags": ["scifi", "cyberpunk", "neon", "futuristic"],
  "popularity": 10
}
```

#### 19. Fantasy Concept Art 🐉
```json
{
  "id": "fantasy_concept",
  "name": "Fantasy Concept Art",
  "description": "Epic fantasy game/film concept art",
  "category": "Digital",
  "icon": "🐉",
  "settings": {
    "artist": "Frank Frazetta",
    "style": "Fantasy",
    "medium": "Digital Art",
    "lighting": "Dramatic lighting",
    "technique": "photorealistic",
    "mood": "Epic"
  },
  "tags": ["fantasy", "concept_art", "epic", "game"],
  "popularity": 9
}
```

#### 20. Vaporwave Aesthetic 🌴
```json
{
  "id": "vaporwave",
  "name": "Vaporwave Aesthetic",
  "description": "Retro-futuristic vaporwave style",
  "category": "Digital",
  "icon": "🌴",
  "settings": {
    "style": "Vaporwave",
    "medium": "Digital Art",
    "lighting": "Neon lighting",
    "mood": "Nostalgic"
  },
  "tags": ["vaporwave", "aesthetic", "retro", "pastel"],
  "popularity": 7
}
```

#### 21. Pixel Art Retro 🕹️
```json
{
  "id": "pixel_art",
  "name": "Pixel Art Retro",
  "description": "8-bit/16-bit retro game art",
  "category": "Digital",
  "icon": "🕹️",
  "settings": {
    "style": "Video Game Art",
    "medium": "Digital Art",
    "technique": "minimalist",
    "mood": "Nostalgic"
  },
  "tags": ["pixel", "retro", "8bit", "gaming"],
  "popularity": 8
}
```

#### 22. Studio Ghibli 🌳
```json
{
  "id": "studio_ghibli",
  "name": "Studio Ghibli",
  "description": "Whimsical Ghibli animation style",
  "category": "Digital",
  "icon": "🌳",
  "settings": {
    "artist": "Studio Ghibli",
    "style": "Anime",
    "medium": "Watercolor painting",
    "lighting": "Soft lighting",
    "mood": "Whimsical"
  },
  "tags": ["ghibli", "anime", "whimsical", "japanese"],
  "popularity": 10
}
```

---

### ✏️ Illustration (4 presets)

#### 23. Children's Book 📚
```json
{
  "id": "childrens_book",
  "name": "Children's Book",
  "description": "Friendly, colorful children's illustration",
  "category": "Illustration",
  "icon": "📚",
  "settings": {
    "style": "Cartoon Art",
    "medium": "Watercolor painting",
    "technique": "with soft shading",
    "mood": "Playful"
  },
  "tags": ["childrens", "friendly", "colorful", "book"],
  "popularity": 8
}
```

#### 24. Editorial Illustration 📰
```json
{
  "id": "editorial",
  "name": "Editorial Illustration",
  "description": "Sophisticated magazine/newspaper art",
  "category": "Illustration",
  "icon": "📰",
  "settings": {
    "style": "Contemporary Art",
    "medium": "Digital Art",
    "technique": "stylized",
    "mood": "Sophisticated"
  },
  "tags": ["editorial", "magazine", "sophisticated", "modern"],
  "popularity": 7
}
```

#### 25. Technical Diagram 🔧
```json
{
  "id": "technical",
  "name": "Technical Diagram",
  "description": "Clean technical/scientific illustration",
  "category": "Illustration",
  "icon": "🔧",
  "settings": {
    "style": "Academic Art",
    "medium": "Digital Illustration",
    "background": "on a clean white background",
    "technique": "minimalist"
  },
  "tags": ["technical", "diagram", "scientific", "clean"],
  "popularity": 6
}
```

#### 26. Fashion Sketch 👗
```json
{
  "id": "fashion_sketch",
  "name": "Fashion Sketch",
  "description": "Elegant fashion design illustration",
  "category": "Illustration",
  "icon": "👗",
  "settings": {
    "style": "Fashion",
    "medium": "Watercolor painting",
    "pose": "standing pose",
    "technique": "with soft shading",
    "mood": "Elegant"
  },
  "tags": ["fashion", "sketch", "elegant", "design"],
  "popularity": 7
}
```

---

### 🕰️ Vintage & Retro (4 presets)

#### 27. 1950s Advertising 📻
```json
{
  "id": "1950s_ad",
  "name": "1950s Advertising",
  "description": "Retro mid-century commercial art",
  "category": "Vintage",
  "icon": "📻",
  "settings": {
    "style": "Streamline Moderne",
    "medium": "Gouache",
    "technique": "stylized",
    "mood": "Cheerful"
  },
  "tags": ["1950s", "vintage", "advertising", "retro"],
  "popularity": 7
}
```

#### 28. Art Deco Poster 🎪
```json
{
  "id": "art_deco",
  "name": "Art Deco Poster",
  "description": "1920s-30s Art Deco style",
  "category": "Vintage",
  "icon": "🎪",
  "settings": {
    "style": "Art Deco",
    "medium": "Poster Art",
    "technique": "with bold outlines",
    "mood": "Glamorous"
  },
  "tags": ["art_deco", "1920s", "vintage", "poster"],
  "popularity": 8
}
```

#### 29. Vintage Travel Poster ✈️
```json
{
  "id": "vintage_travel",
  "name": "Vintage Travel Poster",
  "description": "Classic mid-century travel poster",
  "category": "Vintage",
  "icon": "✈️",
  "settings": {
    "style": "Art Deco",
    "medium": "Screen Print",
    "technique": "minimalist",
    "mood": "Nostalgic"
  },
  "tags": ["travel", "vintage", "poster", "mid_century"],
  "popularity": 8
}
```

#### 30. Victorian Portrait 🎩
```json
{
  "id": "victorian",
  "name": "Victorian Portrait",
  "description": "19th century portrait photography style",
  "category": "Vintage",
  "icon": "🎩",
  "settings": {
    "style": "Academic Art",
    "medium": "Oil Painting",
    "pose": "facing forward",
    "lighting": "Soft lighting",
    "mood": "Formal"
  },
  "tags": ["victorian", "19th_century", "formal", "historical"],
  "popularity": 6
}
```

---

## Preset Usage Patterns

### Discovery Patterns

**By Era:**
- 1920s-30s: Art Deco, Victorian
- 1950s: Advertising, Mid-century
- 1960s-70s: MAD Magazine, Underground Comix, Pop Art
- Modern: Cyberpunk, Vaporwave, Webcomic

**By Mood:**
- Playful: Children's Book, Webcomic, MAD Magazine
- Dark: Noir, Graphic Novel, Cyberpunk
- Elegant: Renaissance, Fashion, Art Deco
- Energetic: Pop Art, Superhero, Fantasy

**By Medium:**
- Traditional: Oil Painting, Watercolor, Ink
- Digital: Digital Art, Concept Art, Pixel Art
- Photography: Portrait, Fashion, Street

---

## Customization Guidelines

### Preset Variations

Each preset should support variations via the `variations` field:
- **Artist swaps:** Same style, different artist
- **Mood shifts:** Same composition, different emotion
- **Era updates:** Classic → Modern interpretation

**Example:**
```json
"variations": [
  {"artist": "Mort Drucker", "description": "Movie parody style"},
  {"mood": "Humorous", "description": "Lighter satirical tone"},
  {"technique": "with cel shading", "description": "Digital ink look"}
]
```

### User-Created Presets

Users can save current settings as custom presets with:
- **Required:** Name, settings
- **Optional:** Description, category, icon
- **Auto-generated:** ID, timestamp, tags
- **Default:** category="Custom", icon="⭐", popularity=5

---

## Implementation Notes

### Preset File Location
`data/prompts/presets.json`

### Loading Priority
1. Built-in presets (this catalog)
2. User custom presets
3. Sort by: Category → Popularity → Name

### Search Integration
Presets should be searchable by:
- Name (exact match)
- Tags (semantic match)
- Category
- Description (fuzzy match)

**Example:** Search "mad" finds "MAD Magazine Style" preset

---

## Future Expansion Ideas

### Community Presets
- Allow preset sharing/export
- Preset rating system
- Popular presets leaderboard
- Downloadable preset packs

### Dynamic Presets
- "Random Variation" button generates new combinations
- "Similar to..." suggestions based on current preset
- Seasonal/trending preset collections

### Contextual Suggestions
- Analyze uploaded reference image → suggest matching presets
- Learn from user history → personalized preset recommendations

---

## Preset Testing Checklist

For each preset:
- [ ] All referenced artists exist in `artists.json`
- [ ] All referenced styles exist in `styles.json`
- [ ] All referenced mediums exist in `mediums.json`
- [ ] Icon renders correctly on all platforms
- [ ] Description is clear and accurate
- [ ] Tags are relevant and discoverable
- [ ] Popularity score reflects expected usage
- [ ] Variations offer meaningful alternatives

---

**Last Updated:** 2025-11-10
**Next Review:** After Phase 1 user testing
