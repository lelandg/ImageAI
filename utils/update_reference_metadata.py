#!/usr/bin/env python3
"""
Update PNG metadata files with reference image information from logs.

This script scans all ImageAI log files to find image generations that used
reference images, then updates the corresponding PNG.json sidecar files with
the reference data.
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import sys

# Add parent directory to path to import from core
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import ConfigManager
from core.utils import sidecar_path


def find_log_files(logs_dir: Path) -> List[Path]:
    """Find all log files sorted by modification time (oldest first)."""
    log_files = list(logs_dir.glob("*.log"))
    # Sort by filename (which contains timestamp) for chronological order
    log_files.sort()
    return log_files


def extract_reference_data_from_log(log_path: Path) -> Dict[str, Dict]:
    """
    Extract reference image usage from a log file.

    Returns:
        Dict mapping image paths to reference data
    """
    results = {}

    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {log_path.name}: {e}")
        return results

    # Track current generation context
    current_prompt = None
    current_references = None
    current_timestamp = None

    for i, line in enumerate(lines):
        # Extract timestamp from log line
        ts_match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
        if ts_match:
            current_timestamp = ts_match.group(1)

        # Look for prompt being sent
        if 'Generating image' in line or 'prompt:' in line.lower():
            # Try to extract prompt from this or next few lines
            prompt_match = re.search(r'prompt["\']?\s*[:=]\s*["\']([^"\']+)["\']', line, re.IGNORECASE)
            if prompt_match:
                current_prompt = prompt_match.group(1)

        # Look for reference images being used
        # Pattern 1: imagen_references data structure
        if 'imagen_references' in line:
            # Try to extract the full imagen_references dict
            # This is complex as it may span multiple lines
            try:
                # Look ahead for the JSON structure
                json_lines = [line]
                brace_count = line.count('{') - line.count('}')
                j = i + 1
                while brace_count > 0 and j < len(lines) and j < i + 50:
                    json_lines.append(lines[j])
                    brace_count += lines[j].count('{') - lines[j].count('}')
                    j += 1

                json_text = ''.join(json_lines)
                # Extract JSON object
                start_idx = json_text.find('{')
                if start_idx >= 0:
                    # Try to parse the JSON
                    try:
                        # Find the closing brace
                        depth = 0
                        for end_idx in range(start_idx, len(json_text)):
                            if json_text[end_idx] == '{':
                                depth += 1
                            elif json_text[end_idx] == '}':
                                depth -= 1
                                if depth == 0:
                                    json_str = json_text[start_idx:end_idx+1]
                                    ref_data = json.loads(json_str)
                                    if 'references' in ref_data:
                                        current_references = ref_data
                                    break
                    except json.JSONDecodeError:
                        pass
            except Exception:
                pass

        # Pattern 2: Legacy reference_image
        elif 'reference_image' in line and '=' in line:
            ref_match = re.search(r'reference_image["\']?\s*[:=]\s*["\']([^"\']+)["\']', line)
            if ref_match:
                ref_path = ref_match.group(1)
                current_references = {'legacy': ref_path}

        # Look for saved image paths
        if 'Saved image to' in line or 'saved:' in line.lower() or '.png' in line:
            # Extract image path
            path_match = re.search(r'([A-Z]:[/\\].*?\.png)', line, re.IGNORECASE)
            if not path_match:
                path_match = re.search(r'(/[^\s]+\.png)', line)

            if path_match and current_references:
                image_path = path_match.group(1)
                # Convert to Path object
                img_path = Path(image_path)

                # Store the reference data for this image
                results[str(img_path)] = {
                    'references': current_references,
                    'prompt': current_prompt,
                    'timestamp': current_timestamp,
                    'log_file': log_path.name
                }

                # Reset context for next generation
                current_references = None

    return results


def update_metadata_file(image_path: Path, reference_data: Dict) -> bool:
    """
    Update a PNG metadata file with reference information.

    Args:
        image_path: Path to the PNG file
        reference_data: Reference data extracted from logs

    Returns:
        True if updated successfully
    """
    if not image_path.exists():
        return False

    json_path = sidecar_path(image_path)

    # Read existing metadata
    metadata = {}
    if json_path.exists():
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except Exception as e:
            print(f"  Error reading {json_path.name}: {e}")
            return False
    else:
        # No existing metadata file
        return False

    # Check if already has reference data
    if 'imagen_references' in metadata or 'reference_image' in metadata:
        return False  # Already has reference data

    # Add reference data
    refs = reference_data.get('references', {})
    if 'legacy' in refs:
        # Legacy single reference format
        metadata['reference_image'] = refs['legacy']
    elif 'references' in refs:
        # New multi-reference format
        metadata['imagen_references'] = refs
    else:
        return False  # No valid reference data

    # Write updated metadata
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"  Error writing {json_path.name}: {e}")
        return False


def main():
    """Main function to scan logs and update metadata files."""
    print("ImageAI Reference Metadata Updater")
    print("=" * 60)

    # Get config directory
    config = ConfigManager()
    logs_dir = config.config_dir / "logs"
    generated_dir = config.config_dir / "generated"

    if not logs_dir.exists():
        print(f"Error: Logs directory not found: {logs_dir}")
        return 1

    if not generated_dir.exists():
        print(f"Error: Generated images directory not found: {generated_dir}")
        return 1

    print(f"Logs directory: {logs_dir}")
    print(f"Generated images directory: {generated_dir}")
    print()

    # Find all log files
    log_files = find_log_files(logs_dir)
    print(f"Found {len(log_files)} log files to scan")
    print()

    # Scan all logs
    all_references = {}
    processed_logs = 0

    for log_file in log_files:
        print(f"Scanning {log_file.name}...", end='')
        refs = extract_reference_data_from_log(log_file)

        if refs:
            all_references.update(refs)
            print(f" Found {len(refs)} images with references")
        else:
            print(" No references found")

        processed_logs += 1

        # Progress indicator
        if processed_logs % 100 == 0:
            print(f"  Progress: {processed_logs}/{len(log_files)} logs scanned, {len(all_references)} total images with references")

    print()
    print(f"Scan complete: Found {len(all_references)} images with reference data")
    print()

    # Update metadata files
    updated_count = 0
    skipped_count = 0
    missing_count = 0

    for image_path_str, ref_data in all_references.items():
        image_path = Path(image_path_str)

        # Convert Windows paths to WSL paths if needed
        if str(image_path).startswith('C:'):
            image_path = Path(str(image_path).replace('C:', '/mnt/c'))

        if not image_path.exists():
            # Try looking in generated_dir
            image_path = generated_dir / image_path.name

        if not image_path.exists():
            missing_count += 1
            continue

        if update_metadata_file(image_path, ref_data):
            updated_count += 1
            print(f"✓ Updated: {image_path.name}")
        else:
            skipped_count += 1

    print()
    print("=" * 60)
    print("Summary:")
    print(f"  Total images with references found in logs: {len(all_references)}")
    print(f"  Successfully updated: {updated_count}")
    print(f"  Skipped (already has references): {skipped_count}")
    print(f"  Missing (file not found): {missing_count}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
