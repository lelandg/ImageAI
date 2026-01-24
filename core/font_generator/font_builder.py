"""
Font file builder for assembling vectorized glyphs into font formats.

This module uses fonttools to create TTF/OTF font files from
vectorized glyphs and calculated metrics.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

try:
    from fontTools.fontBuilder import FontBuilder as FTFontBuilder
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    from fontTools.ttLib import TTFont
    from fontTools.designspaceLib import DesignSpaceDocument
    FONTTOOLS_AVAILABLE = True
except ImportError:
    FONTTOOLS_AVAILABLE = False

# cu2qu for cubic to quadratic conversion (needed for TrueType)
try:
    from fontTools.cu2qu import curve_to_quadratic
    CU2QU_AVAILABLE = True
except ImportError:
    CU2QU_AVAILABLE = False

from .vectorizer import VectorGlyph, VectorPath, PathCommand
from .metrics import FontMetrics

logger = logging.getLogger(__name__)

# Font timestamp epoch: January 1, 1904 (Mac epoch)
_FONT_EPOCH = datetime(1904, 1, 1)


def _datetime_to_font_timestamp(dt: datetime) -> int:
    """Convert datetime to font timestamp (seconds since 1904-01-01)."""
    return int((dt - _FONT_EPOCH).total_seconds())


@dataclass
class FontInfo:
    """Font metadata and naming information."""
    family_name: str = "CustomFont"
    style_name: str = "Regular"
    version: str = "1.0"
    copyright: str = ""
    designer: str = ""
    description: str = ""
    vendor_url: str = ""
    designer_url: str = ""
    license: str = ""
    license_url: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.family_name} {self.style_name}"

    @property
    def postscript_name(self) -> str:
        return f"{self.family_name}-{self.style_name}".replace(" ", "")

    @property
    def unique_id(self) -> str:
        return f"{self.version};{self.postscript_name}"


class FontBuilder:
    """
    Assembles vectorized glyphs into font files.

    Uses fonttools library to create industry-standard TTF/OTF files.
    """

    def __init__(
        self,
        info: Optional[FontInfo] = None,
        metrics: Optional[FontMetrics] = None,
    ):
        """
        Initialize the font builder.

        Args:
            info: Font metadata (name, version, etc.)
            metrics: Pre-calculated font metrics (or will calculate)
        """
        if not FONTTOOLS_AVAILABLE:
            raise ImportError(
                "fonttools is required for font building. "
                "Install with: pip install fonttools"
            )

        self.info = info or FontInfo()
        self.metrics = metrics
        self._glyphs: Dict[str, VectorGlyph] = {}

    def add_glyph(self, glyph: VectorGlyph) -> None:
        """Add a single glyph to the font."""
        self._glyphs[glyph.label] = glyph
        logger.debug(f"Added glyph '{glyph.label}'")

    def add_glyphs(self, glyphs: List[VectorGlyph]) -> None:
        """Add multiple glyphs to the font."""
        for glyph in glyphs:
            self.add_glyph(glyph)

    def build(self, output_path: str | Path) -> Path:
        """
        Build the font file and save to disk.

        Args:
            output_path: Path for output file (.ttf or .otf)

        Returns:
            Path to the created font file
        """
        output_path = Path(output_path)

        if not self._glyphs:
            raise ValueError("No glyphs added to font")

        logger.info(f"Building font with {len(self._glyphs)} glyphs")

        # Determine format from extension
        ext = output_path.suffix.lower()
        if ext not in (".ttf", ".otf"):
            output_path = output_path.with_suffix(".ttf")

        # Get or calculate metrics and normalize glyphs
        metrics = self.metrics
        if metrics is None:
            from .metrics import FontMetricsCalculator
            calculator = FontMetricsCalculator()
            metrics = calculator.calculate(list(self._glyphs.values()))
            # Use normalized glyphs with proper baseline/descender positioning
            normalized_glyphs = calculator.get_normalized_glyphs()
            self._glyphs = {g.label: g for g in normalized_glyphs}
            logger.debug(f"Using {len(normalized_glyphs)} normalized glyphs")

        # Build the font
        if output_path.suffix.lower() == ".otf":
            font = self._build_cff(metrics)
        else:
            font = self._build_truetype(metrics)

        # Save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        font.save(str(output_path))
        logger.info(f"Saved font to {output_path}")

        return output_path

    def _build_truetype(self, metrics: FontMetrics) -> TTFont:
        """Build a TrueType font (.ttf)."""
        from fontTools.pens.t2CharStringPen import T2CharStringPen
        from fontTools.pens.ttGlyphPen import TTGlyphPen

        # Create glyph order
        glyph_order = [".notdef", "space"] + sorted(self._glyphs.keys())

        # Create character map (Unicode -> glyph name)
        cmap = {ord(" "): "space"}
        for label in self._glyphs.keys():
            if len(label) == 1:
                cmap[ord(label)] = label

        # Calculate advance widths
        advance_widths = {".notdef": metrics.units_per_em // 2}
        advance_widths["space"] = metrics.units_per_em // 4

        for label in self._glyphs.keys():
            if label in metrics.advance_widths:
                advance_widths[label] = int(metrics.advance_widths[label])
            else:
                advance_widths[label] = int(metrics.units_per_em * 0.6)

        # Build with fontBuilder
        fb = FTFontBuilder(metrics.units_per_em, isTTF=True)
        fb.setupGlyphOrder(glyph_order)

        # Setup character map
        fb.setupCharacterMap(cmap)

        # Create pen glyphs using TTGlyphPen
        pen_glyphs = {}

        # .notdef glyph (empty rectangle)
        pen_glyphs[".notdef"] = self._draw_notdef_tt(metrics)

        # Space glyph - empty
        pen_glyphs["space"] = self._draw_empty_tt()

        # User glyphs
        for label, glyph in self._glyphs.items():
            pen_glyphs[label] = self._draw_glyph_tt(glyph)

        # Setup glyph outlines
        fb.setupGlyf(pen_glyphs)

        # Setup horizontal metrics
        fb.setupHorizontalMetrics(
            {name: (width, 0) for name, width in advance_widths.items()}
        )

        # Setup head table (timestamps must be font epoch format)
        now = _datetime_to_font_timestamp(datetime.now())
        fb.setupHead(
            unitsPerEm=metrics.units_per_em,
            created=now,
            modified=now,
        )

        # Setup horizontal header (hhea table)
        fb.setupHorizontalHeader(
            ascent=int(metrics.ascender),
            descent=int(metrics.descender),
        )

        # Setup maxp
        fb.setupMaxp()

        # Setup OS/2 table
        fb.setupOS2(
            sTypoAscender=int(metrics.typo_ascender),
            sTypoDescender=int(metrics.typo_descender),
            sTypoLineGap=int(metrics.line_gap),
            usWinAscent=int(metrics.win_ascent),
            usWinDescent=int(metrics.win_descent),
            sxHeight=int(metrics.x_height),
            sCapHeight=int(metrics.cap_height),
        )

        # Setup post table
        fb.setupPost()

        # Setup name table
        fb.setupNameTable({
            "familyName": self.info.family_name,
            "styleName": self.info.style_name,
            "uniqueFontIdentifier": self.info.unique_id,
            "fullName": self.info.full_name,
            "version": f"Version {self.info.version}",
            "psName": self.info.postscript_name,
        })

        # Add kerning if available
        if metrics.kerning:
            self._add_kerning(fb.font, metrics.kerning)

        return fb.font

    def _build_cff(self, metrics: FontMetrics) -> TTFont:
        """Build a CFF-based OpenType font (.otf)."""
        # Create glyph order
        glyph_order = [".notdef", "space"] + sorted(self._glyphs.keys())

        # Create CharStrings for CFF
        charstrings = {}

        # .notdef
        charstrings[".notdef"] = self._create_notdef_charstring(metrics)

        # Space (empty)
        pen = T2CharStringPen(metrics.units_per_em // 4, None)
        charstrings["space"] = pen.getCharString()

        # User glyphs
        for label, glyph in self._glyphs.items():
            width = metrics.advance_widths.get(label, metrics.units_per_em * 0.6)
            charstrings[label] = self._glyph_to_charstring(glyph, int(width))

        # Character map
        cmap = {ord(" "): "space"}
        for label in self._glyphs.keys():
            if len(label) == 1:
                cmap[ord(label)] = label

        # Build
        fb = FTFontBuilder(metrics.units_per_em, isTTF=False)
        fb.setupGlyphOrder(glyph_order)
        fb.setupCharacterMap(cmap)

        # Setup CFF - requires psName, fontInfo, charStringsDict, and privateDict
        fb.setupCFF(
            psName=self.info.postscript_name,
            fontInfo={"FullName": self.info.full_name},
            charStringsDict=charstrings,
            privateDict={},
        )

        # Calculate advance widths
        advance_widths = {".notdef": metrics.units_per_em // 2}
        advance_widths["space"] = metrics.units_per_em // 4
        for label in self._glyphs.keys():
            if label in metrics.advance_widths:
                advance_widths[label] = int(metrics.advance_widths[label])
            else:
                advance_widths[label] = int(metrics.units_per_em * 0.6)

        fb.setupHorizontalMetrics(
            {name: (width, 0) for name, width in advance_widths.items()}
        )

        now_ts = _datetime_to_font_timestamp(datetime.now())
        fb.setupHead(
            unitsPerEm=metrics.units_per_em,
            created=now_ts,
            modified=now_ts,
        )

        fb.setupHorizontalHeader(
            ascent=int(metrics.ascender),
            descent=int(metrics.descender),
        )

        fb.setupMaxp()

        fb.setupOS2(
            sTypoAscender=int(metrics.typo_ascender),
            sTypoDescender=int(metrics.typo_descender),
            sTypoLineGap=int(metrics.line_gap),
            usWinAscent=int(metrics.win_ascent),
            usWinDescent=int(metrics.win_descent),
            sxHeight=int(metrics.x_height),
            sCapHeight=int(metrics.cap_height),
        )

        fb.setupPost()

        fb.setupNameTable({
            "familyName": self.info.family_name,
            "styleName": self.info.style_name,
            "uniqueFontIdentifier": self.info.unique_id,
            "fullName": self.info.full_name,
            "version": f"Version {self.info.version}",
            "psName": self.info.postscript_name,
        })

        if metrics.kerning:
            self._add_kerning(fb.font, metrics.kerning)

        return fb.font

    def _draw_empty_tt(self):
        """Create an empty TrueType glyph."""
        from fontTools.pens.ttGlyphPen import TTGlyphPen
        pen = TTGlyphPen(None)
        return pen.glyph()

    def _draw_notdef_tt(self, metrics: FontMetrics):
        """Create .notdef TrueType glyph (empty rectangle)."""
        from fontTools.pens.ttGlyphPen import TTGlyphPen

        width = metrics.units_per_em // 2
        height = int(metrics.cap_height) if metrics.cap_height > 0 else 700
        thickness = max(width // 10, 20)

        pen = TTGlyphPen(None)

        # Outer rectangle (clockwise for TrueType)
        pen.moveTo((0, 0))
        pen.lineTo((width, 0))
        pen.lineTo((width, height))
        pen.lineTo((0, height))
        pen.closePath()

        # Inner rectangle (counter-clockwise for hole)
        pen.moveTo((thickness, thickness))
        pen.lineTo((thickness, height - thickness))
        pen.lineTo((width - thickness, height - thickness))
        pen.lineTo((width - thickness, thickness))
        pen.closePath()

        return pen.glyph()

    def _draw_glyph_tt(self, glyph: VectorGlyph):
        """Draw a VectorGlyph to TrueType format using TTGlyphPen.

        TrueType requires quadratic curves, so cubic curves are converted.
        """
        from fontTools.pens.ttGlyphPen import TTGlyphPen

        pen = TTGlyphPen(None)

        if not glyph.paths:
            return pen.glyph()

        for path in glyph.paths:
            self._draw_path_to_pen_tt(path, pen)

        return pen.glyph()

    def _cubic_to_quadratic(self, p0: Tuple[float, float], p1: Tuple[float, float],
                            p2: Tuple[float, float], p3: Tuple[float, float],
                            max_err: float = 1.0) -> List[Tuple[Tuple[float, float], ...]]:
        """Convert a cubic Bezier to quadratic Bezier curves.

        Args:
            p0: Start point
            p1: First control point
            p2: Second control point
            p3: End point
            max_err: Maximum allowed error

        Returns:
            List of quadratic curves as (control_point, end_point) tuples
        """
        if CU2QU_AVAILABLE:
            # Use fonttools cu2qu for accurate conversion
            try:
                quadratics = curve_to_quadratic((p0, p1, p2, p3), max_err)
                # curve_to_quadratic returns list of points, convert to qcurve segments
                result = []
                for i in range(1, len(quadratics) - 1, 2):
                    ctrl = quadratics[i]
                    end = quadratics[i + 1] if i + 1 < len(quadratics) else quadratics[-1]
                    result.append((ctrl, end))
                if not result:
                    # Fallback: just return endpoint as line
                    result = [(p3, p3)]
                return result
            except Exception as e:
                logger.debug(f"cu2qu conversion failed, using approximation: {e}")

        # Simple approximation: convert cubic to single quadratic
        # Use midpoint of control points as single control point
        qp1 = (
            (p1[0] + p2[0]) / 2,
            (p1[1] + p2[1]) / 2
        )
        return [(qp1, p3)]

    def _draw_path_to_pen_tt(self, path: VectorPath, pen) -> None:
        """Draw a VectorPath to TrueType pen, converting cubic to quadratic curves."""
        started = False
        last_point = (0, 0)

        for seg in path.segments:
            if seg.command == PathCommand.MOVE:
                if seg.points:
                    pen.moveTo(seg.points[0])
                    last_point = seg.points[0]
                    started = True
            elif seg.command == PathCommand.LINE:
                if seg.points and started:
                    pen.lineTo(seg.points[0])
                    last_point = seg.points[0]
            elif seg.command == PathCommand.CURVE:
                # Convert cubic to quadratic for TrueType
                if len(seg.points) >= 3 and started:
                    p1, p2, p3 = seg.points[:3]
                    quads = self._cubic_to_quadratic(last_point, p1, p2, p3)
                    for ctrl, end in quads:
                        pen.qCurveTo(ctrl, end)
                    last_point = p3
            elif seg.command == PathCommand.QUAD:
                if len(seg.points) >= 2 and started:
                    pen.qCurveTo(*seg.points[:2])
                    last_point = seg.points[1]
            elif seg.command == PathCommand.CLOSE:
                if started:
                    pen.closePath()
                    started = False

        if started:
            pen.closePath()

    def _glyph_to_charstring(self, glyph: VectorGlyph, width: int) -> object:
        """Convert VectorGlyph to CFF CharString."""
        pen = T2CharStringPen(width, None)

        for path in glyph.paths:
            self._draw_path_to_pen(path, pen)

        return pen.getCharString()

    def _draw_path_to_pen(self, path: VectorPath, pen) -> None:
        """Draw a VectorPath using a pen interface."""
        started = False

        for seg in path.segments:
            if seg.command == PathCommand.MOVE:
                if seg.points:
                    pen.moveTo(seg.points[0])
                    started = True
            elif seg.command == PathCommand.LINE:
                if seg.points and started:
                    pen.lineTo(seg.points[0])
            elif seg.command == PathCommand.CURVE:
                if len(seg.points) >= 3 and started:
                    pen.curveTo(*seg.points[:3])
            elif seg.command == PathCommand.QUAD:
                if len(seg.points) >= 2 and started:
                    pen.qCurveTo(*seg.points[:2])
            elif seg.command == PathCommand.CLOSE:
                if started:
                    pen.closePath()
                    started = False

        if started:
            pen.closePath()

    def _create_notdef_charstring(self, metrics: FontMetrics) -> object:
        """Create .notdef CharString for CFF."""
        width = metrics.units_per_em // 2
        height = int(metrics.cap_height)
        thickness = width // 10

        pen = T2CharStringPen(width, None)

        # Outer rectangle
        pen.moveTo((0, 0))
        pen.lineTo((width, 0))
        pen.lineTo((width, height))
        pen.lineTo((0, height))
        pen.closePath()

        # Inner rectangle (hole)
        pen.moveTo((thickness, thickness))
        pen.lineTo((thickness, height - thickness))
        pen.lineTo((width - thickness, height - thickness))
        pen.lineTo((width - thickness, thickness))
        pen.closePath()

        return pen.getCharString()

    def _add_kerning(
        self,
        font: TTFont,
        kerning: Dict[Tuple[str, str], float],
    ) -> None:
        """Add kerning table to font."""
        if not kerning:
            return

        # Convert to kern table format
        kern_pairs = {}
        for (left, right), value in kerning.items():
            if left in self._glyphs and right in self._glyphs:
                kern_pairs[(left, right)] = int(value)

        if not kern_pairs:
            return

        # Create kern table
        from fontTools.ttLib.tables import _k_e_r_n

        kern = _k_e_r_n.table__k_e_r_n()
        kern.version = 0

        subtable = _k_e_r_n.KernTable_format_0()
        subtable.version = 0
        subtable.coverage = 1  # Horizontal kerning
        subtable.kernTable = kern_pairs

        kern.kernTables = [subtable]
        font["kern"] = kern

        logger.info(f"Added {len(kern_pairs)} kerning pairs")


def create_font_from_glyphs(
    glyphs: List[VectorGlyph],
    output_path: str | Path,
    font_name: str = "CustomFont",
    **kwargs,
) -> Path:
    """
    Convenience function to create a font file from glyphs.

    Args:
        glyphs: List of VectorGlyph objects
        output_path: Output file path
        font_name: Font family name
        **kwargs: Additional FontInfo parameters

    Returns:
        Path to created font file
    """
    info = FontInfo(family_name=font_name, **kwargs)
    builder = FontBuilder(info=info)
    builder.add_glyphs(glyphs)
    return builder.build(output_path)
