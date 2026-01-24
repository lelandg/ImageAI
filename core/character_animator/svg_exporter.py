"""
SVG file exporter for Character Animator puppets.

Creates SVG files with grouped structure that Adobe Character Animator
can import and auto-rig. SVG groups map to Character Animator layers.

Supports both:
- Embedded raster (PNG images as base64 within SVG)
- Pure vector (vectorized paths - better for cartoons)
"""

import logging
import base64
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import io
import numpy as np
from PIL import Image

from .models import PuppetStructure, PuppetLayer, VisemeSet, EyeBlinkSet
from .constants import LAYER_NAMES, SVG_SETTINGS, WARP_INDEPENDENT_LAYERS
from .availability import SVG_EXPORT_AVAILABLE

logger = logging.getLogger(__name__)


class SVGExporter:
    """
    Exports Character Animator puppets to SVG format.

    SVG is good for cartoon-style puppets. Character Animator treats
    SVG groups as layers, making it easy to create the proper hierarchy.
    """

    def __init__(
        self,
        puppet: PuppetStructure,
        embed_images: bool = True,
        vectorize: bool = False,
    ):
        """
        Initialize the SVG exporter.

        Args:
            puppet: PuppetStructure to export
            embed_images: Embed raster images as base64 (vs external files)
            vectorize: Convert raster to vector paths
        """
        self.puppet = puppet
        self.embed_images = embed_images
        self.vectorize = vectorize
        self._svg_content: List[str] = []

    def image_to_svg_path(
        self,
        image: Image.Image,
        threshold: int = 128,
        simplify: bool = True,
    ) -> str:
        """
        Convert an image to SVG path data.

        This creates vector paths from the image using edge detection
        and contour tracing. Best for simple cartoon-style images.

        Args:
            image: PIL Image to vectorize
            threshold: Threshold for edge detection
            simplify: Simplify paths to reduce complexity

        Returns:
            SVG path data string
        """
        try:
            import cv2

            # Convert to grayscale and threshold
            img_array = np.array(image.convert("L"))
            _, binary = cv2.threshold(img_array, threshold, 255, cv2.THRESH_BINARY)

            # Find contours
            contours, _ = cv2.findContours(
                binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
            )

            if not contours:
                return ""

            # Convert contours to SVG path
            path_data = []
            for contour in contours:
                if len(contour) < 3:
                    continue

                # Simplify if requested
                if simplify:
                    epsilon = 0.01 * cv2.arcLength(contour, True)
                    contour = cv2.approxPolyDP(contour, epsilon, True)

                # Build path
                points = contour.reshape(-1, 2)
                path_parts = [f"M {points[0][0]},{points[0][1]}"]

                for point in points[1:]:
                    path_parts.append(f"L {point[0]},{point[1]}")

                path_parts.append("Z")
                path_data.append(" ".join(path_parts))

            return " ".join(path_data)

        except ImportError:
            logger.warning("OpenCV not available for vectorization")
            return ""
        except Exception as e:
            logger.error(f"Vectorization failed: {e}")
            return ""

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 data URI."""
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    def create_group_hierarchy(self) -> str:
        """
        Build the SVG group structure.

        Returns:
            Complete SVG content string
        """
        self._svg_content = []

        # SVG header
        width = self.puppet.width or 1024
        height = self.puppet.height or 1024

        self._svg_content.append(
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">\n'
        )

        # Add metadata for Character Animator
        self._svg_content.append(
            f'  <!-- Character Animator Puppet: {self.puppet.name} -->\n'
            f'  <title>{self.puppet.name}</title>\n'
        )

        # Process root layer
        self._process_layer_to_svg(self.puppet.root_layer, indent=2)

        # Close SVG
        self._svg_content.append('</svg>\n')

        return "".join(self._svg_content)

    def _process_layer_to_svg(self, layer: PuppetLayer, indent: int = 2):
        """
        Recursively process a layer to SVG groups/elements.

        Args:
            layer: Layer to process
            indent: Current indentation level
        """
        indent_str = "  " * indent

        # Create group or image element
        if layer.is_group():
            # Create SVG group
            # ID uses layer name for Character Animator recognition
            group_id = self._make_svg_id(layer.display_name)
            visibility = "visible" if layer.visible else "hidden"

            self._svg_content.append(
                f'{indent_str}<g id="{group_id}" '
                f'visibility="{visibility}">\n'
            )

            # Process children
            for child in layer.children:
                self._process_layer_to_svg(child, indent + 1)

            self._svg_content.append(f'{indent_str}</g>\n')

        elif layer.image is not None:
            # Create image element
            self._add_image_element(layer, indent_str)

    def _make_svg_id(self, name: str) -> str:
        """
        Create valid SVG ID from layer name.

        Preserves + prefix for warp independent layers.
        """
        # Keep + but replace other invalid characters
        safe_id = name.replace(" ", "_").replace("-", "_")
        # Ensure ID starts with letter or underscore (or +)
        if safe_id and safe_id[0].isdigit():
            safe_id = "_" + safe_id
        return safe_id

    def _add_image_element(self, layer: PuppetLayer, indent: str):
        """Add an image element to SVG."""
        image = layer.image
        if image is None:
            return

        # Ensure RGBA
        if image.mode != "RGBA":
            image = image.convert("RGBA")

        layer_id = self._make_svg_id(layer.display_name)
        x, y = layer.position
        width, height = image.size

        visibility = "visible" if layer.visible else "hidden"
        opacity = layer.opacity

        if self.vectorize:
            # Try to vectorize
            path_data = self.image_to_svg_path(image)

            if path_data:
                # Use vectorized path
                # Extract dominant color from image
                colors = image.convert("RGB").getcolors(maxcolors=10000)
                if colors:
                    dominant_color = max(colors, key=lambda x: x[0])[1]
                    fill = f"rgb({dominant_color[0]},{dominant_color[1]},{dominant_color[2]})"
                else:
                    fill = "black"

                self._svg_content.append(
                    f'{indent}<path id="{layer_id}" '
                    f'd="{path_data}" '
                    f'fill="{fill}" '
                    f'opacity="{opacity}" '
                    f'visibility="{visibility}" '
                    f'transform="translate({x},{y})"/>\n'
                )
                return

        # Fall back to embedded/linked raster
        if self.embed_images:
            # Embed as base64
            data_uri = self._image_to_base64(image)
            self._svg_content.append(
                f'{indent}<image id="{layer_id}" '
                f'x="{x}" y="{y}" '
                f'width="{width}" height="{height}" '
                f'opacity="{opacity}" '
                f'visibility="{visibility}" '
                f'xlink:href="{data_uri}"/>\n'
            )
        else:
            # Link to external file (will be saved separately)
            filename = f"{layer_id}.png"
            self._svg_content.append(
                f'{indent}<image id="{layer_id}" '
                f'x="{x}" y="{y}" '
                f'width="{width}" height="{height}" '
                f'opacity="{opacity}" '
                f'visibility="{visibility}" '
                f'xlink:href="{filename}"/>\n'
            )

    def embed_raster_layers(self, layers: Dict[str, Image.Image]):
        """
        Add raster images as embedded layers.

        Args:
            layers: Dictionary mapping layer ID to image
        """
        for layer_id, image in layers.items():
            # Find the layer in puppet structure
            layer = self.puppet.root_layer.find_layer(layer_id)
            if layer is not None:
                layer.image = image.convert("RGBA")

    def populate_from_visemes(self, visemes: VisemeSet):
        """
        Add all viseme images to the Mouth group.

        Args:
            visemes: VisemeSet with generated mouth shapes
        """
        mouth_group = self._find_or_create_group(["Head", "Mouth"])

        viseme_dict = visemes.to_dict()
        for name, image in viseme_dict.items():
            if image is not None:
                # Only first (Neutral) should be visible by default
                visible = (name == "Neutral")

                layer = PuppetLayer(
                    name=name,
                    image=image.convert("RGBA"),
                    visible=visible,
                )
                mouth_group.add_child(layer)
                logger.debug(f"Added viseme {name} to SVG Mouth group")

        logger.info(f"Populated {sum(1 for v in viseme_dict.values() if v is not None)} visemes into SVG")

    def populate_from_blinks(self, blinks: EyeBlinkSet):
        """
        Add eye blink states to the Head group.

        Args:
            blinks: EyeBlinkSet with eye states
        """
        head_group = self._find_or_create_group(["Head"])

        # Add blink layers (closed eyes)
        if blinks.left_blink is not None:
            layer = PuppetLayer(
                name="Left Blink",
                image=blinks.left_blink.convert("RGBA"),
                visible=False,  # Hidden by default
            )
            head_group.add_child(layer)
            logger.debug("Added Left Blink to SVG Head group")

        if blinks.right_blink is not None:
            layer = PuppetLayer(
                name="Right Blink",
                image=blinks.right_blink.convert("RGBA"),
                visible=False,
            )
            head_group.add_child(layer)
            logger.debug("Added Right Blink to SVG Head group")

        logger.info("Populated eye blink states into SVG")

    def _find_or_create_group(self, path: List[str]) -> PuppetLayer:
        """Find or create a group at the given path."""
        current = self.puppet.root_layer

        for group_name in path:
            found = None
            for child in current.children:
                if child.name == group_name:
                    found = child
                    break

            if found is None:
                # Create new group
                new_group = PuppetLayer(name=group_name)
                current.add_child(new_group)
                found = new_group

            current = found

        return current

    def export(self, output_path: Path) -> bool:
        """
        Export the puppet to SVG file.

        Args:
            output_path: Path for the output .svg file

        Returns:
            True if export successful
        """
        if not SVG_EXPORT_AVAILABLE:
            logger.warning("svgwrite not available, using basic SVG generation")
            # We can still generate basic SVG without svgwrite

        try:
            # Generate SVG content
            svg_content = self.create_group_hierarchy()

            # Save SVG file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(svg_content)

            # If not embedding, save external images
            if not self.embed_images:
                self._save_external_images(output_path.parent)

            logger.info(f"SVG exported to {output_path}")
            return True

        except Exception as e:
            logger.error(f"SVG export failed: {e}")
            return False

    def _save_external_images(self, output_dir: Path):
        """Save layer images as external PNG files."""
        def save_recursive(layer: PuppetLayer):
            if layer.image is not None:
                filename = f"{self._make_svg_id(layer.display_name)}.png"
                filepath = output_dir / filename
                layer.image.save(filepath, "PNG")

            for child in layer.children:
                save_recursive(child)

        save_recursive(self.puppet.root_layer)

    def export_with_svgwrite(self, output_path: Path) -> bool:
        """
        Export using svgwrite library for better SVG generation.

        Args:
            output_path: Output file path

        Returns:
            True if successful
        """
        if not SVG_EXPORT_AVAILABLE:
            logger.error("svgwrite not available")
            return False

        try:
            import svgwrite

            width = self.puppet.width or 1024
            height = self.puppet.height or 1024

            # Create SVG document
            dwg = svgwrite.Drawing(
                str(output_path),
                size=(f"{width}px", f"{height}px"),
                viewBox=f"0 0 {width} {height}",
            )

            # Add Character Animator metadata
            dwg.set_desc(title=self.puppet.name)

            # Process layers recursively
            root_group = self._create_svgwrite_group(dwg, self.puppet.root_layer)
            dwg.add(root_group)

            # Save
            dwg.save()

            logger.info(f"SVG exported with svgwrite to {output_path}")
            return True

        except Exception as e:
            logger.error(f"svgwrite export failed: {e}")
            return False

    def _create_svgwrite_group(self, dwg, layer: PuppetLayer):
        """Create svgwrite group for a layer."""
        import svgwrite

        group_id = self._make_svg_id(layer.display_name)

        if layer.is_group():
            # Create group
            group = dwg.g(id=group_id)

            if not layer.visible:
                group["visibility"] = "hidden"

            # Add children
            for child in layer.children:
                child_elem = self._create_svgwrite_group(dwg, child)
                group.add(child_elem)

            return group

        elif layer.image is not None:
            # Create image element
            image = layer.image.convert("RGBA")
            x, y = layer.position
            width, height = image.size

            if self.embed_images:
                data_uri = self._image_to_base64(image)
                img = dwg.image(
                    href=data_uri,
                    insert=(x, y),
                    size=(width, height),
                    id=group_id,
                )
            else:
                filename = f"{group_id}.png"
                img = dwg.image(
                    href=filename,
                    insert=(x, y),
                    size=(width, height),
                    id=group_id,
                )

            if not layer.visible:
                img["visibility"] = "hidden"

            if layer.opacity < 1.0:
                img["opacity"] = layer.opacity

            return img

        else:
            # Empty layer - return empty group
            return dwg.g(id=group_id)


class SVGVectorizer:
    """
    Converts raster images to vector SVG paths.

    Uses various methods for vectorization:
    - Potrace (external tool)
    - OpenCV contours
    - AI-based vectorization (if available)
    """

    def __init__(self, method: str = "opencv"):
        """
        Initialize vectorizer.

        Args:
            method: Vectorization method ("opencv", "potrace", "ai")
        """
        self.method = method

    def vectorize(
        self,
        image: Image.Image,
        color_threshold: int = 128,
        simplify_tolerance: float = 0.01,
    ) -> str:
        """
        Convert image to SVG path data.

        Args:
            image: Image to vectorize
            color_threshold: Threshold for color quantization
            simplify_tolerance: Path simplification tolerance

        Returns:
            SVG path data string
        """
        if self.method == "potrace":
            return self._vectorize_potrace(image)
        elif self.method == "opencv":
            return self._vectorize_opencv(image, color_threshold, simplify_tolerance)
        else:
            logger.warning(f"Unknown vectorization method: {self.method}")
            return ""

    def _vectorize_opencv(
        self,
        image: Image.Image,
        threshold: int,
        tolerance: float,
    ) -> str:
        """Vectorize using OpenCV contours."""
        try:
            import cv2

            # Convert to grayscale
            gray = np.array(image.convert("L"))

            # Apply threshold
            _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

            # Find contours
            contours, hierarchy = cv2.findContours(
                binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_TC89_KCOS
            )

            paths = []
            for contour in contours:
                if len(contour) < 3:
                    continue

                # Simplify
                epsilon = tolerance * cv2.arcLength(contour, True)
                simplified = cv2.approxPolyDP(contour, epsilon, True)

                # Convert to SVG path
                points = simplified.reshape(-1, 2)
                path = f"M {points[0][0]},{points[0][1]}"

                for point in points[1:]:
                    path += f" L {point[0]},{point[1]}"

                path += " Z"
                paths.append(path)

            return " ".join(paths)

        except ImportError:
            logger.error("OpenCV not available for vectorization")
            return ""

    def _vectorize_potrace(self, image: Image.Image) -> str:
        """Vectorize using potrace (if installed)."""
        try:
            import subprocess
            import tempfile

            # Save as temporary BMP (potrace input format)
            with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as tmp_in:
                # Convert to 1-bit BMP
                bw = image.convert("1")
                bw.save(tmp_in.name, "BMP")

            with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp_out:
                output_file = tmp_out.name

            # Run potrace
            result = subprocess.run(
                ["potrace", "-s", "-o", output_file, tmp_in.name],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.warning(f"potrace failed: {result.stderr}")
                return ""

            # Read SVG and extract paths
            with open(output_file, "r") as f:
                svg_content = f.read()

            # Extract path data (simplified extraction)
            import re
            paths = re.findall(r'd="([^"]+)"', svg_content)
            return " ".join(paths)

        except FileNotFoundError:
            logger.warning("potrace not installed, falling back to OpenCV")
            return self._vectorize_opencv(image, 128, 0.01)
        except Exception as e:
            logger.error(f"potrace vectorization failed: {e}")
            return ""
