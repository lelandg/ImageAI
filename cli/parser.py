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
        choices=["google", "openai", "stability", "local_sd"],
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
        default=None,
        help="Image size (default: 1024x1024). Mutually exclusive with --custom-size."
    )
    gen_group.add_argument(
        "--quality",
        choices=["auto", "low", "medium", "high", "standard", "hd"],
        default=None,
        help="Image quality / reasoning level (gpt-image-2: auto|low|medium|high; "
             "dall-e-3: standard|hd). Defaults to model's default.",
    )
    gen_group.add_argument(
        "--output-format",
        choices=["png", "jpeg", "webp"],
        help="Output image format (gpt-image-2 / gpt-image-1.5 only)",
    )
    gen_group.add_argument(
        "--output-compression",
        type=int,
        metavar="N",
        help="Output compression 0-100 (jpeg/webp only)",
    )
    gen_group.add_argument(
        "--moderation",
        choices=["auto", "low"],
        help="Content moderation level (gpt-image-2 only; 'low' is permissive)",
    )
    gen_group.add_argument(
        "--custom-size",
        metavar="WxH",
        help="Custom image size; mutually exclusive with --size. "
             "gpt-image-2 only — both edges multiples of 16, max edge 3840, "
             "aspect ≤3:1, total pixels 655K-8.3M.",
    )
    gen_group.add_argument(
        "--stream-partials",
        action="store_true",
        help="Stream up to 2 partial images during generation (gpt-image-2 only). "
             "Saves out.p0.png, out.p1.png, then final out.png.",
    )
    gen_group.add_argument(
        "--reference",
        action="append",
        metavar="IMG",
        help="Reference image path (repeatable, up to 10). Routes to /v1/images/edits.",
    )
    gen_group.add_argument(
        "--mask",
        metavar="PNG",
        help="Alpha mask PNG for inpainting (used with --reference). "
             "Transparent pixels = edit zone; opaque = preserve.",
    )
    gen_group.add_argument(
        "-n", "--num-images",
        type=int,
        default=1,
        help="Number of images to generate"
    )

    # Batch API
    batch_group = parser.add_argument_group("batch API")
    batch_group.add_argument(
        "--batch",
        action="store_true",
        help="Submit as a Batch API job instead of a sync request. Prints job ID.",
    )
    batch_group.add_argument(
        "--batch-status",
        metavar="JOB_ID",
        help="Print the status of a previously submitted batch job",
    )
    batch_group.add_argument(
        "--batch-fetch",
        metavar="JOB_ID",
        help="Download completed batch outputs to the current images dir",
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

    # Help options
    help_group = parser.add_argument_group("help")
    help_group.add_argument(
        "--help-api-key",
        action="store_true",
        help="Show API key setup instructions"
    )
    
    return parser