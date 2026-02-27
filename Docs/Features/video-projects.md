# Video Projects

## Overview

The Video Project tab lets you create AI-powered music videos, lyric videos, and animated slideshows from text. Write or paste your lyrics or script, set scene durations and images, and export a finished video with karaoke overlays, transitions, and optional AI motion.

## Features

### Creating and Managing Projects

Each video is saved as a project file (JSON). Projects store your scenes, images, timings, and settings.

- Click New Project to start fresh.
- Click Open to load an existing project file.
- Click Save (or use Ctrl+S) to save changes.
- Auto-save runs after every generation operation so you never lose work.

Projects support full version history with time-travel restoration — you can go back to any earlier state of your project.

### Writing Your Script or Lyrics

Paste text into the script area. ImageAI supports three input formats:

| Format | Example | What Happens |
|--------|---------|-------------|
| Timestamped lyrics | `[00:30] First verse lyrics` | Scene starts at that timestamp |
| Section headings | `# Verse 1`, `# Chorus`, `# Bridge` | One scene per section |
| Plain text | Any paragraph | Automatic scene detection |

You can also add custom scene markers anywhere in the text for precise control over where scenes split.

### Storyboard and Scene Editor

After parsing your script, each scene appears as a row in the interactive scene table.

- Click any cell to edit the prompt or timing directly.
- Drag rows to reorder scenes.
- Set duration per scene from 0.5 to 30 seconds.
- Select multiple rows to apply batch operations (delete, duplicate, reset timing).

Each scene can have an independently generated image or a chosen image from your library.

### AI Image Generation for Scenes

Click Generate Images on one scene or all scenes to create visuals automatically:

1. ImageAI uses the scene text as the prompt.
2. You can prepend a global style prompt (applied to every scene) to keep visual consistency.
3. Generated images appear in the storyboard preview.
4. Replace any image by right-clicking its cell and choosing Select Image.

### Rendering Options

#### FFmpeg Slideshow

Renders your storyboard into a polished video without AI motion.

- Ken Burns effects: gentle pan and zoom to add life to still images.
- Transitions: crossfade, fade to black, cut.
- Resolution: up to 4K (3840x2160).
- Frame rates: 24, 30, or 60 fps.
- Add an audio track (MP3, WAV, M4A, OGG) that plays under the video.

#### Google Veo 3.0 / 3.1 (AI Motion Video)

Renders each scene as a short AI-generated motion clip, then stitches them together.

- Automatic frame continuity: the last frame of each scene feeds into the next, keeping subjects visually consistent.
- Duration per clip: set individually per scene.
- Combine rendered Veo clips with karaoke overlays in a single export.

### MIDI Synchronization

Import a MIDI file (.mid) to synchronize your scenes to the beat of a song.

- Musical structure is auto-detected: verse, chorus, bridge, intro, outro.
- Scenes are timed to beat boundaries or measure boundaries.
- Fine-tune offsets if scenes drift from the music.

### Karaoke Overlays

Add on-screen lyrics synchronized to your audio.

Choose an overlay style:

| Style | Description |
|-------|-------------|
| Bouncing Ball | A ball bounces over each syllable as it plays |
| Highlighting | Words change color as they are sung |
| Fade-in | Each line fades in at its start time |

**Subtitle Export Formats:**
Export your timed lyrics as standard subtitle files:
- LRC — for music players and karaoke machines
- SRT — for video players and YouTube
- ASS — for advanced styling in video editors

### Suno Package Import

If you have a Suno audio package (with separated stems), import it directly:

1. Click Import Suno Package.
2. Select the package folder.
3. ImageAI merges the stems (vocals, instruments) into a combined audio track.
4. The combined audio is attached to your video project automatically.

### Lipsync (MuseTalk)

Optional AI lipsync for character videos using MuseTalk:

- Installs automatically on first use (~8-12 GB download).
- Syncs a character face to your audio.
- Works alongside the Character Animator workflow.

## Common Questions

**Q: Do I need FFmpeg installed?**
Yes — FFmpeg must be installed on your system for video rendering. On first render, ImageAI will tell you if FFmpeg is missing and how to install it.

**Q: How long does Veo rendering take?**
Each Veo clip takes 1–3 minutes to generate in Google's cloud. A 10-scene video could take 10–30 minutes. FFmpeg slideshow rendering is near-instant.

**Q: Can I add a background music track to a Veo video?**
Yes — after Veo clips are generated, you can add an audio track in the render settings and it will be mixed into the final export.

**Q: My scenes split in the wrong places. How do I fix it?**
Switch to the scene table and drag rows to reorder, or merge two scenes by deleting one row and extending the adjacent duration. You can also add or remove scene markers in your script and re-parse.

**Q: What video formats does ImageAI export?**
MP4 (H.264), AVI, and MOV.
