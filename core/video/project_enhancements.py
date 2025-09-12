"""
Enhanced project management features for video projects.

Includes versioning, image variants, crop/Ken Burns controls.
"""

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum


class VersioningMode(Enum):
    """Project versioning modes"""
    NONE = "none"
    TIMESTAMP = "timestamp"  
    SEQUENTIAL = "sequential"
    BOTH = "both"


class CropMode(Enum):
    """Image crop positioning modes"""
    CENTER = "center"
    RULE_OF_THIRDS = "thirds"
    MANUAL = "manual"
    SMART = "smart"
    TOP = "top"
    BOTTOM = "bottom"


class AudioHandling(Enum):
    """How to handle audio files"""
    LINK = "link"  # Reference original
    COPY = "copy"  # Copy to project
    CONVERT = "convert"  # Copy and convert


@dataclass
class CropSettings:
    """Crop settings for an image"""
    mode: CropMode = CropMode.CENTER
    position: Dict[str, float] = field(default_factory=lambda: {"x": 0.5, "y": 0.5})
    scale: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "position": self.position,
            "scale": self.scale
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CropSettings':
        return cls(
            mode=CropMode(data.get("mode", "center")),
            position=data.get("position", {"x": 0.5, "y": 0.5}),
            scale=data.get("scale", 1.0)
        )


@dataclass
class KenBurnsSettings:
    """Ken Burns effect settings"""
    enabled: bool = False
    start: Dict[str, float] = field(default_factory=lambda: {"x": 0.5, "y": 0.5, "scale": 1.0})
    end: Dict[str, float] = field(default_factory=lambda: {"x": 0.5, "y": 0.5, "scale": 1.1})
    duration_factor: float = 1.0
    easing: str = "ease-in-out"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KenBurnsSettings':
        return cls(**data)


@dataclass
class ProjectSettings:
    """Enhanced project-specific settings"""
    name: str
    versioning_mode: VersioningMode = VersioningMode.NONE
    
    # Ken Burns defaults
    ken_burns_enabled: bool = False
    ken_burns_intensity: float = 0.3
    auto_ken_burns_for_square: bool = False
    
    # Crop defaults  
    default_crop_mode: CropMode = CropMode.CENTER
    default_crop_position: Dict[str, float] = field(default_factory=lambda: {"x": 0.5, "y": 0.5})
    
    # Generation settings
    images_per_scene: int = 3
    auto_crop_square: bool = True
    
    # Rendering settings
    auto_save_renders: bool = True
    keep_draft_renders: int = 3
    render_quality: str = "draft"  # draft, final, custom
    
    # Audio settings
    audio_handling: AudioHandling = AudioHandling.LINK
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "name": self.name,
            "versioning_mode": self.versioning_mode.value,
            "ken_burns_enabled": self.ken_burns_enabled,
            "ken_burns_intensity": self.ken_burns_intensity,
            "auto_ken_burns_for_square": self.auto_ken_burns_for_square,
            "default_crop_mode": self.default_crop_mode.value,
            "default_crop_position": self.default_crop_position,
            "images_per_scene": self.images_per_scene,
            "auto_crop_square": self.auto_crop_square,
            "auto_save_renders": self.auto_save_renders,
            "keep_draft_renders": self.keep_draft_renders,
            "render_quality": self.render_quality,
            "audio_handling": self.audio_handling.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectSettings':
        """Create from dictionary"""
        return cls(
            name=data["name"],
            versioning_mode=VersioningMode(data.get("versioning_mode", "none")),
            ken_burns_enabled=data.get("ken_burns_enabled", False),
            ken_burns_intensity=data.get("ken_burns_intensity", 0.3),
            auto_ken_burns_for_square=data.get("auto_ken_burns_for_square", False),
            default_crop_mode=CropMode(data.get("default_crop_mode", "center")),
            default_crop_position=data.get("default_crop_position", {"x": 0.5, "y": 0.5}),
            images_per_scene=data.get("images_per_scene", 3),
            auto_crop_square=data.get("auto_crop_square", True),
            auto_save_renders=data.get("auto_save_renders", True),
            keep_draft_renders=data.get("keep_draft_renders", 3),
            render_quality=data.get("render_quality", "draft"),
            audio_handling=AudioHandling(data.get("audio_handling", "link"))
        )


@dataclass
class ImageVariant:
    """Represents a generated image variant"""
    filename: str
    provider: str
    prompt: str
    timestamp: datetime
    is_selected: bool = False
    crop_settings: Optional[CropSettings] = None
    ken_burns_settings: Optional[KenBurnsSettings] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "filename": self.filename,
            "provider": self.provider,
            "prompt": self.prompt,
            "timestamp": self.timestamp.isoformat(),
            "is_selected": self.is_selected,
            "crop_settings": self.crop_settings.to_dict() if self.crop_settings else None,
            "ken_burns_settings": self.ken_burns_settings.to_dict() if self.ken_burns_settings else None,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImageVariant':
        """Create from dictionary"""
        return cls(
            filename=data["filename"],
            provider=data["provider"],
            prompt=data.get("prompt", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            is_selected=data.get("is_selected", False),
            crop_settings=CropSettings.from_dict(data["crop_settings"]) if data.get("crop_settings") else None,
            ken_burns_settings=KenBurnsSettings.from_dict(data["ken_burns_settings"]) if data.get("ken_burns_settings") else None,
            metadata=data.get("metadata", {})
        )


@dataclass  
class SceneVariants:
    """Manages multiple image variants for a scene"""
    scene_index: int
    variants: List[ImageVariant] = field(default_factory=list)
    selected_index: int = 0
    max_variants: int = 10
    
    def add_variant(self, variant: ImageVariant) -> bool:
        """Add a new variant, enforcing max limit"""
        if len(self.variants) >= self.max_variants:
            # Remove oldest non-selected variant
            for i, v in enumerate(self.variants):
                if not v.is_selected:
                    self.variants.pop(i)
                    break
            else:
                return False  # All are selected, can't add
        
        self.variants.append(variant)
        return True
    
    def select_variant(self, index: int):
        """Select a specific variant"""
        if 0 <= index < len(self.variants):
            # Deselect all
            for v in self.variants:
                v.is_selected = False
            # Select the chosen one
            self.variants[index].is_selected = True
            self.selected_index = index
    
    def get_selected(self) -> Optional[ImageVariant]:
        """Get the currently selected variant"""
        for v in self.variants:
            if v.is_selected:
                return v
        return self.variants[0] if self.variants else None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_index": self.scene_index,
            "variants": [v.to_dict() for v in self.variants],
            "selected_index": self.selected_index,
            "max_variants": self.max_variants
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SceneVariants':
        scene = cls(
            scene_index=data["scene_index"],
            selected_index=data.get("selected_index", 0),
            max_variants=data.get("max_variants", 10)
        )
        scene.variants = [ImageVariant.from_dict(v) for v in data.get("variants", [])]
        return scene


class KenBurnsPresets:
    """Predefined Ken Burns effect templates"""
    
    PRESETS = {
        "disabled": KenBurnsSettings(enabled=False),
        
        "subtle_zoom": KenBurnsSettings(
            enabled=True,
            start={"x": 0.5, "y": 0.5, "scale": 1.0},
            end={"x": 0.5, "y": 0.5, "scale": 1.1},
            duration_factor=1.0,
            easing="ease-in-out"
        ),
        
        "dramatic_zoom": KenBurnsSettings(
            enabled=True,
            start={"x": 0.5, "y": 0.5, "scale": 0.8},
            end={"x": 0.5, "y": 0.5, "scale": 1.3},
            duration_factor=1.0,
            easing="ease-in-out"
        ),
        
        "pan_left_right": KenBurnsSettings(
            enabled=True,
            start={"x": 0.3, "y": 0.5, "scale": 1.0},
            end={"x": 0.7, "y": 0.5, "scale": 1.0},
            duration_factor=1.0,
            easing="linear"
        ),
        
        "pan_right_left": KenBurnsSettings(
            enabled=True,
            start={"x": 0.7, "y": 0.5, "scale": 1.0},
            end={"x": 0.3, "y": 0.5, "scale": 1.0},
            duration_factor=1.0,
            easing="linear"
        ),
        
        "pan_up_down": KenBurnsSettings(
            enabled=True,
            start={"x": 0.5, "y": 0.3, "scale": 1.0},
            end={"x": 0.5, "y": 0.7, "scale": 1.0},
            duration_factor=1.0,
            easing="linear"
        ),
        
        "zoom_and_pan": KenBurnsSettings(
            enabled=True,
            start={"x": 0.3, "y": 0.3, "scale": 0.9},
            end={"x": 0.7, "y": 0.7, "scale": 1.2},
            duration_factor=1.0,
            easing="ease-in-out"
        )
    }
    
    @classmethod
    def get_preset(cls, name: str) -> KenBurnsSettings:
        """Get a preset by name"""
        return cls.PRESETS.get(name, cls.PRESETS["disabled"])
    
    @classmethod
    def list_presets(cls) -> List[str]:
        """Get list of available preset names"""
        return list(cls.PRESETS.keys())


class EnhancedProjectManager:
    """Enhanced project manager with versioning and variants support"""
    
    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize enhanced project manager"""
        self.logger = logging.getLogger(__name__)
        
        if base_dir is None:
            # Use platform-specific user directory
            import platform
            system = platform.system()
            
            if system == "Windows":
                base_dir = Path(os.environ.get('APPDATA', '')) / 'ImageAI' / 'video_projects'
            elif system == "Darwin":  # macOS
                base_dir = Path.home() / 'Library' / 'Application Support' / 'ImageAI' / 'video_projects'
            else:  # Linux
                base_dir = Path.home() / '.config' / 'ImageAI' / 'video_projects'
        
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Recent projects tracking
        self.recent_projects_file = self.base_dir / "recent_projects.json"
        self.recent_projects = self._load_recent_projects()
    
    def _load_recent_projects(self) -> List[Dict[str, Any]]:
        """Load recent projects list"""
        if self.recent_projects_file.exists():
            try:
                with open(self.recent_projects_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading recent projects: {e}")
        return []
    
    def _save_recent_projects(self):
        """Save recent projects list"""
        try:
            with open(self.recent_projects_file, 'w') as f:
                json.dump(self.recent_projects[:10], f, indent=2)  # Keep last 10
        except Exception as e:
            self.logger.error(f"Error saving recent projects: {e}")
    
    def _add_to_recent(self, project_path: Path, project_name: str):
        """Add project to recent list"""
        entry = {
            "path": str(project_path),
            "name": project_name,
            "last_opened": datetime.now().isoformat()
        }
        
        # Remove if already exists
        self.recent_projects = [p for p in self.recent_projects 
                               if p["path"] != str(project_path)]
        
        # Add to front
        self.recent_projects.insert(0, entry)
        self._save_recent_projects()
    
    def create_project_directory(self, name: str, settings: ProjectSettings) -> Path:
        """Create a new video project directory with versioning"""
        folder_name = self._generate_folder_name(name, settings.versioning_mode)
        project_dir = self.base_dir / folder_name
        
        # Create directory structure
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "assets").mkdir(exist_ok=True)
        (project_dir / "images").mkdir(exist_ok=True)
        (project_dir / "lyrics").mkdir(exist_ok=True)
        (project_dir / "renders").mkdir(exist_ok=True)
        
        # Save settings
        self.save_project_settings(project_dir, settings)
        
        # Initialize workspace
        self.init_workspace(project_dir)
        
        # Add to recent
        self._add_to_recent(project_dir, name)
        
        return project_dir
    
    def _generate_folder_name(self, base_name: str, mode: VersioningMode) -> str:
        """Generate folder name based on versioning mode"""
        clean_name = self._sanitize_filename(base_name)
        
        if mode == VersioningMode.NONE:
            return clean_name
        
        elif mode == VersioningMode.TIMESTAMP:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"{clean_name}_{timestamp}"
        
        elif mode == VersioningMode.SEQUENTIAL:
            version = self._get_next_version(clean_name)
            return f"{clean_name}_v{version:03d}"
        
        elif mode == VersioningMode.BOTH:
            version = self._get_next_version(clean_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"{clean_name}_v{version:03d}_{timestamp}"
        
        return clean_name
    
    def _get_next_version(self, base_name: str) -> int:
        """Get next sequential version number"""
        pattern = f"{base_name}_v*"
        existing = list(self.base_dir.glob(pattern))
        
        if not existing:
            return 1
        
        versions = []
        for path in existing:
            try:
                parts = path.name.split('_v')
                if len(parts) > 1:
                    version_str = parts[1].split('_')[0]
                    versions.append(int(version_str))
            except (ValueError, IndexError):
                continue
        
        return max(versions, default=0) + 1
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename for filesystem"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        return name.strip()
    
    def save_project_settings(self, project_dir: Path, settings: ProjectSettings):
        """Save project settings to file"""
        settings_file = project_dir / "project_settings.json"
        with open(settings_file, 'w') as f:
            json.dump(settings.to_dict(), f, indent=2)
    
    def load_project_settings(self, project_dir: Path) -> ProjectSettings:
        """Load project settings from file"""
        settings_file = project_dir / "project_settings.json"
        if settings_file.exists():
            with open(settings_file, 'r') as f:
                data = json.load(f)
                return ProjectSettings.from_dict(data)
        return ProjectSettings(name=project_dir.name)
    
    def init_workspace(self, project_dir: Path):
        """Initialize workspace file"""
        workspace_file = project_dir / "workspace.json"
        workspace = {
            "created": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "scene_variants": {},
            "ui_state": {}
        }
        with open(workspace_file, 'w') as f:
            json.dump(workspace, f, indent=2)
    
    def save_scene_variants(self, project_dir: Path, scene_index: int, variants: SceneVariants):
        """Save scene variants to disk"""
        scene_dir = project_dir / "images" / f"scene_{scene_index:04d}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        
        variants_file = scene_dir / "variants.json"
        with open(variants_file, 'w') as f:
            json.dump(variants.to_dict(), f, indent=2)
    
    def load_scene_variants(self, project_dir: Path, scene_index: int) -> SceneVariants:
        """Load scene variants from disk"""
        scene_dir = project_dir / "images" / f"scene_{scene_index:04d}"
        variants_file = scene_dir / "variants.json"
        
        if variants_file.exists():
            with open(variants_file, 'r') as f:
                data = json.load(f)
                return SceneVariants.from_dict(data)
        
        return SceneVariants(scene_index=scene_index)
    
    def get_render_filename(self, project_dir: Path, settings: ProjectSettings, 
                          quality: str = "draft") -> Path:
        """Generate render filename based on settings"""
        renders_dir = project_dir / "renders"
        renders_dir.mkdir(exist_ok=True)
        
        base_name = project_dir.name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if settings.auto_save_renders:
            filename = f"{base_name}_{timestamp}_{quality}.mp4"
        else:
            filename = f"{base_name}_{quality}.mp4"
        
        return renders_dir / filename
    
    def clean_old_drafts(self, project_dir: Path, keep_count: int):
        """Clean old draft renders"""
        renders_dir = project_dir / "renders"
        if not renders_dir.exists():
            return
        
        drafts = list(renders_dir.glob("*_draft.mp4"))
        drafts.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        for draft in drafts[keep_count:]:
            try:
                draft.unlink()
                self.logger.info(f"Removed old draft: {draft}")
            except Exception as e:
                self.logger.error(f"Error removing draft {draft}: {e}")