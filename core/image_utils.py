"""Image processing utilities for ImageAI."""

from typing import Tuple, Optional, List
from PIL import Image
import io
import logging

logger = logging.getLogger(__name__)


def auto_crop_solid_borders(image_data: bytes, variance_threshold: float = 5.0) -> bytes:
    """
    Auto-crop uniform color borders from an image.

    This is particularly useful for images from Nano Banana (Gemini) which may return
    square images with uniform color padding when aspect ratio is requested.

    Args:
        image_data: Raw image bytes
        variance_threshold: Threshold for color variance to consider a row/column as uniform

    Returns:
        Cropped image as bytes, or original if no uniform borders detected
    """
    try:
        # Load image
        img = Image.open(io.BytesIO(image_data))
        logger.debug(f"Auto-crop: Original image size: {img.size}")

        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')

        width, height = img.size
        pixels = img.load()

        # Helper function to calculate variance of colors in a line
        def calculate_line_variance(pixels_line: List[Tuple[int, int, int]]) -> float:
            """Calculate the variance of colors in a line of pixels."""
            if not pixels_line:
                return 0.0

            # Calculate mean color
            r_mean = sum(p[0] for p in pixels_line) / len(pixels_line)
            g_mean = sum(p[1] for p in pixels_line) / len(pixels_line)
            b_mean = sum(p[2] for p in pixels_line) / len(pixels_line)

            # Calculate variance
            variance = sum(
                (p[0] - r_mean) ** 2 + (p[1] - g_mean) ** 2 + (p[2] - b_mean) ** 2
                for p in pixels_line
            ) / len(pixels_line)

            return variance

        # Find borders by looking for uniform color areas
        # Start from edges and move inward until we find non-uniform content

        # Check top border - find first non-uniform row
        top = 0
        for y in range(height // 3):  # Only check up to 1/3 of image
            row = [pixels[x, y] for x in range(0, width, max(1, width // 100))]  # Sample pixels
            variance = calculate_line_variance(row)
            if variance > variance_threshold:
                break
            top = y  # Keep updating until we find non-uniform content

        # Check bottom border - find first non-uniform row from bottom
        bottom = height - 1
        for y in range(height - 1, 2 * height // 3, -1):  # Only check bottom 1/3
            row = [pixels[x, y] for x in range(0, width, max(1, width // 100))]  # Sample pixels
            variance = calculate_line_variance(row)
            if variance > variance_threshold:
                break
            bottom = y  # Keep updating until we find non-uniform content

        # Check left border - find first non-uniform column
        left = 0
        for x in range(width // 3):  # Only check left 1/3
            col = [pixels[x, y] for y in range(top, min(bottom + 1, height), max(1, (bottom - top) // 100))]
            if col:
                variance = calculate_line_variance(col)
                if variance > variance_threshold:
                    break
                left = x  # Keep updating until we find non-uniform content

        # Check right border - find first non-uniform column from right
        right = width - 1
        for x in range(width - 1, 2 * width // 3, -1):  # Only check right 1/3
            col = [pixels[x, y] for y in range(top, min(bottom + 1, height), max(1, (bottom - top) // 100))]
            if col:
                variance = calculate_line_variance(col)
                if variance > variance_threshold:
                    break
                right = x  # Keep updating until we find non-uniform content

        # Calculate crop dimensions
        crop_width = right - left + 1
        crop_height = bottom - top + 1

        logger.debug(f"Auto-crop: Detected borders - top:{top}, bottom:{bottom}, left:{left}, right:{right}")
        logger.debug(f"Auto-crop: Crop dimensions - width:{crop_width}, height:{crop_height}")

        # Only crop if we found significant borders (at least 5% reduction)
        # AND ensure we're not cropping too much (keep at least 50% of image)
        if (crop_width < width * 0.95 or crop_height < height * 0.95) and \
           crop_width > width * 0.5 and crop_height > height * 0.5:
            # Crop the image
            cropped = img.crop((left, top, right + 1, bottom + 1))
            logger.info(f"Auto-crop: Cropped from {width}x{height} to {cropped.width}x{cropped.height}")

            # Convert back to bytes
            output = io.BytesIO()
            cropped.save(output, format='PNG')
            return output.getvalue()

        logger.debug("Auto-crop: No significant uniform borders found, returning original")
        # Return original if no significant cropping needed
        return image_data

    except Exception as e:
        logger.error(f"Auto-crop failed: {e}")
        # If any error occurs, return original image
        return image_data


def detect_aspect_ratio(image_data: bytes) -> Tuple[int, int]:
    """
    Detect the actual aspect ratio of image content (after auto-cropping).

    Args:
        image_data: Raw image bytes

    Returns:
        Tuple of (width, height) of the actual content
    """
    try:
        # First try to auto-crop
        cropped_data = auto_crop_solid_borders(image_data)

        # Load the cropped image to get dimensions
        img = Image.open(io.BytesIO(cropped_data))
        return img.size

    except Exception:
        # If error, try to get original dimensions
        try:
            img = Image.open(io.BytesIO(image_data))
            return img.size
        except:
            return (1024, 1024)  # Default fallback