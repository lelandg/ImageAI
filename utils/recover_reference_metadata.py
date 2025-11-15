#!/usr/bin/env python3
"""
Recover reference image metadata from ImageAI logs.

This script scans all log files to find image generations that used reference images,
then updates the corresponding PNG.json metadata files with the reference information.

Based on actual log patterns found in:
- providers/imagen_customization.py (lines 202-206): Multi-reference format
- providers/google.py: Single reference format
- gui/main_window.py (line 5414+): Metadata saving
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
import sys
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import ConfigManager
from core.utils import sidecar_path


class ReferenceRecovery:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.logs_dir = config.config_dir / "logs"
        self.generated_dir = config.config_dir / "generated"
        self.stats = {
            'logs_scanned': 0,
            'images_found': 0,
            'already_has_refs': 0,
            'updated': 0,
            'missing_files': 0,
            'errors': 0
        }

    def scan_logs(self) -> Dict[str, Dict]:
        """
        Scan all log files and extract reference usage.

        Returns:
            Dict mapping saved image paths to their reference data
        """
        results = {}

        log_files = sorted(self.logs_dir.glob("*.log"))
        print(f"Found {len(log_files)} log files\n")

        for log_file in log_files:
            self.stats['logs_scanned'] += 1

            try:
                refs = self._parse_log_file(log_file)
                if refs:
                    results.update(refs)
                    print(f"✓ {log_file.name}: Found {len(refs)} images with references")

                # Progress every 100 logs
                if self.stats['logs_scanned'] % 100 == 0:
                    print(f"  Progress: {self.stats['logs_scanned']}/{len(log_files)} logs, {len(results)} total images")

            except Exception as e:
                self.stats['errors'] += 1
                print(f"✗ {log_file.name}: Error - {e}")

        return results

    def _parse_log_file(self, log_path: Path) -> Dict[str, Dict]:
        """Parse a single log file for reference usage."""
        results = {}

        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            return results

        # Pattern 1: Multi-reference Imagen 3 format
        # Example from logs:
        # GOOGLE IMAGEN 3 CUSTOMIZATION API REQUEST
        # Prompt: ...
        # References: 2
        #   [1] subject - character.png
        #   [2] style - background.png
        # ... later ...
        # Saved image to C:\...\output.png

        # Find all Imagen 3 request blocks
        imagen_blocks = re.finditer(
            r'GOOGLE IMAGEN 3 CUSTOMIZATION API REQUEST\n'
            r'.*?'
            r'References: (\d+)\n'
            r'((?:\s+\[\d+\].*?\n)*?)'
            r'.*?'
            r'(?:Saved image to|Auto-saved to).*?([A-Z]:[/\\].+?\.png)',
            content,
            re.DOTALL | re.MULTILINE
        )

        for match in imagen_blocks:
            ref_count = int(match.group(1))
            ref_lines = match.group(2)
            image_path = match.group(3).strip()

            if ref_count > 0:
                # Parse individual references
                references = []
                ref_pattern = r'\[(\d+)\]\s+(\w+)\s+-\s+(.+?)(?:\n|$)'
                for ref_match in re.finditer(ref_pattern, ref_lines):
                    ref_id = int(ref_match.group(1))
                    ref_type = ref_match.group(2)
                    ref_name = ref_match.group(3).strip()

                    references.append({
                        'reference_id': ref_id,
                        'type': ref_type,
                        'name': ref_name
                    })

                if references:
                    results[image_path] = {
                        'type': 'multi',
                        'references': references,
                        'log': log_path.name
                    }

        # Pattern 2: Legacy single reference format (Google Gemini)
        # Look for reference_image being set, then track to next saved image

        # Split content into lines for line-by-line parsing
        lines = content.split('\n')
        current_ref = None

        for i, line in enumerate(lines):
            # Look for reference image usage
            if 'reference_image' in line.lower() and '=' in line:
                # Extract the path
                ref_match = re.search(r'reference_image.*?[=:]\s*["\']?([^"\']+?\.(?:png|jpg|jpeg))["\']?', line, re.IGNORECASE)
                if ref_match:
                    current_ref = ref_match.group(1)

            # Look for image being saved
            if current_ref and ('Saved image to' in line or 'Auto-saved to' in line):
                path_match = re.search(r'([A-Z]:[/\\].+?\.png)', line)
                if path_match:
                    image_path = path_match.group(1).strip()
                    if image_path not in results:  # Don't override multi-ref data
                        results[image_path] = {
                            'type': 'single',
                            'reference_path': current_ref,
                            'log': log_path.name
                        }
                    current_ref = None  # Reset for next generation

        return results

    def update_metadata_files(self, reference_data: Dict[str, Dict]) -> None:
        """Update PNG metadata files with reference information."""
        print(f"\nUpdating metadata files...")
        print("=" * 60)

        for image_path_str, ref_data in reference_data.items():
            self.stats['images_found'] += 1

            # Convert Windows path to WSL if needed
            image_path = Path(image_path_str)
            if str(image_path).startswith('C:'):
                image_path = Path(str(image_path).replace('C:', '/mnt/c'))

            # Try different locations
            if not image_path.exists():
                # Try in generated dir
                image_path = self.generated_dir / image_path.name

            if not image_path.exists():
                self.stats['missing_files'] += 1
                continue

            # Get sidecar path
            json_path = sidecar_path(image_path)
            if not json_path.exists():
                self.stats['missing_files'] += 1
                continue

            # Read existing metadata
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            except Exception as e:
                self.stats['errors'] += 1
                print(f"✗ Error reading {json_path.name}: {e}")
                continue

            # Check if already has reference data
            if 'imagen_references' in metadata or 'reference_image' in metadata:
                self.stats['already_has_refs'] += 1
                continue

            # Add reference data based on type
            if ref_data['type'] == 'multi':
                # Multi-reference format
                metadata['imagen_references'] = {
                    'mode': 'flexible',  # Default mode
                    'references': [
                        {
                            'reference_id': ref['reference_id'],
                            'type': ref['type'],
                            'path': ref['name']  # Just the filename
                        }
                        for ref in ref_data['references']
                    ]
                }
            elif ref_data['type'] == 'single':
                # Legacy single reference
                metadata['reference_image'] = ref_data['reference_path']

            # Save updated metadata
            try:
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                self.stats['updated'] += 1
                print(f"✓ Updated: {image_path.name}")
            except Exception as e:
                self.stats['errors'] += 1
                print(f"✗ Error writing {json_path.name}: {e}")

    def print_summary(self):
        """Print summary statistics."""
        print("\n" + "=" * 60)
        print("RECOVERY SUMMARY")
        print("=" * 60)
        print(f"Logs scanned:              {self.stats['logs_scanned']}")
        print(f"Images with references:     {self.stats['images_found']}")
        print(f"Already had references:     {self.stats['already_has_refs']}")
        print(f"Successfully updated:       {self.stats['updated']}")
        print(f"Missing files:              {self.stats['missing_files']}")
        print(f"Errors:                     {self.stats['errors']}")
        print("=" * 60)


def main():
    print("ImageAI Reference Metadata Recovery Tool")
    print("=" * 60)
    print("This script scans log files to find images generated with")
    print("reference images, then updates their metadata files.\n")

    config = ConfigManager()
    recovery = ReferenceRecovery(config)

    if not recovery.logs_dir.exists():
        print(f"Error: Logs directory not found: {recovery.logs_dir}")
        return 1

    if not recovery.generated_dir.exists():
        print(f"Error: Generated directory not found: {recovery.generated_dir}")
        return 1

    print(f"Logs dir: {recovery.logs_dir}")
    print(f"Images dir: {recovery.generated_dir}\n")

    # Scan all logs
    print("Scanning log files...")
    print("=" * 60)
    reference_data = recovery.scan_logs()

    print(f"\n Found {len(reference_data)} total images with reference data\n")

    if not reference_data:
        print("No reference data found in logs.")
        return 0

    # Update metadata files
    recovery.update_metadata_files(reference_data)

    # Print summary
    recovery.print_summary()

    return 0


if __name__ == "__main__":
    sys.exit(main())
