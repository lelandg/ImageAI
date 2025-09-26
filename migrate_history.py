#!/usr/bin/env python3
"""
Migration script to convert old history JSON files to new DialogHistoryWidget format.
This script reads the old JSON history files and imports them into the new QSettings-based format.

Run this in PowerShell where PySide6 is installed:
    python migrate_history.py
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime

# PySide6 is no longer required for JSON-only migration
# We're just converting between JSON formats

def get_config_dir():
    """Get the ImageAI config directory."""
    # For cross-platform migration, always use Windows path
    # since that's where the real data is
    config_dir = Path("C:/Users/aboog/AppData/Roaming/ImageAI")
    # Convert to proper path for the current system
    if sys.platform != "win32":
        # Running from WSL/Linux, use /mnt/c path
        config_dir = Path("/mnt/c/Users/aboog/AppData/Roaming/ImageAI")
    return config_dir

def migrate_enhancement_history():
    """Migrate enhancement_history.json to new format."""
    config_dir = get_config_dir()
    old_history_file = config_dir / "enhancement_history.json"
    new_history_file = config_dir / "enhanced_prompts_history.json"

    if not old_history_file.exists():
        print(f"No enhancement history file found at {old_history_file}")
        return 0

    try:
        with open(old_history_file, 'r', encoding='utf-8') as f:
            old_history = json.load(f)

        # Convert to new format
        new_history = []
        for entry in old_history:
            new_entry = {
                "timestamp": entry.get("timestamp", ""),
                "input": entry.get("original", ""),
                "response": entry.get("enhanced", ""),
                "provider": "",  # Old format didn't store provider
                "model": "",  # Old format didn't store model
                "metadata": {
                    "enhancement_level": entry.get("enhancement_level", ""),
                    "style_preset": entry.get("style_preset", "")
                }
            }
            new_history.append(new_entry)

        # Write to new JSON file
        with open(new_history_file, 'w', encoding='utf-8') as f:
            json.dump(new_history, f, indent=2)

        print(f"✓ Migrated {len(old_history)} enhancement history entries")
        return len(old_history)

    except Exception as e:
        print(f"✗ Failed to migrate enhancement history: {e}")
        import traceback
        traceback.print_exc()
        return 0

def migrate_image_analysis_history():
    """Migrate image_analysis_history.json to new format."""
    config_dir = get_config_dir()
    old_history_file = config_dir / "image_analysis_history.json"
    new_history_file = config_dir / "reference_images_history.json"

    if not old_history_file.exists():
        print(f"No image analysis history file found at {old_history_file}")
        return 0

    try:
        with open(old_history_file, 'r', encoding='utf-8') as f:
            old_history = json.load(f)

        # Convert to new format
        new_history = []
        for entry in old_history:
            new_entry = {
                "timestamp": entry.get("timestamp", ""),
                "input": entry.get("analysis_prompt", "Image analysis"),
                "response": entry.get("description", ""),
                "provider": "",  # Old format didn't store provider
                "model": "",  # Old format didn't store model
                "metadata": {
                    "image_path": entry.get("image_path", "")
                }
            }
            new_history.append(new_entry)

        # Write to new JSON file
        with open(new_history_file, 'w', encoding='utf-8') as f:
            json.dump(new_history, f, indent=2)

        print(f"✓ Migrated {len(old_history)} image analysis history entries")
        return len(old_history)

    except Exception as e:
        print(f"✗ Failed to migrate image analysis history: {e}")
        import traceback
        traceback.print_exc()
        return 0

def migrate_prompt_generation_history():
    """Prompt generation dialog still uses JSON directly - no migration needed."""
    config_dir = get_config_dir()
    history_file = config_dir / "prompt_history.json"

    if not history_file.exists():
        print(f"No prompt generation history file found at {history_file}")
        return 0

    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            old_history = json.load(f)

        total_prompts = 0
        for entry in old_history:
            if entry.get("error"):
                total_prompts += 1
            else:
                prompts = entry.get("prompts", [])
                total_prompts += len(prompts)

        print(f"✓ Prompt generation history already in correct format ({total_prompts} entries from {len(old_history)} sessions)")
        return total_prompts

    except Exception as e:
        print(f"✗ Failed to migrate prompt generation history: {e}")
        import traceback
        traceback.print_exc()
        return 0

def migrate_prompt_question_history():
    """Migrate prompt_question_history.json to new format."""
    config_dir = get_config_dir()
    old_history_file = config_dir / "prompt_question_history.json"
    new_history_file = config_dir / "prompt_questions_history.json"

    if not old_history_file.exists():
        print(f"No prompt question history file found at {old_history_file}")
        return 0

    try:
        with open(old_history_file, 'r', encoding='utf-8') as f:
            old_history = json.load(f)

        # Convert to new format
        new_history = []
        for entry in old_history:
            new_entry = {
                "timestamp": entry.get("timestamp", ""),
                "input": entry.get("question", ""),
                "response": entry.get("answer", ""),
                "provider": entry.get("provider", ""),
                "model": entry.get("model", ""),
                "metadata": {}
            }

            # Store additional fields in metadata
            for key in entry:
                if key not in ["timestamp", "question", "answer", "provider", "model"]:
                    new_entry["metadata"][key] = entry[key]

            new_history.append(new_entry)

        # Write to new JSON file
        with open(new_history_file, 'w', encoding='utf-8') as f:
            json.dump(new_history, f, indent=2)

        print(f"✓ Migrated {len(old_history)} prompt question history entries")
        return len(old_history)

    except Exception as e:
        print(f"✗ Failed to migrate prompt question history: {e}")
        import traceback
        traceback.print_exc()
        return 0

def create_backup(file_path):
    """Create a backup of the original history file."""
    if file_path.exists():
        backup_path = file_path.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        import shutil
        shutil.copy2(file_path, backup_path)
        print(f"  Created backup: {backup_path.name}")
        return backup_path
    return None

def show_sample_entries(config_dir):
    """Show sample entries from each history file for verification."""
    print("\nSample entries from history files:")
    print("-" * 40)

    for filename in ["enhancement_history.json", "image_analysis_history.json",
                     "prompt_history.json", "prompt_question_history.json"]:
        file_path = config_dir / filename
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data and isinstance(data, list) and len(data) > 0:
                        print(f"\n{filename}: {len(data)} entries")
                        # Show first entry
                        first = data[0]
                        if 'timestamp' in first:
                            print(f"  First entry: {first.get('timestamp', 'N/A')}")
                        if 'original' in first:  # Enhancement history
                            print(f"    Original: {first.get('original', '')[:50]}...")
                        elif 'input' in first:  # Prompt generation
                            print(f"    Input: {first.get('input', '')[:50]}...")
                        elif 'question' in first:  # Q&A
                            print(f"    Question: {first.get('question', '')[:50]}...")
                        elif 'analysis_prompt' in first:  # Image analysis
                            print(f"    Prompt: {first.get('analysis_prompt', '')[:50]}...")
            except Exception as e:
                print(f"\n{filename}: Error reading - {e}")

def main():
    print("=" * 60)
    print("ImageAI History Migration Tool")
    print("=" * 60)
    print()

    config_dir = get_config_dir()
    print(f"Config directory: {config_dir}")
    print()

    # Show sample entries before migration
    show_sample_entries(config_dir)
    print()

    # Create backups of existing files
    print("Creating backups of original files...")
    backup_files = []
    for filename in ["enhancement_history.json", "image_analysis_history.json",
                     "prompt_history.json", "prompt_question_history.json"]:
        file_path = config_dir / filename
        backup = create_backup(file_path)
        if backup:
            backup_files.append(backup)
    print()

    # Migrate each history type
    print("Starting migration...")
    total_migrated = 0

    total_migrated += migrate_enhancement_history()
    total_migrated += migrate_image_analysis_history()
    total_migrated += migrate_prompt_generation_history()
    total_migrated += migrate_prompt_question_history()

    print()
    print("=" * 60)
    print(f"Migration complete! Total entries migrated: {total_migrated}")
    print("=" * 60)
    print()

    if backup_files:
        print("Backup files created:")
        for backup in backup_files:
            print(f"  - {backup.name}")
        print()

    print("Note: The original JSON files have been backed up and can be")
    print("      safely deleted if the migration was successful.")
    print()
    print("To verify migration:")
    print("1. Open ImageAI")
    print("2. Check the History tabs in:")
    print("   - Enhanced Prompt dialog (Alt+E)")
    print("   - Ask About Image dialog (Alt+I)")
    print("   - Ask About Prompt dialog (Alt+A)")
    print("   - Generate Prompts dialog (Alt+P)")
    print()
    print("If everything looks good, you can delete the original JSON files:")
    for filename in ["enhancement_history.json", "image_analysis_history.json",
                     "prompt_history.json", "prompt_question_history.json"]:
        file_path = config_dir / filename
        if file_path.exists():
            print(f"   del \"{file_path}\"")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)