"""
Constants for Character Animator puppet generation.

Contains:
- Standard layer naming conventions for Adobe Character Animator
- Viseme generation prompts for AI inpainting
- Body part z-ordering
- MediaPipe landmark indices
"""

from typing import Dict, List, Tuple

# =============================================================================
# Layer Naming Conventions
# =============================================================================

LAYER_NAMES = {
    # Root
    "root": "Character",  # Will be prefixed with +

    # Body parts
    "body": "Body",
    "torso": "Torso",
    "left_arm": "Left Arm",
    "right_arm": "Right Arm",
    "left_leg": "Left Leg",
    "right_leg": "Right Leg",

    # Head group
    "head": "Head",

    # Eyebrows (warp independent)
    "left_eyebrow": "Left Eyebrow",
    "right_eyebrow": "Right Eyebrow",

    # Eye groups
    "left_eye": "Left Eye",
    "right_eye": "Right Eye",
    "left_pupil_range": "Left Pupil Range",  # Eyeball white
    "right_pupil_range": "Right Pupil Range",
    "left_pupil": "Left Pupil",  # Warp independent
    "right_pupil": "Right Pupil",

    # Blink layers
    "left_blink": "Left Blink",
    "right_blink": "Right Blink",

    # Mouth group
    "mouth": "Mouth",
}

# Layers that should have + prefix (warp independently)
WARP_INDEPENDENT_LAYERS = [
    "root",
    "left_eyebrow",
    "right_eyebrow",
    "left_pupil",
    "right_pupil",
]

# =============================================================================
# Viseme Definitions
# =============================================================================

# The 14 required mouth shapes for Character Animator
REQUIRED_VISEMES = [
    "Neutral",
    "Ah",
    "D",
    "Ee",
    "F",
    "L",
    "M",
    "Oh",
    "R",
    "S",
    "Uh",
    "W-Oo",
    "Smile",
    "Surprised",
]

# Optional expressions that can be added
OPTIONAL_EXPRESSIONS = [
    "Angry",
    "Sad",
    "Disgusted",
    "Afraid",
]

# Basic viseme prompts (legacy, kept for backwards compatibility)
VISEME_PROMPTS: Dict[str, str] = {
    "Neutral": "mouth at rest, lips gently together, relaxed expression",
    "Ah": "mouth wide open saying 'ah', jaw dropped, tongue visible",
    "D": "tongue touching behind upper teeth, mouth slightly open, saying 'd' or 't'",
    "Ee": "wide smile with teeth showing, lips pulled back, saying 'ee'",
    "F": "biting lower lip, top teeth visible over lower lip, saying 'f' or 'v'",
    "L": "tongue tip touching roof of mouth behind teeth, mouth slightly open",
    "M": "lips pressed firmly together, closed mouth, saying 'm' or 'b' or 'p'",
    "Oh": "mouth in rounded 'O' shape, lips pursed forward, saying 'oh'",
    "R": "lips slightly pursed and rounded, mouth barely open, saying 'r'",
    "S": "teeth together with slight smile, lips parted, saying 's' or 'z'",
    "Uh": "mouth slightly open, relaxed jaw, neutral lips, saying 'uh'",
    "W-Oo": "lips pursed forward as if whistling, rounded small opening, saying 'w' or 'oo'",
    "Smile": "happy warm smile, teeth may be visible, cheeks raised",
    "Surprised": "mouth wide open in surprise, eyebrows raised, shocked expression",
}

# Enhanced prompts optimized for cloud AI image editing (Gemini/OpenAI)
# These are more detailed and include style preservation instructions
# CRITICAL: Must preserve facial hair (beard, mustache, goatee, stubble, etc.)
AI_VISEME_PROMPTS: Dict[str, str] = {
    "Neutral": (
        "Edit ONLY the mouth to show a relaxed, neutral expression with lips gently together. "
        "CRITICAL: Do NOT modify any facial hair (beard, mustache, goatee, stubble). "
        "Keep skin tone, lighting, art style, and ALL facial features except mouth exactly the same."
    ),
    "Ah": (
        "Edit ONLY the mouth to be wide open as if saying 'AH', with jaw dropped and some tongue visible. "
        "The opening should be tall and rounded. "
        "CRITICAL: Preserve all facial hair (beard, mustache, goatee, stubble) around the mouth exactly as is. "
        "Maintain character's style, skin tone, and all other facial features unchanged."
    ),
    "D": (
        "Edit ONLY the mouth showing tongue tip touching behind upper front teeth, slightly open. "
        "This is the position for 'D', 'T', or 'N' sounds. "
        "CRITICAL: Do NOT remove or modify any facial hair (beard, mustache, goatee, stubble). "
        "Keep all other features identical to the original."
    ),
    "Ee": (
        "Edit ONLY the mouth into a wide smile with teeth visible, lips pulled back horizontally. "
        "This is the wide 'EE' sound position. "
        "CRITICAL: Preserve all facial hair (beard, mustache, goatee, stubble) exactly as shown. "
        "Keep the character's face and all other features unchanged."
    ),
    "F": (
        "Edit ONLY the mouth with top teeth resting on lower lip, as if saying 'F' or 'V'. "
        "The lower lip should be slightly tucked under. "
        "CRITICAL: Do NOT modify any facial hair (beard, mustache, goatee, stubble). "
        "Maintain original colors, style, and all other facial features."
    ),
    "L": (
        "Edit ONLY the mouth slightly open with tongue tip visible touching the roof of mouth. "
        "This is the 'L' sound position. "
        "CRITICAL: Preserve all facial hair (beard, mustache, goatee, stubble) unchanged. "
        "Keep the same art style, proportions, and all other features."
    ),
    "M": (
        "Edit ONLY the mouth with lips firmly pressed together, closed. "
        "This is the position for 'M', 'B', or 'P' sounds. The lips should look natural, not pursed. "
        "CRITICAL: Do NOT remove or modify any facial hair (beard, mustache, goatee, stubble). "
        "Keep all other features exactly the same."
    ),
    "Oh": (
        "Edit ONLY the mouth into a rounded 'O' shape with lips pursed forward. "
        "The opening should be circular. "
        "CRITICAL: Preserve all facial hair (beard, mustache, goatee, stubble) exactly as is. "
        "Maintain the character's style, skin tone, and all other features."
    ),
    "R": (
        "Edit ONLY the mouth slightly pursed and rounded, barely open, as if saying 'R'. "
        "The lips should be relaxed but slightly forward. "
        "CRITICAL: Do NOT modify any facial hair (beard, mustache, goatee, stubble). "
        "Keep original appearance and all other facial features unchanged."
    ),
    "S": (
        "Edit ONLY the mouth with teeth together, slight smile, lips parted. "
        "This is the 'S' or 'Z' sound with visible teeth. "
        "CRITICAL: Preserve all facial hair (beard, mustache, goatee, stubble) exactly. "
        "Keep the art style and all other features identical."
    ),
    "Uh": (
        "Edit ONLY the mouth slightly open with relaxed jaw, neutral lip position. "
        "This is a natural speaking position. "
        "CRITICAL: Do NOT remove or modify any facial hair (beard, mustache, goatee, stubble). "
        "Keep the same skin tone, style, and all other features."
    ),
    "W-Oo": (
        "Edit ONLY the mouth with lips pursed forward like whistling, small rounded opening. "
        "This is the 'W' or 'OO' sound. "
        "CRITICAL: Preserve all facial hair (beard, mustache, goatee, stubble) unchanged. "
        "Maintain character proportions, style, and all other features."
    ),
    "Smile": (
        "Edit ONLY the mouth into a warm, happy smile with raised cheeks. Teeth may be visible. "
        "The expression should look natural and genuine. "
        "CRITICAL: Do NOT modify any facial hair (beard, mustache, goatee, stubble). "
        "Preserve the character's style and all other facial features exactly."
    ),
    "Surprised": (
        "Edit ONLY the mouth wide open in surprise with raised eyebrows and a shocked expression. "
        "The jaw should be dropped significantly. "
        "CRITICAL: Preserve all facial hair (beard, mustache, goatee, stubble) exactly as shown. "
        "Maintain the original art style and all other features."
    ),
}

# Enhanced eye blink prompts for cloud AI editing
AI_EYE_BLINK_PROMPTS: Dict[str, str] = {
    "left_open": (
        "Keep the left eye fully open, alert and natural looking. "
        "Maintain the same eye color, style, and proportions as the original."
    ),
    "left_blink": (
        "Edit the left eye to be fully closed in a natural blink. "
        "The eyelid should cover the eye completely. Keep the skin tone and style consistent."
    ),
    "right_open": (
        "Keep the right eye fully open, alert and natural looking. "
        "Maintain the same eye color, style, and proportions as the original."
    ),
    "right_blink": (
        "Edit the right eye to be fully closed in a natural blink. "
        "The eyelid should cover the eye completely. Keep the skin tone and style consistent."
    ),
}

# Enhanced eyebrow expression prompts for cloud AI editing
AI_EYEBROW_PROMPTS: Dict[str, str] = {
    "raised": (
        "Edit the eyebrows to be raised high, creating a surprised or interested expression. "
        "The forehead may show slight wrinkles. Maintain the original style."
    ),
    "lowered": (
        "Edit the eyebrows to be lowered and furrowed, creating a focused or stern expression. "
        "There may be slight wrinkles between the brows. Keep the original style."
    ),
    "concerned": (
        "Edit the eyebrows to be slightly raised in the middle, creating a worried expression. "
        "This is an asymmetric, concerned look. Maintain the character's style."
    ),
    "angry": (
        "Edit the eyebrows to be sharply angled downward toward the center. "
        "This creates an angry or intense expression. Preserve the original art style."
    ),
    "sad": (
        "Edit the eyebrows to be raised on the inner edges, creating a sad expression. "
        "The outer edges should be lower. Maintain the character's style."
    ),
}

# Style hint templates for different art styles
# These can be appended to prompts when the style is detected or user-specified
STYLE_HINT_TEMPLATES: Dict[str, str] = {
    "cartoon": "Use bold, clean lines and vibrant colors typical of cartoon style.",
    "anime": "Maintain the anime aesthetic with characteristic features and stylization.",
    "realistic": "Keep photorealistic skin texture, lighting, and anatomical accuracy.",
    "pixel_art": "Preserve the pixelated aesthetic with crisp pixel boundaries.",
    "comic": "Maintain comic book style with strong outlines and flat colors.",
    "chibi": "Keep the cute, super-deformed chibi proportions and exaggerated features.",
    "watercolor": "Preserve the soft, flowing watercolor texture and color blending.",
    "3d_render": "Maintain the 3D rendered appearance with proper shading and materials.",
    "sketch": "Keep the hand-drawn sketch appearance with visible pencil/pen strokes.",
    "vector": "Maintain clean vector graphics with smooth curves and flat colors.",
}

# Phoneme to viseme mapping (for lip-sync timing)
PHONEME_TO_VISEME: Dict[str, str] = {
    # Ah sounds
    "AA": "Ah", "AE": "Ah", "AH": "Ah", "AO": "Ah", "AW": "Ah", "AY": "Ah",
    # D/T/N sounds
    "D": "D", "T": "D", "N": "D", "TH": "D", "DH": "D",
    # Ee sounds
    "EH": "Ee", "EY": "Ee", "IH": "Ee", "IY": "Ee",
    # F/V sounds
    "F": "F", "V": "F",
    # L sound
    "L": "L",
    # M/B/P sounds
    "M": "M", "B": "M", "P": "M",
    # Oh sounds
    "OW": "Oh", "OY": "Oh",
    # R sound
    "R": "R", "ER": "R",
    # S/Z sounds
    "S": "S", "Z": "S", "SH": "S", "ZH": "S", "CH": "S", "JH": "S",
    # Uh sounds
    "UH": "Uh",
    # W/OO sounds
    "W": "W-Oo", "UW": "W-Oo", "Y": "W-Oo",
    # Other consonants map to neutral
    "K": "Neutral", "G": "Neutral", "NG": "Neutral", "HH": "Neutral",
}

# =============================================================================
# Eye Blink Prompts
# =============================================================================

EYE_BLINK_PROMPTS: Dict[str, str] = {
    "left_open": "left eye fully open, alert, natural eye appearance",
    "left_blink": "left eye closed, eyelid down, natural blink position",
    "right_open": "right eye fully open, alert, natural eye appearance",
    "right_blink": "right eye closed, eyelid down, natural blink position",
}

# =============================================================================
# Body Part Z-Ordering
# =============================================================================

# Order for layer stacking (higher index = closer to viewer/on top)
BODY_PART_ORDER: List[str] = [
    "left_arm",      # 0 - furthest back
    "torso",         # 1
    "right_arm",     # 2
    "head",          # 3 - closest to viewer
]

# Typical depth ranges for each body part (normalized 0-1)
BODY_PART_DEPTH_RANGES: Dict[str, Tuple[float, float]] = {
    "head": (0.7, 1.0),       # Closest
    "torso": (0.3, 0.7),      # Middle
    "left_arm": (0.0, 0.5),   # Can be behind or in front depending on pose
    "right_arm": (0.0, 0.5),
    "left_leg": (0.0, 0.3),
    "right_leg": (0.0, 0.3),
}

# =============================================================================
# MediaPipe Landmark Indices
# =============================================================================

# MediaPipe Face Mesh landmarks (478 total)
# Key landmark groups for facial feature extraction

# Mouth outline landmarks
MOUTH_LANDMARKS = {
    "outer_upper": [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291],
    "outer_lower": [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291],
    "inner_upper": [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308],
    "inner_lower": [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308],
}

# Eye landmarks
LEFT_EYE_LANDMARKS = {
    "upper": [246, 161, 160, 159, 158, 157, 173],
    "lower": [33, 7, 163, 144, 145, 153, 154, 155, 133],
    "iris": [468, 469, 470, 471, 472],  # Left iris
}

RIGHT_EYE_LANDMARKS = {
    "upper": [466, 388, 387, 386, 385, 384, 398],
    "lower": [263, 249, 390, 373, 374, 380, 381, 382, 362],
    "iris": [473, 474, 475, 476, 477],  # Right iris
}

# Eyebrow landmarks
LEFT_EYEBROW_LANDMARKS = [276, 283, 282, 295, 285, 300, 293, 334, 296, 336]
RIGHT_EYEBROW_LANDMARKS = [46, 53, 52, 65, 55, 70, 63, 105, 66, 107]

# Face oval for head segmentation
FACE_OVAL_LANDMARKS = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379,
    378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127,
    162, 21, 54, 103, 67, 109
]

# Nose landmarks
NOSE_LANDMARKS = {
    "bridge": [6, 197, 195, 5, 4],
    "tip": [1, 2, 98, 327],
    "nostrils": [129, 358, 278, 48],
}

# =============================================================================
# MediaPipe Pose Landmarks
# =============================================================================

# MediaPipe Pose landmarks (33 total)
POSE_LANDMARK_INDICES = {
    "nose": 0,
    "left_eye_inner": 1,
    "left_eye": 2,
    "left_eye_outer": 3,
    "right_eye_inner": 4,
    "right_eye": 5,
    "right_eye_outer": 6,
    "left_ear": 7,
    "right_ear": 8,
    "mouth_left": 9,
    "mouth_right": 10,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_pinky": 17,
    "right_pinky": 18,
    "left_index": 19,
    "right_index": 20,
    "left_thumb": 21,
    "right_thumb": 22,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
    "left_heel": 29,
    "right_heel": 30,
    "left_foot_index": 31,
    "right_foot_index": 32,
}

# Connections for drawing skeleton
POSE_CONNECTIONS = [
    # Face
    (0, 1), (1, 2), (2, 3), (3, 7),  # Left eye to left ear
    (0, 4), (4, 5), (5, 6), (6, 8),  # Right eye to right ear
    (9, 10),  # Mouth

    # Upper body
    (11, 12),  # Shoulders
    (11, 13), (13, 15),  # Left arm
    (12, 14), (14, 16),  # Right arm
    (11, 23), (12, 24),  # Torso sides
    (23, 24),  # Hips

    # Hands
    (15, 17), (15, 19), (15, 21),  # Left hand
    (16, 18), (16, 20), (16, 22),  # Right hand

    # Lower body
    (23, 25), (25, 27), (27, 29), (27, 31),  # Left leg
    (24, 26), (26, 28), (28, 30), (28, 32),  # Right leg
]

# =============================================================================
# AI Model Settings
# =============================================================================

# Note: Local SD inpainting, SAM, and depth estimation defaults removed.
# Viseme generation now uses cloud AI (Gemini/OpenAI) - see AIFaceEditor.
# SAM 2 settings are now in the segmenter module where they're used.

# =============================================================================
# Export Settings
# =============================================================================

# PSD export settings
PSD_SETTINGS = {
    "color_mode": "rgba",
    "depth": 8,  # bits per channel
}

# SVG export settings
SVG_SETTINGS = {
    "embed_images": True,  # Embed raster images as base64
    "vectorize": False,    # Convert to vector paths (slower, not always better)
}

# Default canvas size for Character Animator
DEFAULT_CANVAS_SIZE = (2048, 2048)

# Minimum region sizes (in pixels) for detection
MIN_REGION_SIZES = {
    "head": 100,
    "body": 200,
    "arm": 50,
    "eye": 20,
    "mouth": 30,
    "eyebrow": 15,
}
