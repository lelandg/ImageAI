"""
Reference Image Compositor for Multi-Image Character Design Sheets.

Composites multiple reference images into a single square canvas for use with
image generation models that have multi-person/character limitations.
"""

import logging
from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont
import math

logger = logging.getLogger(__name__)


class ReferenceImageCompositor:
    """
    Composites multiple reference images into a single image on a square canvas.

    Designed for creating character design sheets where multiple people/characters
    need to be represented in a single reference image for AI models.
    """

    DEFAULT_CANVAS_SIZE = 1024  # Square canvas (1:1 aspect ratio)
    BACKGROUND_COLOR = (255, 255, 255, 0)  # Transparent white
    PADDING = 20  # Padding between images and edges

    def __init__(self, canvas_size: int = DEFAULT_CANVAS_SIZE):
        """
        Initialize compositor.

        Args:
            canvas_size: Size of square canvas (width = height)
        """
        self.canvas_size = canvas_size
        self.logger = logging.getLogger(__name__)

    def composite_images(
        self,
        image_paths: List[Path],
        output_path: Path,
        arrangement: str = "grid"
    ) -> Optional[Path]:
        """
        Composite multiple images into a single square canvas.

        Args:
            image_paths: List of paths to images to composite
            output_path: Path where composite should be saved
            arrangement: Layout arrangement ("grid", "horizontal", "vertical")

        Returns:
            Path to saved composite image, or None if failed
        """
        if not image_paths:
            self.logger.error("No images provided for compositing")
            return None

        try:
            # Load all images
            images = []
            for img_path in image_paths:
                if not img_path.exists():
                    self.logger.warning(f"Image not found: {img_path}")
                    continue

                img = Image.open(img_path)
                # Convert to RGBA for transparency support
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                images.append(img)

            if not images:
                self.logger.error("No valid images loaded")
                return None

            self.logger.info(
                f"Compositing {len(images)} images into {self.canvas_size}x{self.canvas_size} canvas"
            )

            # Create transparent square canvas
            canvas = Image.new('RGBA', (self.canvas_size, self.canvas_size), self.BACKGROUND_COLOR)

            # Arrange images based on layout
            if arrangement == "grid":
                self._arrange_grid(canvas, images)
            elif arrangement == "horizontal":
                self._arrange_horizontal(canvas, images)
            elif arrangement == "vertical":
                self._arrange_vertical(canvas, images)
            else:
                self.logger.warning(f"Unknown arrangement: {arrangement}, using grid")
                self._arrange_grid(canvas, images)

            # Save composite
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert to RGB if saving as JPEG
            if output_path.suffix.lower() in ['.jpg', '.jpeg']:
                # Create white background for JPEG
                rgb_canvas = Image.new('RGB', canvas.size, (255, 255, 255))
                rgb_canvas.paste(canvas, mask=canvas.split()[3] if canvas.mode == 'RGBA' else None)
                rgb_canvas.save(output_path, quality=95)
            else:
                # Save as PNG with transparency
                canvas.save(output_path)

            self.logger.info(f"✓ Composite saved: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Failed to composite images: {e}", exc_info=True)
            return None

    def _arrange_grid(self, canvas: Image.Image, images: List[Image.Image]):
        """
        Arrange images in a grid layout.

        Args:
            canvas: Canvas to draw on
            images: List of images to arrange
        """
        num_images = len(images)

        # Calculate grid dimensions (as square as possible)
        cols = math.ceil(math.sqrt(num_images))
        rows = math.ceil(num_images / cols)

        # Calculate cell size with padding
        cell_width = (self.canvas_size - self.PADDING * (cols + 1)) // cols
        cell_height = (self.canvas_size - self.PADDING * (rows + 1)) // rows
        cell_size = min(cell_width, cell_height)  # Keep square cells

        self.logger.debug(f"Grid layout: {rows}x{cols}, cell size: {cell_size}x{cell_size}")

        # Place each image in grid
        for idx, img in enumerate(images):
            row = idx // cols
            col = idx % cols

            # Calculate position (centered in grid)
            x_offset = (self.canvas_size - (cols * cell_size + (cols - 1) * self.PADDING)) // 2
            y_offset = (self.canvas_size - (rows * cell_size + (rows - 1) * self.PADDING)) // 2

            x = x_offset + col * (cell_size + self.PADDING)
            y = y_offset + row * (cell_size + self.PADDING)

            # Resize image to fit cell while maintaining aspect ratio
            resized_img = self._resize_to_fit(img, cell_size, cell_size)

            # Center image in cell
            paste_x = x + (cell_size - resized_img.width) // 2
            paste_y = y + (cell_size - resized_img.height) // 2

            # Paste with alpha channel for transparency
            canvas.paste(resized_img, (paste_x, paste_y), resized_img if resized_img.mode == 'RGBA' else None)

    def _arrange_horizontal(self, canvas: Image.Image, images: List[Image.Image]):
        """
        Arrange images horizontally (side by side).

        Args:
            canvas: Canvas to draw on
            images: List of images to arrange
        """
        num_images = len(images)

        # Calculate cell width (equal distribution)
        cell_width = (self.canvas_size - self.PADDING * (num_images + 1)) // num_images
        cell_height = self.canvas_size - 2 * self.PADDING

        self.logger.debug(f"Horizontal layout: {num_images} images, cell size: {cell_width}x{cell_height}")

        # Place each image
        for idx, img in enumerate(images):
            x = self.PADDING + idx * (cell_width + self.PADDING)
            y = self.PADDING

            # Resize to fit
            resized_img = self._resize_to_fit(img, cell_width, cell_height)

            # Center vertically
            paste_y = y + (cell_height - resized_img.height) // 2

            canvas.paste(resized_img, (x, paste_y), resized_img if resized_img.mode == 'RGBA' else None)

    def _arrange_vertical(self, canvas: Image.Image, images: List[Image.Image]):
        """
        Arrange images vertically (stacked).

        Args:
            canvas: Canvas to draw on
            images: List of images to arrange
        """
        num_images = len(images)

        # Calculate cell height (equal distribution)
        cell_height = (self.canvas_size - self.PADDING * (num_images + 1)) // num_images
        cell_width = self.canvas_size - 2 * self.PADDING

        self.logger.debug(f"Vertical layout: {num_images} images, cell size: {cell_width}x{cell_height}")

        # Place each image
        for idx, img in enumerate(images):
            x = self.PADDING
            y = self.PADDING + idx * (cell_height + self.PADDING)

            # Resize to fit
            resized_img = self._resize_to_fit(img, cell_width, cell_height)

            # Center horizontally
            paste_x = x + (cell_width - resized_img.width) // 2

            canvas.paste(resized_img, (paste_x, y), resized_img if resized_img.mode == 'RGBA' else None)

    def _resize_to_fit(self, img: Image.Image, max_width: int, max_height: int) -> Image.Image:
        """
        Resize image to fit within max dimensions while maintaining aspect ratio.

        Args:
            img: Image to resize
            max_width: Maximum width
            max_height: Maximum height

        Returns:
            Resized image
        """
        # Calculate scaling factor
        width_ratio = max_width / img.width
        height_ratio = max_height / img.height
        scale = min(width_ratio, height_ratio)

        # Calculate new size
        new_width = int(img.width * scale)
        new_height = int(img.height * scale)

        # Resize with high-quality resampling
        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    @staticmethod
    def generate_composite_prompt(user_description: str, num_images: int) -> str:
        """
        Generate the complete prompt for composite image generation.

        Takes user's description and appends arrangement instructions.

        Args:
            user_description: User's description (e.g., "These people as cartoon characters")
            num_images: Number of images in the composite

        Returns:
            Complete prompt with arrangement instructions
        """
        # Append arrangement instructions
        arrangement_text = (
            f"Place each in an equal part of the image, "
            f"on a clean background, suitable as character design sheet."
        )

        complete_prompt = f"{user_description}. {arrangement_text}"

        logger.debug(f"Generated composite prompt: {complete_prompt}")
        return complete_prompt
