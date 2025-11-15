"""
Automatically update image metadata with reference images from multiple sources.

Scans log files, config files, and video project files to find reference image
usage and updates image metadata sidecar files accordingly.

Usage:
    python utils/update_history_from_logs.py
"""

import json
import os
import platform
import re
import sys
from pathlib import Path
from typing import Dict, List, Set
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import ConfigManager


def get_logs_directory() -> Path:
    """Get the ImageAI logs directory."""
    config = ConfigManager()
    return config.config_dir / "logs"


def get_output_directory() -> Path:
    """Get the ImageAI generated images directory."""
    config = ConfigManager()
    return config.config_dir / "generated"


def get_config_directory() -> Path:
    """Get the ImageAI config directory."""
    config = ConfigManager()
    return config.config_dir


def parse_log_file(log_path: Path) -> Dict[str, List[str]]:
    """Parse a log file to extract reference image usage and saved image paths."""
    reference_map = {}
    current_refs = []

    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # Look for reference image paths
                if 'reference' in line.lower() and any(ext in line.lower() for ext in ['.png', '.jpg', '.jpeg']):
                    path_patterns = [
                        r'["\']([A-Z]:[/\\][^"\']+\.(?:png|jpg|jpeg))["\']',  # Windows path
                        r'["\']([/][^"\']+\.(?:png|jpg|jpeg))["\']',  # Unix path
                    ]
                    for pattern in path_patterns:
                        matches = re.findall(pattern, line, re.IGNORECASE)
                        for match in matches:
                            if Path(match).exists() and match not in current_refs:
                                current_refs.append(match)

                # Look for saved images
                if 'saved' in line.lower() or 'image to' in line.lower():
                    if any(ext in line.lower() for ext in ['.png', '.jpg', '.jpeg']):
                        filename_patterns = [
                            r'([^/\\"]+\.(?:png|jpg|jpeg))',
                        ]
                        for pattern in filename_patterns:
                            matches = re.findall(pattern, line, re.IGNORECASE)
                            for match in matches:
                                if match.endswith(('.png', '.jpg', '.jpeg')):
                                    filename = Path(match).name
                                    if current_refs and filename not in reference_map:
                                        reference_map[filename] = current_refs.copy()
                                        break
    except Exception as e:
        print(f"Error parsing {log_path.name}: {e}")

    return reference_map


def scan_config_files(config_dir: Path) -> Set[str]:
    """Scan config and backup files for reference images that were used."""
    all_refs = set()

    # Find all config files (current and backups)
    config_files = [
        config_dir / 'config.json',
        *config_dir.glob('config.backup*.json'),
        *config_dir.glob('*config*.json')
    ]

    for config_file in config_files:
        if not config_file.exists():
            continue

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Check imagen_references
            if 'imagen_references' in data:
                refs_data = data['imagen_references']
                if isinstance(refs_data, dict) and 'references' in refs_data:
                    for ref in refs_data['references']:
                        if isinstance(ref, dict) and 'path' in ref:
                            path = ref['path']
                            if Path(path).exists():
                                all_refs.add(path)

            # Check legacy reference_images
            if 'reference_images' in data:
                refs = data['reference_images']
                if isinstance(refs, list):
                    for ref in refs:
                        if isinstance(ref, str) and Path(ref).exists():
                            all_refs.add(ref)
                        elif isinstance(ref, dict) and 'path' in ref:
                            path = ref['path']
                            if Path(path).exists():
                                all_refs.add(path)

        except Exception as e:
            pass

    return all_refs


def scan_video_projects(config_dir: Path) -> Set[str]:
    """Scan video project files for global reference images."""
    all_refs = set()

    video_projects_dir = config_dir / 'video_projects'

    if not video_projects_dir.exists():
        return all_refs

    # Find all project files
    project_files = list(video_projects_dir.glob('*/project.iaproj.json'))

    for project_file in project_files:
        if not project_file.exists():
            continue

        try:
            with open(project_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Check global_reference_images
            if 'global_reference_images' in data:
                for ref in data['global_reference_images']:
                    if isinstance(ref, dict) and 'path' in ref:
                        path = ref['path']
                        # Convert to Path object which handles platform differences
                        path_obj = Path(path)
                        if path_obj.exists():
                            all_refs.add(str(path_obj))

        except Exception as e:
            pass

    return all_refs


def find_images_using_references(output_dir: Path, reference_paths: Set[str]) -> Dict[str, List[str]]:
    """
    Find generated images that likely used the reference images.
    Uses timestamp correlation - images generated within 5 minutes of reference file usage.
    """
    if not reference_paths:
        return {}

    # Get reference file timestamps
    ref_times = {}
    for ref_path in reference_paths:
        try:
            ref_file = Path(ref_path)
            if ref_file.exists():
                # Use modification time as proxy for when it was last used
                ref_times[ref_path] = ref_file.stat().st_mtime
        except:
            pass

    if not ref_times:
        return {}

    # Find generated images with timestamps near reference usage
    image_ref_map = {}

    for img_path in output_dir.glob('*.png'):
        try:
            img_time = img_path.stat().st_mtime

            # Check if image was generated within 24 hours of any reference
            for ref_path, ref_time in ref_times.items():
                # Image generated after reference was created/modified
                if abs(img_time - ref_time) < (24 * 60 * 60):  # 24 hour window
                    if img_path.name not in image_ref_map:
                        image_ref_map[img_path.name] = []
                    if ref_path not in image_ref_map[img_path.name]:
                        image_ref_map[img_path.name].append(ref_path)
        except:
            pass

    return image_ref_map


def update_metadata_file(image_path: Path, references: List[str]) -> bool:
    """Update an image's metadata sidecar file with reference image information."""
    sidecar_path = image_path.with_suffix(image_path.suffix + '.json')

    if not sidecar_path.exists():
        return False

    try:
        # Load existing metadata
        with open(sidecar_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        # Skip if already has reference data
        if 'imagen_references' in metadata or 'reference_image' in metadata:
            return False

        # Add reference data based on count
        if len(references) == 1:
            metadata['reference_image'] = references[0]
        elif len(references) > 1:
            metadata['imagen_references'] = {
                'references': [
                    {
                        'path': str(ref),
                        'type': 'SUBJECT',
                        'description': ''
                    }
                    for ref in references
                ]
            }

        # Write back
        with open(sidecar_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        return True

    except Exception as e:
        return False


def main():
    """Main execution."""
    config_dir = get_config_directory()
    logs_dir = get_logs_directory()
    output_dir = get_output_directory()

    if not output_dir.exists():
        print(f"Output directory not found: {output_dir}")
        return 1

    print("Scanning for reference images...")

    # 1. Scan logs for explicit reference->image mappings
    log_mappings = {}
    if logs_dir.exists():
        log_files = sorted(logs_dir.glob('*.log'), key=lambda p: p.stat().st_mtime, reverse=True)
        for log_file in log_files:
            ref_map = parse_log_file(log_file)
            if ref_map:
                log_mappings.update(ref_map)

    print(f"  Found {len(log_mappings)} images with references in logs")

    # 2. Scan config files for reference images
    config_refs = scan_config_files(config_dir)
    print(f"  Found {len(config_refs)} reference images in config files")

    # Note: We don't scan video projects - those references are for video generation only,
    # not for individual image generation

    # Use config references
    all_refs = config_refs

    # 4. Find images that might use these references (by timestamp)
    timestamp_mappings = find_images_using_references(output_dir, all_refs)
    print(f"  Found {len(timestamp_mappings)} images with timestamp-correlated references")

    # Combine all mappings (log mappings take precedence)
    combined_mappings = {**timestamp_mappings, **log_mappings}

    if not combined_mappings:
        print("No reference image usage found")
        return 0

    print(f"\nTotal images with references: {len(combined_mappings)}")
    print("Updating metadata files...")

    updated_count = 0
    skipped_count = 0

    for filename, references in combined_mappings.items():
        image_path = output_dir / filename

        if not image_path.exists():
            skipped_count += 1
            continue

        if update_metadata_file(image_path, references):
            updated_count += 1
        else:
            skipped_count += 1

    print(f"\nCompleted:")
    print(f"  Updated: {updated_count}")
    print(f"  Skipped: {skipped_count}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
