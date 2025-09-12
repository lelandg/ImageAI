# MIDI Synchronization & Karaoke Features

## Overview
ImageAI now supports MIDI-based synchronization and karaoke overlays for video projects! This enables perfect beat/measure alignment for scene transitions and professional karaoke-style lyric displays.

## New Features

### 🎵 MIDI Synchronization
- **Beat Grid Alignment**: Automatically snap scene transitions to MIDI beats, measures, or musical sections
- **Tempo-Aware Pacing**: Scene durations adapt to the song's tempo and time signature
- **Musical Structure Detection**: Identify verses, choruses, bridges from MIDI data
- **Frame-Accurate Sync**: Leverage MIDI's precise timing for professional results

### 🎤 Karaoke Overlays
- **Multiple Styles**: Bouncing ball, word highlighting, or fade-in effects
- **Export Formats**: Generate LRC, SRT, and ASS subtitle files
- **Customizable Appearance**: Adjust font size, position, colors
- **Word-Level Timing**: Extract timing from MIDI lyric events or align text to beats

### 🎬 Enhanced Video Features
- **Audio Track Support**: Link to MP3, WAV, M4A files without copying
- **Volume & Fade Controls**: Adjust audio levels and add fade in/out
- **Ken Burns Effects**: Automatic pan/zoom on still images
- **Smooth Transitions**: Crossfades between scenes

## How to Use

### In the GUI

1. **Open Video Project Tab**
   - Click on the "🎬 Video Project" tab

2. **Load Your Files**
   - **Audio**: Click "Browse..." next to Audio to select your song file
   - **MIDI**: Click "Browse..." next to MIDI to select your MIDI file
   - The UI will display tempo, time signature, and duration

3. **Configure Synchronization**
   - **Sync Mode**: Choose None, Beat, Measure, or Section
   - **Snap Strength**: Adjust how strongly scenes snap to the grid (0-100%)
   - **Extract Lyrics**: Click to pull lyrics from MIDI or align your text

4. **Enable Karaoke** (Optional)
   - Check "Karaoke Options" box
   - Select style: Bouncing Ball, Highlight, or Fade In
   - Choose position: Bottom, Top, or Center
   - Set font size (16-72)
   - Select export formats: LRC, SRT, ASS

5. **Generate Storyboard**
   - Enter or paste your lyrics/text
   - Click "Generate Storyboard"
   - Scenes will automatically align to MIDI timing

6. **Generate & Export**
   - Click "Generate Images" to create visuals
   - Click "Render Video" to create the final video
   - Karaoke files will be exported to a "lyrics" subfolder

### From Command Line

```bash
# Basic MIDI-synchronized video
python main.py video --in lyrics.txt --midi song.mid --audio song.mp3 \
  --sync-mode measure --snap-strength 0.9 \
  --out video.mp4

# With karaoke overlay
python main.py video --in lyrics.txt --midi song.mid --audio song.mp3 \
  --karaoke --karaoke-style bouncing_ball \
  --export-lrc --export-srt \
  --out karaoke_video.mp4
```

## Testing

Run the test script to verify everything works:

```bash
python test_midi_sync.py
```

This will test:
- MIDI file processing
- Lyric alignment to beats
- LRC/SRT generation
- Scene-to-beat synchronization

## Dependencies

The following packages are required for MIDI support:
- `pretty-midi>=0.2.10` - High-level MIDI analysis
- `mido>=1.3.0` - Low-level MIDI manipulation

Install with:
```bash
pip install pretty-midi mido
```

## File Formats

### Input
- **Audio**: MP3, WAV, M4A, OGG, FLAC, AAC
- **MIDI**: .mid, .midi files
- **Lyrics**: Plain text, timestamped [mm:ss], or structured (# Verse)

### Output
- **Video**: MP4 (H.264/AAC)
- **Lyrics**: 
  - LRC (standard karaoke format)
  - SRT (subtitle format)
  - ASS (advanced styling)

## Tips

1. **Best Results with AI Song Generators**
   - Services like aisonggenerator.ai provide both audio and MIDI
   - MIDI contains exact timing for perfect synchronization

2. **Lyric Alignment**
   - If MIDI has embedded lyrics, they'll be extracted automatically
   - Otherwise, your text will be aligned to beats/measures

3. **Scene Duration**
   - With "Measure" sync, scenes align to musical bars
   - With "Beat" sync, scenes can change on any beat
   - Adjust snap strength for more/less strict alignment

4. **Karaoke Styles**
   - Bouncing Ball: Classic karaoke style
   - Highlight: Words light up when sung
   - Fade In: Words appear gradually

## Architecture

### New Modules
- `core/video/midi_processor.py` - MIDI timing extraction
- `core/video/karaoke_renderer.py` - Karaoke overlay generation
- Updated `VideoProject` model with MIDI/karaoke fields
- Enhanced `StoryboardGenerator` with sync support
- Extended `FFmpegRenderer` for karaoke overlays

### Data Flow
1. MIDI file → Extract tempo, beats, measures, lyrics
2. Lyrics/text → Parse and align to MIDI timing
3. Scenes → Snap durations to musical boundaries
4. Images → Generate aligned to scene timing
5. Video → Render with optional karaoke overlay
6. Export → Generate LRC/SRT files

## Troubleshooting

**MIDI not loading**: Ensure pretty-midi and mido are installed
**No lyrics in MIDI**: Enter text manually - it will align to beats
**Sync not working**: Check that MIDI file is valid and sync mode is enabled
**Karaoke not showing**: Verify karaoke options are checked and MIDI is loaded

## Future Enhancements

Planned improvements:
- Beat detection from audio (without MIDI)
- Phoneme-level alignment for precise word timing
- Custom karaoke animations and effects
- Multi-track timeline with separate lyric layers
- Sheet music overlay support
- Real-time preview with synchronized playback

---

Enjoy creating perfectly synchronized music videos with karaoke! 🎵🎬