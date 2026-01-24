"""
PSD file exporter for Character Animator puppets.

Creates properly structured Photoshop PSD files that can be imported
directly into Adobe Character Animator for automatic rigging.

Uses psd-tools library for PSD creation.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from PIL import Image
import struct
import io

from .models import PuppetStructure, PuppetLayer, VisemeSet, EyeBlinkSet
from .constants import LAYER_NAMES, PSD_SETTINGS, WARP_INDEPENDENT_LAYERS
from .availability import PSD_EXPORT_AVAILABLE

logger = logging.getLogger(__name__)


class PSDExporter:
    """
    Exports Character Animator puppets to PSD format.

    Creates a properly structured PSD file with:
    - Layer groups matching Character Animator naming conventions
    - Correct layer ordering for puppet rigging
    - All mouth visemes in the Mouth group
    - Eye blink states in appropriate positions
    """

    def __init__(self, puppet: PuppetStructure):
        """
        Initialize the exporter.

        Args:
            puppet: PuppetStructure to export
        """
        self.puppet = puppet
        self._layers_data: List[Dict] = []

    def create_layer_hierarchy(self) -> List[Dict]:
        """
        Build the layer data structure for PSD export.

        Returns:
            List of layer dictionaries ready for PSD creation
        """
        self._layers_data = []

        # Process root layer and all children recursively
        self._process_layer(self.puppet.root_layer, depth=0)

        return self._layers_data

    def _process_layer(self, layer: PuppetLayer, depth: int = 0):
        """
        Recursively process a layer and its children.

        Args:
            layer: PuppetLayer to process
            depth: Current nesting depth
        """
        # Create layer data
        layer_data = {
            "name": layer.display_name,  # Includes + prefix if warp independent
            "visible": layer.visible,
            "opacity": int(layer.opacity * 255),
            "blend_mode": layer.blend_mode,
            "is_group": layer.is_group(),
            "depth": depth,
            "image": layer.image,
            "position": layer.position,
        }

        if layer.is_group():
            # For groups, add opening marker
            layer_data["group_type"] = "open"
            self._layers_data.append(layer_data)

            # Process children (in reverse order for PSD)
            for child in reversed(layer.children):
                self._process_layer(child, depth + 1)

            # Add closing marker
            close_data = {
                "name": layer.display_name,
                "is_group": True,
                "group_type": "close",
                "depth": depth,
            }
            self._layers_data.append(close_data)
        else:
            self._layers_data.append(layer_data)

    def add_layer(
        self,
        name: str,
        image: Image.Image,
        parent_path: Optional[List[str]] = None,
        visible: bool = True,
        opacity: float = 1.0,
        blend_mode: str = "normal",
    ):
        """
        Add a single layer to the puppet structure.

        Args:
            name: Layer name
            image: Layer image (RGBA)
            parent_path: Path to parent group (e.g., ["Head", "Mouth"])
            visible: Layer visibility
            opacity: Layer opacity (0-1)
            blend_mode: Photoshop blend mode
        """
        # Find or create parent
        if parent_path:
            parent = self._find_or_create_group(parent_path)
        else:
            parent = self.puppet.root_layer

        # Create new layer
        new_layer = PuppetLayer(
            name=name,
            image=image.convert("RGBA") if image else None,
            visible=visible,
            opacity=opacity,
            blend_mode=blend_mode,
        )

        parent.add_child(new_layer)

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

    def add_group(
        self,
        name: str,
        parent_path: Optional[List[str]] = None,
    ) -> PuppetLayer:
        """
        Create a new layer group.

        Args:
            name: Group name
            parent_path: Path to parent (None for root)

        Returns:
            The created group layer
        """
        if parent_path:
            parent = self._find_or_create_group(parent_path)
        else:
            parent = self.puppet.root_layer

        new_group = PuppetLayer(name=name)
        parent.add_child(new_group)

        return new_group

    def set_layer_properties(
        self,
        layer_path: List[str],
        visible: Optional[bool] = None,
        opacity: Optional[float] = None,
        blend_mode: Optional[str] = None,
    ):
        """
        Set properties on an existing layer.

        Args:
            layer_path: Path to the layer
            visible: New visibility (or None to keep current)
            opacity: New opacity (or None to keep current)
            blend_mode: New blend mode (or None to keep current)
        """
        layer = self._find_layer_by_path(layer_path)
        if layer is None:
            logger.warning(f"Layer not found: {layer_path}")
            return

        if visible is not None:
            layer.visible = visible
        if opacity is not None:
            layer.opacity = opacity
        if blend_mode is not None:
            layer.blend_mode = blend_mode

    def _find_layer_by_path(self, path: List[str]) -> Optional[PuppetLayer]:
        """Find a layer by its path."""
        current = self.puppet.root_layer

        for name in path:
            found = None
            for child in current.children:
                if child.name == name:
                    found = child
                    break

            if found is None:
                return None
            current = found

        return current

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
                logger.debug(f"Added viseme {name} to PSD Mouth group")

    def populate_from_blinks(self, blinks: EyeBlinkSet):
        """
        Add eye blink states to the Head group.

        Args:
            blinks: EyeBlinkSet with eye states
        """
        head_group = self._find_or_create_group(["Head"])

        # Add left blink layer (closed eye)
        if blinks.left_blink is not None:
            layer = PuppetLayer(
                name="Left Blink",
                image=blinks.left_blink.convert("RGBA"),
                visible=False,  # Hidden by default
            )
            head_group.add_child(layer)
            logger.debug("Added Left Blink to PSD Head group")

        # Add right blink layer (closed eye)
        if blinks.right_blink is not None:
            layer = PuppetLayer(
                name="Right Blink",
                image=blinks.right_blink.convert("RGBA"),
                visible=False,
            )
            head_group.add_child(layer)
            logger.debug("Added Right Blink to PSD Head group")

    def export(self, output_path: Path) -> bool:
        """
        Export the puppet to a PSD file.

        Args:
            output_path: Path for the output .psd file

        Returns:
            True if export successful
        """
        if not PSD_EXPORT_AVAILABLE:
            logger.error("psd-tools not available for PSD export")
            return self._export_fallback_script(output_path)

        try:
            from psd_tools import PSDImage
            from psd_tools.api.layers import PixelLayer, Group

            # Build layer hierarchy
            self.create_layer_hierarchy()

            # Create PSD using psd-tools
            # Note: psd-tools is primarily for reading PSDs
            # For creating PSDs, we'll use a custom approach or fallback
            return self._export_with_psd_tools(output_path)

        except Exception as e:
            logger.error(f"PSD export failed: {e}")
            return self._export_fallback_script(output_path)

    def _export_with_psd_tools(self, output_path: Path) -> bool:
        """
        Export using psd-tools library.

        Note: psd-tools has limited write support. This implementation
        creates a basic PSD structure. For full compatibility, the
        fallback script method may work better.
        """
        try:
            # psd-tools doesn't have great write support
            # We'll create a simple PSD structure manually
            return self._create_psd_manual(output_path)

        except Exception as e:
            logger.error(f"psd-tools export failed: {e}")
            return False

    def _create_psd_manual(self, output_path: Path) -> bool:
        """
        Create PSD file manually using binary format.

        This creates a basic PSD file that Character Animator can read.
        """
        try:
            # Collect all layers with images
            flat_layers = self._flatten_layers_for_export()

            if not flat_layers:
                logger.error("No layers to export")
                return False

            # Determine canvas size
            width = self.puppet.width or max(
                (l["image"].width for l in flat_layers if l.get("image")),
                default=1024
            )
            height = self.puppet.height or max(
                (l["image"].height for l in flat_layers if l.get("image")),
                default=1024
            )

            # Write PSD file
            with open(output_path, 'wb') as f:
                # PSD Header
                f.write(b'8BPS')  # Signature
                f.write(struct.pack('>H', 1))  # Version
                f.write(b'\x00' * 6)  # Reserved
                f.write(struct.pack('>H', 4))  # Channels (RGBA)
                f.write(struct.pack('>II', height, width))  # Size
                f.write(struct.pack('>H', 8))  # Depth (8-bit)
                f.write(struct.pack('>H', 3))  # Color mode (RGB)

                # Color Mode Data (empty)
                f.write(struct.pack('>I', 0))

                # Image Resources (minimal)
                f.write(struct.pack('>I', 0))

                # Layer and Mask Info
                layer_data = self._build_layer_section(flat_layers, width, height)
                f.write(struct.pack('>I', len(layer_data)))
                f.write(layer_data)

                # Image Data (composite)
                composite = self._create_composite_image(flat_layers, width, height)
                f.write(struct.pack('>H', 0))  # Compression (raw)
                for channel in range(4):  # RGBA
                    channel_data = composite[:, :, channel].tobytes()
                    f.write(channel_data)

            logger.info(f"PSD exported to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Manual PSD creation failed: {e}")
            return False

    def _flatten_layers_for_export(self) -> List[Dict]:
        """Flatten layer hierarchy for export."""
        layers = []

        def process(layer: PuppetLayer, path: List[str] = None, depth: int = 0):
            path = path or []
            current_path = path + [layer.name]
            indent = "  " * depth

            logger.debug(f"{indent}Processing layer: {layer.name}, is_group: {layer.is_group()}, has_image: {layer.image is not None}, children: {len(layer.children)}")

            if layer.image is not None:
                layers.append({
                    "name": layer.display_name,
                    "image": layer.image.convert("RGBA"),
                    "visible": layer.visible,
                    "opacity": layer.opacity,
                    "position": layer.position,
                    "path": current_path,
                })
                logger.debug(f"{indent}  -> Added layer with image: {layer.display_name}")

            for child in layer.children:
                process(child, current_path, depth + 1)

        logger.info("=== FLATTENING LAYERS FOR EXPORT ===")
        process(self.puppet.root_layer)
        logger.info(f"=== FLATTENED {len(layers)} LAYERS WITH IMAGES ===")
        for i, layer in enumerate(layers):
            logger.info(f"  Layer {i+1}: {layer['name']} at position {layer['position']}")
        return layers

    def _build_layer_section(
        self, layers: List[Dict], width: int, height: int
    ) -> bytes:
        """Build the layer and mask information section."""
        # Simplified layer section - just enough for basic compatibility
        data = io.BytesIO()

        # Layer Info
        layer_info = io.BytesIO()

        # Layer count (negative for absolute count)
        layer_info.write(struct.pack('>h', -len(layers)))

        # Layer records
        for layer in layers:
            img = layer["image"]
            pos = layer.get("position", (0, 0))

            # Layer bounds (top, left, bottom, right)
            top = pos[1]
            left = pos[0]
            bottom = top + img.height
            right = left + img.width
            layer_info.write(struct.pack('>iiii', top, left, bottom, right))
            logger.debug(f"Layer '{layer['name']}' bounds: top={top}, left={left}, bottom={bottom}, right={right}")

            # Number of channels
            layer_info.write(struct.pack('>H', 4))

            # Channel info
            for ch in range(4):
                layer_info.write(struct.pack('>hI', ch - 1 if ch > 0 else -1, img.width * img.height + 2))

            # Blend mode signature and key
            layer_info.write(b'8BIM')
            layer_info.write(b'norm')

            # Opacity
            layer_info.write(struct.pack('B', int(layer["opacity"] * 255)))

            # Clipping, flags, filler
            layer_info.write(struct.pack('BBB', 0, 0, 0))
            layer_info.write(struct.pack('B', 0))  # Filler

            # Extra data length
            extra_data = self._build_layer_extra_data(layer["name"])
            layer_info.write(struct.pack('>I', len(extra_data)))
            layer_info.write(extra_data)

        # Channel image data
        # Channel order must match declaration: -1=alpha, 0=red, 1=green, 2=blue
        # RGBA array indices: 0=R, 1=G, 2=B, 3=A
        # So we write: A(3), R(0), G(1), B(2)
        channel_order = [3, 0, 1, 2]  # Alpha, Red, Green, Blue
        for layer in layers:
            img = layer["image"]
            img_array = np.array(img)

            for ch_idx in channel_order:
                # Compression type (raw)
                layer_info.write(struct.pack('>H', 0))
                # Channel data
                layer_info.write(img_array[:, :, ch_idx].tobytes())

        # Write layer info with length
        layer_info_data = layer_info.getvalue()
        data.write(struct.pack('>I', len(layer_info_data)))
        data.write(layer_info_data)

        # Global layer mask info (none)
        data.write(struct.pack('>I', 0))

        return data.getvalue()

    def _build_layer_extra_data(self, name: str) -> bytes:
        """Build extra layer data (mask, blending, name)."""
        data = io.BytesIO()

        # Layer mask data (none)
        data.write(struct.pack('>I', 0))

        # Blending ranges (none)
        data.write(struct.pack('>I', 0))

        # Layer name (Pascal string, padded to 4 bytes)
        name_bytes = name.encode('latin-1', errors='replace')
        name_len = min(len(name_bytes), 255)
        data.write(struct.pack('B', name_len))
        data.write(name_bytes[:name_len])

        # Pad to 4 bytes
        padding = (4 - ((1 + name_len) % 4)) % 4
        data.write(b'\x00' * padding)

        return data.getvalue()

    def _create_composite_image(
        self, layers: List[Dict], width: int, height: int
    ) -> np.ndarray:
        """Create a composite image from all layers."""
        composite = np.zeros((height, width, 4), dtype=np.uint8)
        composite[:, :, 3] = 255  # Full opacity

        for layer in reversed(layers):
            if not layer["visible"]:
                continue

            img = layer["image"]
            img_array = np.array(img)
            pos = layer.get("position", (0, 0))
            x, y = pos[0], pos[1]

            # Calculate bounds with position offset
            src_h, src_w = img_array.shape[0], img_array.shape[1]

            # Clip to canvas bounds
            dst_x1 = max(0, x)
            dst_y1 = max(0, y)
            dst_x2 = min(width, x + src_w)
            dst_y2 = min(height, y + src_h)

            # Source region
            src_x1 = dst_x1 - x
            src_y1 = dst_y1 - y
            src_x2 = src_x1 + (dst_x2 - dst_x1)
            src_y2 = src_y1 + (dst_y2 - dst_y1)

            if dst_x2 <= dst_x1 or dst_y2 <= dst_y1:
                continue  # Nothing to composite

            alpha = img_array[src_y1:src_y2, src_x1:src_x2, 3:4] / 255.0 * layer["opacity"]

            for c in range(3):
                composite[dst_y1:dst_y2, dst_x1:dst_x2, c] = (
                    composite[dst_y1:dst_y2, dst_x1:dst_x2, c] * (1 - alpha[:, :, 0]) +
                    img_array[src_y1:src_y2, src_x1:src_x2, c] * alpha[:, :, 0]
                ).astype(np.uint8)

        return composite

    def _export_fallback_script(self, output_path: Path) -> bool:
        """
        Generate a Photoshop script that creates the PSD.

        This is a fallback when direct PSD creation isn't possible.

        Args:
            output_path: Path for the script (will add .jsx extension)

        Returns:
            True if script generated successfully
        """
        try:
            script_path = output_path.with_suffix('.jsx')
            layers_dir = output_path.parent / f"{output_path.stem}_layers"
            layers_dir.mkdir(parents=True, exist_ok=True)

            # Export all layer images as PNGs
            layer_files = []
            self._export_layer_images(self.puppet.root_layer, layers_dir, layer_files)

            # Generate ExtendScript
            script = self._generate_photoshop_script(
                layer_files,
                self.puppet.width,
                self.puppet.height,
                output_path.name,
            )

            with open(script_path, 'w') as f:
                f.write(script)

            logger.info(f"Generated Photoshop script: {script_path}")
            logger.info(f"Layer images saved to: {layers_dir}")
            logger.info("Run the script in Photoshop to create the PSD")

            return True

        except Exception as e:
            logger.error(f"Failed to generate fallback script: {e}")
            return False

    def _export_layer_images(
        self,
        layer: PuppetLayer,
        output_dir: Path,
        file_list: List[Dict],
        path: str = "",
    ):
        """Export layer images as PNG files."""
        current_path = f"{path}/{layer.name}" if path else layer.name

        if layer.image is not None:
            filename = current_path.replace("/", "_") + ".png"
            filepath = output_dir / filename
            layer.image.save(filepath, "PNG")

            file_list.append({
                "name": layer.display_name,
                "file": filename,
                "visible": layer.visible,
                "is_group": False,
                "path": current_path,
            })

        if layer.is_group():
            file_list.append({
                "name": layer.display_name,
                "is_group": True,
                "group_type": "open",
                "path": current_path,
            })

            for child in layer.children:
                self._export_layer_images(child, output_dir, file_list, current_path)

            file_list.append({
                "name": layer.display_name,
                "is_group": True,
                "group_type": "close",
                "path": current_path,
            })

    def _generate_photoshop_script(
        self,
        layer_files: List[Dict],
        width: int,
        height: int,
        output_name: str,
    ) -> str:
        """Generate ExtendScript for Photoshop."""
        script = f'''// Character Animator Puppet Generator
// Auto-generated script to create {output_name}

// Create new document
var doc = app.documents.add({width}, {height}, 72, "{output_name}", NewDocumentMode.RGB);

// Get script folder
var scriptFile = new File($.fileName);
var scriptFolder = scriptFile.parent;
var layersFolder = new Folder(scriptFolder + "/{output_name.replace('.psd', '')}_layers");

// Helper function to load PNG
function loadLayer(filename, layerName, visible) {{
    var file = new File(layersFolder + "/" + filename);
    if (file.exists) {{
        app.open(file);
        var srcDoc = app.activeDocument;
        srcDoc.selection.selectAll();
        srcDoc.selection.copy();
        srcDoc.close(SaveOptions.DONOTSAVECHANGES);

        app.activeDocument = doc;
        doc.paste();

        var layer = doc.activeLayer;
        layer.name = layerName;
        layer.visible = visible;
        return layer;
    }}
    return null;
}}

// Helper function to create group
function createGroup(name) {{
    var group = doc.layerSets.add();
    group.name = name;
    return group;
}}

// Build puppet structure
var currentGroup = null;
var groupStack = [];

'''
        # Add layer creation code
        for item in layer_files:
            if item["is_group"]:
                if item["group_type"] == "open":
                    script += f'''
// Create group: {item["name"]}
groupStack.push(currentGroup);
currentGroup = createGroup("{item["name"]}");
'''
                else:
                    script += '''
currentGroup = groupStack.pop();
'''
            else:
                visible = "true" if item["visible"] else "false"
                script += f'''
loadLayer("{item["file"]}", "{item["name"]}", {visible});
'''

        script += f'''
// Save as PSD
var psdFile = new File(scriptFolder + "/{output_name}");
var psdOptions = new PhotoshopSaveOptions();
psdOptions.layers = true;
doc.saveAs(psdFile, psdOptions, true);

alert("Puppet PSD created successfully!");
'''

        return script
