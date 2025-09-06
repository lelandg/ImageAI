#!/usr/bin/env python3
"""
ImageAI - AI Image Generation Tool

A desktop GUI and CLI application for AI image generation using Google Gemini 
and OpenAI (DALL-E) APIs.
"""

import sys
from pathlib import Path


def main():
    """Main entry point for ImageAI."""
    # Default to GUI mode when no arguments provided
    if len(sys.argv) == 1:
        # No arguments - launch GUI by default
        try:
            from gui import launch_gui
            launch_gui()
        except ImportError as e:
            # In WSL or when GUI deps missing, show helpful message
            print(f"GUI mode not available: {e}")
            print("\nTo install GUI dependencies: pip install PySide6")
            print("\nCLI mode is available. Quick start:")
            print("  python3 main.py -h                    # Show all options")
            print("  python3 main.py -t                    # Test API key")
            print("  python3 main.py -p 'your prompt'      # Generate image")
            print("  python3 main.py --help-api-key        # API key setup help")
            sys.exit(0)
    else:
        # Arguments provided - parse and handle CLI/GUI mode
        from cli import build_arg_parser, run_cli
        
        parser = build_arg_parser()
        args = parser.parse_args()
        
        # Check if --gui flag was explicitly provided
        if getattr(args, "gui", False):
            try:
                from gui import launch_gui
                launch_gui()
            except ImportError as e:
                print(f"Error: GUI dependencies not installed. {e}")
                print("Install with: pip install PySide6")
                sys.exit(1)
        else:
            # Run CLI with parsed arguments
            exit_code = run_cli(args)
            sys.exit(exit_code)


if __name__ == "__main__":
    main()