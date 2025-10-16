"""
Video Project data models and persistence for ImageAI.
Handles project state, scenes, and metadata management.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from enum import Enum

# Import MIDI and karaoke modules if available
try:
    from .midi_processor import MidiTimingData
    from .karaoke_renderer import KaraokeConfig
    MIDI_SUPPORT = True
except ImportError:
    MidiTimingData = None
    KaraokeConfig = None
    MIDI_SUPPORT = False


class VideoProvider(Enum):
    """Available video generation providers"""
    VEO = "veo"
    SLIDESHOW = "slideshow"


class SceneStatus(Enum):
    """Status of a scene in the generation pipeline"""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class AudioTrack:
    """Audio track configuration for video projects"""
    track_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_path: Optional[Path] = None  # Absolute path to audio file (not copied)
    track_type: str = "music"  # 'music', 'narration', 'sfx'
    volume: float = 1.0  # 0.0 to 1.0
    fade_in_duration: float = 0.0  # seconds
    fade_out_duration: float = 0.0  # seconds
    start_offset: float = 0.0  # trim from beginning
    end_offset: float = 0.0  # trim from end
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "track_id": self.track_id,
            "file_path": str(self.file_path) if self.file_path else None,
            "track_type": self.track_type,
            "volume": self.volume,
            "fade_in": self.fade_in_duration,
            "fade_out": self.fade_out_duration,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioTrack":
        """Create from dictionary"""
        return cls(
            track_id=data.get("track_id", str(uuid.uuid4())),
            file_path=Path(data["file_path"]) if data.get("file_path") else None,
            track_type=data.get("track_type", "music"),
            volume=data.get("volume", 1.0),
            fade_in_duration=data.get("fade_in", 0.0),
            fade_out_duration=data.get("fade_out", 0.0),
            start_offset=data.get("start_offset", 0.0),
            end_offset=data.get("end_offset", 0.0)
        )


class PromptHistory:
    """Manages undo/redo history for a single prompt field (max 256 levels)"""

    def __init__(self, max_size: int = 256):
        self.history: List[str] = []
        self.current_index: int = -1
        self.max_size = max_size

    def add(self, prompt: str):
        """Add a new prompt to history"""
        # If we're not at the end of history, discard everything after current position
        if self.current_index < len(self.history) - 1:
            self.history = self.history[:self.current_index + 1]

        # Add new prompt
        self.history.append(prompt)
        self.current_index = len(self.history) - 1

        # Trim to max size if needed (remove oldest)
        if len(self.history) > self.max_size:
            self.history = self.history[-self.max_size:]
            self.current_index = len(self.history) - 1

    def can_undo(self) -> bool:
        """Check if undo is available"""
        return self.current_index > 0

    def can_redo(self) -> bool:
        """Check if redo is available"""
        return self.current_index < len(self.history) - 1

    def undo(self) -> Optional[str]:
        """Undo to previous prompt, returns the prompt or None"""
        if self.can_undo():
            self.current_index -= 1
            return self.history[self.current_index]
        return None

    def redo(self) -> Optional[str]:
        """Redo to next prompt, returns the prompt or None"""
        if self.can_redo():
            self.current_index += 1
            return self.history[self.current_index]
        return None

    def get_current(self) -> Optional[str]:
        """Get current prompt"""
        if 0 <= self.current_index < len(self.history):
            return self.history[self.current_index]
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "history": self.history,
            "current_index": self.current_index,
            "max_size": self.max_size
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptHistory":
        """Create from dictionary"""
        ph = cls(max_size=data.get("max_size", 256))
        ph.history = data.get("history", [])
        ph.current_index = data.get("current_index", -1)
        return ph


@dataclass
class ImageVariant:
    """A single generated image variant for a scene"""
    path: Path
    provider: str
    model: str
    seed: Optional[int] = None
    cost: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "path": str(self.path),
            "provider": self.provider,
            "model": self.model,
            "seed": self.seed,
            "cost": self.cost,
            "metadata": self.metadata,
            "generated_at": self.generated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImageVariant":
        """Create from dictionary"""
        return cls(
            path=Path(data["path"]),
            provider=data["provider"],
            model=data["model"],
            seed=data.get("seed"),
            cost=data.get("cost", 0.0),
            metadata=data.get("metadata", {}),
            generated_at=datetime.fromisoformat(data.get("generated_at", datetime.now().isoformat()))
        )


@dataclass
class Scene:
    """A single scene in the video project"""
    id: str = field(default_factory=lambda: f"scene-{uuid.uuid4().hex[:8]}")
    source: str = ""  # Original text/lyric line
    prompt: str = ""  # AI-enhanced prompt for image generation (start frame)
    video_prompt: str = ""  # AI-enhanced prompt for video generation with motion/camera
    prompt_history: List[str] = field(default_factory=list)  # All previous prompt versions
    duration_sec: float = 4.0  # Scene duration in seconds
    images: List[ImageVariant] = field(default_factory=list)  # Generated image variants (start frames)
    approved_image: Optional[Path] = None  # Selected image for final video (start frame)
    video_clip: Optional[Path] = None  # Generated video clip path
    first_frame: Optional[Path] = None  # First frame extracted from video clip
    last_frame: Optional[Path] = None  # Last frame extracted from video clip
    use_last_frame_as_seed: bool = False  # Use last frame for continuous video
    caption: Optional[str] = None  # Optional caption overlay
    status: SceneStatus = SceneStatus.PENDING
    order: int = 0  # Scene order in timeline
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Veo 3.1 Frames-to-Video fields
    end_prompt: str = ""  # Optional end scene description for Veo 3.1
    end_frame_images: List[ImageVariant] = field(default_factory=list)  # Generated end frame variants
    end_frame: Optional[Path] = None  # Selected end frame for Veo 3.1
    end_frame_auto_linked: bool = False  # True if using next scene's start frame as end frame
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "source": self.source,
            "prompt": self.prompt,
            "video_prompt": self.video_prompt,
            "prompt_history": self.prompt_history,
            "duration_sec": self.duration_sec,
            "images": [img.to_dict() for img in self.images],
            "approved_image": str(self.approved_image) if self.approved_image else None,
            "video_clip": str(self.video_clip) if self.video_clip else None,
            "first_frame": str(self.first_frame) if self.first_frame else None,
            "last_frame": str(self.last_frame) if self.last_frame else None,
            "use_last_frame_as_seed": self.use_last_frame_as_seed,
            "caption": self.caption,
            "status": self.status.value,
            "order": self.order,
            "metadata": self.metadata,
            # Veo 3.1 end frame fields
            "end_prompt": self.end_prompt,
            "end_frame_images": [img.to_dict() for img in self.end_frame_images],
            "end_frame": str(self.end_frame) if self.end_frame else None,
            "end_frame_auto_linked": self.end_frame_auto_linked
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Scene":
        """Create from dictionary"""
        return cls(
            id=data.get("id", f"scene-{uuid.uuid4().hex[:8]}"),
            source=data.get("source", ""),
            prompt=data.get("prompt", ""),
            video_prompt=data.get("video_prompt", ""),
            prompt_history=data.get("prompt_history", []),
            duration_sec=data.get("duration_sec", 4.0),
            images=[ImageVariant.from_dict(img) for img in data.get("images", [])],
            approved_image=Path(data["approved_image"]) if data.get("approved_image") else None,
            video_clip=Path(data["video_clip"]) if data.get("video_clip") else None,
            first_frame=Path(data["first_frame"]) if data.get("first_frame") else None,
            last_frame=Path(data["last_frame"]) if data.get("last_frame") else None,
            use_last_frame_as_seed=data.get("use_last_frame_as_seed", False),
            caption=data.get("caption"),
            status=SceneStatus(data.get("status", "pending")),
            order=data.get("order", 0),
            metadata=data.get("metadata", {}),
            # Veo 3.1 end frame fields
            end_prompt=data.get("end_prompt", ""),
            end_frame_images=[ImageVariant.from_dict(img) for img in data.get("end_frame_images", [])],
            end_frame=Path(data["end_frame"]) if data.get("end_frame") else None,
            end_frame_auto_linked=data.get("end_frame_auto_linked", False)
        )
    
    def add_prompt_to_history(self, prompt: str):
        """Add a prompt to the history if it's different from current"""
        if prompt != self.prompt and prompt not in self.prompt_history:
            if self.prompt:  # Save current prompt to history before updating
                self.prompt_history.append(self.prompt)
            self.prompt = prompt

    def uses_veo_31(self) -> bool:
        """Check if this scene will use Veo 3.1 (has end frame)"""
        return self.end_frame is not None

    def can_generate_video(self) -> bool:
        """Check if scene is ready for video generation"""
        # Need at least start frame (approved_image or first image in images list)
        has_start_frame = self.approved_image is not None or (self.images and len(self.images) > 0)
        return has_start_frame


@dataclass
class VideoProject:
    """Main video project data model"""
    schema: str = "imageai.video_project.v1"
    name: str = "Untitled Project"
    project_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created: datetime = field(default_factory=datetime.now)
    modified: datetime = field(default_factory=datetime.now)
    
    # Provider configuration
    llm_provider: Optional[str] = None  # For prompt generation
    llm_model: Optional[str] = None
    image_provider: str = "gemini"
    image_model: str = "gemini-2.5-flash-image-preview"
    video_provider: str = "slideshow"  # 'veo' or 'slideshow'
    video_model: Optional[str] = None  # For Veo: 'veo-3.0-generate-001', etc.
    
    # Template and style
    prompt_template: str = "templates/video/lyric_prompt.j2"
    prompt_style: Optional[str] = None  # Cinematic, Artistic, etc.
    style: Dict[str, Any] = field(default_factory=lambda: {
        "aspect_ratio": "16:9",
        "negative_prompt": "",
        "seed": None,
        "quality": "high",
        "resolution": "1080p"
    })
    
    # Generation settings
    variants: int = 3  # Number of image variants to generate
    ken_burns: bool = True  # Enable Ken Burns effect
    transitions: bool = True  # Enable transitions
    captions: bool = False  # Enable captions
    video_muted: bool = True  # Video playback muted by default
    auto_link_enabled: bool = False  # Veo 3.1: Auto-link end frames to next scene's start
    
    # Input configuration
    input_text: str = ""
    input_format: str = "structured"  # 'timestamped' or 'structured' or 'Auto-detect'
    timing_preset: str = "medium"  # 'fast', 'medium', 'slow' or 'Medium', 'Fast', 'Slow'
    target_duration: Optional[str] = None  # "00:02:45" format
    aspect_ratio: Optional[str] = None  # Redundant with style, but kept for compatibility
    resolution: Optional[str] = None  # Redundant with style, but kept for compatibility
    seed: Optional[int] = None  # Redundant with style, but kept for compatibility  
    negative_prompt: Optional[str] = None  # Redundant with style, but kept for compatibility
    
    # Audio configuration
    audio_tracks: List[AudioTrack] = field(default_factory=list)
    
    # MIDI configuration (optional)
    midi_file_path: Optional[Path] = None
    midi_timing_data: Optional[MidiTimingData] = None
    sync_mode: str = "none"  # 'none', 'beat', 'measure', 'section'
    snap_strength: float = 0.8  # 0.0-1.0
    
    # Karaoke configuration (optional)
    karaoke_config: Optional[KaraokeConfig] = None
    karaoke_export_formats: List[str] = field(default_factory=list)  # ['lrc', 'srt', 'ass']
    karaoke_generated_files: Dict[str, Path] = field(default_factory=dict)
    
    # Scenes
    scenes: List[Scene] = field(default_factory=list)
    
    # Project paths
    project_dir: Optional[Path] = None
    export_path: Optional[Path] = None
    
    # Cost tracking
    total_cost: float = 0.0

    # Wizard configuration (not persisted - dynamically created)
    wizard_enabled: bool = True  # Enable/disable wizard mode
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "schema": self.schema,
            "name": self.name,
            "project_id": self.project_id,
            "created": self.created.isoformat(),
            "modified": self.modified.isoformat(),
            "provider": {
                "llm": {
                    "provider": self.llm_provider,
                    "model": self.llm_model
                },
                "images": {
                    "provider": self.image_provider,
                    "model": self.image_model
                },
                "video": {
                    "provider": self.video_provider,
                    "model": self.video_model
                }
            },
            "prompt_template": self.prompt_template,
            "prompt_style": self.prompt_style,
            "style": self.style,
            "input": {
                "raw": self.input_text,
                "format": self.input_format
            },
            "timing": {
                "target": self.target_duration,
                "preset": self.timing_preset
            },
            "generation": {
                "variants": self.variants,
                "ken_burns": self.ken_burns,
                "transitions": self.transitions,
                "captions": self.captions,
                "video_muted": self.video_muted,
                "auto_link_enabled": self.auto_link_enabled
            },
            "audio": {
                "tracks": [track.to_dict() for track in self.audio_tracks]
            },
            "midi": {
                "file_path": str(self.midi_file_path) if self.midi_file_path else None,
                "sync_mode": self.sync_mode,
                "snap_strength": self.snap_strength,
                "timing_data": self.midi_timing_data.to_dict() if self.midi_timing_data else None
            } if self.midi_file_path else None,
            "karaoke": {
                "config": self.karaoke_config.to_dict() if self.karaoke_config else None,
                "export_formats": self.karaoke_export_formats,
                "generated_files": {k: str(v) for k, v in self.karaoke_generated_files.items()}
            } if self.karaoke_config else None,
            "scenes": [scene.to_dict() for scene in self.scenes],
            "export": {
                "path": str(self.export_path) if self.export_path else None
            },
            "total_cost": self.total_cost
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoProject":
        """Create from dictionary"""
        project = cls(
            schema=data.get("schema", "imageai.video_project.v1"),
            name=data.get("name", "Untitled Project"),
            project_id=data.get("project_id", str(uuid.uuid4())),
            created=datetime.fromisoformat(data.get("created", datetime.now().isoformat())),
            modified=datetime.fromisoformat(data.get("modified", datetime.now().isoformat()))
        )
        
        # Load providers
        if "provider" in data:
            providers = data["provider"]
            if "llm" in providers:
                project.llm_provider = providers["llm"].get("provider")
                project.llm_model = providers["llm"].get("model")
            if "images" in providers:
                project.image_provider = providers["images"].get("provider", "gemini")
                project.image_model = providers["images"].get("model", "gemini-2.5-flash-image-preview")
            if "video" in providers:
                project.video_provider = providers["video"].get("provider", "slideshow")
                project.video_model = providers["video"].get("model")
        
        # Load style and templates
        project.prompt_template = data.get("prompt_template", "templates/video/lyric_prompt.j2")
        project.prompt_style = data.get("prompt_style")
        project.style = data.get("style", project.style)
        
        # Load generation settings
        if "generation" in data:
            gen = data["generation"]
            project.variants = gen.get("variants", 3)
            project.ken_burns = gen.get("ken_burns", True)
            project.transitions = gen.get("transitions", True)
            project.captions = gen.get("captions", False)
            project.video_muted = gen.get("video_muted", True)
            project.auto_link_enabled = gen.get("auto_link_enabled", False)
        else:
            # Fallback for older projects
            project.variants = 3
            project.ken_burns = True
            project.transitions = True
            project.captions = False
            project.video_muted = True
            project.auto_link_enabled = False
        
        # Load input configuration
        if "input" in data:
            project.input_text = data["input"].get("raw", "")
            project.input_format = data["input"].get("format", "structured")
        
        if "timing" in data:
            project.target_duration = data["timing"].get("target")
            project.timing_preset = data["timing"].get("preset", "medium")
        
        # Load audio tracks
        if "audio" in data and "tracks" in data["audio"]:
            project.audio_tracks = [AudioTrack.from_dict(track) for track in data["audio"]["tracks"]]
        
        # Load MIDI configuration
        if "midi" in data and data["midi"]:
            midi_data = data["midi"]
            if midi_data.get("file_path"):
                project.midi_file_path = Path(midi_data["file_path"])
            project.sync_mode = midi_data.get("sync_mode", "none")
            project.snap_strength = midi_data.get("snap_strength", 0.8)
            if midi_data.get("timing_data") and MidiTimingData:
                project.midi_timing_data = MidiTimingData.from_dict(midi_data["timing_data"])
        
        # Load karaoke configuration
        if "karaoke" in data and data["karaoke"]:
            karaoke_data = data["karaoke"]
            if karaoke_data.get("config") and KaraokeConfig:
                project.karaoke_config = KaraokeConfig.from_dict(karaoke_data["config"])
            project.karaoke_export_formats = karaoke_data.get("export_formats", [])
            if karaoke_data.get("generated_files"):
                project.karaoke_generated_files = {
                    k: Path(v) for k, v in karaoke_data["generated_files"].items()
                }
        
        # Load scenes
        project.scenes = [Scene.from_dict(scene) for scene in data.get("scenes", [])]
        
        # Load export path
        if "export" in data and data["export"].get("path"):
            project.export_path = Path(data["export"]["path"])
        
        project.total_cost = data.get("total_cost", 0.0)
        
        return project
    
    def save(self, path: Optional[Path] = None) -> Path:
        """Save project to JSON file"""
        if path is None:
            if self.project_dir:
                path = self.project_dir / "project.iaproj.json"
            else:
                raise ValueError("No save path specified and project_dir not set")
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        self.modified = datetime.now()
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        
        return path
    
    @classmethod
    def load(cls, path: Path) -> "VideoProject":
        """Load project from JSON file"""
        import logging
        logger = logging.getLogger(__name__)

        path = Path(path)

        # Check if file exists and is not empty
        if not path.exists():
            raise FileNotFoundError(f"Project file not found: {path}")

        if path.stat().st_size == 0:
            logger.error(f"Project file is empty: {path}")
            # Try to create a backup of the empty file
            backup_path = path.with_suffix('.json.empty')
            try:
                import shutil
                shutil.copy2(path, backup_path)
                logger.info(f"Backed up empty file to: {backup_path}")
            except Exception:
                pass
            raise ValueError(f"Project file is empty. A backup was created.")

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    raise ValueError(f"Project file contains no data: {path}")
                data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in project file {path}: {e}")
            # Try to create a backup of the corrupted file
            backup_path = path.with_suffix('.json.corrupted')
            try:
                import shutil
                shutil.copy2(path, backup_path)
                logger.info(f"Backed up corrupted file to: {backup_path}")
            except Exception as backup_error:
                logger.warning(f"Could not create backup: {backup_error}")
            raise ValueError(f"Project file contains invalid JSON. Backup saved to {backup_path.name}") from e

        project = cls.from_dict(data)
        project.project_dir = path.parent

        return project
    
    def add_scene(self, source: str, prompt: str = "", duration: float = 4.0) -> Scene:
        """Add a new scene to the project"""
        scene = Scene(
            source=source,
            prompt=prompt or source,
            duration_sec=duration,
            order=len(self.scenes)
        )
        self.scenes.append(scene)
        return scene
    
    def reorder_scenes(self, new_order: List[str]):
        """Reorder scenes by their IDs"""
        scene_map = {scene.id: scene for scene in self.scenes}
        self.scenes = []
        for i, scene_id in enumerate(new_order):
            if scene_id in scene_map:
                scene = scene_map[scene_id]
                scene.order = i
                self.scenes.append(scene)
    
    def get_total_duration(self) -> float:
        """Calculate total video duration in seconds"""
        return sum(scene.duration_sec for scene in self.scenes)
    
    def add_audio_track(self, audio_file: Path, track_type: str = 'music') -> AudioTrack:
        """Add an audio track to the project"""
        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        track = AudioTrack(
            file_path=audio_file.absolute(),
            track_type=track_type
        )
        self.audio_tracks.append(track)
        return track

    def get_workflow_wizard(self):
        """
        Get workflow wizard for guided video generation.

        Returns:
            WorkflowWizard instance for this project

        Note:
            Wizard is created dynamically and analyzes current project state.
            It's not persisted - fresh wizard is created each time project is loaded.
        """
        try:
            from .workflow_wizard import WorkflowWizard
            return WorkflowWizard(self)
        except ImportError as e:
            import logging
            logging.getLogger(__name__).warning(f"Workflow wizard not available: {e}")
            return None

    def get_wizard_next_step(self) -> Optional[str]:
        """
        Quick helper to get next workflow step without creating full wizard.

        Returns:
            Human-readable next step description, or None if wizard unavailable
        """
        wizard = self.get_workflow_wizard()
        if wizard:
            next_action = wizard.get_next_action()
            return f"{next_action['step_title']}: {next_action['action']}"
        return None