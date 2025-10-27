"""
Advanced image processing for the Layout/Books module.

Provides sophisticated image handling with filters, masks, alpha channel
support, and anti-aliased rounded corners.
"""

from pathlib import Path
from typing import Tuple, Optional, Literal
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

from core.logging_config import LogManager
from .models import ImageStyle, Rect

logger = LogManager().get_logger("layout.image")


class ImageProcessor:
    """
    Advanced image processor for layout rendering.

    Features:
    - Multiple fit modes (cover, contain, fill)
    - Rounded corners with anti-aliasing
    - Image filters (blur, grayscale, sepia, etc.)
    - Alpha channel support
    - Border/stroke rendering
    """

    @staticmethod
    def load_and_process(
        image_path: str,
        target_rect: Rect,
        style: ImageStyle
    ) -> Optional[Image.Image]:
        """
        Load and process an image according to style specifications.

        Args:
            image_path: Path to source image
            target_rect: Target rectangle (x, y, width, height)
            style: Image style configuration

        Returns:
            Processed PIL Image or None if loading fails
        """
        try:
            # Load image
            img = Image.open(image_path)

            # Convert to RGBA for alpha channel support
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            _, _, target_w, target_h = target_rect

            # Apply fit mode
            img = ImageProcessor._apply_fit_mode(img, target_w, target_h, style.fit)

            # Apply rounded corners if specified
            if style.border_radius_px > 0:
                img = ImageProcessor._apply_rounded_corners(
                    img, style.border_radius_px
                )

            logger.debug(f"Processed image: {image_path}, size: {img.size}")
            return img

        except Exception as e:
            logger.error(f"Failed to process image {image_path}: {e}")
            return None

    @staticmethod
    def _apply_fit_mode(
        img: Image.Image,
        target_w: int,
        target_h: int,
        fit_mode: Literal["cover", "contain", "fill", "fit_width", "fit_height"]
    ) -> Image.Image:
        """Apply the specified fit mode to the image."""

        if fit_mode == "fill":
            # Stretch to exact dimensions
            return img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        elif fit_mode == "contain":
            # Scale to fit inside, preserve aspect ratio
            img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
            # Create a transparent canvas
            canvas = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
            # Center the image
            x = (target_w - img.width) // 2
            y = (target_h - img.height) // 2
            canvas.paste(img, (x, y))
            return canvas

        elif fit_mode == "cover":
            # Scale to cover entire area, crop excess
            img_ratio = img.width / img.height
            target_ratio = target_w / target_h

            if img_ratio > target_ratio:
                # Image is wider, scale by height
                new_h = target_h
                new_w = int(img.width * (target_h / img.height))
            else:
                # Image is taller, scale by width
                new_w = target_w
                new_h = int(img.height * (target_w / img.width))

            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Crop to exact size (center crop)
            left = (new_w - target_w) // 2
            top = (new_h - target_h) // 2
            img = img.crop((left, top, left + target_w, top + target_h))
            return img

        elif fit_mode == "fit_width":
            # Scale to match width, preserve aspect ratio
            new_w = target_w
            new_h = int(img.height * (target_w / img.width))
            return img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        elif fit_mode == "fit_height":
            # Scale to match height, preserve aspect ratio
            new_h = target_h
            new_w = int(img.width * (target_h / img.height))
            return img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        return img

    @staticmethod
    def _apply_rounded_corners(img: Image.Image, radius: int) -> Image.Image:
        """
        Apply rounded corners to an image with anti-aliasing.

        Args:
            img: Source image (RGBA)
            radius: Corner radius in pixels

        Returns:
            Image with rounded corners
        """
        # Create a mask for rounded corners
        mask = Image.new('L', img.size, 0)
        draw = ImageDraw.Draw(mask)

        # Draw rounded rectangle on mask at 2x resolution for better AA
        scale = 2
        large_size = (img.size[0] * scale, img.size[1] * scale)
        large_mask = Image.new('L', large_size, 0)
        large_draw = ImageDraw.Draw(large_mask)

        large_draw.rounded_rectangle(
            [(0, 0), large_size],
            radius=radius * scale,
            fill=255
        )

        # Downscale mask for anti-aliasing effect
        mask = large_mask.resize(img.size, Image.Resampling.LANCZOS)

        # Apply mask to alpha channel
        if img.mode == 'RGBA':
            # Composite with existing alpha
            alpha = img.split()[3]
            alpha = Image.composite(alpha, Image.new('L', img.size, 0), mask)
            img.putalpha(alpha)
        else:
            img.putalpha(mask)

        return img

    @staticmethod
    def apply_filter(
        img: Image.Image,
        filter_type: Literal["blur", "grayscale", "sepia", "sharpen", "none"] = "none",
        intensity: float = 1.0
    ) -> Image.Image:
        """
        Apply a filter to the image.

        Args:
            img: Source image
            filter_type: Type of filter to apply
            intensity: Filter intensity (0.0 to 1.0)

        Returns:
            Filtered image
        """
        if filter_type == "none":
            return img

        try:
            if filter_type == "blur":
                return img.filter(ImageFilter.GaussianBlur(radius=5 * intensity))

            elif filter_type == "grayscale":
                gray = img.convert('L')
                if intensity < 1.0:
                    # Blend with original
                    return Image.blend(img.convert('RGB'), gray.convert('RGB'), intensity)
                return gray.convert('RGBA')

            elif filter_type == "sepia":
                # Convert to grayscale first
                gray = img.convert('L')
                # Apply sepia tone
                sepia = Image.new('RGB', img.size)
                pixels = sepia.load()
                gray_pixels = gray.load()

                for y in range(img.size[1]):
                    for x in range(img.size[0]):
                        gray_val = gray_pixels[x, y]
                        # Sepia tone formula
                        r = min(255, int(gray_val * 1.0))
                        g = min(255, int(gray_val * 0.95))
                        b = min(255, int(gray_val * 0.82))
                        pixels[x, y] = (r, g, b)

                if intensity < 1.0:
                    return Image.blend(img.convert('RGB'), sepia, intensity).convert('RGBA')
                return sepia.convert('RGBA')

            elif filter_type == "sharpen":
                return img.filter(ImageFilter.UnsharpMask(radius=2 * intensity))

        except Exception as e:
            logger.warning(f"Failed to apply filter {filter_type}: {e}")
            return img

        return img

    @staticmethod
    def apply_adjustments(
        img: Image.Image,
        brightness: float = 1.0,
        contrast: float = 1.0,
        saturation: float = 1.0
    ) -> Image.Image:
        """
        Apply brightness, contrast, and saturation adjustments.

        Args:
            img: Source image
            brightness: Brightness factor (1.0 = no change, <1 darker, >1 brighter)
            contrast: Contrast factor (1.0 = no change)
            saturation: Saturation factor (1.0 = no change, 0 = grayscale)

        Returns:
            Adjusted image
        """
        try:
            if brightness != 1.0:
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(brightness)

            if contrast != 1.0:
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(contrast)

            if saturation != 1.0:
                enhancer = ImageEnhance.Color(img)
                img = enhancer.enhance(saturation)

        except Exception as e:
            logger.warning(f"Failed to apply adjustments: {e}")

        return img

    @staticmethod
    def draw_border(
        draw: ImageDraw.ImageDraw,
        rect: Rect,
        radius: int,
        stroke_width: int,
        stroke_color: Tuple[int, int, int]
    ) -> None:
        """
        Draw a border around a rectangle.

        Args:
            draw: ImageDraw instance
            rect: Rectangle (x, y, width, height)
            radius: Corner radius
            stroke_width: Border width in pixels
            stroke_color: RGB color tuple
        """
        x, y, w, h = rect

        if radius > 0:
            draw.rounded_rectangle(
                [x, y, x + w, y + h],
                radius=radius,
                outline=stroke_color,
                width=stroke_width
            )
        else:
            draw.rectangle(
                [x, y, x + w, y + h],
                outline=stroke_color,
                width=stroke_width
            )
