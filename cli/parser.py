"""Argument parser for ImageAI CLI."""

import argparse
from core.constants import VERSION, __author__, __email__, __copyright__


def build_arg_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for CLI."""
    parser = argparse.ArgumentParser(
        prog="imageai",
        description="Generate AI images via Google Gemini or OpenAI API"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}\n{__copyright__}\nAuthor: {__author__} <{__email__}>"
    )
    
    # Provider selection
    parser.add_argument(
        "--provider",
        choices=["google", "openai", "stability", "local_sd", "ltx-video"],
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
    action_group.add_argument(
        "--lyrics-to-prompts",
        metavar="LYRICS_FILE",
        help="Convert lyrics file to image prompts using AI"
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

    # Lyrics-to-prompts options
    lyrics_group = parser.add_argument_group("lyrics-to-prompts options")
    lyrics_group.add_argument(
        "--lyrics-model",
        help="LLM model for lyrics-to-prompts (e.g., gpt-4o, gemini/gemini-2.0-flash-exp)"
    )
    lyrics_group.add_argument(
        "--lyrics-temperature",
        type=float,
        default=0.7,
        help="Temperature for lyrics generation (default: 0.7)"
    )
    lyrics_group.add_argument(
        "--lyrics-style",
        help="Style hint for prompt generation (e.g., cinematic, photorealistic)"
    )
    lyrics_group.add_argument(
        "--lyrics-output",
        help="Output JSON file for generated prompts"
    )

    # LTX-Video options
    ltx_group = parser.add_argument_group("ltx-video options")
    ltx_group.add_argument(
        "--ltx-deployment",
        choices=["local", "fal", "replicate", "comfyui"],
        default="local",
        help="LTX-Video deployment mode (default: local)"
    )
    ltx_group.add_argument(
        "--ltx-model",
        choices=["ltx-video-2b", "ltx-video-13b", "ltx-2-fast", "ltx-2-pro", "ltx-2-ultra"],
        default="ltx-video-2b",
        help="LTX-Video model (default: ltx-video-2b)"
    )
    ltx_group.add_argument(
        "--ltx-resolution",
        choices=["720p", "1080p", "4K"],
        default="1080p",
        help="Video resolution (default: 1080p)"
    )
    ltx_group.add_argument(
        "--ltx-aspect",
        choices=["16:9", "9:16", "1:1", "21:9"],
        default="16:9",
        help="Video aspect ratio (default: 16:9)"
    )
    ltx_group.add_argument(
        "--ltx-fps",
        type=int,
        choices=[24, 30, 50],
        default=30,
        help="Video FPS (default: 30)"
    )
    ltx_group.add_argument(
        "--ltx-duration",
        type=int,
        default=5,
        help="Video duration in seconds, 1-10 (default: 5)"
    )
    ltx_group.add_argument(
        "--ltx-image",
        help="Start frame image for image-to-video"
    )
    ltx_group.add_argument(
        "--ltx-camera-motion",
        choices=["pan_left", "pan_right", "zoom_in", "zoom_out", "orbit",
                 "dolly_forward", "dolly_backward", "crane_up", "crane_down"],
        help="Camera motion type"
    )
    ltx_group.add_argument(
        "--ltx-guidance",
        type=float,
        default=7.5,
        help="Guidance scale (default: 7.5)"
    )
    ltx_group.add_argument(
        "--ltx-steps",
        type=int,
        default=50,
        help="Number of inference steps (default: 50)"
    )
    ltx_group.add_argument(
        "--ltx-seed",
        type=int,
        help="Random seed for reproducibility"
    )

    # Help options
    help_group = parser.add_argument_group("help")
    help_group.add_argument(
        "--help-api-key",
        action="store_true",
        help="Show API key setup instructions"
    )

    return parser