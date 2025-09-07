#!/usr/bin/env python3
"""Command-line model downloader for Local SD."""

import sys
import argparse
from pathlib import Path
from providers.model_info import ModelInfo

def list_models(cache_dir: Path):
    """List available and installed models."""
    print("\n=== Installed Models ===")
    installed = ModelInfo.get_installed_models(cache_dir)
    if installed:
        for model_id in installed:
            size = ModelInfo.get_model_size(model_id, cache_dir)
            print(f"✓ {model_id} ({size:.1f} GB)")
    else:
        print("No models installed yet")
    
    print("\n=== Available Models ===")
    for model_id, info in ModelInfo.POPULAR_MODELS.items():
        if model_id not in installed:
            status = "⭐ " if info.get("recommended") else "  "
            print(f"{status}{info['name']} ({model_id})")
            print(f"    Size: ~{info['size_gb']:.1f} GB | {info['description'][:60]}...")

def download_model(model_id: str, cache_dir: Path):
    """Download a model."""
    try:
        from huggingface_hub import snapshot_download, HfFolder
        
        # Check for authentication
        token = HfFolder.get_token()
        if not token:
            print("⚠ No HuggingFace authentication found.")
            print("  Some models may require authentication.")
            print("  Run 'python download_models.py login' to authenticate.")
            response = input("\nContinue without authentication? (y/n): ")
            if response.lower() != 'y':
                sys.exit(0)
        
        print(f"Downloading {model_id}...")
        print("This may take a while depending on your internet connection...")
        
        local_dir = snapshot_download(
            repo_id=model_id,
            cache_dir=cache_dir,
            resume_download=True,
            local_files_only=False,
            ignore_patterns=["*.md", "*.txt", ".gitattributes"],
            token=token
        )
        
        print(f"✓ Successfully downloaded {model_id}")
        print(f"  Location: {local_dir}")
        
        size = ModelInfo.get_model_size(model_id, cache_dir)
        print(f"  Size: {size:.1f} GB")
        
    except ImportError:
        print("Error: huggingface_hub not installed")
        print("Install with: pip install huggingface_hub")
        sys.exit(1)
    except Exception as e:
        print(f"Error downloading {model_id}: {e}")
        if "401" in str(e) or "Unauthorized" in str(e):
            print("\n⚠ This model requires authentication.")
            print("  Run 'python download_models.py login' to authenticate with HuggingFace.")
        sys.exit(1)

def login_huggingface():
    """Login to HuggingFace."""
    try:
        from huggingface_hub import HfFolder, whoami
        import getpass
        
        # Check current status
        current_token = HfFolder.get_token()
        if current_token:
            try:
                user_info = whoami(current_token)
                username = user_info.get('name', 'Unknown')
                print(f"Currently logged in as: {username}")
                response = input("Do you want to login with a different account? (y/n): ")
                if response.lower() != 'y':
                    return
            except:
                print("Current token is invalid.")
        
        print("\n=== HuggingFace Login ===")
        print("Get your token from: https://huggingface.co/settings/tokens")
        print("(Create a READ token if you don't have one)")
        print()
        
        token = getpass.getpass("Enter your HuggingFace token (hidden): ")
        
        if not token:
            print("No token provided.")
            sys.exit(1)
        
        # Validate token
        try:
            user_info = whoami(token)
            username = user_info.get('name', 'Unknown')
            
            # Save token
            HfFolder.save_token(token)
            
            print(f"\n✓ Successfully logged in as: {username}")
            print("Your token has been saved for future use.")
            
        except Exception as e:
            print(f"\n✗ Failed to authenticate: {e}")
            sys.exit(1)
            
    except ImportError:
        print("Error: huggingface_hub not installed")
        print("Install with: pip install huggingface_hub")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Download Stable Diffusion models for Local SD provider"
    )
    parser.add_argument(
        "action",
        choices=["list", "download", "login"],
        help="Action to perform"
    )
    parser.add_argument(
        "--model",
        help="Model ID to download (e.g., runwayml/stable-diffusion-v1-5)"
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / ".cache" / "huggingface",
        help="Cache directory for models"
    )
    
    args = parser.parse_args()
    
    if args.action == "login":
        login_huggingface()
    else:
        print(f"Cache directory: {args.cache_dir}")
        
        if args.action == "list":
            list_models(args.cache_dir)
        elif args.action == "download":
            if not args.model:
                print("Error: --model required for download action")
                print("\nRecommended models to download:")
                for model_id, info in ModelInfo.POPULAR_MODELS.items():
                    if info.get("recommended"):
                        print(f"  {model_id} - {info['name']}")
                sys.exit(1)
            download_model(args.model, args.cache_dir)

if __name__ == "__main__":
    main()