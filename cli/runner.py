"""CLI runner for ImageAI."""

import sys
from pathlib import Path
from typing import Optional, Tuple, List

from core import ConfigManager, get_api_key_url, sanitize_filename, read_key_file
from core.utils import read_readme_text, extract_api_key_help
from core.lyrics_to_prompts import LyricsToPromptsGenerator, load_lyrics_from_file
from providers import get_provider, preload_provider


def resolve_api_key(
    cli_key: Optional[str],
    key_file: Optional[str],
    provider: str = "google"
) -> Tuple[Optional[str], str]:
    """
    Resolve API key from various sources.
    
    Args:
        cli_key: API key from command line
        key_file: Path to key file
        provider: Provider name
    
    Returns:
        Tuple of (api_key, source_description)
    """
    # Priority: CLI arg > file > config > env
    if cli_key:
        return cli_key, "command-line"
    
    if key_file:
        fp = Path(key_file).expanduser()
        if fp.exists():
            key = read_key_file(fp)
            if key:
                return key, f"file:{fp}"
    
    # Check config
    config = ConfigManager()
    key = config.get_api_key(provider)
    if key:
        return key, "config"
    
    # Check environment variables
    import os
    env_vars = {
        "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "openai": ["OPENAI_API_KEY"],
        "stability": ["STABILITY_KEY", "STABILITY_API_KEY"],
        "local_sd": [],  # No API key needed
    }
    
    for var in env_vars.get(provider, []):
        key = os.getenv(var)
        if key:
            return key, f"env:{var}"
    
    return None, "none"


def store_api_key(api_key: str, provider: str = "google") -> None:
    """Store API key in configuration."""
    config = ConfigManager()
    config.set_api_key(provider, api_key)
    config.save()


def handle_lyrics_to_prompts(args) -> int:
    """
    Handle lyrics-to-prompts generation.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    lyrics_file = args.lyrics_to_prompts

    # Validate file
    lyrics_path = Path(lyrics_file).expanduser()
    if not lyrics_path.exists():
        print(f"Error: Lyrics file not found: {lyrics_file}")
        return 2

    # Load lyrics
    try:
        print(f"Loading lyrics from {lyrics_path}...")
        lyrics = load_lyrics_from_file(str(lyrics_path))
        print(f"Loaded {len(lyrics)} lyric lines")
    except Exception as e:
        print(f"Error loading lyrics: {e}")
        return 2

    # Get model (default to gpt-4o)
    model = getattr(args, "lyrics_model", None) or "gpt-4o"
    temperature = getattr(args, "lyrics_temperature", 0.7)
    style_hint = getattr(args, "lyrics_style", None)
    output_file = getattr(args, "lyrics_output", None)

    # Get API keys from config
    config = ConfigManager()
    config_dict = {}

    try:
        # Try to get API keys for different providers
        for provider_name in ["openai", "google", "anthropic"]:
            try:
                key = config.get_api_key(provider_name)
                if key:
                    config_dict[f"{provider_name}_api_key"] = key
            except:
                pass
    except Exception as e:
        print(f"Warning: Could not load API keys from config: {e}")

    if not config_dict:
        print("Error: No API keys found. Please set API keys using --set-key first.")
        print("Example: python main.py --provider openai --api-key YOUR_KEY --set-key")
        return 2

    # Create generator
    print(f"Initializing generator with model: {model}")
    print(f"Temperature: {temperature}")
    if style_hint:
        print(f"Style: {style_hint}")

    try:
        generator = LyricsToPromptsGenerator(config=config_dict)
    except Exception as e:
        print(f"Error initializing generator: {e}")
        print("Make sure LiteLLM is installed: pip install litellm")
        return 2

    # Generate prompts
    print("\nGenerating image prompts...")
    print("=" * 60)

    try:
        result = generator.generate(
            lyrics=lyrics,
            model=model,
            temperature=temperature,
            style_hint=style_hint
        )

        if not result.success:
            print(f"Error: {result.error}")
            return 3

        # Display results
        print(f"\n✅ Successfully generated {len(result.prompts)} image prompts\n")
        print("=" * 60)

        for i, prompt in enumerate(result.prompts, 1):
            print(f"\n{i}. Lyric: {prompt.line}")
            print(f"   Prompt: {prompt.image_prompt}")

        print("\n" + "=" * 60)

        # Save to file if requested
        if output_file:
            output_path = Path(output_file).expanduser()
            generator.save_to_json(result, str(output_path))
            print(f"\n💾 Saved to: {output_path}")
        else:
            # Auto-save with default name
            default_output = lyrics_path.with_suffix('.prompts.json')
            generator.save_to_json(result, str(default_output))
            print(f"\n💾 Saved to: {default_output}")

        return 0

    except Exception as e:
        print(f"Error during generation: {e}")
        import traceback
        traceback.print_exc()
        return 3


def run_cli(args) -> int:
    """
    Run CLI with parsed arguments.
    
    Args:
        args: Parsed command-line arguments
    
    Returns:
        Exit code (0 for success)
    """
    # Get provider and auth mode
    provider = (getattr(args, "provider", None) or "google").strip().lower()
    auth_mode = getattr(args, "auth_mode", "api-key")
    
    # Handle help for API key setup
    if getattr(args, "help_api_key", False):
        md = read_readme_text()
        section = extract_api_key_help(md)
        print(section)
        return 0

    # Handle --lyrics-to-prompts
    if getattr(args, "lyrics_to_prompts", None):
        return handle_lyrics_to_prompts(args)

    # Validate auth mode for provider
    if provider != "google" and auth_mode == "gcloud":
        print(f"Warning: --auth-mode=gcloud is only supported for Google provider.")
        print(f"Using api-key mode for {provider}.")
        auth_mode = "api-key"
    
    # Resolve API key
    key = None
    source = "none"
    
    if auth_mode == "api-key":
        key, source = resolve_api_key(args.api_key, args.api_key_file, provider)
    
    # Handle --set-key
    if args.set_key:
        set_key = args.api_key
        if not set_key and args.api_key_file:
            fp = Path(args.api_key_file).expanduser()
            set_key = read_key_file(fp)
        
        if not set_key:
            print("No API key provided to --set-key. Use --api-key or --api-key-file.")
            return 2
        
        store_api_key(set_key, provider=provider)
        config = ConfigManager()
        print(f"API key saved to {config.config_path}")
        key = set_key
        source = "stored"
    
    # Create provider configuration
    provider_config = {
        "api_key": key,
        "auth_mode": auth_mode,
    }
    
    # Preload the provider to show loading message early
    # This happens for all operations to give user feedback
    if args.test or args.prompt:
        preload_provider(provider, provider_config)
    
    # Handle --test
    if args.test:
        if auth_mode == "api-key" and not key and provider != "local_sd":
            print("No API key found. Provide with --api-key/--api-key-file or set via --set-key.")
            return 2
        
        try:
            provider_instance = get_provider(provider, provider_config)
            is_valid, message = provider_instance.validate_auth()
            
            if is_valid:
                print(f"Authentication successful for {provider} (source={source})")
                print(f"Status: {message}")
                return 0
            else:
                print(f"Authentication failed for {provider}")
                print(f"Error: {message}")
                return 3
                
        except Exception as e:
            print(f"Test failed for provider '{provider}': {e}")
            return 3
    
    # Handle --prompt
    if args.prompt:
        if auth_mode == "api-key" and not key and provider != "local_sd":
            print("No API key. Use --api-key/--api-key-file or --set-key.")
            return 2
        
        try:
            provider_instance = get_provider(provider, provider_config)
            
            # Get model or use default
            model = args.model or provider_instance.get_default_model()
            
            # Generate
            print(f"Generating with {provider} ({model})...")
            texts, images = provider_instance.generate(
                prompt=args.prompt,
                model=model,
                size=getattr(args, "size", "1024x1024"),
                quality=getattr(args, "quality", "standard"),
                n=getattr(args, "num_images", 1),
            )
            
            # Print any text output
            for text in texts:
                print(text)
            
            # Save images
            if images:
                if args.out:
                    # Save to specified path
                    out_path = Path(args.out).expanduser().resolve()
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Save first image
                    out_path.write_bytes(images[0])
                    print(f"Saved image to {out_path}")
                    
                    # Save additional images with suffixes
                    if len(images) > 1:
                        stem = out_path.stem
                        ext = out_path.suffix or ".png"
                        for i, img_data in enumerate(images[1:], start=2):
                            numbered_path = out_path.with_name(f"{stem}_{i}{ext}")
                            numbered_path.write_bytes(img_data)
                            print(f"Saved image to {numbered_path}")
                else:
                    # Auto-save to default directory
                    config = ConfigManager()
                    images_dir = config.get_images_dir()
                    
                    # Create filename from prompt
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    stub = sanitize_filename(args.prompt, max_len=60)
                    
                    for i, img_data in enumerate(images, start=1):
                        filename = f"{stub}_{timestamp}_{i}.png"
                        img_path = images_dir / filename
                        img_path.write_bytes(img_data)
                        print(f"Saved image to {img_path}")
                        
                        # Save metadata sidecar
                        meta = {
                            "prompt": args.prompt,
                            "provider": provider,
                            "model": model,
                            "timestamp": timestamp,
                        }
                        sidecar_path = img_path.with_suffix(".png.json")
                        import json
                        sidecar_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            
            return 0
            
        except Exception as e:
            print(f"Generation failed for provider '{provider}': {e}")
            return 4
    
    # If nothing to do, show help
    if not args.gui:
        print("Nothing to do. Run without arguments or with --gui to open the GUI,")
        print("use -p/--prompt to generate, or -t/--test to validate the key.")
        print("Use -h/--help for more options.")
    
    return 0