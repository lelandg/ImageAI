# Suno Package Support

**Version:** 1.0
**Added in:** ImageAI v0.27.0 (planned)
**Status:** ✅ Implemented

## Overview

ImageAI's Video Project now supports importing multi-file Suno packages (stem exports) directly into your projects. When you export audio and MIDI from Suno with individual stems, you can import the entire zip file and select which stems to merge.

## What is a Suno Package?

When you download from Suno.ai with the following options:
- **Individual stems** (Vocals, Drums, Bass, Guitar, FX, Backing Vocals, Synth, etc.)
- **MIDI files** for each stem
- **Export as zip** (multiple files)

You get a zip file containing:
- 7 audio stems (`.wav` files)
- 7 matching MIDI files (`.mid` files)

Example: `Ice Ice Baby (Heavy Metal Reprisal) v2-2 Stems.zip`

## Features

### Automatic Detection
- Drop a `.zip` file into the Audio or MIDI file browser
- ImageAI automatically detects if it's a Suno package
- Shows preprocessing dialog with all available stems

### Stem Selection
- All stems are selected by default
- Uncheck any stems you don't want in the final mix
- Separate selection for audio stems and MIDI files

### Audio Merging
- Merges selected stems into a single audio file using FFmpeg
- All stems mixed at equal volume (1.0)
- Output: `{package_name}_merged.wav` in project's `suno_imports/` directory
- **Important:** Do volume mixing in Suno before export

### MIDI Merging
- Merges selected MIDI files into a single multi-track MIDI file
- Each stem becomes a separate track with its name preserved
- Tempo and time signature from first MIDI file used as master
- Output: `{package_name}_merged.mid` in project's `suno_imports/` directory

### Project Integration
- Merged files stored in `project_dir/suno_imports/`
- Original zip path saved for potential re-import
- Selected stems saved in project file for reference
- Fully integrated with existing audio/MIDI workflow

## How to Use

### Method 1: Import via Audio Browser

1. Click **Browse Audio** button in Video Project tab
2. Select your Suno package `.zip` file
3. Preprocessing dialog opens automatically
4. Select which audio stems to include
5. Click **Preprocess & Merge**
6. Merged audio becomes your project's audio track

### Method 2: Import via MIDI Browser

1. Click **Browse MIDI** button in Video Project tab
2. Select your Suno package `.zip` file
3. Preprocessing dialog opens automatically
4. Select which MIDI files to include
5. Click **Preprocess & Merge**
6. Merged MIDI becomes your project's MIDI track

### Method 3: Import Both at Once

When you import a Suno package that contains both audio and MIDI:
- First import via Audio browser → gets audio stems
- Then import the same zip via MIDI browser → gets MIDI files
- Or vice versa (order doesn't matter)

## Volume Mixing

**CRITICAL:** Volume mixing should be done in Suno **before** exporting the package.

ImageAI merges all selected stems at **equal volume (1.0)**. If you need:
- Louder vocals
- Quieter drums
- Different instrument balance

**Adjust these in Suno's mixer before exporting!**

This design decision keeps the workflow simple and ensures you have full control over the final mix using Suno's professional mixing tools.

## File Locations

### Merged Files
```
project_dir/
└── suno_imports/
    ├── Ice Ice Baby_merged.wav    # Merged audio
    └── Ice Ice Baby_merged.mid    # Merged MIDI
```

### Original Package
The original `.zip` file path is saved in the project so you can:
- See which package was used
- Re-import with different stem selection (future feature)

## Supported Stem Names

ImageAI recognizes the following stem names (case-insensitive):
- Vocals
- Drums
- Bass
- Guitar
- Synth / Synthesizer
- Piano / Keys
- Strings
- Brass
- FX / Effects
- Backing Vocals
- Lead
- Rhythm
- Percussion

Files must follow Suno's naming pattern:
```
Song Name (Stem Name).wav
Song Name (Stem Name).mid
```

Example: `Ice Ice Baby (Heavy Metal) v2-2 (Vocals).wav`

## Dependencies

### Required (already in ImageAI)
- Python `zipfile` (standard library)
- `pathlib` (standard library)

### Optional (for merging)
- **FFmpeg** - Required for audio stem merging
  - Download: https://ffmpeg.org/download.html
  - Must be in system PATH
  - Used for: Combining multiple audio files into one

- **mido** - Required for MIDI merging
  - Install: `pip install mido`
  - Used for: Combining multiple MIDI files into multi-track MIDI

**Note:** If dependencies are missing, you'll get a clear error message with instructions to install them.

## Preprocessing Dialog

When a Suno package is detected, you see:

```
┌─ Suno Package Detected ─────────────────────┐
│                                              │
│ Found Suno package: Ice Ice Baby.zip        │
│ Audio stems: 7 | MIDI files: 7              │
│                                              │
│ Select which stems and MIDI files to        │
│ include in the merge. All items selected    │
│ by default.                                  │
│                                              │
│ Note: For custom volume mixing, adjust      │
│ stem volumes in Suno before exporting.      │
│                                              │
│ ┌─ Audio Stems ─────────────────────────┐  │
│ │ ☑ Backing Vocals                      │  │
│ │ ☑ Bass                                │  │
│ │ ☑ Drums                               │  │
│ │ ☑ FX                                  │  │
│ │ ☑ Guitar                              │  │
│ │ ☑ Synth                               │  │
│ │ ☑ Vocals                              │  │
│ └───────────────────────────────────────┘  │
│                                              │
│ ┌─ MIDI Files ──────────────────────────┐  │
│ │ ☑ Backing Vocals                      │  │
│ │ ☑ Bass                                │  │
│ │ ☑ Drums                               │  │
│ │ ☑ FX                                  │  │
│ │ ☑ Guitar                              │  │
│ │ ☑ Synth                               │  │
│ │ ☑ Vocals                              │  │
│ └───────────────────────────────────────┘  │
│                                              │
│ [Select All] [Deselect All]                 │
│                                              │
│ [Preprocess & Merge]  [Cancel]              │
└──────────────────────────────────────────────┘
```

## Technical Details

### Audio Merge Command
Using FFmpeg's `amix` filter:
```bash
ffmpeg -i vocals.wav -i drums.wav -i bass.wav \
       -filter_complex "[0:a][1:a][2:a]amix=inputs=3:duration=longest" \
       -ac 2 merged.wav
```

### MIDI Merge Process
Using Python `mido` library:
1. Create new MidiFile
2. Track 0: Tempo map (from first MIDI)
3. Tracks 1-N: Each stem as separate track
4. Preserve original track names
5. Sync all to same tempo/time signature

### Project File Schema
```json
{
  "suno_package": {
    "package_path": "/path/to/Ice Ice Baby.zip",
    "selected_stems": ["Vocals", "Drums", "Bass", "Guitar"],
    "selected_midi": ["Vocals", "Drums", "Bass"]
  }
}
```

## Error Handling

### Invalid Package
- **Error:** "Not a valid Suno package"
- **Cause:** Zip doesn't contain recognizable stem files
- **Solution:** Ensure files follow Suno naming convention

### Missing FFmpeg
- **Error:** "ffmpeg not found"
- **Cause:** FFmpeg not installed or not in PATH
- **Solution:** Install FFmpeg and add to system PATH

### Missing mido
- **Error:** "mido library not found"
- **Cause:** mido not installed in Python environment
- **Solution:** Run `pip install mido`

### Merge Failure
- **Error:** "Failed to merge audio/MIDI"
- **Cause:** Corrupted files or incompatible formats
- **Solution:** Check logs, verify original package integrity

## Future Enhancements

Potential features for future versions:

### Re-merge Capability
- Button to re-open preprocessing dialog
- Adjust stem selection without re-importing
- Uses saved package path

### Stem Volume Controls
- Individual volume sliders per stem in dialog
- Live preview before merging
- Save volume settings in project

### Advanced Options
- Custom output format (FLAC, MP3, etc.)
- Normalization options
- Audio effects per stem

## Code References

- **Detection:** `core/video/suno_package.py:79` - `detect_suno_package()`
- **Audio Merge:** `core/video/suno_package.py:137` - `merge_audio_stems()`
- **MIDI Merge:** `core/video/suno_package.py:225` - `merge_midi_files()`
- **UI Dialog:** `gui/video/suno_preprocess_dialog.py:24` - `SunoPreprocessDialog`
- **Integration:** `gui/video/workspace_widget.py:5899` - `_import_suno_package()`

## Testing

Tested with:
- **Sample:** `Ice Ice Baby (Heavy Metal Reprisal) v2-2 Stems.zip`
- **Stems:** 7 audio + 7 MIDI
- **Results:**
  - ✅ Detection successful
  - ✅ Stem extraction working
  - ✅ MIDI merge logic correct
  - ⚠️ Audio merge requires FFmpeg (not in WSL test env)

## Troubleshooting

**Q: Why don't I see volume sliders?**
A: By design. Do volume mixing in Suno before export for professional results.

**Q: Can I import just audio or just MIDI?**
A: Yes! Use the appropriate browser button. The dialog only shows what's available in the package.

**Q: Where are the merged files stored?**
A: In `project_dir/suno_imports/` - they're part of your project.

**Q: Can I use different packages for audio and MIDI?**
A: Yes, but not recommended. Better to use one package for consistency.

**Q: Does this work with non-Suno files?**
A: Only if they follow Suno's naming convention: `Song (StemName).wav`

**Q: I see warnings about "invalid key signature" in the logs. Is this a problem?**
A: No! Suno sometimes generates MIDI files with invalid key signature metadata (e.g., "19 sharps"). ImageAI automatically skips this invalid metadata while preserving all the actual note data. Your merged MIDI will play correctly. The key signature is just metadata and can be set manually in your DAW if needed.

## Known Issues

### Invalid Key Signatures in Suno MIDI Files

**Issue:** Suno-generated MIDI files sometimes contain invalid key signature metadata (e.g., 19 sharps, which is impossible in music theory).

**Impact:** None - ImageAI automatically handles this.

**How it works:**
- ImageAI skips invalid key signature metadata
- All note data is preserved correctly
- Tempo and time signature are kept
- Merged MIDI plays normally

**What you'll see:**
- Warning in logs: `"Skipping X - MIDI error: Could not decode key with 19 sharps"`
- Import succeeds normally
- Merged MIDI works perfectly

**If you need key signature:**
- Set it manually in your DAW after import
- Or edit the MIDI in your DAW to add proper key signature

**Technical details:** See `BUGFIX_suno_midi_key_signature.md` for full analysis.

---

**Last Updated:** 2025-01-16
**Author:** Claude Code Assistant
**Status:** Ready for testing in PowerShell environment with FFmpeg and mido installed
