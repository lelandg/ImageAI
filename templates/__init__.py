"""Template management for ImageAI."""

from pathlib import Path
from typing import List, Dict, Any

from core.constants import GEMINI_TEMPLATES_PATH


def get_gemini_doc_templates() -> List[Dict[str, Any]]:
    """
    Load templates from GEMINI.md if available, otherwise use defaults.
    
    Returns:
        List of template dictionaries
    """
    # Default templates
    default_templates = [
        {
            "name": "Simple subject",
            "template": "A [adjective] [subject] in [setting]",
            "defaults": {
                "adjective": "beautiful",
                "subject": "sunset",
                "setting": "the mountains",
            },
        },
        {
            "name": "Art style",
            "template": "[subject], [art style] style, [details]",
            "defaults": {
                "subject": "portrait of a cat",
                "art style": "impressionist",
                "details": "vibrant colors, thick brushstrokes",
            },
        },
        {
            "name": "Product shot",
            "template": "Professional product photography of [product], [background] background, [lighting] lighting, high resolution",
            "defaults": {
                "product": "luxury watch",
                "background": "white",
                "lighting": "studio",
            },
        },
        {
            "name": "Character design",
            "template": "Character concept art of [character], [clothing], [pose], [style] style, detailed",
            "defaults": {
                "character": "warrior",
                "clothing": "armor",
                "pose": "heroic stance",
                "style": "fantasy",
            },
        },
        {
            "name": "Landscape",
            "template": "[time of day] landscape of [location], [weather], [style] style, [mood] mood",
            "defaults": {
                "time of day": "sunset",
                "location": "mountain valley",
                "weather": "clear sky",
                "style": "photorealistic",
                "mood": "peaceful",
            },
        },
        {
            "name": "Logo design",
            "template": "Minimalist logo design for [company], [colors] colors, [style] style, vector art",
            "defaults": {
                "company": "tech startup",
                "colors": "blue and white",
                "style": "modern",
            },
        },
        {
            "name": "Food photography",
            "template": "Delicious [dish] on [plate], [garnish], [lighting] lighting, appetizing, food photography",
            "defaults": {
                "dish": "pasta",
                "plate": "white ceramic plate",
                "garnish": "fresh herbs",
                "lighting": "natural",
            },
        },
        {
            "name": "Architecture",
            "template": "[building type] in [location], [architectural style] architecture, [time of day], [perspective]",
            "defaults": {
                "building type": "modern house",
                "location": "forest",
                "architectural style": "minimalist",
                "time of day": "golden hour",
                "perspective": "exterior view",
            },
        },
        {
            "name": "Portrait",
            "template": "Portrait of [subject], [age], [expression], [lighting] lighting, [style] style",
            "defaults": {
                "subject": "person",
                "age": "young adult",
                "expression": "smiling",
                "lighting": "soft",
                "style": "photorealistic",
            },
        },
        {
            "name": "Anime/Manga",
            "template": "Anime style [character] with [features], [outfit], [background], [mood]",
            "defaults": {
                "character": "girl",
                "features": "long hair",
                "outfit": "school uniform",
                "background": "cherry blossoms",
                "mood": "cheerful",
            },
        },
        {
            "name": "Sci-fi scene",
            "template": "Futuristic [scene] on [location], [technology], [atmosphere], sci-fi concept art",
            "defaults": {
                "scene": "cityscape",
                "location": "alien planet",
                "technology": "flying vehicles",
                "atmosphere": "neon lights",
            },
        },
        {
            "name": "Abstract art",
            "template": "Abstract [composition] with [colors], [texture], [movement], modern art",
            "defaults": {
                "composition": "geometric shapes",
                "colors": "vibrant blues and oranges",
                "texture": "smooth gradients",
                "movement": "dynamic flow",
            },
        },
        {
            "name": "Fantasy creature",
            "template": "Fantasy [creature] with [features], in [environment], [style] art style, magical",
            "defaults": {
                "creature": "dragon",
                "features": "iridescent scales",
                "environment": "ancient forest",
                "style": "detailed digital",
            },
        },
        {
            "name": "Vintage poster",
            "template": "Vintage [era] poster for [subject], [color scheme], retro design, [text]",
            "defaults": {
                "era": "1950s",
                "subject": "travel destination",
                "color scheme": "muted pastels",
                "text": "stylized typography",
            },
        },
        {
            "name": "Watercolor painting",
            "template": "Watercolor painting of [subject], [colors], soft edges, [paper texture]",
            "defaults": {
                "subject": "flowers in vase",
                "colors": "pastel colors",
                "paper texture": "visible paper texture",
            },
        },
        {
            "name": "3D render",
            "template": "3D render of [object], [material], [lighting] lighting, [background], photorealistic",
            "defaults": {
                "object": "geometric sculpture",
                "material": "metallic surface",
                "lighting": "dramatic",
                "background": "gradient",
            },
        },
        {
            "name": "Comic book style",
            "template": "Comic book illustration of [scene], [characters], [action], bold colors, ink outlines",
            "defaults": {
                "scene": "superhero battle",
                "characters": "hero vs villain",
                "action": "dynamic action pose",
            },
        },
        {
            "name": "Minimalist design",
            "template": "Minimalist [type] design featuring [element], [color] color scheme, clean, simple",
            "defaults": {
                "type": "poster",
                "element": "single object",
                "color": "monochrome",
            },
        },
        {
            "name": "Steampunk style",
            "template": "Steampunk [object/scene] with [mechanical elements], brass and copper, Victorian era inspired",
            "defaults": {
                "object/scene": "airship",
                "mechanical elements": "gears and pipes",
            },
        },
        {
            "name": "Nature photography",
            "template": "[season] nature scene of [subject], [time of day], [weather], professional photography",
            "defaults": {
                "season": "autumn",
                "subject": "forest path",
                "time of day": "morning",
                "weather": "misty",
            },
        },
        {
            "name": "Concept vehicle",
            "template": "Futuristic concept [vehicle type], [design style], [color], [environment], detailed render",
            "defaults": {
                "vehicle type": "car",
                "design style": "aerodynamic",
                "color": "metallic silver",
                "environment": "showroom",
            },
        },
        {
            "name": "Sticker design",
            "template": "Cute sticker design of [subject], [expression], kawaii style, white border, simple background",
            "defaults": {
                "subject": "animal",
                "expression": "happy",
            },
        },
        {
            "name": "Fashion illustration",
            "template": "Fashion illustration of [model] wearing [outfit], [pose], [style] style, elegant",
            "defaults": {
                "model": "woman",
                "outfit": "evening dress",
                "pose": "runway pose",
                "style": "watercolor",
            },
        },
        {
            "name": "Pixel art",
            "template": "Pixel art of [subject], [size] pixels, [color palette], retro game style",
            "defaults": {
                "subject": "character sprite",
                "size": "32x32",
                "color palette": "limited palette",
            },
        },
        {
            "name": "Infographic style",
            "template": "Infographic showing [topic], [visual elements], clean design, [color scheme]",
            "defaults": {
                "topic": "data visualization",
                "visual elements": "charts and icons",
                "color scheme": "professional blue",
            },
        },
        {
            "name": "Surreal art",
            "template": "Surreal artwork featuring [elements], [atmosphere], dreamlike, [art style]",
            "defaults": {
                "elements": "floating objects",
                "atmosphere": "mysterious",
                "art style": "oil painting",
            },
        },
        {
            "name": "Icon design",
            "template": "App icon for [app type], [main element], [style], [colors], rounded corners",
            "defaults": {
                "app type": "productivity app",
                "main element": "simple symbol",
                "style": "flat design",
                "colors": "gradient",
            },
        },
        {
            "name": "Isometric illustration",
            "template": "Isometric illustration of [scene], [details], clean vectors, [color palette]",
            "defaults": {
                "scene": "room interior",
                "details": "furniture and decorations",
                "color palette": "pastel colors",
            },
        },
        {
            "name": "Tattoo design",
            "template": "Tattoo design of [subject], [style] style, black ink, [size] size, detailed linework",
            "defaults": {
                "subject": "rose",
                "style": "traditional",
                "size": "medium",
            },
        },
        {
            "name": "Book cover",
            "template": "Book cover for [genre] novel titled '[title]', [visual elements], [mood], professional design",
            "defaults": {
                "genre": "fantasy",
                "title": "The Journey",
                "visual elements": "symbolic imagery",
                "mood": "mysterious",
            },
        },
        {
            "name": "Album art",
            "template": "Album cover for [music genre] band, [visual style], [color scheme], [mood]",
            "defaults": {
                "music genre": "indie rock",
                "visual style": "artistic photography",
                "color scheme": "moody colors",
                "mood": "atmospheric",
            },
        },
        {
            "name": "Emoji style",
            "template": "Emoji-style icon of [subject], [expression], simple, colorful, flat design",
            "defaults": {
                "subject": "face",
                "expression": "smiling",
            },
        },
        {
            "name": "Movie poster",
            "template": "Movie poster for [genre] film, [main character], [setting], dramatic lighting, [tagline area]",
            "defaults": {
                "genre": "action",
                "main character": "hero silhouette",
                "setting": "city skyline",
                "tagline area": "text space at bottom",
            },
        },
        {
            "name": "Pattern design",
            "template": "Seamless pattern of [elements], [style], [colors], repeating, decorative",
            "defaults": {
                "elements": "geometric shapes",
                "style": "modern",
                "colors": "complementary colors",
            },
        },
        {
            "name": "Technical diagram",
            "template": "Technical diagram of [subject], labeled parts, [view type], clean lines, professional",
            "defaults": {
                "subject": "machine components",
                "view type": "cross-section view",
            },
        },
        {
            "name": "Street art",
            "template": "Street art mural of [subject], [style], vibrant colors, urban setting, [technique]",
            "defaults": {
                "subject": "abstract design",
                "style": "graffiti",
                "technique": "spray paint effect",
            },
        },
        {
            "name": "Mascot design",
            "template": "Friendly mascot character for [brand type], [animal/character], [colors], approachable, memorable",
            "defaults": {
                "brand type": "sports team",
                "animal/character": "animal character",
                "colors": "team colors",
            },
        },
        {
            "name": "Kawaii style",
            "template": "Super cute kawaii [subject] with [features], pastel colors, big eyes, [accessories]",
            "defaults": {
                "subject": "cat",
                "features": "round shape",
                "accessories": "bow tie",
            },
        },
        {
            "name": "Neon sign",
            "template": "Neon sign saying '[text]', [color] glow, [background], retro style, realistic lighting",
            "defaults": {
                "text": "OPEN",
                "color": "pink",
                "background": "dark brick wall",
            },
        },
        {
            "name": "Coloring book page",
            "template": "Black and white line art of [subject] for coloring book, detailed outlines, no shading",
            "defaults": {
                "subject": "mandala pattern",
            },
        },
        {
            "name": "Ice/Glass sculpture",
            "template": "[material] sculpture of [subject], transparent, [lighting], detailed, artistic",
            "defaults": {
                "material": "crystal clear ice",
                "subject": "swan",
                "lighting": "backlit",
            },
        },
        {
            "name": "Double exposure",
            "template": "Double exposure photography combining [subject 1] and [subject 2], artistic blend, [mood]",
            "defaults": {
                "subject 1": "portrait silhouette",
                "subject 2": "forest landscape",
                "mood": "dreamy",
            },
        },
        {
            "name": "Clay/Plasticine style",
            "template": "Claymation style [character/scene], colorful plasticine, [lighting], stop-motion aesthetic",
            "defaults": {
                "character/scene": "cute monster",
                "lighting": "soft studio lighting",
            },
        },
        {
            "name": "Sports action",
            "template": "[sport] action shot of [athlete/player], [moment], dynamic, professional sports photography",
            "defaults": {
                "sport": "basketball",
                "athlete/player": "player",
                "moment": "mid-jump shot",
            },
        },
        {
            "name": "Cyberpunk style",
            "template": "Cyberpunk [scene/character], neon lights, [setting], high-tech low-life, [weather]",
            "defaults": {
                "scene/character": "street scene",
                "setting": "neo-Tokyo inspired",
                "weather": "rainy night",
            },
        },
        {
            "name": "Low poly 3D",
            "template": "Low poly 3D model of [subject], [color scheme], geometric simplification, clean render",
            "defaults": {
                "subject": "landscape",
                "color scheme": "gradient colors",
            },
        },
        {
            "name": "Retro gaming",
            "template": "[era] retro game style [scene/character], pixel perfect, [color palette], nostalgic",
            "defaults": {
                "era": "16-bit",
                "scene/character": "platformer level",
                "color palette": "limited color palette",
            },
        },
        {
            "name": "Paper craft",
            "template": "Paper craft art of [subject], [paper type], layered, [colors], 3D effect",
            "defaults": {
                "subject": "butterfly",
                "paper type": "colored cardstock",
                "colors": "vibrant colors",
            },
        },
        {
            "name": "Vaporwave aesthetic",
            "template": "Vaporwave style [scene], [elements], purple and pink, retro-futuristic, glitch effects",
            "defaults": {
                "scene": "sunset beach",
                "elements": "palm trees and geometric shapes",
            },
        },
        {
            "name": "Renaissance painting",
            "template": "Renaissance style painting of [subject], [setting], classical composition, oil paint texture",
            "defaults": {
                "subject": "noble portrait",
                "setting": "ornate background",
            },
        },
        {
            "name": "Sketch/Drawing",
            "template": "[medium] sketch of [subject], [style], [shading], artistic study",
            "defaults": {
                "medium": "pencil",
                "subject": "portrait",
                "style": "realistic",
                "shading": "cross-hatching",
            },
        },
        {
            "name": "Art Nouveau",
            "template": "Art Nouveau style [subject], flowing organic lines, [colors], decorative, elegant",
            "defaults": {
                "subject": "woman with flowers",
                "colors": "muted earth tones",
            },
        },
        {
            "name": "Pop art",
            "template": "Pop art style [subject], bold colors, [technique], comic book aesthetic",
            "defaults": {
                "subject": "portrait",
                "technique": "Ben Day dots",
            },
        },
        {
            "name": "Geometric art",
            "template": "Geometric abstract art with [shapes], [color scheme], [composition], modern design",
            "defaults": {
                "shapes": "triangles and circles",
                "color scheme": "complementary colors",
                "composition": "balanced asymmetry",
            },
        },
        {
            "name": "Dark fantasy",
            "template": "Dark fantasy [scene/creature], gothic atmosphere, [lighting], ominous mood, detailed",
            "defaults": {
                "scene/creature": "haunted castle",
                "lighting": "moonlight through fog",
            },
        },
        {
            "name": "Zen/Minimalist",
            "template": "Zen minimalist composition of [subject], [background], peaceful, balanced, [style]",
            "defaults": {
                "subject": "single stone",
                "background": "white space",
                "style": "Japanese inspired",
            },
        },
        {
            "name": "Propaganda poster",
            "template": "Vintage propaganda poster style, [message theme], bold typography, [color scheme], dramatic",
            "defaults": {
                "message theme": "motivational",
                "color scheme": "red and black",
            },
        },
        {
            "name": "Diorama",
            "template": "Miniature diorama of [scene], tilt-shift effect, [scale], detailed, [setting]",
            "defaults": {
                "scene": "tiny town",
                "scale": "HO scale",
                "setting": "countryside",
            },
        },
        {
            "name": "Holographic",
            "template": "Holographic [subject], iridescent colors, [background], futuristic, prismatic effects",
            "defaults": {
                "subject": "geometric shape",
                "background": "dark background",
            },
        },
        {
            "name": "Origami",
            "template": "Origami [subject] made from [paper type], [color], clean folds, [background]",
            "defaults": {
                "subject": "crane",
                "paper type": "traditional paper",
                "color": "white",
                "background": "simple background",
            },
        },
        {
            "name": "Mosaic art",
            "template": "Mosaic artwork of [subject], [tile type], [color palette], intricate pattern",
            "defaults": {
                "subject": "geometric pattern",
                "tile type": "ceramic tiles",
                "color palette": "Mediterranean colors",
            },
        },
        {
            "name": "Synthwave",
            "template": "Synthwave [scene], retro 80s aesthetic, [elements], neon grid, sunset colors",
            "defaults": {
                "scene": "car on highway",
                "elements": "palm trees and mountains",
            },
        },
        {
            "name": "Botanical illustration",
            "template": "Scientific botanical illustration of [plant], detailed, labeled, [style], educational",
            "defaults": {
                "plant": "flower",
                "style": "vintage textbook",
            },
        },
        {
            "name": "Film noir",
            "template": "Film noir style [scene], black and white, dramatic shadows, [setting], mysterious",
            "defaults": {
                "scene": "detective in alley",
                "setting": "1940s city",
            },
        },
        {
            "name": "Psychedelic art",
            "template": "Psychedelic artwork with [patterns], vibrant colors, [style], trippy, flowing",
            "defaults": {
                "patterns": "swirling fractals",
                "style": "60s inspired",
            },
        },
        {
            "name": "Chalk art",
            "template": "Chalk art on [surface] of [subject], [colors], textured, [style]",
            "defaults": {
                "surface": "blackboard",
                "subject": "mathematical equations",
                "colors": "white and pastel",
                "style": "educational",
            },
        },
        {
            "name": "Glitch art",
            "template": "Glitch art of [subject], digital distortion, [colors], corrupted aesthetic, cyberpunk",
            "defaults": {
                "subject": "portrait",
                "colors": "RGB color separation",
            },
        },
        {
            "name": "Woodcut print",
            "template": "Woodcut print style [subject], bold lines, [ink color] on [paper color], vintage",
            "defaults": {
                "subject": "landscape",
                "ink color": "black ink",
                "paper color": "cream paper",
            },
        },
        {
            "name": "Bauhaus design",
            "template": "Bauhaus style [design type], geometric, [colors], functional aesthetic, modernist",
            "defaults": {
                "design type": "poster",
                "colors": "primary colors",
            },
        },
        {
            "name": "Ukiyo-e Japanese",
            "template": "Ukiyo-e Japanese woodblock print of [subject], [setting], traditional style, [season]",
            "defaults": {
                "subject": "Mount Fuji",
                "setting": "landscape",
                "season": "cherry blossom season",
            },
        },
        {
            "name": "Constructivist",
            "template": "Constructivist poster design, [subject], bold geometric shapes, [colors], revolutionary",
            "defaults": {
                "subject": "abstract composition",
                "colors": "red and black",
            },
        },
        {
            "name": "Afrofuturism",
            "template": "Afrofuturist [scene/character], [elements], vibrant, cultural fusion, futuristic",
            "defaults": {
                "scene/character": "warrior",
                "elements": "traditional meets high-tech",
            },
        },
        {
            "name": "Cottagecore",
            "template": "Cottagecore aesthetic [scene], cozy, [elements], soft lighting, pastoral",
            "defaults": {
                "scene": "cottage garden",
                "elements": "wildflowers and rustic details",
            },
        },
        {
            "name": "Brutalist architecture",
            "template": "Brutalist [building type], concrete, [setting], monolithic, dramatic shadows",
            "defaults": {
                "building type": "structure",
                "setting": "urban environment",
            },
        },
        {
            "name": "Studio Ghibli style",
            "template": "Studio Ghibli anime style [scene], [characters], whimsical, detailed background, magical",
            "defaults": {
                "scene": "countryside",
                "characters": "young protagonist",
            },
        },
        {
            "name": "Medical illustration",
            "template": "Medical illustration of [anatomy/process], detailed, labeled, educational, [style]",
            "defaults": {
                "anatomy/process": "human anatomy",
                "style": "textbook diagram",
            },
        },
        {
            "name": "Solarpunk",
            "template": "Solarpunk [scene], green technology, [architecture], optimistic future, lush vegetation",
            "defaults": {
                "scene": "eco-city",
                "architecture": "sustainable buildings",
            },
        },
        {
            "name": "Dieselpunk",
            "template": "Dieselpunk [vehicle/scene], industrial aesthetic, [era] inspired, mechanical details",
            "defaults": {
                "vehicle/scene": "war machine",
                "era": "1940s",
            },
        },
        {
            "name": "Liminal space",
            "template": "Liminal space photograph of [location], empty, eerie atmosphere, [lighting], unsettling",
            "defaults": {
                "location": "abandoned mall",
                "lighting": "fluorescent lighting",
            },
        },
        {
            "name": "Maximalist design",
            "template": "Maximalist [design type], overwhelming detail, [patterns], vibrant, more is more",
            "defaults": {
                "design type": "interior",
                "patterns": "mixed patterns and textures",
            },
        },
        {
            "name": "Biomorphic design",
            "template": "Biomorphic [object/architecture], organic forms, flowing curves, [material], natural inspired",
            "defaults": {
                "object/architecture": "furniture",
                "material": "smooth surfaces",
            },
        },
        {
            "name": "Witch house aesthetic",
            "template": "Witch house aesthetic [scene], occult symbols, dark, [elements], mysterious",
            "defaults": {
                "scene": "ritual space",
                "elements": "candles and crystals",
            },
        },
        {
            "name": "Y2K aesthetic",
            "template": "Y2K aesthetic [design/fashion], [colors], early 2000s style, tech-inspired, nostalgic",
            "defaults": {
                "design/fashion": "graphic design",
                "colors": "metallic and neon",
            },
        },
        {
            "name": "Memphis design",
            "template": "Memphis design style [object], bold patterns, [colors], postmodern, playful",
            "defaults": {
                "object": "furniture piece",
                "colors": "primary colors with pastels",
            },
        },
        {
            "name": "Dark academia",
            "template": "Dark academia aesthetic [scene], [elements], moody lighting, scholarly, gothic",
            "defaults": {
                "scene": "old library",
                "elements": "books and vintage items",
            },
        },
        {
            "name": "Weirdcore",
            "template": "Weirdcore [scene], surreal, unsettling, [elements], dreamlike, distorted reality",
            "defaults": {
                "scene": "empty room",
                "elements": "floating eyes",
            },
        },
        {
            "name": "Frutiger Aero",
            "template": "Frutiger Aero aesthetic, [subject], glossy, [elements], 2000s tech optimism",
            "defaults": {
                "subject": "interface design",
                "elements": "water droplets and glass",
            },
        },
        {
            "name": "Goblincore",
            "template": "Goblincore aesthetic [collection/scene], [items], earthy, whimsical, nature finds",
            "defaults": {
                "collection/scene": "treasure collection",
                "items": "mushrooms and shiny objects",
            },
        },
        {
            "name": "Traumacore",
            "template": "Traumacore aesthetic [scene], [elements], nostalgic toys, unsettling, emotional",
            "defaults": {
                "scene": "childhood room",
                "elements": "distorted memories",
            },
        },
        {
            "name": "Cluttercore",
            "template": "Cluttercore [room/space], maximalist decor, [collections], organized chaos, cozy",
            "defaults": {
                "room/space": "bedroom",
                "collections": "books and trinkets",
            },
        },
        {
            "name": "Poolcore/Liminal",
            "template": "Poolcore liminal space, empty [pool area], [lighting], nostalgic, eerie calm",
            "defaults": {
                "pool area": "indoor pool",
                "lighting": "artificial lighting",
            },
        },
        {
            "name": "Analog horror",
            "template": "Analog horror style [subject], VHS quality, [distortion], found footage aesthetic",
            "defaults": {
                "subject": "emergency broadcast",
                "distortion": "static and glitches",
            },
        },
        {
            "name": "Biopunk",
            "template": "Biopunk [creature/scene], organic technology, [elements], genetic modification, visceral",
            "defaults": {
                "creature/scene": "hybrid organism",
                "elements": "bio-mechanical fusion",
            },
        },
        {
            "name": "Fairycore",
            "template": "Fairycore aesthetic [scene], [elements], soft pastels, whimsical, magical nature",
            "defaults": {
                "scene": "enchanted forest",
                "elements": "mushroom circles and sparkles",
            },
        },
        {
            "name": "Prehistoricore",
            "template": "Prehistoricore [scene], [creatures], ancient landscape, [time period], natural history",
            "defaults": {
                "scene": "primordial jungle",
                "creatures": "dinosaurs",
                "time period": "Jurassic",
            },
        },
        {
            "name": "Angelcore",
            "template": "Angelcore aesthetic [figure/scene], [elements], ethereal, holy light, heavenly",
            "defaults": {
                "figure/scene": "angel statue",
                "elements": "clouds and golden light",
            },
        },
        {
            "name": "Kidcore",
            "template": "Kidcore aesthetic [scene], primary colors, [toys/items], nostalgic childhood, playful",
            "defaults": {
                "scene": "playroom",
                "toys/items": "stuffed animals and crayons",
            },
        },
        {
            "name": "Dreamcore",
            "template": "Dreamcore [scene], surreal, [elements], hazy atmosphere, subconscious imagery",
            "defaults": {
                "scene": "endless hallway",
                "elements": "doors and clouds",
            },
        },
        {
            "name": "Webcore/Old internet",
            "template": "Old web aesthetic [design], [elements], early internet, pixel graphics, nostalgic",
            "defaults": {
                "design": "website layout",
                "elements": "animated GIFs and starry background",
            },
        },
        {
            "name": "Romantic academia",
            "template": "Romantic academia [scene], [elements], warm lighting, literary, classical beauty",
            "defaults": {
                "scene": "university courtyard",
                "elements": "poetry books and flowers",
            },
        },
        {
            "name": "Spacecore",
            "template": "Spacecore aesthetic [scene], [celestial elements], cosmic colors, vast, ethereal",
            "defaults": {
                "scene": "nebula",
                "celestial elements": "stars and planets",
            },
        },
        {
            "name": "Vintage Americana",
            "template": "Vintage Americana [scene/subject], [era], nostalgic, [elements], patriotic colors",
            "defaults": {
                "scene/subject": "diner",
                "era": "1950s",
                "elements": "chrome and neon signs",
            },
        },
        {
            "name": "Naturecore",
            "template": "Naturecore [landscape], untouched wilderness, [season], [elements], peaceful",
            "defaults": {
                "landscape": "mountain meadow",
                "season": "spring",
                "elements": "wildflowers and streams",
            },
        },
        {
            "name": "Technocore",
            "template": "Technocore [scene], high-tech, [elements], LED lights, futuristic interfaces",
            "defaults": {
                "scene": "server room",
                "elements": "cables and screens",
            },
        },
        {
            "name": "Carnivalcore",
            "template": "Carnivalcore [scene], vintage circus, [elements], nostalgic, slightly eerie",
            "defaults": {
                "scene": "abandoned fairground",
                "elements": "carousel and string lights",
            },
        },
        {
            "name": "Desertwave",
            "template": "Desertwave aesthetic [landscape], [time], warm tones, [elements], southwestern",
            "defaults": {
                "landscape": "desert vista",
                "time": "golden hour",
                "elements": "cacti and mesas",
            },
        },
        {
            "name": "Forestpunk",
            "template": "Forestpunk [structure/scene], nature reclaimed, [elements], post-civilization, green",
            "defaults": {
                "structure/scene": "treehouse city",
                "elements": "rope bridges and moss",
            },
        },
        {
            "name": "After hours",
            "template": "After hours [urban scene], [time], neon lights, empty streets, [mood]",
            "defaults": {
                "urban scene": "city street",
                "time": "3 AM",
                "mood": "lonely but peaceful",
            },
        },
        {
            "name": "Grandmacore/Grandpacore",
            "template": "Grandmacore [scene/items], vintage homey, [patterns], cozy, nostalgic comfort",
            "defaults": {
                "scene/items": "living room",
                "patterns": "floral and doilies",
            },
        },
        {
            "name": "Light academia",
            "template": "Light academia [scene], [elements], bright and airy, scholarly, optimistic",
            "defaults": {
                "scene": "sunlit library",
                "elements": "open books and coffee",
            },
        },
        {
            "name": "Nostalgiacore",
            "template": "[decade] nostalgiacore [subject], period accurate, [elements], memory-like",
            "defaults": {
                "decade": "90s",
                "subject": "bedroom",
                "elements": "posters and CRT TV",
            },
        },
        {
            "name": "Royalcore",
            "template": "Royalcore [scene/subject], regal, [elements], luxury, [era] inspired",
            "defaults": {
                "scene/subject": "throne room",
                "elements": "velvet and gold",
                "era": "baroque",
            },
        },
        {
            "name": "Scientificcore",
            "template": "Scientific [subject/scene], laboratory aesthetic, [equipment], detailed, educational",
            "defaults": {
                "subject/scene": "experiment setup",
                "equipment": "beakers and microscopes",
            },
        },
        {
            "name": "Villagecore",
            "template": "Villagecore [scene], rural life, [elements], peaceful, simple living",
            "defaults": {
                "scene": "cottage with garden",
                "elements": "vegetable patch and chickens",
            },
        },
        {
            "name": "Warmcore",
            "template": "Warmcore [scene], cozy atmosphere, [elements], soft textures, inviting",
            "defaults": {
                "scene": "reading nook",
                "elements": "blankets and warm light",
            },
        },
        {
            "name": "Spiritcore",
            "template": "Spiritcore [scene/elements], mystical, [spiritual items], ethereal, transcendent",
            "defaults": {
                "scene/elements": "meditation space",
                "spiritual items": "crystals and incense",
            },
        },
        {
            "name": "Junglecore",
            "template": "Junglecore [scene], lush vegetation, [elements], tropical, wild nature",
            "defaults": {
                "scene": "rainforest canopy",
                "elements": "vines and exotic birds",
            },
        },
        {
            "name": "Cloudcore",
            "template": "Cloudcore [scene], sky aesthetic, [cloud types], dreamy, atmospheric",
            "defaults": {
                "scene": "aerial view",
                "cloud types": "cumulus clouds",
            },
        },
        {
            "name": "Rainbowcore",
            "template": "Rainbowcore [subject/scene], all rainbow colors, [elements], vibrant, joyful",
            "defaults": {
                "subject/scene": "room decor",
                "elements": "gradient everything",
            },
        },
        {
            "name": "Dragoncore",
            "template": "Dragoncore [scene/subject], [dragon elements], fantasy, medieval inspired, treasure",
            "defaults": {
                "scene/subject": "dragon's lair",
                "dragon elements": "scales and gold",
            },
        },
        {
            "name": "Craftcore",
            "template": "Craftcore [project/scene], handmade aesthetic, [materials], DIY, creative process",
            "defaults": {
                "project/scene": "craft table",
                "materials": "yarn and fabric",
            },
        },
        {
            "name": "Dollcore",
            "template": "Dollcore aesthetic [scene], [doll types], vintage toys, slightly unsettling, nostalgic",
            "defaults": {
                "scene": "doll collection",
                "doll types": "porcelain dolls",
            },
        },
        {
            "name": "Etherealcore",
            "template": "Etherealcore [figure/scene], translucent, [elements], angelic, delicate beauty",
            "defaults": {
                "figure/scene": "floating figure",
                "elements": "sheer fabric and light",
            },
        },
        {
            "name": "Clowncore",
            "template": "Clowncore [subject/scene], circus colors, [elements], playful chaos, whimsical",
            "defaults": {
                "subject/scene": "clown portrait",
                "elements": "balloons and confetti",
            },
        },
        {
            "name": "Miniaturecore",
            "template": "Miniaturecore [scene], tiny scale, [details], dollhouse aesthetic, intricate",
            "defaults": {
                "scene": "miniature room",
                "details": "tiny furniture",
            },
        },
        {
            "name": "Oceancore",
            "template": "Oceancore [scene], marine aesthetic, [elements], deep blue, aquatic",
            "defaults": {
                "scene": "underwater view",
                "elements": "coral and fish",
            },
        },
        {
            "name": "Rusticcore",
            "template": "Rusticcore [scene/object], weathered wood, [elements], farmhouse style, aged",
            "defaults": {
                "scene/object": "barn interior",
                "elements": "old tools and hay",
            },
        },
        {
            "name": "Apocalypsecore",
            "template": "Post-apocalyptic [scene], [elements], desolate, survival aesthetic, gritty",
            "defaults": {
                "scene": "abandoned city",
                "elements": "overgrown ruins",
            },
        },
        {
            "name": "Crystalcore",
            "template": "Crystalcore [scene/subject], [crystal types], prismatic light, geological beauty",
            "defaults": {
                "scene/subject": "crystal cave",
                "crystal types": "amethyst and quartz",
            },
        },
        {
            "name": "Mushroomcore",
            "template": "Mushroomcore [scene], [mushroom types], forest floor, whimsical fungi, fairy-tale",
            "defaults": {
                "scene": "mushroom circle",
                "mushroom types": "red toadstools",
            },
        },
        {
            "name": "Catcore",
            "template": "Catcore [scene], cat-themed, [elements], cozy, feline aesthetic",
            "defaults": {
                "scene": "cat cafe",
                "elements": "cat toys and towers",
            },
        },
        {
            "name": "Plantcore",
            "template": "Plantcore [space], indoor jungle, [plant types], green aesthetic, botanical",
            "defaults": {
                "space": "living room",
                "plant types": "monstera and pothos",
            },
        },
        {
            "name": "Mooncore",
            "template": "Mooncore [scene], lunar aesthetic, [phase], nighttime, mystical glow",
            "defaults": {
                "scene": "moonlit landscape",
                "phase": "full moon",
            },
        },
        {
            "name": "Starcore",
            "template": "Starcore [scene], stellar aesthetic, [constellation/elements], cosmic, twinkling",
            "defaults": {
                "scene": "night sky",
                "constellation/elements": "Orion constellation",
            },
        },
        {
            "name": "Suncore",
            "template": "Suncore [scene], solar aesthetic, golden hour, [elements], warm and bright",
            "defaults": {
                "scene": "sunrise landscape",
                "elements": "lens flares and warmth",
            },
        },
        {
            "name": "Sparklecore",
            "template": "Sparklecore [subject], glitter everywhere, [colors], shimmering, maximum shine",
            "defaults": {
                "subject": "accessories",
                "colors": "holographic",
            },
        },
        {
            "name": "Pastelcore",
            "template": "Pastelcore [subject/scene], soft pastel palette, [elements], gentle, sweet",
            "defaults": {
                "subject/scene": "bedroom decor",
                "elements": "plushies and pillows",
            },
        },
        {
            "name": "Gothcore",
            "template": "Gothcore [scene/subject], dark aesthetic, [elements], Victorian gothic, dramatic",
            "defaults": {
                "scene/subject": "gothic cathedral",
                "elements": "gargoyles and arches",
            },
        },
        {
            "name": "Metalcore",
            "template": "Metalcore [subject], industrial metal, [finish], mechanical aesthetic, heavy",
            "defaults": {
                "subject": "machinery",
                "finish": "brushed steel",
            },
        },
        {
            "name": "Mirrorcore",
            "template": "Mirrorcore [scene], infinite reflections, [elements], surreal, disorienting",
            "defaults": {
                "scene": "mirror maze",
                "elements": "fractured reflections",
            },
        },
        {
            "name": "Glowcore",
            "template": "Glowcore [scene/subject], bioluminescent, [colors], radioactive aesthetic, neon glow",
            "defaults": {
                "scene/subject": "glowing mushrooms",
                "colors": "green and blue",
            },
        },
        {
            "name": "Chromecore",
            "template": "Chromecore [object/scene], reflective chrome, [style], futuristic, high polish",
            "defaults": {
                "object/scene": "chrome sculpture",
                "style": "liquid metal",
            },
        },
        {
            "name": "Goldcore",
            "template": "Goldcore [subject/scene], everything gold, luxurious, [elements], opulent",
            "defaults": {
                "subject/scene": "golden palace",
                "elements": "gilded details",
            },
        },
        {
            "name": "Silvercore",
            "template": "Silvercore [subject/scene], silver aesthetic, [elements], elegant, metallic",
            "defaults": {
                "subject/scene": "silver jewelry",
                "elements": "moonlight reflection",
            },
        },
        {
            "name": "Bronzecore",
            "template": "Bronzecore [subject], aged bronze, [patina], classical, antique metal",
            "defaults": {
                "subject": "bronze statue",
                "patina": "green patina",
            },
        },
        {
            "name": "Coppercore",
            "template": "Coppercore [subject/scene], copper tones, [elements], warm metallic, industrial",
            "defaults": {
                "subject/scene": "copper pipes",
                "elements": "oxidized details",
            },
        },
        {
            "name": "Velvetcore",
            "template": "Velvetcore [scene/subject], plush velvet, [color], luxurious texture, rich",
            "defaults": {
                "scene/subject": "velvet curtains",
                "color": "deep burgundy",
            },
        },
        {
            "name": "Silkcore",
            "template": "Silkcore [subject], flowing silk, [colors], smooth, elegant draping",
            "defaults": {
                "subject": "silk fabric",
                "colors": "iridescent",
            },
        },
        {
            "name": "Lacecore",
            "template": "Lacecore [subject/scene], delicate lace, [pattern], vintage, intricate",
            "defaults": {
                "subject/scene": "lace dress",
                "pattern": "floral lace",
            },
        },
        {
            "name": "Leathercore",
            "template": "Leathercore [subject], [leather type], rugged, [color], textured",
            "defaults": {
                "subject": "leather jacket",
                "leather type": "distressed",
                "color": "black",
            },
        },
        {
            "name": "Woodcore",
            "template": "Woodcore [scene/object], [wood type], natural grain, rustic, organic",
            "defaults": {
                "scene/object": "wooden cabin",
                "wood type": "oak",
            },
        },
        {
            "name": "Stonecore",
            "template": "Stonecore [structure/scene], [stone type], ancient, solid, geological",
            "defaults": {
                "structure/scene": "stone circle",
                "stone type": "granite",
            },
        },
        {
            "name": "Marblecore",
            "template": "Marblecore [subject/scene], [marble type], classical, luxurious, veined",
            "defaults": {
                "subject/scene": "marble statue",
                "marble type": "white Carrara",
            },
        },
        {
            "name": "Concretecore",
            "template": "Concretecore [structure], raw concrete, brutalist, [texture], industrial",
            "defaults": {
                "structure": "concrete building",
                "texture": "rough cast",
            },
        },
        {
            "name": "Sandcore",
            "template": "Sandcore [scene], desert sand, [formation], natural patterns, arid",
            "defaults": {
                "scene": "sand dunes",
                "formation": "wind patterns",
            },
        },
        {
            "name": "Snowcore",
            "template": "Snowcore [scene], winter wonderland, [elements], pristine white, cold",
            "defaults": {
                "scene": "snowy forest",
                "elements": "icicles and frost",
            },
        },
        {
            "name": "Icecore",
            "template": "Icecore [structure/scene], frozen, [ice type], crystalline, arctic",
            "defaults": {
                "structure/scene": "ice cave",
                "ice type": "blue glacier ice",
            },
        },
        {
            "name": "Firecore",
            "template": "Firecore [scene], flames and embers, [intensity], warm glow, dynamic",
            "defaults": {
                "scene": "campfire",
                "intensity": "roaring flames",
            },
        },
        {
            "name": "Watercore",
            "template": "Watercore [scene], flowing water, [water type], fluid, refreshing",
            "defaults": {
                "scene": "waterfall",
                "water type": "crystal clear",
            },
        },
        {
            "name": "Aircore",
            "template": "Aircore [scene], atmospheric, [elements], breezy, ethereal lightness",
            "defaults": {
                "scene": "sky view",
                "elements": "wind currents",
            },
        },
        {
            "name": "Earthcore",
            "template": "Earthcore [scene], natural earth, [elements], grounded, organic",
            "defaults": {
                "scene": "canyon",
                "elements": "rock layers",
            },
        },
        {
            "name": "Lightcore",
            "template": "Lightcore [scene], bright illumination, [light source], radiant, luminous",
            "defaults": {
                "scene": "light installation",
                "light source": "LED arrays",
            },
        },
        {
            "name": "Darkcore",
            "template": "Darkcore [scene], absence of light, [elements], shadow aesthetic, void",
            "defaults": {
                "scene": "dark room",
                "elements": "subtle shadows",
            },
        },
        {
            "name": "Shadowcore",
            "template": "Shadowcore [scene], dramatic shadows, [light source], silhouettes, mysterious",
            "defaults": {
                "scene": "alleyway",
                "light source": "street lamp",
            },
        },
        {
            "name": "Fogcore",
            "template": "Fogcore [scene], misty atmosphere, [density], obscured, mysterious",
            "defaults": {
                "scene": "foggy forest",
                "density": "thick fog",
            },
        },
        {
            "name": "Smokecore",
            "template": "Smokecore [scene], smoke effects, [color], swirling, atmospheric",
            "defaults": {
                "scene": "incense smoke",
                "color": "white smoke",
            },
        },
        {
            "name": "Dustcore",
            "template": "Dustcore [scene], dust particles, [lighting], abandoned, time-worn",
            "defaults": {
                "scene": "attic",
                "lighting": "sunbeam through dust",
            },
        },
        {
            "name": "Rustcore",
            "template": "Rustcore [object/scene], oxidized metal, [color], decay aesthetic, weathered",
            "defaults": {
                "object/scene": "rusted machinery",
                "color": "orange-brown rust",
            },
        },
        {
            "name": "Decaycore",
            "template": "Decaycore [subject], decomposition, [stage], natural cycle, memento mori",
            "defaults": {
                "subject": "abandoned building",
                "stage": "overgrown",
            },
        },
        {
            "name": "Bloomcore",
            "template": "Bloomcore [scene], flowers in full bloom, [flower types], vibrant, spring",
            "defaults": {
                "scene": "flower field",
                "flower types": "wildflowers",
            },
        },
        {
            "name": "Fadecore",
            "template": "Fadecore [subject], sun-bleached, [original color], washed out, nostalgic",
            "defaults": {
                "subject": "old photograph",
                "original color": "faded colors",
            },
        },
        {
            "name": "Blurcore",
            "template": "Blurcore [subject], motion blur, [direction], dynamic, speed aesthetic",
            "defaults": {
                "subject": "moving lights",
                "direction": "horizontal blur",
            },
        },
        {
            "name": "Sharpcore",
            "template": "Sharpcore [subject], hyper-detailed, crisp edges, [focus], ultra-sharp",
            "defaults": {
                "subject": "macro photography",
                "focus": "tack sharp",
            },
        },
        {
            "name": "Softcore",
            "template": "Softcore [subject], soft focus, [elements], gentle, dreamy quality",
            "defaults": {
                "subject": "portrait",
                "elements": "soft lighting",
            },
        },
        {
            "name": "Hardcode",
            "template": "Hardcode [subject], harsh contrast, [elements], aggressive, stark",
            "defaults": {
                "subject": "industrial scene",
                "elements": "hard shadows",
            },
        },
        {
            "name": "Roundcore",
            "template": "Roundcore [subject], circular forms, [elements], soft curves, no edges",
            "defaults": {
                "subject": "bubble design",
                "elements": "spherical shapes",
            },
        },
        {
            "name": "Squarecore",
            "template": "Squarecore [subject], cubic forms, [arrangement], grid-based, angular",
            "defaults": {
                "subject": "block architecture",
                "arrangement": "perfect grid",
            },
        },
        {
            "name": "Trianglecore",
            "template": "Trianglecore [subject], triangular geometry, [pattern], pointed, dynamic",
            "defaults": {
                "subject": "geometric art",
                "pattern": "tessellation",
            },
        },
        {
            "name": "Hexagoncore",
            "template": "Hexagoncore [subject], hexagonal patterns, [arrangement], honeycomb, efficient",
            "defaults": {
                "subject": "hexagon tiles",
                "arrangement": "perfect tessellation",
            },
        },
        {
            "name": "Spiralcore",
            "template": "Spiralcore [subject], spiral patterns, [direction], hypnotic, fibonacci",
            "defaults": {
                "subject": "nautilus shell",
                "direction": "clockwise spiral",
            },
        },
        {
            "name": "Wavecore",
            "template": "Wavecore [subject], undulating waves, [frequency], rhythmic, flowing",
            "defaults": {
                "subject": "ocean waves",
                "frequency": "regular pattern",
            },
        },
        {
            "name": "Gridcore",
            "template": "Gridcore [subject], perfect grid, [spacing], organized, systematic",
            "defaults": {
                "subject": "city layout",
                "spacing": "uniform spacing",
            },
        },
        {
            "name": "Chaoscore",
            "template": "Chaoscore [scene], organized chaos, [elements], entropy, disorder aesthetic",
            "defaults": {
                "scene": "cluttered workspace",
                "elements": "random arrangement",
            },
        },
        {
            "name": "Ordercore",
            "template": "Ordercore [scene], perfect organization, [arrangement], systematic, precise",
            "defaults": {
                "scene": "organized shelves",
                "arrangement": "color-coded",
            },
        },
        {
            "name": "Balancecore",
            "template": "Balancecore [composition], perfect balance, [elements], harmony, equilibrium",
            "defaults": {
                "composition": "zen garden",
                "elements": "symmetrical arrangement",
            },
        },
        {
            "name": "Tensioncore",
            "template": "Tensioncore [scene], visual tension, [elements], about to break, suspense",
            "defaults": {
                "scene": "tightrope walker",
                "elements": "precarious balance",
            },
        },
        {
            "name": "Flowcore",
            "template": "Flowcore [subject], fluid movement, [direction], continuous, graceful",
            "defaults": {
                "subject": "water stream",
                "direction": "natural flow",
            },
        },
        {
            "name": "Staticcore",
            "template": "Staticcore [subject], TV static, [interference], analog noise, glitchy",
            "defaults": {
                "subject": "old TV screen",
                "interference": "white noise",
            },
        },
        {
            "name": "Pixelcore",
            "template": "Pixelcore [subject], visible pixels, [resolution], digital aesthetic, blocky",
            "defaults": {
                "subject": "pixel art",
                "resolution": "low-res",
            },
        },
        {
            "name": "Vectorcore",
            "template": "Vectorcore [subject], clean vectors, [style], scalable, geometric precision",
            "defaults": {
                "subject": "logo design",
                "style": "flat design",
            },
        },
        {
            "name": "Bitmapcore",
            "template": "Bitmapcore [subject], raster graphics, [color depth], digital painting",
            "defaults": {
                "subject": "digital artwork",
                "color depth": "full color",
            },
        },
        {
            "name": "Analogcore",
            "template": "Analogcore [subject], analog aesthetic, [medium], pre-digital, authentic",
            "defaults": {
                "subject": "film photography",
                "medium": "35mm film",
            },
        },
        {
            "name": "Digitalcore",
            "template": "Digitalcore [subject], pure digital, [elements], cyber aesthetic, binary",
            "defaults": {
                "subject": "digital interface",
                "elements": "code and data",
            },
        },
        {
            "name": "Vintagecore",
            "template": "Vintagecore [subject], [era] vintage, aged patina, nostalgic, authentic",
            "defaults": {
                "subject": "antique furniture",
                "era": "Victorian",
            },
        },
        {
            "name": "Moderncore",
            "template": "Moderncore [subject], contemporary design, [style], current trends, sleek",
            "defaults": {
                "subject": "modern architecture",
                "style": "minimalist",
            },
        },
        {
            "name": "Futurecore",
            "template": "Futurecore [subject], futuristic vision, [technology], sci-fi aesthetic",
            "defaults": {
                "subject": "future city",
                "technology": "hovercars",
            },
        },
        {
            "name": "Ancientcore",
            "template": "Ancientcore [subject], ancient civilization, [culture], archaeological, historical",
            "defaults": {
                "subject": "temple ruins",
                "culture": "Greek",
            },
        },
        {
            "name": "Timelesscore",
            "template": "Timelesscore [subject], eternal aesthetic, [style], classic, enduring",
            "defaults": {
                "subject": "classical sculpture",
                "style": "neoclassical",
            },
        },
        {
            "name": "Instantcore",
            "template": "Instantcore [moment], captured instant, [action], freeze frame, decisive",
            "defaults": {
                "moment": "splash",
                "action": "water drop impact",
            },
        },
        {
            "name": "Eternitycore",
            "template": "Eternitycore [scene], infinite perspective, [elements], endless, cosmic scale",
            "defaults": {
                "scene": "infinite corridor",
                "elements": "repeating arches",
            },
        },
        {
            "name": "Microcore",
            "template": "Microcore [subject], microscopic view, [magnification], cellular, tiny world",
            "defaults": {
                "subject": "cell structure",
                "magnification": "1000x",
            },
        },
        {
            "name": "Macrocore",
            "template": "Macrocore [subject], extreme close-up, [detail], magnified beauty",
            "defaults": {
                "subject": "insect eye",
                "detail": "compound eye structure",
            },
        },
        {
            "name": "Megacore",
            "template": "Megacore [structure], massive scale, [size comparison], colossal, overwhelming",
            "defaults": {
                "structure": "megastructure",
                "size comparison": "dwarfing mountains",
            },
        },
        {
            "name": "Nanocore",
            "template": "Nanocore [subject], nanoscale, [technology], molecular level, invisible tech",
            "defaults": {
                "subject": "nanobot",
                "technology": "molecular machines",
            },
        },
        {
            "name": "Quantumcore",
            "template": "Quantumcore [visualization], quantum effects, [phenomenon], subatomic, probability",
            "defaults": {
                "visualization": "particle wave",
                "phenomenon": "superposition",
            },
        },
        {
            "name": "Cosmiccore",
            "template": "Cosmiccore [scene], cosmic scale, [celestial objects], universe, vast",
            "defaults": {
                "scene": "galaxy cluster",
                "celestial objects": "nebulae and stars",
            },
        },
        {
            "name": "Atomiccore",
            "template": "Atomiccore [visualization], atomic structure, [elements], electron orbits",
            "defaults": {
                "visualization": "atom model",
                "elements": "protons and electrons",
            },
        },
        {
            "name": "Voidcore",
            "template": "Voidcore [scene], empty void, [elements], nothingness, existential",
            "defaults": {
                "scene": "black void",
                "elements": "single point of light",
            },
        },
        {
            "name": "Fullcore",
            "template": "Fullcore [scene], maximum capacity, [elements], overflowing, abundance",
            "defaults": {
                "scene": "packed venue",
                "elements": "crowd filling space",
            },
        },
        {
            "name": "Emptycore",
            "template": "Emptycore [space], vacant space, [atmosphere], abandoned, hollow",
            "defaults": {
                "space": "empty mall",
                "atmosphere": "eerie silence",
            },
        },
        {
            "name": "Busycore",
            "template": "Busycore [scene], hectic activity, [elements], overwhelming detail, chaos",
            "defaults": {
                "scene": "rush hour",
                "elements": "crowds and traffic",
            },
        },
        {
            "name": "Calmcore",
            "template": "Calmcore [scene], serene atmosphere, [elements], peaceful, tranquil",
            "defaults": {
                "scene": "zen pond",
                "elements": "still water",
            },
        },
        {
            "name": "Loudcore",
            "template": "Loudcore [visual], visual noise, [colors], overwhelming, maximum intensity",
            "defaults": {
                "visual": "concert poster",
                "colors": "neon explosion",
            },
        },
        {
            "name": "Quietcore",
            "template": "Quietcore [scene], visual silence, [elements], subdued, contemplative",
            "defaults": {
                "scene": "empty church",
                "elements": "soft light",
            },
        },
        {
            "name": "Fastcore",
            "template": "Fastcore [subject], speed lines, [motion], velocity, rapid movement",
            "defaults": {
                "subject": "racing car",
                "motion": "motion blur",
            },
        },
        {
            "name": "Slowcore",
            "template": "Slowcore [subject], slow motion, [movement], languid, time stretched",
            "defaults": {
                "subject": "honey dripping",
                "movement": "viscous flow",
            },
        },
        {
            "name": "Hotcore",
            "template": "Hotcore [scene], heat aesthetic, [elements], scorching, thermal",
            "defaults": {
                "scene": "desert heat",
                "elements": "heat waves",
            },
        },
        {
            "name": "Coldcore",
            "template": "Coldcore [scene], freezing aesthetic, [elements], icy, frigid",
            "defaults": {
                "scene": "arctic landscape",
                "elements": "frost and ice",
            },
        },
        {
            "name": "Wetcore",
            "template": "Wetcore [subject], water drops, [surface], moisture, drenched",
            "defaults": {
                "subject": "rain on window",
                "surface": "glass",
            },
        },
        {
            "name": "Drycore",
            "template": "Drycore [landscape], arid aesthetic, [elements], parched, desert",
            "defaults": {
                "landscape": "cracked earth",
                "elements": "drought conditions",
            },
        },
        {
            "name": "Heavycore",
            "template": "Heavycore [object], massive weight, [material], gravity, dense",
            "defaults": {
                "object": "concrete block",
                "material": "solid steel",
            },
        },
        {
            "name": "Feathercore",
            "template": "Feathercore [subject], lightweight, [elements], floating, delicate",
            "defaults": {
                "subject": "feathers",
                "elements": "drifting in air",
            },
        },
        {
            "name": "Thickcore",
            "template": "Thickcore [subject], viscous texture, [consistency], dense, substantial",
            "defaults": {
                "subject": "thick paint",
                "consistency": "impasto technique",
            },
        },
        {
            "name": "Thincore",
            "template": "Thincore [subject], paper-thin, [material], delicate, translucent",
            "defaults": {
                "subject": "rice paper",
                "material": "sheer fabric",
            },
        },
        {
            "name": "Tallcore",
            "template": "Tallcore [structure], extreme height, [perspective], towering, vertical",
            "defaults": {
                "structure": "skyscraper",
                "perspective": "looking up",
            },
        },
        {
            "name": "Shortcore",
            "template": "Shortcore [subject], compressed height, [proportions], squat, low",
            "defaults": {
                "subject": "compressed building",
                "proportions": "wide and short",
            },
        },
        {
            "name": "Widecore",
            "template": "Widecore [scene], panoramic view, [aspect ratio], expansive, horizontal",
            "defaults": {
                "scene": "wide landscape",
                "aspect ratio": "ultra-wide",
            },
        },
        {
            "name": "Narrowcore",
            "template": "Narrowcore [space], confined width, [perspective], compressed, tight",
            "defaults": {
                "space": "narrow alley",
                "perspective": "squeezed view",
            },
        },
        {
            "name": "Deepcore",
            "template": "Deepcore [scene], extreme depth, [perspective], bottomless, profound",
            "defaults": {
                "scene": "ocean trench",
                "perspective": "looking down",
            },
        },
        {
            "name": "Shallowcore",
            "template": "Shallowcore [water/subject], minimal depth, [clarity], surface level",
            "defaults": {
                "water/subject": "shallow pool",
                "clarity": "clear water",
            },
        },
        {
            "name": "Nearcore",
            "template": "Nearcore [subject], extreme proximity, [detail], intimate distance",
            "defaults": {
                "subject": "face close-up",
                "detail": "skin texture visible",
            },
        },
        {
            "name": "Farcore",
            "template": "Farcore [scene], distant view, [elements], remote, horizon",
            "defaults": {
                "scene": "distant mountains",
                "elements": "atmospheric perspective",
            },
        },
        {
            "name": "Insidecore",
            "template": "Insidecore [space], interior view, [atmosphere], enclosed, internal",
            "defaults": {
                "space": "cozy room",
                "atmosphere": "warm interior",
            },
        },
        {
            "name": "Outsidecore",
            "template": "Outsidecore [scene], exterior view, [environment], open air, outdoor",
            "defaults": {
                "scene": "open field",
                "environment": "natural landscape",
            },
        },
        {
            "name": "Abovecore",
            "template": "Abovecore [view], aerial perspective, [height], bird's eye, overhead",
            "defaults": {
                "view": "drone shot",
                "height": "high altitude",
            },
        },
        {
            "name": "Belowcore",
            "template": "Belowcore [perspective], underground view, [depth], subterranean, beneath",
            "defaults": {
                "perspective": "cave system",
                "depth": "deep underground",
            },
        },
        {
            "name": "Frontcore",
            "template": "Frontcore [subject], frontal view, [angle], direct, face-on",
            "defaults": {
                "subject": "building facade",
                "angle": "straight on",
            },
        },
        {
            "name": "Backcore",
            "template": "Backcore [subject], rear view, [perspective], from behind, reverse",
            "defaults": {
                "subject": "person walking away",
                "perspective": "back view",
            },
        },
        {
            "name": "Sidecore",
            "template": "Sidecore [subject], profile view, [angle], lateral, 90 degrees",
            "defaults": {
                "subject": "side profile",
                "angle": "perfect profile",
            },
        },
        {
            "name": "Cornercore",
            "template": "Cornercore [scene], corner perspective, [angle], junction, meeting point",
            "defaults": {
                "scene": "room corner",
                "angle": "corner view",
            },
        },
        {
            "name": "Edgecore",
            "template": "Edgecore [subject], edge focus, [sharpness], boundary, precipice",
            "defaults": {
                "subject": "cliff edge",
                "sharpness": "sharp edge",
            },
        },
        {
            "name": "Centercore",
            "template": "Centercore [composition], central focus, [arrangement], middle, focal point",
            "defaults": {
                "composition": "centered subject",
                "arrangement": "radial symmetry",
            },
        },
        {
            "name": "Bordercore",
            "template": "Bordercore [design], decorative border, [pattern], frame, edge decoration",
            "defaults": {
                "design": "ornate frame",
                "pattern": "repeating motif",
            },
        },
        {
            "name": "Sushi/Foodcore",
            "template": "Japanese food aesthetic, [dish], artistic presentation, [garnish], minimalist plating",
            "defaults": {
                "dish": "sushi platter",
                "garnish": "wasabi and ginger",
            },
        },
        {
            "name": "Shiba inu holding boba",
            "template": "A [mood] shiba inu dog holding [flavor] boba tea with its paws, [setting], [style] style",
            "defaults": {
                "mood": "happy",
                "flavor": "taro",
                "setting": "in a boba shop",
                "style": "kawaii illustration",
            },
        },
        {
            "name": "Blueprint / schematic",
            "template": "Blueprint drawing of [object], white lines on [blueprint color] background, labeled parts: [labels], technical style",
            "defaults": {
                "object": "retro camera",
                "blueprint color": "navy blue",
                "labels": "lens, shutter, viewfinder",
            },
        },
        {
            "name": "Low-poly 3D render",
            "template": "Low-poly 3D render of [subject], pastel colors, simple geometry, soft lighting",
            "defaults": {
                "subject": "small island with palm tree",
            },
        },
        {
            "name": "Cyberpunk cityscape",
            "template": "Neon cyberpunk cityscape at [time of day], rainy streets, reflections, [camera angle] angle, [details]",
            "defaults": {
                "time of day": "night",
                "camera angle": "low angle",
                "details": "neon signs and rain reflections",
            },
        },
    ]
    
    # Try to load from GEMINI.md file if it exists
    if GEMINI_TEMPLATES_PATH.exists():
        try:
            # Parse GEMINI.md for additional templates
            # This is a placeholder - implement actual parsing if needed
            pass
        except Exception:
            pass
    
    return default_templates