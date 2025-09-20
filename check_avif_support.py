#!/usr/bin/env python3
"""
Check AVIF support in PIL/Pillow and provide installation instructions if needed.

AVIF (AV1 Image File Format) is a modern image format that provides better
compression than JPEG and WebP while maintaining quality.
"""

import sys
from PIL import Image
import PIL.features

def check_avif_support():
    """Check if AVIF format is supported."""
    print("=" * 60)
    print("ImageAI - AVIF Support Check")
    print("=" * 60)
    print()

    # Check PIL version
    import PIL
    print(f"PIL/Pillow version: {PIL.__version__}")
    print()

    # Check registered formats
    extensions = Image.registered_extensions()
    avif_supported = '.avif' in extensions

    if avif_supported:
        print("✅ AVIF support is AVAILABLE")
        print("   You can open and save AVIF images.")
    else:
        print("❌ AVIF support is NOT available")
        print()
        print("To add AVIF support, install pillow-avif-plugin:")
        print()
        print("  pip install pillow-avif-plugin")
        print()
        print("Or for better performance, you can compile Pillow with AVIF support:")
        print("  pip uninstall pillow")
        print("  pip install pillow --no-binary :all: --compile-options=\"--enable-avif\"")
        print()
        print("Note: AVIF support requires libavif to be installed on your system.")
        print("  On Ubuntu/Debian: sudo apt-get install libavif-dev")
        print("  On macOS: brew install libavif")
        print("  On Windows: Use pre-compiled wheels or conda")

    print()
    print("Currently supported image formats:")
    print("-" * 40)

    # Group extensions by format
    formats = {}
    for ext, fmt in extensions.items():
        if fmt not in formats:
            formats[fmt] = []
        formats[fmt].append(ext)

    # Show common formats
    common_formats = ['PNG', 'JPEG', 'GIF', 'BMP', 'WEBP', 'TIFF', 'ICO']
    for fmt in common_formats:
        if fmt in formats:
            exts = ', '.join(formats[fmt])
            print(f"  {fmt}: {exts}")

    print()
    print("Other supported formats:")
    for fmt, exts in sorted(formats.items()):
        if fmt not in common_formats:
            exts_str = ', '.join(exts[:3])
            if len(exts) > 3:
                exts_str += f" (+{len(exts)-3} more)"
            print(f"  {fmt}: {exts_str}")

    return avif_supported

if __name__ == "__main__":
    avif_supported = check_avif_support()

    # Test loading an AVIF file if available
    if len(sys.argv) > 1 and avif_supported:
        test_file = sys.argv[1]
        print()
        print(f"Testing AVIF file: {test_file}")
        print("-" * 40)
        try:
            img = Image.open(test_file)
            print(f"✅ Successfully loaded AVIF image")
            print(f"   Size: {img.size}")
            print(f"   Mode: {img.mode}")
            print(f"   Format: {img.format}")
        except Exception as e:
            print(f"❌ Failed to load AVIF: {e}")

    print()
    print("To use AVIF in ImageAI after installing support:")
    print("1. AVIF files will be automatically supported in file dialogs")
    print("2. Generated images can be saved as AVIF for better compression")
    print("3. Reference images in AVIF format can be loaded")