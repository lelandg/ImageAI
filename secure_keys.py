#!/usr/bin/env python3
"""
Secure API Keys Script for ImageAI
Moves API keys from config.json to Windows Credential Manager (encrypted).

Run this script in Windows (PowerShell or Command Prompt), not WSL:
    python secure_keys.py
"""

import json
import sys
from pathlib import Path
import platform

def main():
    """Main function to secure API keys."""
    # Check if running on Windows
    if platform.system() != "Windows":
        print("ERROR: This script must be run on Windows, not in WSL!")
        print("Please run in PowerShell or Command Prompt:")
        print("  python secure_keys.py")
        return 1
    
    try:
        import keyring
    except ImportError:
        print("ERROR: keyring module not installed!")
        print("Please install it first:")
        print("  pip install keyring")
        return 1
    
    # Get config path
    config_path = Path.home() / "AppData" / "Roaming" / "ImageAI" / "config.json"
    
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        return 1
    
    print(f"Loading config from: {config_path}")
    
    # Load config
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Track what we secure
    secured = []
    failed = []
    
    # Process each provider
    providers = config.get("providers", {})
    for provider, provider_config in providers.items():
        if "api_key" in provider_config:
            api_key = provider_config["api_key"]
            if api_key and api_key.strip():
                print(f"\nSecuring {provider} API key...")
                try:
                    # Store in Windows Credential Manager
                    keyring.set_password("ImageAI", f"{provider}_api_key", api_key)
                    
                    # Verify it was stored
                    retrieved = keyring.get_password("ImageAI", f"{provider}_api_key")
                    if retrieved == api_key:
                        # Remove from config
                        del provider_config["api_key"]
                        secured.append(provider)
                        print(f"  ✓ {provider} key secured in Windows Credential Manager")
                    else:
                        failed.append(provider)
                        print(f"  ✗ Failed to verify {provider} key storage")
                except Exception as e:
                    failed.append(provider)
                    print(f"  ✗ Error securing {provider} key: {e}")
    
    if secured:
        # Backup original with timestamp if needed
        backup_path = config_path.with_suffix(".backup_before_encryption.json")
        if backup_path.exists():
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = config_path.with_suffix(f".backup_encryption_{timestamp}.json")
        
        import shutil
        shutil.copy2(config_path, backup_path)
        print(f"\nBacked up original to: {backup_path}")
        
        # Write updated config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"\nSuccessfully secured API keys for: {', '.join(secured)}")
        print("Keys are now encrypted in Windows Credential Manager")
        print("They have been removed from config.json for security")
        
        # Show current keyring backend
        print(f"\nUsing keyring backend: {keyring.get_keyring()}")
    else:
        print("\nNo keys were secured")
    
    if failed:
        print(f"\nFailed to secure keys for: {', '.join(failed)}")
        print("These keys remain in config.json")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())