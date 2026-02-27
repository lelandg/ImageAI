# Character Animator Puppet Creation

## Overview

The Character Animator tab converts a single character image into a fully rigged puppet ready for import into Adobe Character Animator. AI automatically segments body parts, generates lip-sync mouth shapes, and exports everything in PSD or SVG format with Adobe-compatible layer naming.

## Features

### How It Works

The wizard guides you through five steps. Heavy AI components (~8-12 GB) are downloaded on first use and cached for future sessions.

### Step 1 — Dependency Check

Before anything else, ImageAI checks whether the required AI components are installed:

- MediaPipe Pose and Face models
- SAM 2 (Segment Anything Model 2) for body segmentation

If any are missing, click Install and ImageAI handles the download automatically. You only need to do this once.

### Step 2 — Image Selection

Load your character image:

- Supported formats: PNG, JPEG, WebP.
- The character should be front-facing with arms visible.
- The panel shows a preview and guidance notes about optimal image requirements (clear background, visible hands, etc.).

### Step 3 — Body Part Detection

AI analyzes your image and draws bounding boxes around detected body parts:

- Head / face
- Torso
- Left arm and right arm
- Left hand and right hand
- Left leg and right leg (if visible)

You can adjust any bounding box by dragging its edges. If a body part was not detected, you can draw a box manually.

### Step 4 — Viseme Generation

ImageAI generates 14 mouth shapes (visemes) for natural lip-sync animation:

| Viseme | Sound Example |
|--------|--------------|
| Neutral | Silence |
| Ah | "f**a**ther" |
| D | "**d**og", "**t**op" |
| Ee | "s**ee**" |
| F | "**f**ish", "**v**an" |
| L | "**l**ight" |
| M | "**m**ap", "**b**ig", "**p**et" |
| Oh | "**o**pen" |
| R | "**r**ed" |
| S | "**s**un", "**z**oo" |
| Uh | "**u**p" |
| W-Oo | "**w**oo" |
| Smile | General smile expression |
| Surprised | Open-mouthed surprise |

Visemes are generated using your cloud AI provider (Google Gemini or OpenAI). Select your provider and see the cost estimate before generating.

Eye blinks are also created automatically for natural-looking animation.

Results are cached — if you need to regenerate the same character, previously generated visemes are reused without additional API cost.

### Step 5 — Export

Choose your export format:

#### PSD (Photoshop Document)

Best for photorealistic puppets.

- Full Adobe Character Animator layer hierarchy.
- Layer names match Adobe's expected naming convention automatically.
- Includes all body part layers and mouth shape states.

#### SVG (Scalable Vector Graphics)

Best for cartoon or flat illustration styles.

- Vector-based layers scale to any size without quality loss.
- Compatible with Adobe Character Animator's SVG puppet workflow.

After export, open the PSD or SVG in Adobe Character Animator using File > Import.

## Common Questions

**Q: How long does Step 3 (body part detection) take?**
Detection runs locally on your CPU or GPU and typically takes 10–60 seconds depending on your hardware and image complexity.

**Q: The AI did not detect my character's hands correctly. Can I fix it?**
Yes — drag the existing bounding box to adjust, or draw a new box over the area. Manual corrections are fully supported before proceeding to Step 4.

**Q: Can I use a character with a transparent background?**
Yes — PNG images with transparency work well and typically give better segmentation results.

**Q: Do I need an Adobe subscription to use the exported puppet?**
You need Adobe Character Animator to use the exported PSD or SVG. ImageAI only creates the puppet file — animation is done in Adobe's software.

**Q: What happens if I close the wizard mid-way?**
Progress is saved through the wizard steps. You can reopen the Character Animator tab and continue from where you left off for the same image.

**Q: Which AI provider should I choose for viseme generation?**
Both Google Gemini and OpenAI produce good results. Gemini is generally less expensive per character. The cost estimate is shown before you confirm generation.
