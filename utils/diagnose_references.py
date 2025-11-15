"""Diagnose reference image usage in generated images."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import ConfigManager

config = ConfigManager()
generated_dir = config.config_dir / 'generated'

print("=" * 70)
print("REFERENCE IMAGE DIAGNOSTIC")
print("=" * 70)

# Check how many images already have reference data
images_with_refs = 0
images_without_refs = 0
images_no_metadata = 0

png_files = list(generated_dir.glob('*.png'))
print(f"\nFound {len(png_files)} PNG images in generated folder")

for img_path in png_files:
    sidecar = img_path.with_suffix(img_path.suffix + '.json')

    if not sidecar.exists():
        images_no_metadata += 1
        continue

    try:
        with open(sidecar) as f:
            meta = json.load(f)

        if 'imagen_references' in meta or 'reference_image' in meta:
            images_with_refs += 1
            # Show first few examples
            if images_with_refs <= 3:
                print(f"\n✓ {img_path.name}")
                if 'imagen_references' in meta:
                    refs = meta['imagen_references'].get('references', [])
                    print(f"  Multi-reference: {len(refs)} images")
                    for ref in refs[:2]:
                        print(f"    - {Path(ref['path']).name}")
                else:
                    print(f"  Single reference: {Path(meta['reference_image']).name}")
        else:
            images_without_refs += 1
    except:
        images_no_metadata += 1

print(f"\n{'=' * 70}")
print("SUMMARY")
print("=" * 70)
print(f"Images with reference data:    {images_with_refs:4d} ({images_with_refs/len(png_files)*100:.1f}%)")
print(f"Images without reference data: {images_without_refs:4d} ({images_without_refs/len(png_files)*100:.1f}%)")
print(f"Images with no metadata:       {images_no_metadata:4d} ({images_no_metadata/len(png_files)*100:.1f}%)")

# Check config for historical reference usage
print(f"\n{'=' * 70}")
print("CHECKING CONFIG FOR REFERENCE IMAGE HISTORY")
print("=" * 70)

config_files = [
    config.config_dir / 'config.json',
    *list(config.config_dir.glob('config.backup*.json'))
]

refs_found_in_configs = set()
for cfg_file in config_files[:5]:  # Check first 5 config files
    if not cfg_file.exists():
        continue
    try:
        with open(cfg_file) as f:
            data = json.load(f)

        # Check imagen_references
        if 'imagen_references' in data:
            refs_data = data.get('imagen_references', {})
            if isinstance(refs_data, dict):
                refs = refs_data.get('references', [])
                if refs:
                    print(f"\n{cfg_file.name}: {len(refs)} references")
                    for ref in refs[:2]:
                        if isinstance(ref, dict) and 'path' in ref:
                            ref_path = Path(ref['path'])
                            print(f"  - {ref_path.name}")
                            print(f"    Exists: {ref_path.exists()}")
                            if ref_path.exists():
                                refs_found_in_configs.add(str(ref_path))
    except:
        pass

if refs_found_in_configs:
    print(f"\nFound {len(refs_found_in_configs)} unique reference images in config files")
else:
    print("\nNo reference images found in config files")

print(f"\n{'=' * 70}")
print("CONCLUSION")
print("=" * 70)

if images_with_refs > 0:
    print("✓ Some images already have reference data saved")
    print("  The history tab should show these references")
else:
    print("✗ NO images have reference data saved")

if refs_found_in_configs:
    print(f"✓ Found {len(refs_found_in_configs)} reference images in config history")
    print("  These could potentially be matched to generated images by timestamp")
else:
    print("✗ NO reference images found in config history")
    print("  Either you haven't used reference images for individual image generation,")
    print("  or they weren't saved to config")
