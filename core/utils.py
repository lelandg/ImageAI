"""Utility functions for ImageAI."""

import re
import string
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from .constants import README_PATH
from .security import path_validator


def sanitize_filename(name: str, max_len: int = 100) -> str:
    """
    Sanitize a string for use as a filename.
    
    Args:
        name: String to sanitize
        max_len: Maximum length of filename
    
    Returns:
        Sanitized filename string
    """
    # Remove or replace invalid characters
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
    sanitized = "".join(c if c in valid_chars else "_" for c in name)
    
    # Remove multiple spaces/underscores
    sanitized = re.sub(r"[_\s]+", "_", sanitized)
    
    # Trim to max length
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len]
    
    # Remove trailing dots/spaces (Windows compatibility)
    sanitized = sanitized.rstrip(". ")
    
    # Fallback if empty
    if not sanitized:
        sanitized = "image"
    
    return sanitized


def read_key_file(path: Path) -> Optional[str]:
    """
    Read API key from a file.
    
    Args:
        path: Path to key file
    
    Returns:
        API key string or None if not found
    """
    try:
        # Read first non-empty line as key
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s:
                return s
    except (OSError, IOError, UnicodeDecodeError):
        return None
    return None


def read_readme_text() -> str:
    """
    Read README content for help display.
    
    Returns:
        README content or fallback help text
    """
    try:
        if README_PATH.exists():
            return README_PATH.read_text(encoding="utf-8")
    except (OSError, IOError, UnicodeDecodeError):
        pass
    
    # Fallback minimal help
    from .config import get_api_key_url
    return (
        "Authentication Setup:\n\n"
        "OPTION A: API Key (Simple)\n"
        f"1) Get a provider API key:\n"
        f"   - Google AI Studio: {get_api_key_url('google')}\n"
        f"   - OpenAI: {get_api_key_url('openai')}\n"
        "2) Save your key in the app Settings or via CLI -s with -k/-K.\n\n"
        "OPTION B: Google Cloud Account (Advanced)\n"
        "1) Install Google Cloud CLI:\n"
        "   https://cloud.google.com/sdk/docs/install\n"
        "2) Authenticate:\n"
        "   gcloud auth application-default login\n"
        "3) Use --auth-mode gcloud in CLI or select in GUI Settings\n\n"
        "For detailed instructions, see the README.md file.\n"
    )


def extract_api_key_help(md: str) -> str:
    """
    Extract API key help section from README.
    
    Args:
        md: Markdown content
    
    Returns:
        Extracted help section
    """
    # Extract the section starting at the API key/billing header
    start_header = "## 2) Get your Gemini API key OR set up Google Cloud authentication"
    if start_header in md:
        start = md.index(start_header)
        remainder = md[start + len(start_header):]
        next_idx = remainder.find("\n## ")
        if next_idx != -1:
            return start_header + remainder[:next_idx]
        else:
            return md[start:]
    
    # Fallback to old header format
    old_header = "## 2) Get your Gemini API key and enable billing"
    if old_header in md:
        start = md.index(old_header)
        remainder = md[start + len(old_header):]
        next_idx = remainder.find("\n## ")
        if next_idx != -1:
            return old_header + remainder[:next_idx]
        else:
            return md[start:]
    
    return md


def generate_timestamp() -> str:
    """
    Generate a timestamp string for filenames.
    
    Returns:
        Timestamp in format YYYYMMDD_HHMMSS
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
    
    Returns:
        Formatted size string
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def parse_image_size(size_str: str) -> tuple[int, int]:
    """
    Parse image size string like "1024x768" into tuple.
    
    Args:
        size_str: Size string in format "WIDTHxHEIGHT"
    
    Returns:
        Tuple of (width, height)
    """
    try:
        parts = size_str.lower().split("x")
        if len(parts) == 2:
            return (int(parts[0]), int(parts[1]))
    except (ValueError, IndexError, AttributeError):
        pass
    return (1024, 1024)  # Default size


def images_output_dir() -> Path:
    """Directory where generated images are auto-saved."""
    from .config import ConfigManager
    config = ConfigManager()
    d = config.config_dir / "generated"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sidecar_path(image_path: Path) -> Path:
    """Return the path of the JSON sidecar for a given image path."""
    return image_path.with_suffix(image_path.suffix + ".json")


def write_image_sidecar(image_path: Path, meta: dict) -> None:
    """Write human-readable JSON beside the image."""
    try:
        p = sidecar_path(image_path)
        p.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    except (OSError, IOError, json.JSONEncodeError):
        pass


def read_image_sidecar(image_path: Path) -> Optional[dict]:
    """Read metadata from image sidecar file."""
    try:
        sp = sidecar_path(image_path)
        if sp.exists():
            return json.loads(sp.read_text(encoding="utf-8"))
    except (OSError, IOError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return None


def detect_image_extension(data: bytes) -> str:
    """Guess file extension from image bytes. Defaults to .png."""
    try:
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if data.startswith(b"\xff\xd8"):
            return ".jpg"
        if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
            return ".gif"
        if data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
            return ".webp"
    except (IndexError, TypeError):
        pass
    return ".png"


def sanitize_stub_from_prompt(prompt: str, max_len: int = 60) -> str:
    """Create a safe filename stub from the prompt."""
    try:
        s = (prompt or "").strip()
        # use only first line to avoid huge names
        s = s.splitlines()[0] if s else ""
        # Replace separators with spaces, keep alnum, space, dash, underscore
        allowed = []
        for ch in s:
            if ch.isalnum() or ch in (" ", "-", "_"):
                allowed.append(ch)
            else:
                # convert other separators to space
                allowed.append(" ")
        s = "".join(allowed)
        # collapse whitespace to single underscore
        s = "_".join([t for t in s.strip().split() if t])
        if not s:
            s = "gen"
        # trim length
        if len(s) > max_len:
            s = s[:max_len].rstrip("_-")
        # Ensure doesn't start with dot to avoid hidden files
        if s.startswith("."):
            s = s.lstrip(".") or "gen"
        return s
    except (AttributeError, TypeError, ValueError):
        return "gen"


def auto_save_images(images: list, base_stub: str = "gen") -> list:
    """Auto-save all images to the images_output_dir(). Returns list of absolute Paths."""
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = images_output_dir()
    saved = []
    for idx, data in enumerate(images, start=1):
        ext = detect_image_extension(data if isinstance(data, (bytes, bytearray)) else bytes(data))
        name = f"{base_stub}_{ts}_{idx}{ext}"
        
        # Validate filename is safe
        if not path_validator.validate_filename(name):
            name = sanitize_filename(name)
        
        p = out_dir / name
        
        # Validate path doesn't escape output directory
        if not path_validator.is_safe_path(p, out_dir):
            continue  # Skip unsafe paths
        
        try:
            p.write_bytes(data)
            saved.append(p.resolve())
        except (OSError, IOError):
            continue
    return saved


def scan_disk_history(max_items: int = 500, project_only: bool = False) -> list[Path]:
    """Scan generated dir for images and return sorted list by mtime desc.

    Optimized to collect mtime in single pass and exit early when enough files found.

    Args:
        max_items: Maximum number of items to return
        project_only: If True, only return images with metadata sidecar files
    """
    try:
        out_dir = images_output_dir()
        exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

        # Collect files with mtime in single pass (avoid double stat calls)
        items_with_time = []
        scan_limit = max_items * 3  # Scan up to 3x max_items for early exit

        for p in out_dir.iterdir():
            # Skip DEBUG images entirely for performance
            if p.name.startswith("DEBUG_"):
                continue

            # Check file type
            if not (p.is_file() and p.suffix.lower() in exts):
                continue

            # Check for sidecar if project_only
            if project_only:
                sidecar = p.with_suffix(p.suffix + ".json")
                if not sidecar.exists():
                    continue

            # Get mtime once
            try:
                mtime = p.stat().st_mtime
                items_with_time.append((mtime, p))
            except (OSError, AttributeError):
                continue

            # Early exit if we have enough files
            if len(items_with_time) >= scan_limit:
                break

        # Sort by mtime (descending) and return top max_items
        items_with_time.sort(reverse=True, key=lambda x: x[0])
        return [p for _, p in items_with_time[:max_items]]

    except (OSError, IOError, AttributeError):
        return []


def find_cached_demo(prompt: str, provider: str = "google") -> Optional[Path]:
    """If prompt is one of the examples and a sidecar matches prompt+provider, return newest image path."""
    try:
        # Define examples here to avoid circular import
        EXAMPLES = [
            "A whimsical city made of candy canes and gumdrops at sunset, ultra-detailed, 8k",
            "A photorealistic glass terrarium containing a micro jungle with tiny glowing fauna",
            "Retro-futuristic poster of a rocket-powered bicycle racing across neon clouds",
            "An isometric diorama of a tiny island with waterfalls flowing into space",
            "Blueprint style render of a mechanical hummingbird with clockwork internals",
            "Studio portrait of a robot chef carefully plating molecular gastronomy",
            "A children's book illustration of a dragon learning to paint with oversized brushes",
            "Macro shot of dew drops forming constellations on a leaf under moonlight",
        ]
        
        if prompt not in EXAMPLES:
            return None
        matches: list[tuple[float, Path]] = []
        for img in scan_disk_history(1000):
            meta = read_image_sidecar(img)
            if not meta:
                continue
            if meta.get("prompt") == prompt and meta.get("provider") == provider:
                try:
                    mtime = img.stat().st_mtime
                except (OSError, AttributeError):
                    mtime = 0.0
                matches.append((mtime, img))
        if matches:
            matches.sort(key=lambda t: t[0], reverse=True)
            return matches[0][1]
    except (OSError, IOError, IndexError):
        return None
    return None


def default_model_for_provider(provider: str) -> str:
    """Get default model for a provider."""
    provider = (provider or "google").lower()
    if provider == "openai":
        return "dall-e-3"
    return "gemini-2.5-flash-image"


def cleanup_debug_images() -> tuple[int, int]:
    """Clean up debug images at startup.

    - Delete all DEBUG_CANVAS_COMPOSED images
    - Delete DEBUG_RAW_GEMINI images that are redundant (same timestamp/resolution as final image)

    Returns:
        Tuple of (composed_deleted, raw_deleted)
    """
    try:
        from PIL import Image
        import io

        out_dir = images_output_dir()
        composed_deleted = 0
        raw_deleted = 0

        # Step 1: Delete all DEBUG_CANVAS_COMPOSED images
        for p in out_dir.glob("DEBUG_CANVAS_COMPOSED_*.png"):
            try:
                p.unlink()
                composed_deleted += 1
            except (OSError, IOError):
                pass

        # Step 2: Find and delete redundant DEBUG_RAW_GEMINI images
        # Build a map of final images by timestamp (within 5 second window)
        final_images = {}  # timestamp_range -> (path, width, height)
        for p in out_dir.iterdir():
            # Skip debug files
            if p.name.startswith("DEBUG_"):
                continue
            # Only process images
            if not (p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg"}):
                continue

            try:
                # Get timestamp from file mtime
                mtime = int(p.stat().st_mtime)
                # Get resolution
                img_data = p.read_bytes()
                img = Image.open(io.BytesIO(img_data))
                width, height = img.size

                # Store in map with timestamp range (within 5 seconds)
                for offset in range(-5, 6):  # -5 to +5 seconds
                    ts = mtime + offset
                    if ts not in final_images:
                        final_images[ts] = []
                    final_images[ts].append((p, width, height))
            except (OSError, IOError, Exception):
                pass

        # Step 3: Check each DEBUG_RAW_GEMINI image
        for debug_path in out_dir.glob("DEBUG_RAW_GEMINI_*.*"):
            try:
                # Get debug image mtime and resolution (don't parse filename - use filesystem)
                debug_mtime = int(debug_path.stat().st_mtime)
                debug_data = debug_path.read_bytes()
                debug_img = Image.open(io.BytesIO(debug_data))
                debug_width, debug_height = debug_img.size

                # Check if there's a matching final image within time window
                # Search within ±10 seconds for generous matching
                matched = False
                for offset in range(-10, 11):
                    check_time = debug_mtime + offset
                    if check_time in final_images:
                        for final_path, final_width, final_height in final_images[check_time]:
                            # Match if resolution is same (or very close)
                            if abs(final_width - debug_width) <= 10 and abs(final_height - debug_height) <= 10:
                                # Redundant - delete it
                                debug_path.unlink()
                                raw_deleted += 1
                                matched = True
                                break
                    if matched:
                        break
            except (OSError, IOError, ValueError, Exception):
                pass

        return (composed_deleted, raw_deleted)
    except Exception:
        return (0, 0)