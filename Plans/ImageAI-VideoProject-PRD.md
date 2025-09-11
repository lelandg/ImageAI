# 🎬 ImageAI – Video Project Feature (PRD & Build Plan)
*Version:* 1.0 • *Date:* 2025-09-11 20:30 UTC  
*Owner:* ImageAI • *Status:* Implementation Ready

Veo API reference: 
https://ai.google.dev/gemini-api/docs/video?example=dialogue

---

## 1) Overview
Add a **Video Project** workflow to ImageAI that turns **lyrics/text** into an **auto‑storyboard** → **AI-powered prompt generation** → **image generation** pipeline → **video assembly**.  

**Key Features:**
- **AI Prompt Generation**: Use Gemini or OpenAI to generate cinematic prompts from lyrics/text
- **Full Edit Control**: All AI-generated prompts are editable by the user
- **Comprehensive History**: Complete versioning system with time-travel restore capability
- **Image Generation**: Leverage existing providers (Gemini, OpenAI, Stable Diffusion/local)
- **Video Assembly**: Two paths:
  - **Gemini Veo API** (veo-3.0-generate-001): Generate 8-second AI video clips
  - **Local FFmpeg**: Create slideshow videos with Ken Burns effects and transitions

**Out of scope now:** music/beat/TTS, song mixing, external audio alignment.

**Additional development data:** I used ChatGPT-5 to create lyrics, image prompts, and "Veo project." Everything is in the (project root) `./Sample/` folder. It shows examples of image prompts based on lyrics, and a template folder layout for each Veo scene. I don't care what format the output is in, since it will produce a valid MP4. So consider this an example. It *would* be nice to save projects so the user can switch between them, and always restore the same images/videos.

---

## 2) Goals & Non‑Goals
### ✅ Goals
- Paste lyrics/text (the same format you used in *Grandpa Was a Democrat*) or load from file.
- **AI-powered prompt generation** using Gemini or OpenAI LLMs with full user edit capability.
- Auto‑derive a **shotlist/storyboard** with scene durations that sum to either:
  - a user‑specified total length (e.g., 2:45), or
  - an auto‑estimate (based on line counts and pacing presets).
- Generate **N images** (per scene) using a selected **provider/model** (already wired in ImageAI).
- Human‑in‑the‑loop **review/approve/reorder/regenerate**.
- **Comprehensive version history** with time-travel restore to any previous state.
- **Render video** via:
  - **Gemini Veo API** (veo-3.0-generate-001): Generate 8-second AI video clips.
  - **Local slideshow** (Ken Burns, crossfades, captions; silent by default).
- Save a **project file** (`.iaproj.json`) and all assets under a dedicated project folder.
- Keep detailed **metadata** for reproducibility & cost tracking.

### 🚫 Non‑Goals (initial)
- Audio/music timing, vocal synthesis, lyric karaoke overlays.
- Advanced continuity (face/character locking across all scenes) beyond seed/prompt carry‑over.
- Multi‑track timelines; we’ll ship a single-track MVP, then iterate.

---

## 3) AI Prompt Generation & Editing

### Prompt Generation Pipeline
1. **Input Analysis**: Parse lyrics/text to identify scenes and key elements
2. **LLM Enhancement**: Use Gemini or OpenAI to generate cinematic prompts
3. **User Review**: Present generated prompts with inline editing capability
4. **Version Tracking**: Save all prompt versions (AI-generated and user-edited)

### Prompt Generation Features
- **Provider Selection**: Choose between Gemini or OpenAI for prompt generation
- **Style Templates**: Apply cinematic, artistic, or photorealistic styles
- **Batch Generation**: Generate all scene prompts in one operation
- **Regeneration**: Re-generate individual prompts while preserving others
- **Edit History**: Track all changes with diff visualization

### Example Prompt Enhancement
```
Input: "Grandpa was a Democrat"
AI Output: "Cinematic wide shot of an elderly man in worn denim overalls, 
sitting on a weathered porch in rural America, golden hour lighting, 
American flag gently waving, nostalgic 1960s aesthetic, Norman Rockwell style"
```

---

## 4) Version History & Time Travel

### Event Sourcing Architecture
Every action creates an immutable event, enabling complete reconstruction of any previous state:

#### Event Types
- **Project Events**: Creation, settings changes, exports
- **Scene Events**: Addition, deletion, reordering, duration changes
- **Prompt Events**: AI generation, user edits, regeneration
- **Image Events**: Generation, selection, deletion
- **Render Events**: Video generation, export settings

### History Features
#### History Tab (Per Project)
- **Timeline View**: Visual representation of all project events
- **Filter Controls**: Show/hide event types, search by content
- **Diff Viewer**: Compare any two versions side-by-side
- **Restore Points**: One-click restore to any previous state
- **Branch Support**: Create alternate versions from any point

#### Storage Strategy
- **Event Store**: SQLite with JSON columns for flexibility
- **Snapshots**: Periodic full-state captures for fast restoration
- **Delta Compression**: Efficient storage of incremental changes
- **Media Caching**: Preserve generated images/videos with events

### Implementation Example
```python
@dataclass
class ProjectEvent:
    event_id: str
    project_id: str
    event_type: str
    event_data: Dict[str, Any]
    timestamp: datetime
    user_action: bool  # True if user-initiated, False if AI-generated
    
class ProjectHistory:
    def save_prompt_edit(self, scene_id: str, old_prompt: str, new_prompt: str):
        event = ProjectEvent(
            event_id=uuid.uuid4(),
            project_id=self.project_id,
            event_type="prompt_edited",
            event_data={
                "scene_id": scene_id,
                "old_prompt": old_prompt,
                "new_prompt": new_prompt,
                "diff": difflib.unified_diff(old_prompt, new_prompt)
            },
            timestamp=datetime.now(),
            user_action=True
        )
        self.event_store.append(event)
```

---

## 5) UX Spec (GUI)
### New Tab: **🎬 Video Project**
- **Project header**: name, base folder, open/save.
- **Input panel**:
  - Text area + “Load from file…” (accepts `.txt`, `.md`, `.iaproj.json`).
  - **Format selector** (auto‑detect):  
    - *Timestamped lines:* `[mm:ss] line` (also accept `[mm:ss.mmm]`)  
    - *Structured lyrics:* `# Verse`, `# Chorus`, etc. (no timestamps)  
  - **Pacing preset**: *Fast / Medium / Slow* (affects scene durations when no timestamps).  
  - **Target Length**: `hh:mm:ss` (optional).

- **Provider & Prompting**:
  - **Image Provider**: Gemini / OpenAI / Stability / Local SD (+ model dropdown).  
  - **Style controls**: aspect ratio (pre‑set to **16:9**), quality, negative prompt, seed.  
  - **Prompt strategy**:  
    - “Literal line” vs “Cinematic rewrite” (LLM rewrites each line into a robust image prompt; supports template tokens).  
    - Template picker (Jinja‑like): `templates/lyric_prompt.j2`.

- **Storyboard panel**:
  - Auto‑computed **scenes table** (line → prompt → duration).
  - **Inline prompt editing** with syntax highlighting and AI suggestions.
  - Per‑scene **N variants** (e.g., 1–4) with thumbnail grid. Re‑roll per scene.  
  - Drag to reorder scenes; duration knob per scene; title/caption toggle.
  - **Prompt history dropdown** showing all versions for each scene.

- **Preview & Export**:
  - **Preview cut**: quick render (low res, fast transitions).  
  - **Export**:
    - **Local Slideshow** → `MP4 (H.264, 24fps)`; pan/zoom + crossfades; optional burned‑in captions.  
    - **Gemini Veo**: choose model (**Veo 3**, **Veo 3 Fast**, **Veo 2**), aspect ratio 16:9, resolution 720p/1080p (per model constraints), negative prompt; clip chaining with concat.  
    - **Mute audio** option (for Veo 3 outputs).  
  - **Render queue** with progress & logs.

### New Tab: **📜 Project History**
- **Timeline View**: Interactive timeline showing all project events
- **Event Filters**: Toggle visibility of different event types
- **Diff Viewer**: Side-by-side comparison of any two versions
- **Restore Controls**: 
  - Restore button for any historical state
  - Create branch from any point
  - Export history as JSON
- **Search**: Find events by content, date, or type
- **Statistics Panel**: Event counts, storage usage, activity graph

---

## 6) Data & Files
```
{
  "schema": "imageai.video_project.v1",
  "name": "Grandpa Was a Democrat",
  "created": "ISO-8601",
  "provider": {
    "images": { "provider": "gemini|openai|stability|local", "model": "…" },
    "video":   { "provider": "veo|slideshow", "model": "veo-3.0-generate-001|veo-2.0-generate-001|…" }
  },
  "prompt_template": "templates/lyric_prompt.j2",
  "style": { "aspect_ratio": "16:9", "negative": "…", "seed": 1234 },
  "input": { "raw": "…lyrics…", "format": "timestamped|structured" },
  "timing": { "target": "00:02:45", "preset": "medium" },
  "scenes": [
    {
      "id": "scene-001",
      "source": "[00:12] Grandpa was a Democrat…",
      "prompt": "Cinematic Americana kitchen…",
      "duration_sec": 4.5,
      "images": [
        {
          "path": "assets/scene-001/var-1.png",
          "provider": "gemini",
          "model": "imagen-4.0-generate-001",
          "seed": 1234,
          "cost": 0.02,
          "metadata": {…}
        }
      ],
      "approved_image": "assets/scene-001/var-1.png"
    }
  ],
  "export": { "path": "exports/grandpa_2025-09-11.mp4" }
}
```

**Folders under project root**
- `assets/scene-xxx/*.png` (all variants + chosen)  
- `exports/*.mp4` (finals + previews)  
- `logs/*.jsonl` (events & cost)  
- `project.iaproj.json`

---

## 7) Architecture & Code Layout (Detailed)

### Directory Structure
```
/gui
  video/
    video_project_tab.py         # Main tab widget with all panels
    storyboard_table.py          # Scene management table widget
    render_queue.py              # Export queue with progress tracking
    timeline_widget.py           # Visual timeline for scene durations
    preview_player.py            # Video preview widget

/core
  video/
    __init__.py                  # Video module exports
    project.py                   # VideoProject data model & persistence
    storyboard.py                # Scene parsing and management
    timing.py                    # Duration allocation algorithms
    prompt_engine.py             # LLM-based prompt enhancement
    image_batcher.py             # Concurrent image generation
    cache.py                     # Content-addressed storage
    
  video/renderers/
    ffmpeg_slideshow.py          # Local slideshow generator
    veo_renderer.py              # Veo API video generation
    base_renderer.py             # Abstract renderer interface

/providers
  video/
    __init__.py                  # Video provider exports
    gemini_veo.py                # Veo 2/3 implementation
    base_video.py                # Abstract video provider

/templates
  video/
    lyric_prompt.j2              # Template for lyric → image prompt
    shot_prompt.j2               # Template for cinematic shots
    scene_description.j2         # Template for scene metadata

/cli
  commands/
    video.py                     # Video subcommand implementation
```

### Integration Points with Existing Code

#### main.py modifications:
```python
# Add to GUI tab registration
if self.config.get("features", {}).get("video_enabled", True):
    from gui.video.video_project_tab import VideoProjectTab
    self.video_tab = VideoProjectTab(self.config, self.providers)
    self.tabs.addTab(self.video_tab, "🎬 Video Project")

# Add to CLI argument parser
subparsers = parser.add_subparsers(dest='command')
video_parser = subparsers.add_parser('video', help='Video generation')
cli.commands.video.setup_parser(video_parser)
```

#### Provider Interface Extension:
```python
# providers/base.py - Add video generation interface
class BaseProvider:
    def generate_image(self, prompt: str, **kwargs) -> Path:
        """Existing image generation"""
        pass
    
    def generate_video(self, prompt: str, image: Path = None, **kwargs) -> Path:
        """New video generation interface"""
        raise NotImplementedError("Video generation not supported")

# providers/google.py - Extend for Veo
class GoogleProvider(BaseProvider):
    def generate_video(self, prompt: str, image: Path = None, **kwargs):
        from providers.video.gemini_veo import VeoRenderer
        renderer = VeoRenderer(self.client)
        return renderer.generate(prompt, image, **kwargs)
```

#### Configuration Schema:
```python
# core/config.py - Add video settings
VIDEO_CONFIG_SCHEMA = {
    "video_projects_dir": str,  # Default: user_config_dir / "video_projects"
    "default_video_provider": str,  # "veo" or "slideshow"
    "veo_model": str,  # "veo-3.0-generate-001"
    "ffmpeg_path": str,  # Auto-detect or user-specified
    "cache_size_mb": int,  # Max cache size (default: 5000)
    "concurrent_images": int,  # Max parallel generations (default: 3)
}

---

## 8) Core Algorithms
### 6.1 Lyric/Text → Scenes
- **Timestamped** lines: exact cut points from `[mm:ss(.mmm)]`; otherwise use **pacing preset** to distribute total length over lines, weighted by line length.
- **Shot count**: `ceil(total_length / target_shot_seconds)` (defaults: 3–5s per shot).  
- **LLM rewrite** (optional): for each line, produce a **cinematic** prompt (subject, action, style, camera, ambiance, negative).

### 6.2 Image Batch
- Concurrency capped per provider.
- **Idempotent cache** by hash of `(provider, model, prompt, seed, size)`.
- Backoff on rate limits; light dedupe of semantically near‑identical prompts.

### 6.3 Video Assembly
- **Local slideshow**: 24fps, H.264 MP4, default 16:9; per‑scene pan/zoom + 0.5s crossfades; optional captions (line text).  
- **Gemini Veo**:
  - Clip generator → `generate_videos(model, prompt, image=approved_first_frame, config)` producing **5–8s** segments (Veo 3/3 Fast: **audio on**; Veo 2: **silent**).  
  - Concat clips; **mute** if requested.  
  - Download within **2 days** (server retention) and store locally.

---

## 9) Constraints & Model Notes
- **Veo 3 / Veo 3 Fast**: 8s, 24fps, 720p or 1080p (16:9 only), audio always on.  
- **Veo 2**: 5–8s, 24fps, 720p, silent; can do 9:16 portrait.  
- **Region/person rules**: `personGeneration` options vary by region; enforce in UI.  
- **Ops pattern**: long‑running operation; poll until `done`, then download video file.  
- **Watermarking**: SynthID applied to Veo output.
- **Token/Input limits**: keep prompts concise; image‑to‑video supported.

> See links in References for the official docs; implement guardrails in the tab (tooltips & validation).

---

## 10) CLI (initial sketch)
```bash
# Build storyboard and images, then render slideshow
imageai video --in lyrics.txt --provider gemini --model imagen-4.0-generate-001   --length 00:02:30 --slideshow --out exports/grandpa.mp4

# Build Gemini Veo chain (silent)
imageai video --in lyrics.txt --image-provider openai --image-model dall-e-3   --veo-model veo-2.0-generate-001 --out exports/grandpa_veo.mp4 --mute
```

---

## 11) API Implementation Examples

### 9.1 Complete Veo Integration Class
```python
# providers/video/gemini_veo.py
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from google import genai
from google.genai import types

class VeoRenderer:
    """Gemini Veo video generation wrapper"""
    
    MODELS = {
        "veo-3": "veo-3.0-generate-001",
        "veo-3-fast": "veo-3.0-fast-generate-001", 
        "veo-2": "veo-2.0-generate-001"
    }
    
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.logger = logging.getLogger(__name__)
    
    def generate_video(self, 
                      prompt: str,
                      model: str = "veo-3",
                      image: Optional[Path] = None,
                      aspect_ratio: str = "16:9",
                      resolution: str = "720p",
                      negative_prompt: Optional[str] = None,
                      person_generation: str = "dont_allow",
                      seed: Optional[int] = None,
                      output_path: Optional[Path] = None,
                      timeout: int = 600) -> Path:
        """
        Generate video using Veo API
        
        Args:
            prompt: Text description for video
            model: Model key (veo-3, veo-3-fast, veo-2)
            image: Optional first frame image
            aspect_ratio: Video aspect ratio (16:9 or 9:16)
            resolution: Output resolution (720p or 1080p)
            negative_prompt: Things to avoid in generation
            person_generation: Person generation policy
            seed: Random seed for reproducibility
            output_path: Where to save the video
            timeout: Maximum wait time in seconds
            
        Returns:
            Path to saved video file
        """
        
        # Validate model
        if model not in self.MODELS:
            raise ValueError(f"Unknown model: {model}")
        
        model_name = self.MODELS[model]
        
        # Build config
        config_kwargs = {
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "person_generation": person_generation
        }
        
        if negative_prompt:
            config_kwargs["negative_prompt"] = negative_prompt
        if seed is not None:
            config_kwargs["seed"] = seed
            
        config = types.GenerateVideosConfig(**config_kwargs)
        
        # Load image if provided
        image_file = None
        if image and image.exists():
            with open(image, 'rb') as f:
                image_file = self.client.files.upload(f)
        
        # Start generation
        self.logger.info(f"Starting video generation with {model_name}")
        operation = self.client.models.generate_videos(
            model=model_name,
            prompt=prompt,
            image=image_file,
            config=config
        )
        
        # Poll for completion
        start_time = time.time()
        while not operation.done:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Video generation timed out after {timeout}s")
            
            time.sleep(10)
            operation = self.client.operations.get(operation)
            self.logger.debug(f"Generation status: {operation.metadata}")
        
        # Check for errors
        if operation.error:
            raise Exception(f"Video generation failed: {operation.error}")
        
        # Download result
        if not operation.result or not operation.result.generated_videos:
            raise Exception("No video was generated")
        
        video = operation.result.generated_videos[0]
        self.client.files.download(file=video.video)
        
        # Save to file
        if not output_path:
            output_path = Path(f"veo_{model}_{int(time.time())}.mp4")
        
        video.video.save(str(output_path))
        self.logger.info(f"Video saved to {output_path}")
        
        return output_path
    
    def concatenate_videos(self, video_paths: list[Path], output: Path) -> Path:
        """Concatenate multiple Veo clips into one video"""
        import subprocess
        
        # Create concat file
        concat_file = Path("concat.txt")
        with open(concat_file, 'w') as f:
            for path in video_paths:
                f.write(f"file '{path.absolute()}'\n")
        
        # Run ffmpeg concat
        cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",  # No re-encoding
            str(output)
        ]
        
        subprocess.run(cmd, check=True)
        concat_file.unlink()
        
        return output
```

### 9.2 FFmpeg Slideshow Generator
```python
# core/video/renderers/ffmpeg_slideshow.py
import subprocess
import json
from pathlib import Path
from typing import List, Optional, Tuple

class FFmpegSlideshow:
    """Generate video slideshows from images using FFmpeg"""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg = ffmpeg_path
        self._verify_ffmpeg()
    
    def _verify_ffmpeg(self):
        """Check if FFmpeg is available"""
        try:
            subprocess.run([self.ffmpeg, "-version"], 
                         capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("FFmpeg not found. Please install FFmpeg.")
    
    def create_slideshow(self,
                        images: List[Path],
                        durations: List[float],
                        output: Path,
                        resolution: Tuple[int, int] = (1920, 1080),
                        fps: int = 24,
                        transition_duration: float = 0.5,
                        enable_ken_burns: bool = True,
                        captions: Optional[List[str]] = None) -> Path:
        """
        Create slideshow video from images
        
        Args:
            images: List of image paths
            durations: Duration for each image in seconds
            output: Output video path
            resolution: Output resolution (width, height)
            fps: Frames per second
            transition_duration: Crossfade duration
            enable_ken_burns: Enable pan/zoom effect
            captions: Optional captions for each image
        """
        
        # Build filter complex
        filter_parts = []
        
        for i, (img, duration) in enumerate(zip(images, durations)):
            # Scale and pad to resolution
            filter_parts.append(
                f"[{i}:v]scale={resolution[0]}:{resolution[1]}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={resolution[0]}:{resolution[1]}:(ow-iw)/2:(oh-ih)/2"
            )
            
            # Ken Burns effect (zoom and pan)
            if enable_ken_burns:
                zoom_factor = 1.1
                pan_x = "(iw-ow)/2+sin(t/10)*20"
                pan_y = "(ih-oh)/2+cos(t/10)*20"
                filter_parts[-1] += (
                    f",zoompan=z='min(zoom+0.002,{zoom_factor})':"
                    f"x='{pan_x}':y='{pan_y}':"
                    f"d={int(duration * fps)}:s={resolution[0]}x{resolution[1]}"
                )
            
            # Add caption if provided
            if captions and i < len(captions):
                caption = captions[i].replace("'", "\\'")
                filter_parts[-1] += (
                    f",drawtext=text='{caption}':"
                    f"fontsize=48:fontcolor=white:"
                    f"shadowcolor=black:shadowx=2:shadowy=2:"
                    f"x=(w-text_w)/2:y=h-80"
                )
            
            filter_parts[-1] += f"[v{i}]"
        
        # Build crossfade chain
        if len(images) > 1:
            # Start with first video
            concat_filter = f"[v0]"
            
            for i in range(1, len(images)):
                offset = sum(durations[:i]) - transition_duration * i
                concat_filter += (
                    f"[v{i}]xfade=transition=fade:"
                    f"duration={transition_duration}:"
                    f"offset={offset}"
                )
                if i < len(images) - 1:
                    concat_filter += f"[vx{i}];[vx{i}]"
            
            filter_parts.append(concat_filter + ",format=yuv420p[out]")
        else:
            filter_parts.append("[v0]format=yuv420p[out]")
        
        # Build FFmpeg command
        cmd = [self.ffmpeg, "-y"]
        
        # Add inputs
        for img in images:
            cmd.extend(["-loop", "1", "-i", str(img)])
        
        # Add filter complex
        cmd.extend([
            "-filter_complex", ";".join(filter_parts),
            "-map", "[out]",
            "-r", str(fps),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(output)
        ])
        
        # Run FFmpeg
        subprocess.run(cmd, check=True)
        
        return output
```

### 9.3 Scene-to-Video Pipeline
```python
# core/video/pipeline.py
from typing import List, Dict, Any
from pathlib import Path
import asyncio
import concurrent.futures

class VideoProjectPipeline:
    """End-to-end video generation pipeline"""
    
    def __init__(self, config: Dict[str, Any], providers: Dict[str, Any]):
        self.config = config
        self.providers = providers
        self.image_cache = {}
    
    async def process_scene(self, scene: Dict[str, Any]) -> List[Path]:
        """Generate images for a single scene"""
        
        # Check cache first
        cache_key = self._get_cache_key(scene)
        if cache_key in self.image_cache:
            return self.image_cache[cache_key]
        
        # Get provider
        provider_name = scene.get("provider", self.config["default_provider"])
        provider = self.providers[provider_name]
        
        # Generate variants
        images = []
        num_variants = scene.get("variants", 3)
        
        for i in range(num_variants):
            seed = scene.get("seed", 0) + i if scene.get("seed") else None
            
            image_path = await self._generate_image_async(
                provider=provider,
                prompt=scene["prompt"],
                seed=seed,
                negative=scene.get("negative_prompt"),
                size=(1920, 1080)  # 16:9 for video
            )
            images.append(image_path)
        
        # Cache results
        self.image_cache[cache_key] = images
        return images
    
    async def generate_all_scenes(self, scenes: List[Dict]) -> Dict[str, List[Path]]:
        """Generate images for all scenes concurrently"""
        
        # Limit concurrency
        semaphore = asyncio.Semaphore(self.config.get("concurrent_images", 3))
        
        async def process_with_limit(scene):
            async with semaphore:
                return await self.process_scene(scene)
        
        # Process all scenes
        tasks = [process_with_limit(scene) for scene in scenes]
        results = await asyncio.gather(*tasks)
        
        # Map scene IDs to images
        return {
            scene["id"]: images 
            for scene, images in zip(scenes, results)
        }
    
    def render_video(self, project: Dict, renderer: str = "slideshow") -> Path:
        """Render final video using specified renderer"""
        
        if renderer == "slideshow":
            from core.video.renderers.ffmpeg_slideshow import FFmpegSlideshow
            slideshow = FFmpegSlideshow()
            
            # Collect approved images
            images = []
            durations = []
            captions = []
            
            for scene in project["scenes"]:
                images.append(Path(scene["approved_image"]))
                durations.append(scene["duration_sec"])
                captions.append(scene.get("caption", ""))
            
            return slideshow.create_slideshow(
                images=images,
                durations=durations,
                captions=captions,
                output=Path(project["export"]["path"])
            )
        
        elif renderer == "veo":
            from providers.video.gemini_veo import VeoRenderer
            veo = VeoRenderer(self.config["google_api_key"])
            
            # Generate Veo clips for each scene
            clips = []
            for scene in project["scenes"]:
                clip = veo.generate_video(
                    prompt=scene["prompt"],
                    image=Path(scene["approved_image"]),
                    model=project["provider"]["video"]["model"]
                )
                clips.append(clip)
            
            # Concatenate clips
            return veo.concatenate_videos(
                clips, 
                Path(project["export"]["path"])
            )
```

---

## 12) Validation
- Golden sample projects checked into `Plans/samples/` with deterministic seeds.
- Headless **CI smoke**: generate 2 scenes with tiny images + 2s clips; assert MP4 exists.

---

## 13) Risks & Mitigations
- **Model safety blocks** → auto‑rewrite prompts (LLM), add negative terms, or switch provider.
- **Latency** (Veo ops) → queue + UI progress + local preview path.
- **Regional restrictions** → gate `personGeneration` options by `iso_region`.
- **Cost overruns** → show running cost estimate per batch.

---

## 14) Phased Delivery
1. **MVP Phase 1**: Core foundation - Event sourcing, AI prompt generation, storyboard, image batcher.
2. **MVP Phase 2**: Video generation - Veo API integration (8s clips), FFmpeg slideshow export.
3. **Enhancement (v1.1)**: History tab, advanced transitions, captions, presets, caching, cost panel.
4. **Polish (v1.2)**: Drag-reorder UX, branch support, diff viewer, restore points.
5. **Continuity (v2.0)**: Seed carry-over, character consistency, style transfer.
6. **Audio (v3.0)**: External track alignment, beat mapping, music sync.

---

## 15) References
- Gemini API – Generate videos with Veo (models, durations, polling, retention): https://ai.google.dev/gemini-api/docs/video  
- Gemini API – Models catalog: https://ai.google.dev/gemini-api/docs/models  
- ImageAI repo README (providers, PySide6 GUI, CLI): https://github.com/lelandg/ImageAI

---

## 16) Acceptance Criteria (MVP)
- I can paste lyrics, click **Storyboard**, see scene rows with durations summing to target length.
- I can **Generate Images** and see thumbnails per scene; re‑roll one scene without touching others.
- I can **Export → Slideshow** and get a valid MP4 at 24fps, 16:9.
- All artifacts + a `project.iaproj.json` are saved under the project folder.
- Rerunning the same prompts with the same seed reuses cached images.

---

## 17) Implementation Checklist

### Phase 1: Foundation & Core Components
#### 1.1 Project Structure Setup
- [ ] Create core video module directories: `core/video/`, `gui/video/`
- [ ] Create templates directory: `templates/video/`
- [ ] Set up project storage structure under user config directory
- [ ] Create sample project structure in `Plans/samples/`

#### 1.2 Data Models & Storage
- [ ] Define `VideoProject` class with schema version control
- [ ] Implement `Scene` data model (id, source, prompt, duration, images, approved)
- [ ] Create `ProjectManager` for save/load/migrate operations
- [ ] Implement project file validation & schema migration

#### 1.3 Dependencies & Configuration
- [ ] Add Jinja2 to requirements.txt for template processing
- [ ] Add moviepy or imageio-ffmpeg for video processing
- [ ] Verify google-genai supports latest Veo models
- [ ] Update config system to include video-specific settings

### Phase 2: AI Prompt Generation & History System
#### 2.1 Version History Foundation
- [ ] Implement event sourcing with SQLite backend
- [ ] Create ProjectEvent dataclass and event types enum
- [ ] Build EventStore with append and query operations
- [ ] Implement snapshot system for performance
- [ ] Add delta compression for storage efficiency

#### 2.2 AI Prompt Generation
- [ ] Integrate LLM providers for prompt generation (Gemini/OpenAI)
- [ ] Create prompt enhancement templates
- [ ] Build batch prompt generation system
- [ ] Implement style presets (cinematic, artistic, photorealistic)
- [ ] Add prompt regeneration with preservation of other prompts

#### 2.3 Prompt Editing & Tracking
- [ ] Build inline prompt editor with syntax highlighting
- [ ] Implement prompt version tracking
- [ ] Create diff visualization for prompt changes
- [ ] Add prompt history dropdown per scene
- [ ] Build prompt lineage tracking system

### Phase 3: Text Processing & Storyboarding
#### 3.1 Input Parsing
- [ ] Implement timestamped format parser: `[mm:ss] text` and `[mm:ss.mmm] text`
- [ ] Implement structured lyrics parser: `# Verse`, `# Chorus`, etc.
- [ ] Create format auto-detection logic
- [ ] Add file loaders for `.txt`, `.md`, `.iaproj.json`

#### 3.2 Timing & Scene Generation
- [ ] Implement `TimingEngine` with pacing presets (Fast/Medium/Slow)
- [ ] Create duration allocation algorithm for target length
- [ ] Build scene splitter with configurable shot duration (3-5s default)
- [ ] Add duration validation and adjustment logic

#### 3.3 Prompt Engineering
- [ ] Create base Jinja2 templates: `lyric_prompt.j2`, `shot_prompt.j2`
- [ ] Implement `PromptEngine` with LLM rewrite capability
- [ ] Add template token system for style variables
- [ ] Create cinematic prompt generator with camera/style/ambiance tokens

### Phase 4: Image Generation Pipeline
#### 4.1 Provider Integration
- [ ] Ensure unified `generate_image()` interface across all providers
- [ ] Add batch generation support with concurrency limits
- [ ] Implement provider-specific error handling and retries
- [ ] Add cost estimation and tracking per provider

#### 4.2 Image Caching & Management
- [ ] Create idempotent cache with hash-based lookup
- [ ] Implement cache invalidation and cleanup
- [ ] Add image variant management (N per scene)
- [ ] Build thumbnail generation for UI display

#### 4.3 Scene Management
- [ ] Implement per-scene regeneration without affecting others
- [ ] Add approved image selection and persistence
- [ ] Create scene reordering logic
- [ ] Build metadata tracking for each generation

### Phase 5: GUI Implementation
#### 5.1 Video Project Tab
- [ ] Create `VideoProjectTab` widget in PySide6
- [ ] Implement project header with name/folder/save controls
- [ ] Add input panel with text area and format selector
- [ ] Build provider selection with model dropdowns

#### 5.2 Storyboard Interface
- [ ] Create `StoryboardTable` widget with scene rows
- [ ] Implement thumbnail grid display (N variants per scene)
- [ ] Add drag-and-drop scene reordering
- [ ] Build duration adjustment controls per scene
- [ ] Add caption/title toggle switches

#### 5.3 Style & Configuration
- [ ] Add aspect ratio selector (16:9, 9:16)
- [ ] Implement quality/resolution controls
- [ ] Add negative prompt input
- [ ] Create seed management UI
- [ ] Build template selector and editor

#### 5.4 Progress & Feedback
- [ ] Implement `RenderQueue` widget with progress bars
- [ ] Add real-time generation status display
- [ ] Create cost estimate display
- [ ] Build error notification system

#### 5.5 History Tab Implementation
- [ ] Create `HistoryTab` widget with timeline view
- [ ] Implement event filtering and search
- [ ] Build diff viewer for comparing versions
- [ ] Add restore point creation and management
- [ ] Implement branch creation from historical states
- [ ] Create history export functionality
- [ ] Add storage usage analytics display

### Phase 6: Video Assembly - Local Slideshow
#### 6.1 FFmpeg Integration
- [ ] Implement `FFmpegSlideshow` class
- [ ] Add Ken Burns effect (pan/zoom) support
- [ ] Create crossfade transition system (0.5s default)
- [ ] Build caption overlay system

#### 6.2 Video Export
- [ ] Implement H.264 encoding at 24fps
- [ ] Add resolution options (720p, 1080p)
- [ ] Create preview generation (low-res, fast)
- [ ] Build final export with quality settings

### Phase 7: Veo API Integration
#### 7.1 Veo Client Implementation
- [ ] Create `VeoClient` wrapper class using google.genai
- [ ] Implement `generate_videos()` with all config options
- [ ] Add polling mechanism for long-running operations (11s-6min)
- [ ] Build download and local storage system (2-day retention handling)
- [ ] Implement timeout and retry logic

#### 7.2 Veo Model Support
- [ ] Add Veo 3.0 support (`veo-3.0-generate-001`)
- [ ] Add Veo 3.0 Fast support (`veo-3.0-fast-generate-001`)
- [ ] Add Veo 2.0 support (`veo-2.0-generate-001`)
- [ ] Implement model-specific constraints (resolution, duration, audio)
- [ ] Add aspect ratio support (16:9, 9:16)

#### 7.3 Regional Compliance
- [ ] Implement region detection system
- [ ] Add `personGeneration` option gating by region
- [ ] Create UI warnings for regional restrictions
- [ ] Build fallback strategies for blocked content
- [ ] Handle MENA/EU restrictions appropriately

#### 7.4 Video Processing
- [ ] Implement clip concatenation system using ffmpeg
- [ ] Add audio muting option for Veo 3 outputs
- [ ] Build 2-day retention warning system
- [ ] Create automatic local backup on generation
- [ ] Add SynthID watermark detection/display

### Phase 8: CLI Implementation
#### 8.1 Command Structure
- [ ] Add `video` subcommand to main CLI
- [ ] Implement all GUI features in CLI
- [ ] Add batch processing support
- [ ] Create progress indicators for terminal

#### 8.2 CLI Arguments
- [ ] `--in`: Input file path
- [ ] `--provider`: Image provider selection
- [ ] `--model`: Model selection
- [ ] `--length`: Target video length
- [ ] `--slideshow`: Use local slideshow renderer
- [ ] `--veo-model`: Veo model selection
- [ ] `--out`: Output file path
- [ ] `--mute`: Mute audio option

### Phase 9: Testing & Validation
#### 9.1 Unit Tests
- [ ] Test lyric parsing (all formats)
- [ ] Test timing allocation algorithms
- [ ] Test prompt generation and templates
- [ ] Test project save/load/migration

#### 9.2 Integration Tests
- [ ] Test provider image generation pipeline
- [ ] Test video assembly (slideshow)
- [ ] Test Veo API integration
- [ ] Test end-to-end workflow

#### 9.3 Sample Projects
- [ ] Create "Grandpa Was a Democrat" reference project
- [ ] Add deterministic seed test cases
- [ ] Build CI/CD smoke tests
- [ ] Document expected outputs

### Phase 10: Documentation & Polish
#### 10.1 User Documentation
- [ ] Update README with video feature documentation
- [ ] Create video workflow tutorial
- [ ] Add troubleshooting guide
- [ ] Document all CLI options

#### 10.2 Developer Documentation
- [ ] Document API interfaces
- [ ] Create plugin architecture docs
- [ ] Add contribution guidelines
- [ ] Build architecture diagrams

#### 10.3 UI Polish
- [ ] Add tooltips and help text
- [ ] Implement keyboard shortcuts
- [ ] Create preset management
- [ ] Add export history viewer

### Technical Requirements & Notes

#### Dependencies to Add
```txt
# Add to requirements.txt
Jinja2>=3.1.0  # Template processing
moviepy>=1.0.3  # Video processing (or imageio-ffmpeg)
# google-genai already present
```

#### FFmpeg Requirements
- Must be installed separately by user
- Provide installation instructions per platform
- Implement graceful fallback if not available

#### File Size Considerations
- Image cache management (auto-cleanup old projects)
- Video file compression options
- Streaming preview instead of full download

#### Performance Optimizations
- Concurrent image generation with rate limiting
- Lazy loading of thumbnails in UI
- Background video rendering with queue
- Incremental project saves

#### Error Handling Priority
- Network timeouts and retries
- API rate limiting and backoff
- Provider safety blocks and fallbacks
- Disk space monitoring

---

## 18) Known Limitations & Future Enhancements

### Current Limitations
- No audio synchronization (music/beat alignment)
- Limited to 8-second Veo clips
- No character consistency across scenes
- Regional restrictions on person generation
- 2-day retention for Veo videos

### Future Enhancements (Post-MVP)
- Music beat detection and sync
- TTS narration integration
- Multi-track timeline editor
- Character consistency via ControlNet/IP-Adapter
- External audio track alignment
- Longer video generation via clip chaining
- Style transfer between scenes
- Motion templates and presets
