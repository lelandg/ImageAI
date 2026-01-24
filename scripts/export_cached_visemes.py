#!/usr/bin/env python3
"""
Manual export script for cached Character Animator visemes.

Usage:
    python scripts/export_cached_visemes.py [output_folder]

If no output folder is specified, creates 'exported_puppet' in the cache folder.
"""

import sys
import shutil
from pathlib import Path
from PIL import Image

# Cache directory
CACHE_DIR = Path(__file__).parent.parent / "cache" / "visemes"

# Character Animator viseme names (in order)
VISEME_ORDER = [
    "Neutral", "Ah", "D", "Ee", "F", "L", "M",
    "Oh", "R", "S", "Uh", "W-Oo", "Smile", "Surprised"
]


def find_latest_viseme_set(cache_dir: Path) -> dict:
    """Find the most recent set of visemes in the cache."""
    if not cache_dir.exists():
        print(f"Cache directory not found: {cache_dir}")
        return {}

    # Get all cached files
    files = list(cache_dir.glob("*_mouth_*.png"))
    if not files:
        print("No cached visemes found")
        return {}

    # Group by hash prefix
    hash_groups = {}
    for f in files:
        parts = f.stem.split("_mouth_")
        if len(parts) == 2:
            hash_prefix, viseme_name = parts
            if hash_prefix not in hash_groups:
                hash_groups[hash_prefix] = {}
            hash_groups[hash_prefix][viseme_name] = f

    # Find the group with most visemes (and most recent)
    best_hash = None
    best_count = 0
    best_time = 0

    for hash_prefix, visemes in hash_groups.items():
        count = len(visemes)
        # Get newest file time in this group
        newest = max(f.stat().st_mtime for f in visemes.values())

        if count > best_count or (count == best_count and newest > best_time):
            best_hash = hash_prefix
            best_count = count
            best_time = newest

    if best_hash:
        print(f"Found {best_count} visemes with hash {best_hash}")
        return hash_groups[best_hash]

    return {}


def export_visemes(visemes: dict, output_dir: Path, create_psd: bool = True):
    """Export visemes to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectory for mouth visemes
    mouth_dir = output_dir / "Mouth"
    mouth_dir.mkdir(exist_ok=True)

    exported = []
    for viseme_name in VISEME_ORDER:
        if viseme_name in visemes:
            src = visemes[viseme_name]
            # Use clean names for Character Animator
            dst = mouth_dir / f"{viseme_name}.png"
            shutil.copy2(src, dst)
            exported.append(viseme_name)
            print(f"  Exported: {viseme_name}")

    print(f"\nExported {len(exported)} visemes to {mouth_dir}")

    # Create a simple manifest
    manifest_path = output_dir / "manifest.txt"
    with open(manifest_path, "w") as f:
        f.write("Character Animator Puppet Export\n")
        f.write("=" * 40 + "\n\n")
        f.write("Mouth Visemes:\n")
        for name in exported:
            f.write(f"  - {name}\n")
        f.write(f"\nTotal: {len(exported)} visemes\n")
        f.write("\nTo use in Character Animator:\n")
        f.write("1. Import the Mouth folder as a layer group\n")
        f.write("2. Set each viseme layer to the corresponding mouth shape\n")
        f.write("3. Use Neutral as the default/rest position\n")

    print(f"Created manifest: {manifest_path}")

    # Try to create PSD if requested
    if create_psd:
        try:
            create_simple_psd(visemes, output_dir)
        except Exception as e:
            print(f"PSD creation failed (non-critical): {e}")

    return exported


def create_simple_psd(visemes: dict, output_dir: Path):
    """Create a simple layered PSD from visemes."""
    try:
        # Try using psd-tools or photoshop-connection
        from psd_tools import PSDImage
        print("PSD export via psd-tools not fully supported for creation")
    except ImportError:
        pass

    # Create a combined preview image instead
    preview_path = output_dir / "preview_all_visemes.png"

    images = []
    for name in VISEME_ORDER:
        if name in visemes:
            img = Image.open(visemes[name])
            # Resize for preview
            img.thumbnail((256, 256), Image.Resampling.LANCZOS)
            images.append((name, img))

    if not images:
        return

    # Create grid
    cols = 4
    rows = (len(images) + cols - 1) // cols
    cell_w, cell_h = 280, 300  # Extra space for labels

    preview = Image.new("RGBA", (cols * cell_w, rows * cell_h), (40, 40, 40, 255))

    for i, (name, img) in enumerate(images):
        col = i % cols
        row = i // cols
        x = col * cell_w + (cell_w - img.width) // 2
        y = row * cell_h + 20
        preview.paste(img, (x, y))

    preview.save(preview_path)
    print(f"Created preview grid: {preview_path}")


def main():
    # Determine output directory
    if len(sys.argv) > 1:
        output_dir = Path(sys.argv[1])
    else:
        output_dir = CACHE_DIR.parent / "exported_puppet"

    print("Character Animator Viseme Export")
    print("=" * 40)
    print(f"Cache directory: {CACHE_DIR}")
    print(f"Output directory: {output_dir}")
    print()

    # Find visemes
    visemes = find_latest_viseme_set(CACHE_DIR)
    if not visemes:
        print("No visemes to export")
        return 1

    # Export
    exported = export_visemes(visemes, output_dir)

    if exported:
        print(f"\nSuccess! Exported to: {output_dir}")
        return 0
    else:
        print("\nExport failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
