#!/usr/bin/env python3
"""
Config Migration Script for ImageAI
Migrates old config.json format to new structure and secures API keys.

Old format issues:
- Top-level 'api_key' for Google (legacy)
- 'keys' object with provider keys (incorrect structure)
- Plaintext API keys in config.json

New format:
- All API keys under 'providers.<provider>.api_key'
- No top-level 'api_key'
- No 'keys' object
- API keys stored in system keyring when available (encrypted by OS)
"""

import json
import shutil
from pathlib import Path
import platform
import sys
import os
from datetime import datetime

# Add parent directory to path to import ImageAI modules
sys.path.insert(0, str(Path(__file__).parent))

try:
    from core.security import secure_storage
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False
    print("Warning: Could not import security module. Keys will remain in config.json")


def get_config_path() -> Path:
    """Get platform-specific configuration directory."""
    system = platform.system()
    home = Path.home()
    
    if system == "Windows":
        base = Path.home() / "AppData" / "Roaming"
    elif system == "Darwin":  # macOS
        base = Path.home() / "Library" / "Application Support"
    else:  # Linux and others
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    
    return base / "ImageAI" / "config.json"


def migrate_config(config_path: Path, dry_run: bool = False, secure_keys: bool = True) -> dict:
    """
    Migrate old config format to new format and optionally secure API keys.
    
    Args:
        config_path: Path to config.json
        dry_run: If True, don't write changes, just return what would be written
        secure_keys: If True, attempt to store keys in system keyring
    
    Returns:
        The migrated configuration
    """
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        return {}
    
    # Read current config
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    print(f"Migrating config at: {config_path}")
    print(f"Dry run: {dry_run}")
    
    # Track what we're migrating
    migrations = []
    
    # Initialize providers if not present
    if "providers" not in config:
        config["providers"] = {}
        migrations.append("Created 'providers' section")
    
    # Migrate legacy top-level api_key (Google)
    if "api_key" in config:
        google_key = config.pop("api_key")
        if "google" not in config["providers"]:
            config["providers"]["google"] = {}
        config["providers"]["google"]["api_key"] = google_key
        migrations.append(f"Migrated top-level 'api_key' to 'providers.google.api_key'")
    
    # Migrate incorrect 'keys' structure
    if "keys" in config:
        keys = config.pop("keys")
        for provider, api_key in keys.items():
            if provider not in config["providers"]:
                config["providers"][provider] = {}
            # Only migrate if not already present
            if "api_key" not in config["providers"][provider]:
                config["providers"][provider]["api_key"] = api_key
                migrations.append(f"Migrated 'keys.{provider}' to 'providers.{provider}.api_key'")
            else:
                migrations.append(f"Skipped 'keys.{provider}' (already exists in providers)")
    
    # Clean up any duplicates - prefer existing providers entries
    # This ensures we don't overwrite newer keys with older ones
    
    # Attempt to secure API keys in system keyring
    secured_keys = []
    if secure_keys and SECURITY_AVAILABLE and not dry_run:
        print("\nAttempting to secure API keys in system keyring...")
        for provider, provider_config in config.get("providers", {}).items():
            if "api_key" in provider_config:
                api_key = provider_config["api_key"]
                if api_key and api_key.strip():
                    # Try to store in keyring
                    if secure_storage.store_key(provider, api_key):
                        # Remove from config if successfully stored in keyring
                        del provider_config["api_key"]
                        secured_keys.append(provider)
                        migrations.append(f"Secured {provider} API key in system keyring")
                    else:
                        migrations.append(f"Failed to secure {provider} key - keeping in config.json")
    
    if migrations:
        print("\nMigrations performed:")
        for migration in migrations:
            print(f"  - {migration}")
    else:
        print("\nNo migrations needed - config is already in correct format")
    
    if secured_keys:
        print(f"\n✓ API keys secured in system keyring for: {', '.join(secured_keys)}")
        print("  Keys are now encrypted by your operating system")
        print("  They have been removed from config.json for security")
    
    if not dry_run and migrations:
        # Backup original config
        backup_path = config_path.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        shutil.copy2(config_path, backup_path)
        print(f"\nBacked up original config to: {backup_path}")
        
        # Write migrated config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Updated config written to: {config_path}")
    
    return config


def main():
    """Main entry point for migration script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate ImageAI config.json to new format and secure API keys")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without modifying files")
    parser.add_argument("--config", type=Path, help="Path to config.json (defaults to platform-specific location)")
    parser.add_argument("--no-secure", action="store_true", help="Don't attempt to secure keys in system keyring")
    args = parser.parse_args()
    
    config_path = args.config if args.config else get_config_path()
    
    try:
        migrated = migrate_config(config_path, dry_run=args.dry_run, secure_keys=not args.no_secure)
        
        if args.dry_run:
            print("\n--- Migrated config (dry run) ---")
            print(json.dumps(migrated, indent=2))
            print("\nNo files were modified (dry run mode)")
        
        print("\nMigration complete!")
        return 0
    except Exception as e:
        print(f"Error during migration: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import os
    sys.exit(main())