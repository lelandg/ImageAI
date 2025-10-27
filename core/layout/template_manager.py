"""
Template Management System

Handles template discovery, validation, preview generation, and caching.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
import logging

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

from PIL import Image, ImageDraw, ImageFont

from core.logging_config import LogManager
from core.config import ConfigManager

logger = LogManager().get_logger("layout.templates")


@dataclass
class TemplateMetadata:
    """Metadata for a template"""
    name: str
    filepath: Path
    category: str = "custom"
    description: str = ""
    tags: List[str] = field(default_factory=list)
    author: str = ""
    schema_version: str = "1.0"
    page_size_px: tuple = (2480, 3508)
    thumbnail_path: Optional[Path] = None
    extends: Optional[str] = None
    block_count: int = 0
    last_modified: Optional[datetime] = None

    def matches_search(self, query: str) -> bool:
        """Check if template matches search query"""
        query_lower = query.lower()
        return (
            query_lower in self.name.lower() or
            query_lower in self.description.lower() or
            any(query_lower in tag.lower() for tag in self.tags)
        )


@dataclass
class ValidationError:
    """Template validation error"""
    path: str
    message: str
    line_number: Optional[int] = None

    def __str__(self) -> str:
        if self.line_number:
            return f"{self.path} (line {self.line_number}): {self.message}"
        return f"{self.path}: {self.message}"


class TemplateValidator:
    """Validates template JSON against schema"""

    def __init__(self, schema_path: Optional[Path] = None):
        self.schema_path = schema_path or Path(__file__).parent / "template_schema.json"
        self.schema = None

        if HAS_JSONSCHEMA:
            try:
                with open(self.schema_path, 'r', encoding='utf-8') as f:
                    self.schema = json.load(f)
                logger.info(f"Loaded template schema from {self.schema_path}")
            except Exception as e:
                logger.warning(f"Failed to load template schema: {e}")
        else:
            logger.warning("jsonschema library not installed - validation will be basic")

    def validate(self, template_data: Dict[str, Any], filepath: Path) -> List[ValidationError]:
        """
        Validate template data against schema

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Basic required fields check
        required_fields = ["name", "page_size_px", "blocks"]
        for field in required_fields:
            if field not in template_data:
                errors.append(ValidationError(
                    path=str(filepath),
                    message=f"Missing required field: {field}"
                ))

        # Check blocks structure
        if "blocks" in template_data:
            blocks = template_data["blocks"]
            if not isinstance(blocks, list):
                errors.append(ValidationError(
                    path=str(filepath),
                    message="'blocks' must be an array"
                ))
            elif len(blocks) == 0:
                errors.append(ValidationError(
                    path=str(filepath),
                    message="'blocks' must contain at least one block"
                ))
            else:
                # Validate each block
                block_ids = set()
                for i, block in enumerate(blocks):
                    if not isinstance(block, dict):
                        errors.append(ValidationError(
                            path=str(filepath),
                            message=f"Block {i} must be an object"
                        ))
                        continue

                    # Check block type
                    if "type" not in block:
                        errors.append(ValidationError(
                            path=str(filepath),
                            message=f"Block {i} missing 'type' field"
                        ))
                    elif block["type"] not in ["text", "image"]:
                        errors.append(ValidationError(
                            path=str(filepath),
                            message=f"Block {i} has invalid type: {block['type']}"
                        ))

                    # Check block ID uniqueness
                    if "id" in block:
                        block_id = block["id"]
                        if block_id in block_ids:
                            errors.append(ValidationError(
                                path=str(filepath),
                                message=f"Duplicate block ID: {block_id}"
                            ))
                        block_ids.add(block_id)
                    else:
                        errors.append(ValidationError(
                            path=str(filepath),
                            message=f"Block {i} missing 'id' field"
                        ))

                    # Check rect
                    if "rect" not in block:
                        errors.append(ValidationError(
                            path=str(filepath),
                            message=f"Block {i} ({block.get('id', 'unknown')}) missing 'rect' field"
                        ))
                    elif not isinstance(block["rect"], list) or len(block["rect"]) != 4:
                        errors.append(ValidationError(
                            path=str(filepath),
                            message=f"Block {i} ({block.get('id', 'unknown')}) 'rect' must be [x, y, width, height]"
                        ))

        # Use jsonschema if available for comprehensive validation
        if self.schema and HAS_JSONSCHEMA:
            try:
                jsonschema.validate(instance=template_data, schema=self.schema)
            except jsonschema.ValidationError as e:
                errors.append(ValidationError(
                    path=str(filepath),
                    message=f"Schema validation failed: {e.message}",
                    line_number=None
                ))
            except jsonschema.SchemaError as e:
                logger.error(f"Invalid schema: {e}")

        return errors


class TemplatePreviewGenerator:
    """Generates preview thumbnails for templates"""

    def __init__(self, cache_dir: Optional[Path] = None):
        config = ConfigManager()
        if cache_dir is None:
            cache_dir = config.config_dir / "template_cache"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.preview_size = (256, 256)

    def get_cache_path(self, template_path: Path) -> Path:
        """Get cached preview path for template"""
        # Use hash of template path + modification time for cache key
        template_stat = template_path.stat()
        cache_key = f"{template_path.name}_{template_stat.st_mtime}"
        cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
        return self.cache_dir / f"{cache_hash}.png"

    def get_preview(self, template_path: Path, template_data: Dict[str, Any]) -> Optional[Path]:
        """
        Get or generate preview for template

        Returns:
            Path to preview image, or None if generation failed
        """
        cache_path = self.get_cache_path(template_path)

        # Return cached preview if it exists
        if cache_path.exists():
            logger.debug(f"Using cached preview for {template_path.name}")
            return cache_path

        # Generate new preview
        try:
            preview_img = self._generate_preview(template_data)
            preview_img.save(cache_path, "PNG")
            logger.info(f"Generated preview for {template_path.name} -> {cache_path}")
            return cache_path
        except Exception as e:
            logger.error(f"Failed to generate preview for {template_path.name}: {e}")
            return None

    def _generate_preview(self, template_data: Dict[str, Any]) -> Image.Image:
        """Generate preview thumbnail from template data"""
        page_w, page_h = template_data.get("page_size_px", [2480, 3508])

        # Calculate scale to fit preview size
        scale = min(self.preview_size[0] / page_w, self.preview_size[1] / page_h)
        preview_w = int(page_w * scale)
        preview_h = int(page_h * scale)

        # Create canvas with padding
        canvas = Image.new("RGB", self.preview_size, "#F8F9FA")
        preview = Image.new("RGB", (preview_w, preview_h), "#FFFFFF")
        draw = ImageDraw.Draw(preview)

        # Parse background color
        bg_color = template_data.get("background", "#FFFFFF")
        if bg_color and bg_color != "transparent" and not bg_color.startswith("{{"):
            preview = Image.new("RGB", (preview_w, preview_h), bg_color)
            draw = ImageDraw.Draw(preview)

        # Draw blocks
        blocks = template_data.get("blocks", [])
        for block in blocks:
            rect = block.get("rect", [0, 0, 100, 100])
            x, y, w, h = [int(v * scale) for v in rect]

            block_type = block.get("type", "")
            if block_type == "image":
                # Draw image placeholder
                color = "#E2E8F0"
                draw.rectangle([x, y, x + w, y + h], fill=color, outline="#94A3B8", width=1)
                # Draw X to indicate image
                draw.line([x, y, x + w, y + h], fill="#94A3B8", width=1)
                draw.line([x + w, y, x, y + h], fill="#94A3B8", width=1)
            elif block_type == "text":
                # Draw text placeholder
                color = "#FEF3C7"
                draw.rectangle([x, y, x + w, y + h], fill=color, outline="#F59E0B", width=1)
                # Draw lines to indicate text
                line_height = max(6, h // 8)
                for i in range(0, h, line_height + 2):
                    if y + i + 4 < y + h:
                        draw.rectangle([x + 4, y + i + 2, x + w - 4, y + i + 4], fill="#F59E0B")

        # Center preview on canvas
        offset_x = (self.preview_size[0] - preview_w) // 2
        offset_y = (self.preview_size[1] - preview_h) // 2
        canvas.paste(preview, (offset_x, offset_y))

        # Draw border
        draw_canvas = ImageDraw.Draw(canvas)
        draw_canvas.rectangle(
            [offset_x - 1, offset_y - 1, offset_x + preview_w, offset_y + preview_h],
            outline="#CBD5E1",
            width=1
        )

        return canvas

    def clear_cache(self, template_path: Optional[Path] = None):
        """Clear preview cache (all or specific template)"""
        if template_path:
            cache_path = self.get_cache_path(template_path)
            if cache_path.exists():
                cache_path.unlink()
                logger.info(f"Cleared cache for {template_path.name}")
        else:
            for cache_file in self.cache_dir.glob("*.png"):
                cache_file.unlink()
            logger.info("Cleared all preview cache")


class TemplateManager:
    """
    Manages template discovery, loading, validation, and caching
    """

    def __init__(self, template_dirs: Optional[List[Path]] = None):
        """
        Initialize template manager

        Args:
            template_dirs: List of directories to search for templates
                          If None, uses ConfigManager.get_templates_dir()
        """
        config = ConfigManager()

        if template_dirs is None:
            default_dir = config.get_templates_dir()
            template_dirs = [default_dir]

        self.template_dirs = [Path(d) for d in template_dirs]
        self.validator = TemplateValidator()
        self.preview_generator = TemplatePreviewGenerator()

        # Template registry
        self._templates: Dict[str, TemplateMetadata] = {}
        self._template_data_cache: Dict[str, Dict[str, Any]] = {}

        logger.info(f"Initialized TemplateManager with directories: {self.template_dirs}")

    def discover_templates(self, rescan: bool = False) -> List[TemplateMetadata]:
        """
        Discover all templates in configured directories

        Args:
            rescan: If True, force rescan even if templates are cached

        Returns:
            List of template metadata
        """
        if self._templates and not rescan:
            return list(self._templates.values())

        self._templates.clear()

        for template_dir in self.template_dirs:
            if not template_dir.exists():
                logger.warning(f"Template directory does not exist: {template_dir}")
                continue

            # Find all .json files
            for json_file in template_dir.rglob("*.json"):
                try:
                    metadata = self._load_template_metadata(json_file)
                    if metadata:
                        # Use filename without extension as key
                        key = json_file.stem
                        self._templates[key] = metadata
                        logger.debug(f"Discovered template: {key} ({metadata.name})")
                except Exception as e:
                    logger.error(f"Failed to load template {json_file}: {e}")

        logger.info(f"Discovered {len(self._templates)} templates")
        return list(self._templates.values())

    def _load_template_metadata(self, filepath: Path) -> Optional[TemplateMetadata]:
        """Load metadata from template file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Validate template
            errors = self.validator.validate(data, filepath)
            if errors:
                logger.warning(f"Template {filepath.name} has validation errors:")
                for error in errors[:3]:  # Show first 3 errors
                    logger.warning(f"  - {error}")
                # Don't load templates with errors
                return None

            # Extract metadata
            stat = filepath.stat()
            page_size = tuple(data.get("page_size_px", [2480, 3508]))

            metadata = TemplateMetadata(
                name=data.get("name", filepath.stem),
                filepath=filepath,
                category=data.get("category", "custom"),
                description=data.get("description", ""),
                tags=data.get("tags", []),
                author=data.get("author", ""),
                schema_version=data.get("schema_version", "1.0"),
                page_size_px=page_size,
                extends=data.get("extends"),
                block_count=len(data.get("blocks", [])),
                last_modified=datetime.fromtimestamp(stat.st_mtime)
            )

            # Generate preview
            preview_path = self.preview_generator.get_preview(filepath, data)
            metadata.thumbnail_path = preview_path

            return metadata

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {filepath}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load metadata from {filepath}: {e}")
            return None

    def get_template(self, template_key: str) -> Optional[TemplateMetadata]:
        """Get template metadata by key (filename without extension)"""
        if not self._templates:
            self.discover_templates()
        return self._templates.get(template_key)

    def load_template_data(self, template_key: str) -> Optional[Dict[str, Any]]:
        """
        Load full template data (with inheritance resolved)

        Args:
            template_key: Template key (filename without extension)

        Returns:
            Template data dictionary, or None if not found
        """
        # Check cache
        if template_key in self._template_data_cache:
            return self._template_data_cache[template_key]

        # Get metadata
        metadata = self.get_template(template_key)
        if not metadata:
            logger.error(f"Template not found: {template_key}")
            return None

        # Load JSON
        try:
            with open(metadata.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Resolve inheritance if needed
            if metadata.extends:
                data = self._resolve_inheritance(data, metadata.extends)

            # Cache and return
            self._template_data_cache[template_key] = data
            return data

        except Exception as e:
            logger.error(f"Failed to load template data for {template_key}: {e}")
            return None

    def _resolve_inheritance(self, child_data: Dict[str, Any], parent_key: str) -> Dict[str, Any]:
        """Resolve template inheritance"""
        parent_data = self.load_template_data(parent_key)
        if not parent_data:
            logger.warning(f"Base template not found: {parent_key}")
            return child_data

        # Deep copy parent data
        import copy
        merged = copy.deepcopy(parent_data)

        # Override with child properties
        for key, value in child_data.items():
            if key == "extends":
                continue  # Don't copy extends field
            elif key == "blocks":
                # Merge blocks by ID
                parent_blocks = {b["id"]: b for b in merged.get("blocks", []) if "id" in b}
                child_blocks = {b["id"]: b for b in value if "id" in b}
                parent_blocks.update(child_blocks)
                merged["blocks"] = list(parent_blocks.values())
            elif key == "variables":
                # Merge variables
                merged.setdefault("variables", {}).update(value)
            else:
                merged[key] = value

        return merged

    def search_templates(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[TemplateMetadata]:
        """
        Search templates by query, category, and tags

        Args:
            query: Text search in name/description/tags
            category: Filter by category
            tags: Filter by tags (any match)

        Returns:
            List of matching template metadata
        """
        if not self._templates:
            self.discover_templates()

        results = list(self._templates.values())

        # Filter by query
        if query:
            results = [t for t in results if t.matches_search(query)]

        # Filter by category
        if category:
            results = [t for t in results if t.category == category]

        # Filter by tags
        if tags:
            results = [
                t for t in results
                if any(tag in t.tags for tag in tags)
            ]

        return results

    def get_categories(self) -> List[str]:
        """Get list of all template categories"""
        if not self._templates:
            self.discover_templates()

        categories = set(t.category for t in self._templates.values())
        return sorted(categories)

    def get_all_tags(self) -> List[str]:
        """Get list of all template tags"""
        if not self._templates:
            self.discover_templates()

        all_tags: Set[str] = set()
        for template in self._templates.values():
            all_tags.update(template.tags)

        return sorted(all_tags)

    def validate_template_file(self, filepath: Path) -> List[ValidationError]:
        """Validate a template file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return self.validator.validate(data, filepath)
        except json.JSONDecodeError as e:
            return [ValidationError(
                path=str(filepath),
                message=f"Invalid JSON: {e}",
                line_number=e.lineno
            )]
        except Exception as e:
            return [ValidationError(
                path=str(filepath),
                message=f"Error reading file: {e}"
            )]

    def clear_cache(self):
        """Clear template data cache"""
        self._template_data_cache.clear()
        logger.info("Cleared template data cache")
