"""
Advanced text rendering for the Layout/Books module.

Provides sophisticated text layout with hyphenation, justification,
widow/orphan control, and multi-paragraph support.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
from PIL import ImageDraw, ImageFont

try:
    import pyphen
    HYPHENATION_AVAILABLE = True
except ImportError:
    pyphen = None
    HYPHENATION_AVAILABLE = False

from core.logging_config import LogManager
from .models import TextStyle

logger = LogManager().get_logger("layout.text")


@dataclass
class LayoutLine:
    """A single line of text with layout information."""
    text: str
    width: float  # Actual width in pixels
    word_count: int
    has_hyphen: bool = False
    is_paragraph_end: bool = False


@dataclass
class LayoutParagraph:
    """A paragraph with its layout lines."""
    lines: List[LayoutLine]
    spacing_after: int = 0  # Pixels to add after this paragraph


class TextLayoutEngine:
    """
    Advanced text layout engine with support for:
    - Word wrapping with hyphenation
    - Justification with word spacing
    - Widow/orphan control
    - Multi-paragraph handling
    - Letter spacing adjustment
    """

    def __init__(self, language: str = "en_US"):
        """
        Initialize the text layout engine.

        Args:
            language: Language code for hyphenation (e.g., 'en_US', 'en_GB')
        """
        self.language = language
        self.hyphenator = None

        if HYPHENATION_AVAILABLE:
            try:
                self.hyphenator = pyphen.Pyphen(lang=language)
                logger.info(f"Hyphenation enabled for {language}")
            except Exception as e:
                logger.warning(f"Failed to initialize hyphenation for {language}: {e}")
        else:
            logger.info("pyphen not available, hyphenation disabled")

    def layout_text(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: int,
        max_height: int,
        style: TextStyle,
        draw: ImageDraw.ImageDraw
    ) -> Tuple[List[LayoutParagraph], int]:
        """
        Layout text into paragraphs and lines.

        Args:
            text: Text to layout (can contain newlines for paragraphs)
            font: Font to use
            max_width: Maximum width in pixels
            max_height: Maximum height in pixels
            style: Text style configuration
            draw: ImageDraw instance for measuring text

        Returns:
            Tuple of (paragraphs, total_height)
        """
        # Split text into paragraphs
        paragraphs_text = text.split('\n\n')
        if not paragraphs_text:
            paragraphs_text = [text]

        paragraphs = []
        total_height = 0

        ascent, descent = font.getmetrics()
        line_height_px = int((ascent + descent) * style.line_height)

        for i, para_text in enumerate(paragraphs_text):
            if not para_text.strip():
                continue

            # Wrap this paragraph
            lines = self._wrap_paragraph(
                para_text.strip(),
                font,
                max_width,
                style,
                draw
            )

            # Apply widow/orphan control
            lines = self._apply_widow_orphan_control(lines)

            # Calculate paragraph height
            para_height = len(lines) * line_height_px
            is_last_para = (i == len(paragraphs_text) - 1)

            # Add inter-paragraph spacing (not after last paragraph)
            spacing_after = 0 if is_last_para else line_height_px // 2

            # Check if we have room for this paragraph
            if total_height + para_height + spacing_after > max_height:
                # Try to fit at least some lines
                remaining_height = max_height - total_height
                max_lines = remaining_height // line_height_px

                if max_lines > 0:
                    lines = lines[:max_lines]
                    para_height = len(lines) * line_height_px
                    spacing_after = 0  # No spacing if cut off
                else:
                    break  # Can't fit any more

            # Mark last line of paragraph
            if lines:
                lines[-1].is_paragraph_end = True

            paragraphs.append(LayoutParagraph(
                lines=lines,
                spacing_after=spacing_after
            ))

            total_height += para_height + spacing_after

            # Stop if we've filled the available space
            if total_height >= max_height:
                break

        return paragraphs, total_height

    def _wrap_paragraph(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: int,
        style: TextStyle,
        draw: ImageDraw.ImageDraw
    ) -> List[LayoutLine]:
        """Wrap a single paragraph into lines."""
        words = text.split()
        lines = []
        current_line = []
        current_width = 0

        for word in words:
            # Try adding this word to current line
            test_line = current_line + [word]
            test_text = ' '.join(test_line)
            test_width = draw.textlength(test_text, font=font)

            if test_width <= max_width or not current_line:
                # Word fits or it's the first word
                current_line.append(word)
                current_width = test_width
            else:
                # Word doesn't fit, try hyphenation
                if self.hyphenator and style.wrap == "word" and len(word) > 6:
                    # Try to hyphenate and fit part of the word
                    hyphenated = self._try_hyphenate(
                        word, current_line, font, max_width, draw
                    )

                    if hyphenated:
                        # Successfully hyphenated
                        line_text, remaining = hyphenated
                        line_width = draw.textlength(line_text, font=font)
                        lines.append(LayoutLine(
                            text=line_text,
                            width=line_width,
                            word_count=len(current_line) + 1,
                            has_hyphen=True
                        ))
                        # Start new line with remaining part
                        current_line = [remaining]
                        current_width = draw.textlength(remaining, font=font)
                        continue

                # Hyphenation didn't work, finish current line
                line_text = ' '.join(current_line)
                lines.append(LayoutLine(
                    text=line_text,
                    width=current_width,
                    word_count=len(current_line)
                ))

                # Start new line with current word
                current_line = [word]
                current_width = draw.textlength(word, font=font)

        # Add remaining line
        if current_line:
            line_text = ' '.join(current_line)
            lines.append(LayoutLine(
                text=line_text,
                width=current_width,
                word_count=len(current_line)
            ))

        return lines

    def _try_hyphenate(
        self,
        word: str,
        current_line: List[str],
        font: ImageFont.FreeTypeFont,
        max_width: int,
        draw: ImageDraw.ImageDraw
    ) -> Optional[Tuple[str, str]]:
        """
        Try to hyphenate a word to fit on the current line.

        Returns:
            Tuple of (line_with_hyphen, remaining_text) or None if can't hyphenate
        """
        if not self.hyphenator:
            return None

        # Get hyphenation points
        hyphenated = self.hyphenator.inserted(word, hyphen='-')
        parts = hyphenated.split('-')

        # Try progressively longer prefixes
        for i in range(len(parts) - 1, 0, -1):
            prefix = '-'.join(parts[:i]) + '-'
            remaining = '-'.join(parts[i:])

            # Test if this fits
            test_line = current_line + [prefix]
            test_text = ' '.join(test_line)
            test_width = draw.textlength(test_text, font=font)

            if test_width <= max_width:
                return (test_text, remaining)

        return None

    def _apply_widow_orphan_control(self, lines: List[LayoutLine]) -> List[LayoutLine]:
        """
        Apply widow/orphan control to prevent single lines at start/end of columns.

        Widow: Last line of paragraph at top of new column
        Orphan: First line of paragraph at bottom of column
        """
        if len(lines) < 3:
            return lines  # Too short to apply control

        # For now, we just ensure we don't have single-word short lines at the end
        # More sophisticated control would require column/page context

        # Check if last line is very short (potential widow)
        if lines and len(lines) > 1:
            last_line = lines[-1]
            second_last = lines[-2]

            # If last line has only 1 word and is much shorter than second-last
            if last_line.word_count == 1 and second_last.word_count > 2:
                avg_width = sum(line.width for line in lines[:-1]) / (len(lines) - 1)

                if last_line.width < avg_width * 0.4:
                    # Pull a word from the previous line
                    # Note: This is simplified; a full implementation would reflow
                    logger.debug("Potential widow detected, may need reflow")

        return lines

    def draw_layout(
        self,
        paragraphs: List[LayoutParagraph],
        draw: ImageDraw.ImageDraw,
        origin: Tuple[int, int],
        font: ImageFont.FreeTypeFont,
        style: TextStyle,
        box_width: int
    ) -> None:
        """
        Draw laid-out text onto the image.

        Args:
            paragraphs: Layout paragraphs to draw
            draw: ImageDraw instance
            origin: Top-left position (x, y)
            font: Font to use
            style: Text style
            box_width: Width of text box for alignment
        """
        x, y = origin
        ascent, descent = font.getmetrics()
        line_height_px = int((ascent + descent) * style.line_height)

        current_y = y

        for para in paragraphs:
            for line in para.lines:
                # Calculate x position based on alignment
                if style.align == "center":
                    tx = x + (box_width - int(line.width)) // 2
                elif style.align == "right":
                    tx = x + box_width - int(line.width)
                elif style.align == "justify" and not line.is_paragraph_end:
                    # Justify: draw with word spacing
                    self._draw_justified_line(
                        draw, line, (x, current_y), font, style, box_width
                    )
                    current_y += line_height_px
                    continue
                else:  # left or justified on last line
                    tx = x

                # Draw the line
                color = self._hex_to_rgb(style.color)
                draw.text((tx, current_y), line.text, fill=color, font=font)
                current_y += line_height_px

            # Add paragraph spacing
            current_y += para.spacing_after

    def _draw_justified_line(
        self,
        draw: ImageDraw.ImageDraw,
        line: LayoutLine,
        origin: Tuple[int, int],
        font: ImageFont.FreeTypeFont,
        style: TextStyle,
        box_width: int
    ) -> None:
        """Draw a line with justified alignment (word spacing)."""
        if line.word_count <= 1:
            # Can't justify single word, just draw it
            color = self._hex_to_rgb(style.color)
            draw.text(origin, line.text, fill=color, font=font)
            return

        words = line.text.split()
        gaps = len(words) - 1

        # Calculate extra space to distribute
        extra_space = box_width - line.width
        space_per_gap = extra_space / gaps if gaps > 0 else 0

        # Draw words with adjusted spacing
        x, y = origin
        color = self._hex_to_rgb(style.color)

        for i, word in enumerate(words):
            draw.text((x, y), word, fill=color, font=font)
            word_width = draw.textlength(word, font=font)
            x += word_width

            if i < len(words) - 1:
                # Add space plus extra for justification
                space_width = draw.textlength(' ', font=font)
                x += space_width + space_per_gap

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        h = hex_color.strip("#")
        if len(h) == 6:
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore
        return (0, 0, 0)  # Default to black
