"""Argument parser for ImageAI CLI."""

import argparse
from core.constants import VERSION


def build_arg_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for CLI."""
    parser = argparse.ArgumentParser(
        prog="imageai",
        description="Generate AI images via Google Gemini or OpenAI API"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}"
    )
    
    # Provider selection
    parser.add_argument(
        "--provider",
        choices=["google", "openai"],
        default="google",
        help="AI provider to use (default: google)"
    )
    
    # Authentication
    auth_group = parser.add_argument_group("authentication")
    auth_group.add_argument(
        "-k", "--api-key",
        help="API key for the selected provider"
    )
    auth_group.add_argument(
        "-K", "--api-key-file",
        help="Path to file containing API key"
    )
    auth_group.add_argument(
        "--auth-mode",
        choices=["api-key", "gcloud"],
        default="api-key",
        help="Authentication mode (gcloud only for Google provider)"
    )
    
    # Actions
    action_group = parser.add_argument_group("actions")
    action_group.add_argument(
        "-p", "--prompt",
        help="Generate image from this text prompt"
    )
    action_group.add_argument(
        "-t", "--test",
        action="store_true",
        help="Test API key validity"
    )
    action_group.add_argument(
        "-s", "--set-key",
        action="store_true",
        help="Save API key to config file"
    )
    action_group.add_argument(
        "--gui",
        action="store_true",
        help="Launch graphical user interface"
    )
    
    # Generation options
    gen_group = parser.add_argument_group("generation options")
    gen_group.add_argument(
        "-m", "--model",
        help="Model to use for generation"
    )
    gen_group.add_argument(
        "-o", "--out",
        help="Output path for generated image"
    )
    gen_group.add_argument(
        "--size",
        default="1024x1024",
        help="Image size (default: 1024x1024)"
    )
    gen_group.add_argument(
        "--quality",
        choices=["standard", "hd"],
        default="standard",
        help="Image quality (OpenAI only)"
    )
    gen_group.add_argument(
        "-n", "--num-images",
        type=int,
        default=1,
        help="Number of images to generate"
    )
    
    # Help options
    help_group = parser.add_argument_group("help")
    help_group.add_argument(
        "--help-api-key",
        action="store_true",
        help="Show API key setup instructions"
    )
    
    return parser