# ImageAI Utilities

This directory contains utility scripts for managing and analyzing ImageAI data.

## update_history_from_logs.py

Automatically scans all log files and updates image metadata sidecar files with reference image information.

**Purpose:**
- Retroactively add reference image data to metadata for images generated before tracking was implemented
- Run automatically without user input
- Keep history tab data complete

**Usage:**
```bash
python utils/update_history_from_logs.py
```

**What it does:**
1. Scans all log files for explicit reference->image mappings
2. Scans config files and backups for reference images that were used
3. Scans video project files for global reference images
4. Correlates generated images with reference images by timestamp (24-hour window)
5. Updates metadata sidecar JSON files to include reference data
6. Skips files that already have reference data (safe to run multiple times)

**Output:**
```
Scanning for reference images...
  Found 0 images with references in logs
  Found 0 reference images in config files
  Found 5 reference images in video projects
  Found 44 images with timestamp-correlated references

Total images with references: 44
Updating metadata files...

Completed:
  Updated: 26
  Skipped: 18
```

## How Reference Images Work

Reference images in ImageAI are stored in metadata sidecar JSON files:

### Single Reference (Legacy)
```json
{
  "prompt": "A sunset landscape",
  "provider": "google",
  "reference_image": "/path/to/reference.png"
}
```

### Multi-Reference (Imagen 3)
```json
{
  "prompt": "A sunset landscape",
  "provider": "google",
  "imagen_references": {
    "references": [
      {
        "path": "/path/to/ref1.png",
        "type": "SUBJECT",
        "description": "Character design"
      },
      {
        "path": "/path/to/ref2.png",
        "type": "STYLE",
        "description": "Art style"
      }
    ]
  }
}
```

## Directory Locations

The script automatically detects the correct directories:
- **Logs**: `{AppData}/ImageAI/logs/` (Windows) or `~/.config/ImageAI/logs/` (Linux/Mac)
- **Generated Images**: `{AppData}/ImageAI/generated/` (Windows) or `~/.config/ImageAI/generated/` (Linux/Mac)
- **WSL Support**: Automatically uses Windows paths when running in WSL

## Notes

- Safe to run multiple times (skips already-updated files)
- No command-line arguments needed
- Minimal output (only shows when references are found and updated)
- Uses the same paths as the main ImageAI application
