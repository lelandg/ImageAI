"""
Layout Engine for the Layout/Books module.

Handles page rendering to PNG and PDF, text layout, and image placement.
"""

import json
from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont

try:
    from reportlab.pdfgen import canvas as pdf_canvas
    from reportlab.lib.pagesizes import letter, A4
    REPORTLAB_AVAILABLE = True
except ImportError:
    pdf_canvas = None
    REPORTLAB_AVAILABLE = False

from core.logging_config import LogManager
from .models import (
    PageSpec, DocumentSpec, TextBlock, ImageBlock,
    TextStyle, ImageStyle, Rect
)
from .font_manager import FontManager
from .text_renderer import TextLayoutEngine
from .image_processor import ImageProcessor
from .template_engine import TemplateEngine

logger = LogManager().get_logger("layout.engine")


class LayoutEngine:
    """
    Main layout engine for rendering pages and documents.

    Phase 2 enhancements:
    - Advanced text rendering with hyphenation
    - Image processing with filters and effects
    - Template variable substitution
    """

    def __init__(
        self,
        font_manager: FontManager,
        use_advanced_text: bool = True,
        hyphenation_language: str = "en_US"
    ):
        """
        Initialize the layout engine.

        Args:
            font_manager: FontManager instance for font loading
            use_advanced_text: Whether to use advanced text rendering (Phase 2)
            hyphenation_language: Language for hyphenation (e.g., 'en_US')
        """
        self.font_manager = font_manager
        self.use_advanced_text = use_advanced_text

        # Phase 2 components
        self.text_engine = TextLayoutEngine(hyphenation_language) if use_advanced_text else None
        self.image_processor = ImageProcessor()
        self.template_engine = TemplateEngine()

    def render_page_png(
        self,
        page: PageSpec,
        out_path: Path,
        page_variables: Optional[dict] = None,
        process_template: bool = True
    ) -> None:
        """
        Render a single page to a PNG file.

        Args:
            page: PageSpec describing the page layout
            out_path: Output path for the PNG file
            page_variables: Optional variables for template substitution
            process_template: Whether to process template variables (Phase 2)
        """
        logger.info(f"Rendering page to PNG: {out_path}")

        # Process template variables if enabled
        if process_template:
            page = self.template_engine.process_page(page, page_variables)

        W, H = page.page_size_px
        bg = page.background or "#FFFFFF"

        # Create image with background
        img = Image.new("RGB", (W, H), self._hex_to_rgb(bg))
        draw = ImageDraw.Draw(img)

        # Render each block
        for block in page.blocks:
            try:
                if isinstance(block, ImageBlock):
                    self._render_image_block(img, draw, block)
                elif isinstance(block, TextBlock):
                    self._render_text_block(img, draw, block)
            except Exception as e:
                logger.error(f"Failed to render block {block.id}: {e}")

        # Save the image
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path)
        logger.info(f"Page rendered successfully to {out_path}")

    def _render_image_block(self, img: Image.Image, draw: ImageDraw.ImageDraw, block: ImageBlock) -> None:
        """Render an image block onto the page using Phase 2 ImageProcessor."""
        if not block.image_path or not Path(block.image_path).exists():
            logger.warning(f"Image path not found for block {block.id}: {block.image_path}")
            return

        x, y, w, h = block.rect

        # Use ImageProcessor for advanced image handling (Phase 2)
        processed_img = self.image_processor.load_and_process(
            block.image_path,
            block.rect,
            block.style
        )

        if processed_img is None:
            logger.warning(f"Failed to process image for block {block.id}")
            return

        # Handle RGBA images properly
        if processed_img.mode == 'RGBA':
            # Paste with alpha compositing
            img.paste(processed_img, (x, y), processed_img)
        else:
            # Simple paste for RGB
            img.paste(processed_img, (x, y))

        # Draw border if needed
        if block.style.stroke_px > 0:
            color_tuple = self._hex_to_rgb(block.style.stroke_color)
            self.image_processor.draw_border(
                draw, block.rect,
                block.style.border_radius_px,
                block.style.stroke_px,
                color_tuple
            )

    def _render_text_block(self, img: Image.Image, draw: ImageDraw.ImageDraw, block: TextBlock) -> None:
        """Render a text block onto the page with auto-sizing and Phase 2 enhancements."""
        x, y, w, h = block.rect
        text = block.text or ""

        if not text:
            return

        # Use advanced text rendering if available (Phase 2)
        if self.use_advanced_text and self.text_engine:
            self._render_text_advanced(draw, block)
        else:
            # Fallback to simple rendering (Phase 1)
            self._render_text_simple(draw, block)

    def _render_text_advanced(self, draw: ImageDraw.ImageDraw, block: TextBlock) -> None:
        """Render text using Phase 2 TextLayoutEngine with hyphenation and justification."""
        x, y, w, h = block.rect
        text = block.text or ""

        # Get optimal font size
        size = block.style.size_px
        font = self.font_manager.pil_font(block.style.family, size)

        # Layout text with advanced features
        paragraphs, total_height = self.text_engine.layout_text(
            text, font, w, h, block.style, draw
        )

        # Draw the laid-out text
        self.text_engine.draw_layout(paragraphs, draw, (x, y), font, block.style, w)

        logger.debug(f"Advanced text rendering: {len(paragraphs)} paragraphs, {total_height}px height")

    def _render_text_simple(self, draw: ImageDraw.ImageDraw, block: TextBlock) -> None:
        """Simple text rendering (Phase 1 compatibility)."""
        x, y, w, h = block.rect
        text = block.text or ""

        # Binary search for optimal font size that fits the box
        size = block.style.size_px
        while size >= 8:
            font = self.font_manager.pil_font(block.style.family, size)
            wrapped = self._wrap_to_width(draw, text, font, w)
            text_h = self._measure_text_height(draw, wrapped, font, block.style.line_height)

            if text_h <= h:
                break

            size -= 2

        # Draw the text
        self._draw_multiline_text(draw, wrapped, (x, y), font, block.style, w, h)

    def _wrap_to_width(self, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> List[str]:
        """Wrap text to fit within a maximum width."""
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            trial = (current_line + " " + word).strip()
            if draw.textlength(trial, font=font) <= max_w:
                current_line = trial
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines

    def _measure_text_height(self, draw: ImageDraw.ImageDraw, lines: List[str], font: ImageFont.FreeTypeFont, line_height: float) -> int:
        """Calculate total height of wrapped text."""
        ascent, descent = font.getmetrics()
        line_px = int((ascent + descent) * line_height)
        return line_px * len(lines)

    def _draw_multiline_text(
        self,
        draw: ImageDraw.ImageDraw,
        lines: List[str],
        origin: Tuple[int, int],
        font: ImageFont.FreeTypeFont,
        style: TextStyle,
        box_w: int,
        box_h: int
    ) -> None:
        """Draw multi-line text with alignment."""
        x, y = origin
        ascent, descent = font.getmetrics()
        line_px = int((ascent + descent) * style.line_height)

        for i, line in enumerate(lines):
            ty = y + i * line_px

            # Stop if we exceed the box height
            if ty + line_px > y + box_h:
                break

            # Calculate x position based on alignment
            if style.align == "center":
                tx = x + (box_w - int(draw.textlength(line, font=font))) // 2
            elif style.align == "right":
                tx = x + box_w - int(draw.textlength(line, font=font))
            else:  # left
                tx = x

            draw.text((tx, ty), line, fill=self._hex_to_rgb(style.color), font=font)

    def _draw_rounded_rectangle(
        self,
        draw: ImageDraw.ImageDraw,
        rect: Rect,
        radius: int,
        outline_px: int = 0,
        outline_color: str = "#000000"
    ) -> None:
        """Draw a rounded rectangle border."""
        x, y, w, h = rect

        if radius <= 0:
            if outline_px > 0:
                draw.rectangle([x, y, x + w, y + h], outline=self._hex_to_rgb(outline_color), width=outline_px)
            return

        # Use PIL's built-in rounded_rectangle
        draw.rounded_rectangle(
            [x, y, x + w, y + h],
            radius,
            outline=self._hex_to_rgb(outline_color) if outline_px > 0 else None,
            width=outline_px
        )

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color string to RGB tuple."""
        h = hex_color.strip("#")
        if len(h) == 6:
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore
        raise ValueError(f"Only #RRGGBB format supported, got: {hex_color}")

    def render_document_png(self, doc: DocumentSpec, output_dir: Path) -> List[Path]:
        """
        Render all pages of a document to PNG files.

        Args:
            doc: DocumentSpec describing the document
            output_dir: Directory to save PNG files

        Returns:
            List of paths to generated PNG files
        """
        logger.info(f"Rendering document '{doc.title}' to PNG pages in {output_dir}")

        output_dir.mkdir(parents=True, exist_ok=True)
        png_paths = []

        for i, page in enumerate(doc.pages, start=1):
            out_path = output_dir / f"page_{i:03d}.png"
            self.render_page_png(page, out_path)
            png_paths.append(out_path)

        logger.info(f"Rendered {len(png_paths)} pages to {output_dir}")
        return png_paths

    def save_pdf(self, doc: DocumentSpec, out_pdf: Path, png_pages: List[Path]) -> None:
        """
        Create a PDF from rendered PNG pages.

        Args:
            doc: DocumentSpec (for metadata)
            out_pdf: Output PDF path
            png_pages: List of PNG page images to include

        Note: Currently uses image-based PDF. Vector text rendering is a future enhancement.
        """
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError("ReportLab not installed. Cannot generate PDF.")

        logger.info(f"Creating PDF: {out_pdf}")

        c = pdf_canvas.Canvas(str(out_pdf))

        for i, png_path in enumerate(png_pages, start=1):
            logger.debug(f"Adding page {i}/{len(png_pages)} to PDF")

            with Image.open(png_path) as im:
                w, h = im.size
                c.setPageSize((w, h))
                c.drawInlineImage(str(png_path), 0, 0, width=w, height=h)
                c.showPage()

        c.save()
        logger.info(f"PDF saved: {out_pdf}")


def load_template_json(path: Path) -> PageSpec:
    """
    Load a page template from a JSON file.

    Args:
        path: Path to the template JSON file

    Returns:
        PageSpec instance
    """
    logger.info(f"Loading template from {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    blocks = []

    for b in data.get("blocks", []):
        rect = tuple(b["rect"])  # type: ignore

        if b["type"] == "text":
            style_data = b.get("style", {})
            style = TextStyle(**style_data)
            blocks.append(TextBlock(
                id=b["id"],
                rect=rect,
                text=b.get("text", ""),
                style=style
            ))

        elif b["type"] == "image":
            style_data = b.get("style", {})
            style = ImageStyle(**style_data)
            blocks.append(ImageBlock(
                id=b["id"],
                rect=rect,
                image_path=b.get("image_path"),
                style=style,
                alt_text=b.get("alt_text")
            ))

    page = PageSpec(
        page_size_px=tuple(data["page_size_px"]),  # type: ignore
        margin_px=data.get("margin_px", 64),
        bleed_px=data.get("bleed_px", 0),
        background=data.get("background"),
        blocks=blocks,
        variables=data.get("variables", {})
    )

    logger.info(f"Template loaded: {data.get('name', 'Unnamed')} with {len(blocks)} blocks")
    return page
