# Sprite Tab — Design

**Date:** 2026-08-29
**Status:** Approved selections (2026-08-24 selector) → design ready for plan
writing. Not yet implemented.
**Author:** Claude Code (with Leland Green)
**Inputs:** `Plans/sprite-tab-feature-selector.md` (39 features + 10 gaps +
10 answered questions), `Plans/2026-08-24-sprite-tab-research.md`,
`Plans/2026-08-24-sprite-tab-research/catalog.json`.

## Problem

ImageAI generates images and video, but it has no path from "a character
image" to "an engine-ready animated sprite". Game developers need: frames on a
transparent background, a fixed cell size, a known frame rate, a shared
palette (for pixel art), and a sheet + metadata file their engine can load.
Today the repo has no frame extractor, no chroma keyer, no quantizer, and no
sprite-sheet writer.

## Goal

Add a **Sprite tab** (and CLI) that turns a character image plus a one-line
brief into per-action animations, then exports them as sprite sheets, PNG
sequences, GIFs, and engine files. The tab must also process video clips and
PNG sequences that other tools produced, and it must export single frames.

## Non-goals (this feature)

- Frame interpolation (RIFE/FILM), onion skin, pivot editor, packed atlas,
  APNG/WebP, hardware palettes, palette-file I/O, libimagequant, outline
  pass, CorridorKey bridge, multi-direction sets, skeleton animation, tilesets,
  local Wan, pixel-native backends. All deselected on 2026-08-24.
- Native gpt-image alpha frames (`background=transparent`) — deselected.
  Note: the caps table `providers/openai.py` `supports_transparent_bg` for
  `gpt-image-2` is stale (API preview 2026-08-20). Out of scope here; file a
  follow-up.
- Cloud or network storage for sprite projects.

## Decisions (from the 2026-08-24 answers)

| # | Decision | Consequence |
|---|---|---|
| 1 | Phase-1 generation route is **video (Veo/Omni)**. The image route ships later in the same feature. | Sub-project 2 = video route. Sub-project 6 = image route + retouch. |
| 2 | Pixel-art conversion is **optional**. The pipeline produces **two output profiles**: `hd` (soft alpha, large cells) and `pixel` (binary alpha, integer downscale, shared palette). Either or both can be enabled. | `OutputProfile` in the project model; every exporter runs per enabled profile. |
| 3 | CLI parity ships **before the PR**. | Sub-project 7 is a PR gate. |
| 4 | Python floor for the sprite feature is **3.11**. rembg pins `>=3.11,<3.14`. | `requirements-sprite-ml.txt` optional extra; runtime gate on `sys.version_info`. README support line moves to "3.11+" in the docs task. |
| 5 | **Approved new deps:** scikit-image + scipy (de-jitter, with an OpenCV `phaseCorrelate` fallback when the import fails); mediapipe promoted to a **declared optional extra**. | Add to `requirements.txt` (scikit-image, scipy) and `requirements-sprite-ml.txt` (mediapipe, rembg[cpu]). Obey the 7-day package-age rule at install time. |
| 6 | Undo model: **non-destructive pipeline + snapshot on destructive ops**. | `FrameListSnapshot` stack, depth 50, per action. No command stack. |
| 7 | Content policy: **allow** any source image. | No pre-block. Refusals surface as `SafetyRefusal` errors with a logged, user-facing message. |
| 8 | **No spend confirmation.** Show a cost estimate per sprite (action) and per sheet for the current settings. **Record actual cost per action** in the project ledger, because settings change mid-project. | `CostLedger` in the project; estimate label in the queue panel and in the CLI `--json` payload. |
| 9 | Defaults live in a **Generation Settings dialog** with preset pickers; every field is editable; users **save multiple named configurations**. Cells up to **720×720** must work. **Omni is the default provider.** | `GenerationSettings` + `NamedConfigStore` (JSON under the Settings root). Cell presets include 256, 512, 720, 1024 and a custom W×H. |
| 10 | Intermediates live in a **sibling of the generated folder** (Images group). **Auto-purge after export** is optional, off by default, sticky, and confirmed when enabled. `sprites` joins the **storage-migration journal**. | `DataPaths.sprite_projects()` → `<Images root>/sprites`. `GROUP_CONTENTS[Group.IMAGES]` gains `"sprites"`. |
| — | General note: export **individual frames**, not only animations. Be **flexible in resolutions**; add larger presets for quality sprites. | Per-tag PNG sequence + "Export selected frame" action; custom cell size; presets up to 1024. |

## 1. Architecture

Three new packages mirror the layout feature (`core/layout`, `gui/layout`,
`cli/commands/layout.py`):

```
core/sprite/                 pure Python, no Qt — all logic and all tests
gui/sprite/                  PySide6 tab, panels, dialogs, workers
cli/commands/sprite.py       --sprite-* verbs; stdout stays pure for --json
```

Two generation **routes** feed one **processing spine**. Every stage reads
files from the previous stage and writes files for the next one. Every stage
is re-runnable from cache.

```
character image
   │ normalize (pad, never crop)             core/sprite/source.py
   ├─ chroma plate (Nano Banana edit)         core/sprite/generation/plate.py
   ├─ turnaround pack (front/side/back/¾)     core/sprite/generation/turnaround.py
   ▼
action cards (LLM contract)                   core/sprite/generation/action_cards.py
   │
   ├─ Route A: video clips (Omni default, Veo)  core/sprite/generation/video_route.py
   │     → frame extraction (every-N / fps / exact-N)   core/sprite/extract.py
   └─ Route B: image sheets / edit-chain           core/sprite/generation/image_route.py
         → sheet slicing                          core/sprite/slicing.py
   ▼
 processing spine (per action, cached per stage)  core/sprite/pipeline.py
   extract → key/matte → cleanup → alpha → crop+pad → dejitter
        → profile(hd)   : resize to hd cell, soft alpha
        → profile(pixel): integer downscale, quantize (shared palette), dither
   ▼
 SheetMeta (one source of truth)                  core/sprite/models.py
   ▼
 exporters (pure projections of SheetMeta)        core/sprite/exporters/
   grid PNG · Aseprite JSON · TexturePacker JSON · PNG sequence · GIF
   Godot .tres · native .aseprite · engine presets
```

External inputs enter the spine at two points (gap G9): a video file enters
at *extract*; a PNG sequence or a sprite sheet enters after *extract*.

### 1.1 Threading, progress, and cancellation contract (G2, G3)

`core/sprite/pipeline.py` defines the contract. Everything long-running in
`core/sprite` accepts it. The GUI and the CLI supply it.

```python
class CancelToken:
    """Thread-safe cancel flag. Stages poll it between frames and stages."""
    def __init__(self) -> None: self._event = threading.Event()
    def cancel(self) -> None: self._event.set()
    @property
    def cancelled(self) -> bool: return self._event.is_set()
    def raise_if_cancelled(self) -> None:
        if self.cancelled: raise Cancelled()

class Cancelled(Exception): ...

ProgressFn = Callable[[str, int, int, str], None]
# (stage_name, done, total, message) — done/total may be 0,0 for indeterminate.

def no_progress(stage: str, done: int, total: int, message: str) -> None: ...
```

Rules:

- A stage checks `token.raise_if_cancelled()` at least once per frame.
- The video clients have no abort hook. Sub-project 2 adds an optional
  `cancel_check: Callable[[], bool] | None` parameter to
  `VeoClient._poll_for_completion` and `OmniClient._await_terminal`. When it
  returns `True`, the poll loop stops and the client returns a result with
  `success=False, error="cancelled"`. The provider job keeps running remotely;
  the queue records the operation id so the user can recover the clip later.
- The GUI runs every stage and every generation job in one `SpriteWorker`
  (`QThread`) per job. Signals: `progress(str, int, int, str)`,
  `finished(object)`, `failed(str)`. The worker owns one `CancelToken`; the
  panel's Cancel button calls `token.cancel()`.
- The UI thread never touches PIL or ffmpeg for more than one thumbnail.

### 1.2 Stage cache and invalidation (G1)

Every stage has a **fingerprint** = SHA-1 of (upstream stage fingerprint +
the JSON of that stage's settings + the stage code version constant). A stage
writes to `stages/<action_id>/<stage>/` and records the fingerprint in
`SpriteProject.stage_fingerprints[action_id][stage]`. `Pipeline.run()` walks
the stage list in order; a stage whose recorded fingerprint equals the
computed one and whose output directory exists is skipped. A changed TOL
slider therefore re-runs *key* and everything after it, never *extract*.
Raw clips and extracted frames are never overwritten by a later stage.

### 1.3 Failure handling (G6)

`core/sprite/generation/errors.py`:

```python
class SpriteGenerationError(Exception):
    user_message: str      # shown in the UI / CLI; always logged
    retryable: bool = False
class SafetyRefusal(SpriteGenerationError): ...        # RAI / person_generation
class QuotaExceeded(SpriteGenerationError): retryable = True   # 429 / RESOURCE_EXHAUSTED
class ProviderError(SpriteGenerationError): ...
class Cancelled(Exception): ...                         # from pipeline.py
```

`classify_provider_error(exc) -> SpriteGenerationError` maps provider
exceptions by message/status. The queue retries `retryable` errors with
exponential backoff (2 s, 4 s, 8 s; 3 tries), then marks the card `failed`
with `user_message`. A `SafetyRefusal` is never retried; its message names
the other provider as an option. Every failure is logged with the full
request (provider, model, params, prompt) and the full error text, per
AGENTS.md.

### 1.4 Undo (G4)

`core/sprite/undo.py`:

```python
@dataclass(frozen=True)
class FrameListSnapshot:
    action_id: str
    frames: Tuple[FrameMeta, ...]      # deep copy of the action's frame list
    label: str                         # "delete frame 3", "reorder", "retouch 5"

class SnapshotStack:
    def __init__(self, depth: int = 50): ...
    def push(self, snap: FrameListSnapshot) -> None
    def undo(self, current: FrameListSnapshot) -> Optional[FrameListSnapshot]
    def redo(self) -> Optional[FrameListSnapshot]
    @property
    def can_undo(self) -> bool
    @property
    def can_redo(self) -> bool
```

Destructive frame-list operations (delete, reorder, duplicate, insert,
duration edit, retouch, per-frame override edit) push a snapshot first.
Retouch writes a new file `NNNN.r<k>.png` beside the original and repoints
`FrameMeta.source_path`, so undo is a pointer swap and never deletes a file.
Pipeline re-runs are non-destructive by §1.2 and do not enter the stack.

### 1.5 Keyboard shortcuts (G5)

| Key | Action | Where |
|---|---|---|
| Space | Play / pause | preview player |
| `,` / `.` | Previous / next frame | preview + strip |
| Home / End | First / last frame | preview + strip |
| Ctrl+Enter | Primary action (Generate selected / Run pipeline / Export) | every panel & dialog (`bind_primary_action`) |
| Escape | Close dialog | dialogs (`DialogCleanupMixin`) |
| Delete | Delete selected frame(s) | strip |
| Ctrl+D | Duplicate frame | strip |
| Ctrl+Z / Ctrl+Y | Undo / redo | tab |
| `+` / `-` / Ctrl+0 | Zoom in / out / 100 % | pixel view |
| G | Toggle pixel grid | pixel view |
| L | Cycle loop mode (forward → reverse → ping-pong) | preview |

### 1.6 Storage (decision 10)

```
<Images root>/sprites/<project-slug>/
  project.iasprite.json
  source/character.png (+ .json)  plate.png (+ .json)  turnaround/<view>.png (+ .json)
  clips/<action_id>.mp4 (+ .json sidecar: provider, model, params, prompt, cost)
  stages/<action_id>/extracted/0001.png …
  stages/<action_id>/keyed/ … cleaned/ … cells/ … hd/ … pixel/ …
  exports/<profile>/<engine-preset>/<files>
  configs are NOT here — see NamedConfigStore
```

- `DataPaths.sprite_projects()` returns `self.root(Group.IMAGES) / "sprites"`.
- `GROUP_CONTENTS[Group.IMAGES]` gains `"sprites"`; a test in
  `tests/migration/` pins it.
- Named generation configurations: `<Settings root>/sprite_configs.json`
  via `DataPaths.sprite_configs()`; add `"sprite_configs.json"` to
  `SETTINGS_FILES`.
- Purge: `SpriteProject.purge_intermediates()` deletes `stages/` and
  `clips/` after an export **only when** the sticky preference
  `sprite/purge_after_export` (QSettings, default `False`) is on. Enabling it
  shows a confirmation that names what gets deleted. Deleted files go through
  `core/recycle_bin.py`.
- `SpriteProject.load()` calls `reanchor_media_paths()` the way `VideoProject`
  does, so a moved storage root does not orphan clips.

### 1.7 Dependencies

| Dependency | Status | Used by |
|---|---|---|
| Pillow, numpy, opencv-python | present | everything |
| ffmpeg via `core/video/ffmpeg_utils.py` | present | extraction, chroma preview |
| scikit-image, scipy | **new, hard** (`requirements.txt`) | de-jitter (`phase_cross_correlation`); OpenCV `phaseCorrelate` fallback on ImportError |
| mediapipe | **new optional extra** (`requirements-sprite-ml.txt`) | ML background removal, zero-download path |
| rembg[cpu] | **new optional extra** (same file), Python ≥ 3.11 | ML background removal; default model `isnet-anime`; `bria-rmbg` listed as non-commercial and never default |
| litellm | present | action cards |

Never a hard dependency: libimagequant/imagequant (GPL), CorridorKey,
bria-rmbg weights, LPC assets. Code review checks this.

## 2. Data model (`core/sprite/models.py`)

Stdlib dataclasses only. Every exporter is a pure function of `SheetMeta`.

```python
Rect = Tuple[int, int, int, int]       # x, y, w, h
Size = Tuple[int, int]                 # w, h

@dataclass
class FrameMeta:
    name: str                          # "hero_walk_03"
    source_path: Optional[Path]        # per-frame PNG (RGBA) on disk
    frame: Rect                        # cell rect on the sheet (filled by grid exporter)
    rotated: bool = False              # always False (rotation OFF by default)
    trimmed: bool = False
    sprite_source_size: Rect = (0, 0, 0, 0)   # offset+size inside the untrimmed cell
    source_size: Size = (0, 0)         # untrimmed cell size
    duration_ms: int = 100
    pivot: Tuple[float, float] = (0.5, 1.0)   # normalized; bottom-center default
    overrides: Dict[str, Any] = field(default_factory=dict)  # per-frame processing overrides

@dataclass
class TagMeta:
    name: str                          # snake_case action name
    from_index: int
    to_index: int
    direction: str = "forward"         # forward | reverse | pingpong | pingpong_reverse
    repeat: int = 0                    # 0 = loop forever
    fps_hint: Optional[int] = None

@dataclass
class SheetMeta:
    title: str
    frames: List[FrameMeta]
    tags: List[TagMeta]
    sheet_size: Size = (0, 0)
    cell_size: Size = (64, 64)
    scale: float = 1.0
    palette: Optional[List[str]] = None   # "#RRGGBB" list when quantized
    profile: str = "hd"                   # "hd" | "pixel"
    app: str = "ImageAI"
    version: str = VERSION                # core.constants.VERSION
    def to_dict(self) -> dict / from_dict(cls, d) -> "SheetMeta"
    def frames_for(self, tag: TagMeta) -> List[FrameMeta]
```

`core/sprite/project.py`:

```python
@dataclass
class GenerationSettings:
    provider: str = "omni"             # "omni" | "veo"
    model: str = ""                    # resolved at runtime; "" = provider default
    resolution: str = "720p"
    aspect_ratio: str = "16:9"
    duration_s: int = 8
    fps: int = 24
    loop_conditioning: bool = True     # Veo FIRST&LAST; ignored by Omni
    plate_color: str = "#00FF00"
    use_turnaround_refs: bool = True
    include_audio: bool = False        # Veo only; halves the price
    config_name: str = "Default"

@dataclass
class ExtractionSettings:
    mode: str = "every_n"              # every_n | target_fps | exact_n
    every_n: int = 8
    target_fps: int = 12
    exact_n: int = 8
    trim_start_s: float = 0.0
    trim_end_s: float = 0.0
    cull_duplicates: bool = False
    duplicate_threshold: float = 0.02  # mean abs diff, 0..1

@dataclass
class KeySettings:
    method: str = "chroma"             # chroma | ml | none (source already has alpha)
    key_color: Optional[str] = None    # None → plate_color
    tolerance: float = 0.20            # fully keyed distance (Cr,Cb plane, 0..1)
    softness: float = 0.10             # ramp width
    despill: str = "average"           # none | average | double | limit
    edge_decontaminate: bool = True
    choke_px: int = 0
    feather_px: int = 0
    despeckle_px: int = 0
    ml_backend: str = "mediapipe"      # mediapipe | rembg
    ml_model: str = "isnet-anime"
    ml_refine_edges: bool = False

@dataclass
class StabilizeSettings:
    anchor: str = "bottom_center"      # bottom_center | center | top_left …
    dejitter: bool = True
    dejitter_method: str = "phase"     # phase | centroid
    pad_px: int = 0

@dataclass
class OutputProfile:
    name: str                          # "hd" | "pixel"
    enabled: bool = True
    cell_size: Size = (64, 64)
    binary_alpha: bool = False         # pixel: True
    alpha_threshold: int = 128
    defringe_px: int = 0
    palette_size: Optional[int] = None # pixel: 32; None = no quantize
    dither: str = "none"               # none | bayer2 | bayer4 | bayer8 | floyd
    palette_lock: bool = True
    locked_palette: Optional[List[str]] = None

@dataclass
class ActionCard:
    id: str                            # uuid4 hex
    name: str                          # snake_case, unique per project
    prompt: str
    duration_s: int = 8
    loop: bool = True
    target_frames: int = 8
    fps: int = 12
    status: str = "draft"              # draft | queued | rendering | rendered | failed | processed
    error: Optional[str] = None
    clip: Optional["ClipRecord"] = None
    frames: List[FrameMeta] = field(default_factory=list)

@dataclass
class ClipRecord:
    path: Path
    provider: str
    model: str
    operation_id: Optional[str]        # Veo op id / Omni interaction id
    params: Dict[str, Any]
    prompt: str
    generated_at: str                  # ISO-8601
    estimated_usd: Optional[float]
    actual_usd: Optional[float]

@dataclass
class CostEntry:
    action_id: str
    action_name: str
    provider: str
    model: str
    seconds: float
    estimated_usd: Optional[float]
    actual_usd: Optional[float]
    timestamp: str
    note: str = ""

@dataclass
class SpriteProject:
    name: str
    project_dir: Optional[Path]
    character_source: Optional[Path]
    plate_path: Optional[Path]
    plate_color: str = "#00FF00"
    turnaround: Dict[str, Path]        # "front" | "side" | "back" | "three_quarter"
    brief: str = ""
    genre_preset: str = "sidescroller"
    actions: List[ActionCard]
    generation: GenerationSettings
    extraction: ExtractionSettings
    key: KeySettings
    stabilize: StabilizeSettings
    profiles: List[OutputProfile]      # [hd, pixel]
    stage_fingerprints: Dict[str, Dict[str, str]]
    cost_ledger: List[CostEntry]
    created: str; modified: str
    def save(self, path=None) -> Path
    @classmethod def load(cls, path) -> "SpriteProject"
    def reanchor_media_paths(self) -> int
    def sheet_meta(self, profile: str) -> SheetMeta
    def total_cost(self) -> Tuple[float, float]       # (estimated, actual)
    def purge_intermediates(self) -> int
```

Cell-size presets (`core/sprite/presets.py`): 8, 16, 16×24, 24, 16×32, 32,
48 (RPG Maker), 64 (default), 96, 128, 256, 512, 720, 1024, custom. Canvas
presets: 320×180, 384×216, 400×240, 480×270, 640×360 with an integer-scale
calculator to 720p/1080p/4K. FPS presets: 8 ("on threes"), 12 ("on twos",
default), 24, 30, 60. Genre presets for action cards: sidescroller, top-down,
fighting.

## 3. Sub-projects (plan files)

One branch `feat/sprite-tab`, cut from `origin/main` plus the research commit
`572d246` (cherry-picked). Commits land per task. **One PR** after
sub-project 7, per the house rule and the comic-layout precedent. Each
sub-project produces working, tested software on its own.

| # | Sub-project | Plan file | Features |
|---|---|---|---|
| 1 | **Core spine** | `2026-08-29-sprite-core-spine-plan.md` | frame-metadata-model, sprite-project-persistence (+paths, migration journal), sprite-size-presets, frame-extractor (+exact-N), sheet-import-slicing, autocrop-stabilize, pipeline stage cache (G1), cancel/progress contract (G2, G3), external video/PNG import (G9), grid-sheet-export, aseprite-json-export, texturepacker-json-export, per-tag-png-export, gif-export, HD profile (G17), testing strategy (G16) |
| 2 | **Video generation route** | `2026-08-29-sprite-video-route-plan.md` | character-source-import, chroma-plate-prep, chroma-prompt-injection, character-turnaround-pack, action-card-generator, clip-timing-hints, video-route-rendering, loop-closure-conditioning, omni-conversational-refine, batch-queue-cost-estimator, cost price source + ledger (G12), failure handling (G6), client cancel hooks (G2) |
| 3 | **Keying & cleanup** | `2026-08-29-sprite-keying-plan.md` | chroma-keyer, despill-edge-cleanup, binary-alpha-threshold, ml-background-removal, frame-dejitter, per-frame overrides |
| 4 | **Pixel-art profile** | `2026-08-29-sprite-pixel-art-plan.md` | fit-pad-integer-downscale (+ source-resolution check), shared-palette-quantization (+ lock/remap), dither-selector |
| 5a | **GUI: tab skeleton, intake, generation** | `2026-08-29-sprite-gui-a-plan.md` | SpriteTab lazy load, character panel, action-cards panel, generation settings dialog + named configs, queue panel with DialogStatusConsole + cost labels, SpriteWorker, send-to-sprite, purge preference |
| 5b | **GUI: frames, preview, processing, export** | `2026-08-29-sprite-gui-b-plan.md` | frame-strip-manager, animation-preview-player (+ loop-seam meter), pixel-zoom-view, processing panel (key / cleanup / stabilize / profiles), export dialog, shortcuts (G5), undo (G4) |
| 6 | **Image route, retouch, engine exports** | `2026-08-29-sprite-image-route-exports-plan.md` | image-route-frame-generation (sheet + edit-chain + difference matting), ai-frame-retouch, godot-tres-export, engine-preset-picker, native-aseprite-writer |
| 7 | **CLI + docs + release** | `2026-08-29-sprite-cli-release-plan.md` | sprite-cli, `Docs/Sprite-Tab-Guide.md`, `imageai-cli` skill update, README Python line, CodeMap, version bump + changelog, PR |

Dependency order: 1 → 2 → 3 → 4 → 5a → 5b → 6 → 7. Sub-projects 3 and 4
depend only on 1 and can run in parallel with 2.

## 4. Sub-project details

### 4.1 Core spine

**`core/sprite/extract.py`**

```python
@dataclass
class ExtractResult:
    frames: List[Path]; source_fps: float; source_frames: int; duration_s: float

def probe_video(path: Path) -> Dict[str, Any]           # ffprobe json: fps, nb_frames, duration, w, h
def extract_frames(video: Path, out_dir: Path, settings: ExtractionSettings,
                   *, progress: ProgressFn = no_progress,
                   token: Optional[CancelToken] = None) -> ExtractResult
def estimate_frame_count(probe: Dict[str, Any], settings: ExtractionSettings) -> int
def cull_duplicates(frames: List[Path], threshold: float) -> List[Path]
```

ffmpeg filters: `every_n` → `select='not(mod(n\,N))'` with `-fps_mode vfr`;
`target_fps` → `fps=F`; `exact_n` → extract at source fps into a temp dir,
then pick N indices `round(i * (count-1) / (N-1))`. Trim via `-ss`/`-to`.
Output `%04d.png`. Runs `subprocess.run` with `get_ffmpeg_path()`; raises
`FFmpegError(user_message)` with stderr tail on failure.

**`core/sprite/slicing.py`**

```python
@dataclass
class GridGuess: columns: int; rows: int; cell: Size; confidence: float
def guess_grid(sheet: Image.Image, key_color: Optional[str] = None) -> GridGuess
def slice_sheet(sheet: Path, out_dir: Path, columns: int, rows: int,
                cell: Optional[Size] = None, margin: int = 0, spacing: int = 0) -> List[Path]
def import_png_sequence(paths: Sequence[Path], out_dir: Path) -> List[Path]   # copies + renumbers
```

`guess_grid` projects the non-background mask onto both axes and finds
periodic gaps; confidence < 0.6 means "ask the user".

**`core/sprite/stabilize.py`**

```python
def union_alpha_bbox(frames: Sequence[Path]) -> Rect
def solid_border_bbox(frames: Sequence[Path], variance: float = 5.0) -> Rect   # pre-key path
def crop_and_pad(frames: Sequence[Path], out_dir: Path, bbox: Rect, cell: Size,
                 anchor: str = "bottom_center", pad_px: int = 0,
                 *, progress=no_progress, token=None) -> List[Path]
```

`crop_and_pad` scales the crop **proportionally** into `cell` (never
distorts), with `Image.LANCZOS` for the hd profile; the pixel profile uses
`pixelart.fit_pad_integer` instead (sub-project 4). Anchors: bottom_center,
center, top_left, top_center, bottom_left.

**`core/sprite/pipeline.py`** — stage graph (§1.1, §1.2).

```python
STAGES = ("extract", "key", "cleanup", "alpha", "stabilize", "hd", "pixel")
STAGE_CODE_VERSION = {"extract": 1, "key": 1, ...}
def stage_fingerprint(project, action, stage) -> str
def run_pipeline(project: SpriteProject, action: ActionCard, *, upto: str = "pixel",
                 progress: ProgressFn = no_progress, token: Optional[CancelToken] = None,
                 force: bool = False) -> Dict[str, List[Path]]      # stage → output frames
def stage_dir(project, action, stage) -> Path
```

Sub-project 1 ships `extract` and `stabilize` and the two profile stages
with pass-through resize; `key`/`cleanup`/`alpha` are identity stages until
sub-project 3 fills them; `pixel` is identity until sub-project 4.

**`core/sprite/exporters/`** — every function takes a `SheetMeta` whose
frames point at per-frame PNGs, and writes files. Signatures:

```python
# grid.py
@dataclass
class GridOptions:
    columns: int = 0            # 0 = one row per tag
    border_px: int = 0; shape_px: int = 1; inner_px: int = 0
    extrude_px: int = 0; power_of_two: bool = False
    scales: Tuple[int, ...] = (1,)          # (1, 2, 4) → @2x/@4x nearest copies
def export_grid(meta: SheetMeta, out_png: Path, opts: GridOptions) -> SheetMeta   # returns meta with frame rects filled
# aseprite_json.py
def export_aseprite_json(meta: SheetMeta, out_json: Path, *, image_name: str, layout: str = "hash") -> None  # hash | array
# texturepacker_json.py
def export_texturepacker_json(meta: SheetMeta, out_json: Path, *, image_name: str, layout: str = "hash") -> None  # + "animations"
# png_sequence.py
def export_png_sequence(meta: SheetMeta, out_dir: Path, template: str = "{title}_{tag}_{frame01}.png") -> List[Path]
def export_single_frame(frame: FrameMeta, out_png: Path) -> Path
# gif.py
def export_gif(meta: SheetMeta, tag: TagMeta, out_gif: Path, *, loop: int = 0) -> Path
```

GIF recipe (regression-tested): frames converted with a reserved transparent
index, `disposal=2`, `optimize=False`, `transparency=<index>`, per-frame
`duration` list clamped to ≥ 20 ms with a returned warning list.

**Grid export always writes an Aseprite JSON sidecar** next to the PNG, so a
grid-only consumer still gets timing (gap 18).

**Tests (G16):** `tests/sprite/` with synthetic frames generated by numpy
(no binary fixtures larger than 4 KB). Golden files under
`tests/sprite/golden/`: `aseprite_hash.json`, `aseprite_array.json`,
`texturepacker_hash.json`, `godot.tres` (sub-project 6). ffmpeg tests use
`pytest.mark.skipif(not is_ffmpeg_available())`. GUI smoke tests construct
each widget under `qapp` (offscreen).

### 4.2 Video generation route

**`core/sprite/source.py`**

```python
@dataclass
class SourceAnalysis: has_alpha: bool; border_color: Optional[str]; border_uniform: bool; size: Size
def normalize_source(image: Path, out_png: Path, aspect_ratio: str = "16:9") -> Path   # pad on transparent canvas via apply_transparent_canvas_fix
def analyze_source(image: Path) -> SourceAnalysis
```

**`core/sprite/generation/prompts.py`** (chroma-prompt-injection)

```python
CHROMA_SUFFIX = ("solid chroma {color_name} background {hex}, flat even lighting, "
                 "no shadows on the background, no camera movement, character stays centered")
LOOP_SUFFIX = "seamless loop, ends in the same pose it starts"
FORBIDDEN_WORDS = ("transparent", "checkerboard", "alpha")
def inject_chroma(prompt: str, plate_color: str, *, loop: bool) -> str
def color_name(hex_color: str) -> str
```

`inject_chroma` strips forbidden words, appends the suffixes, and never puts
an aspect ratio or pixel size in the text.

**`core/sprite/generation/plate.py`** (chroma-plate-prep)

```python
def make_chroma_plate(provider: ImageProvider, character: Path, out_png: Path,
                      plate_color: str = "#00FF00", *, model: Optional[str] = None,
                      log: Callable[[str], None] = logger.info) -> Path
```

Calls `GoogleProvider.edit_image(image, prompt, model, aspect_ratio=...)`.
Prompt: "Place this exact character on a flat solid {color_name} background
{hex}. Remove all shadows and reflections. Do not change the character."
Writes the sidecar with `plate_color`.

**`core/sprite/generation/turnaround.py`**

```python
VIEWS = ("front", "side", "back", "three_quarter")
def generate_turnaround(provider, character: Path, out_dir: Path, views=VIEWS,
                        *, plate_color: str, do_not_change: Sequence[str] = ("face", "hair", "proportions", "outfit"),
                        model=None, log=logger.info, token=None) -> Dict[str, Path]
```

**`core/sprite/generation/action_cards.py`** — LLM contract
"Sprite Action Cards — Strict v1.0" (per `Docs/LLM-Contracts.md`).

```python
@dataclass
class ActionCardDraft: name: str; prompt: str; duration_s: int; loop: bool; target_frames: int; fps: int
GENRE_CHECKLISTS = {"sidescroller": ["idle", "walk", "run", "jump", "fall", "attack", "hurt", "death"], "top_down": [...], "fighting": [...]}
def build_messages(brief: str, genre: str, plate_color: str, character_notes: str) -> List[Dict[str, str]]
def parse_action_cards(text: str) -> List[ActionCardDraft]       # tolerant of fences; validates snake_case, 1..15 s
def generate_action_cards(brief, genre, *, provider, model, api_key, plate_color,
                          completion_fn=None, log=logger.info) -> List[ActionCardDraft]
```

`completion_fn` defaults to `litellm.completion` with kwargs from
`core.llm_params.build_completion_kwargs`. The model comes from
`resolve_model(provider, "chat")`. Request and response are logged in full.

**`core/sprite/timing.py`** (clip-timing-hints)

```python
def loop_seconds(target_frames: int, fps: int) -> float
def suggest_clip_duration(target_frames: int, fps: int, provider: str, model: str) -> int   # snaps to provider's legal durations, ≥ 2 loops
def frames_per_clip(duration_s: float, source_fps: float, settings: ExtractionSettings) -> int
def ms_to_fps(durations_ms: Sequence[int]) -> Tuple[int, List[float]]   # GCD-based: fps + per-frame multipliers; drift reported
```

**`core/sprite/generation/video_route.py`**

```python
@dataclass
class RenderRequest: action: ActionCard; plate: Path; refs: List[Path]; settings: GenerationSettings; out_mp4: Path
def build_omni_config(req: RenderRequest) -> OmniGenerationConfig
def build_veo_config(req: RenderRequest) -> VeoGenerationConfig       # loop_conditioning → image=plate, last_frame=plate; duration snapped
def render_action(req: RenderRequest, *, api_key: str, auth_mode: str = "api-key",
                  progress=no_progress, token=None, log=logger.info) -> ClipRecord
def refine_action(clip: ClipRecord, instruction: str, out_mp4: Path, *, api_key, log) -> ClipRecord   # Omni previous_interaction_id
def trim_to_loop(clip: Path, out_mp4: Path, *, seam_threshold: float = 0.08) -> Tuple[Path, float]   # tail-trim fallback; returns seam score
```

Veo `last_frame` with a same-image loop only works at 8 s; `build_veo_config`
forces `duration=8` when `loop_conditioning` is on and logs the reason.

**`core/sprite/generation/cost.py`** (G12)

```python
PRICE_TABLE_VERIFIED = "YYYY-MM-DD"    # the implementer sets the date they verified the rates
def price_per_second(provider: str, model: str, *, include_audio: bool) -> Optional[float]   # None = unknown
def estimate_action(settings: GenerationSettings, action: ActionCard) -> Optional[float]
def estimate_project(project: SpriteProject) -> Tuple[Optional[float], int]   # (usd, unknown_count)
def record_actual(project, action, usd: Optional[float], note="") -> CostEntry
```

Veo rates reuse `VeoClient.estimate_cost`. The Omni rate is a module constant
the implementer verifies against the Google pricing page on the day of
implementation and records in `PRICE_TABLE_VERIFIED`; when no verified rate
exists the estimator returns `None` and the UI shows "unknown", never a
guess. A config override `sprite.price_overrides` (config.json) lets the user
correct rates without a release.

**`core/sprite/generation/queue.py`**

```python
class ActionQueue:
    def __init__(self, project: SpriteProject, *, api_key: str, auth_mode: str,
                 progress: ProgressFn = no_progress, token: Optional[CancelToken] = None,
                 log: Callable[[str], None] = logger.info, max_concurrent: int = 1): ...
    def enqueue(self, action_ids: Sequence[str]) -> None
    def run(self) -> Dict[str, ClipRecord | SpriteGenerationError]   # sequential by default; honors token between and inside jobs
    def retry(self, action_id: str) -> None
```

The queue runs `render_action` per card, then `run_pipeline(upto="stabilize")`
so frames appear as soon as a clip lands. It writes `CostEntry` rows.

### 4.3 Keying & cleanup (`core/sprite/keying.py`, `core/sprite/matting.py`)

```python
# keying.py — numpy/OpenCV only
def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]
def chroma_alpha(rgb: np.ndarray, key_rgb: Tuple[int, int, int], tolerance: float, softness: float) -> np.ndarray   # float32 0..1 from (Cr,Cb) distance
def despill(rgb: np.ndarray, key_rgb, mode: str) -> np.ndarray             # average | double | limit; luminance restored
def decontaminate_edges(rgb: np.ndarray, alpha: np.ndarray, key_rgb) -> np.ndarray   # F = (C − (1−α)K) / α
def choke_feather(alpha: np.ndarray, choke_px: int, feather_px: int, despeckle_px: int) -> np.ndarray
def binary_alpha(alpha: np.ndarray, threshold: int = 128, defringe_px: int = 0) -> np.ndarray
def key_frame(image: Image.Image, settings: KeySettings, overrides: Dict[str, Any]) -> Image.Image   # RGBA
def ffmpeg_chromakey_preview(video: Path, out_mp4: Path, key_color: str, similarity: float, blend: float) -> Path
def pick_key_color(image: Image.Image, xy: Tuple[int, int], radius: int = 2) -> str

# matting.py
def available_backends() -> Dict[str, bool]                     # {"mediapipe": bool, "rembg": bool}
def ml_alpha(image: Image.Image, backend: str, model: str, *, refine_edges: bool) -> np.ndarray
REMBG_MODELS = {"isnet-anime": {"size_mb": 168, "license": "MIT"}, "u2netp": {"size_mb": 4.4, "license": "Apache-2.0"},
                "bria-rmbg": {"size_mb": 1000, "license": "CC BY-NC (paid commercial)", "default_ok": False}}
def rembg_model_dir() -> Path                                   # get_data_paths().model_cache("rembg")
def difference_matte(on_white: Image.Image, on_black: Image.Image) -> Image.Image   # image route
```

`stabilize.py` gains `dejitter(frames, out_dir, method)` using
`skimage.registration.phase_cross_correlation(upsample_factor=10)` on the
alpha masks, falling back to `cv2.phaseCorrelate`, then `centroid`.

### 4.4 Pixel-art profile (`core/sprite/pixelart.py`)

```python
def integer_fit_scale(src: Size, cell: Size) -> int                         # largest integer downscale that fits; 1 if src ≤ cell
def fit_pad_integer(image: Image.Image, cell: Size, anchor: str) -> Image.Image   # box filter downscale, then pad on transparent canvas
def resolution_check(src: Size, cell: Size) -> Optional[str]                # warning text when src < cell (needs upscale) 
def build_shared_palette(frames: Sequence[Image.Image], colors: int) -> List[str]   # MEDIANCUT on flattened RGB of the union
def quantize_to_palette(image: Image.Image, palette: Sequence[str], dither: str) -> Image.Image   # alpha carried separately
def bayer_matrix(n: int) -> np.ndarray                                       # 2, 4, 8
```

Palette lock: when `OutputProfile.palette_lock` is on and
`locked_palette` exists, new frames map to it (Aseprite "Remap"); the
palette rebuilds only on an explicit "Rebuild palette" action.

### 4.5 GUI (`gui/sprite/`)

```
sprite_tab.py            SpriteTab(QWidget): splitter [left: character + actions + queue] [right: strip + preview + processing]; status console at the bottom
character_panel.py       import / drag-drop, normalize, "Make chroma plate", "Generate turnaround", key-color picker
action_cards_panel.py    brief + genre + "Generate cards"; editable card list (name, prompt, duration, loop, frames, fps); per-card Render / Refine / Re-render
generation_settings_dialog.py  provider/model/resolution/duration/aspect/fps/loop/plate color; named configs (save/load/delete); cost preview line
queue_panel.py           cards with status + cost estimate per action + sheet total; Cancel; retry; DialogStatusConsole
frame_strip.py           QListWidget icon mode; drag reorder; duplicate/delete/insert; duration spin; per-frame overrides; snapshot on every destructive op
preview_player.py        QTimer + QPixmap; per-frame ms; forward/reverse/pingpong; tag combo; scrub; loop-seam meter (mean abs diff last-vs-first, 0..1)
pixel_view.py            QGraphicsView, Qt.FastTransformation, integer zoom 1–16×, pixel grid, checkerboard
processing_panel.py      key / cleanup / alpha / stabilize / profile groups; "Run pipeline" (Ctrl+Enter); live re-run of changed stages
export_dialog.py         profile × engine preset × formats; output dir; "Export selected frame"; purge-after-export checkbox (sticky, confirmed)
workers.py               SpriteWorker(QThread) — §1.1 signals; one CancelToken per worker
shortcuts.py             install_shortcuts(tab) — §1.5 table
```

Main-window wiring: `SpriteTab` lazy-loads on first activation like the
Video tab (placeholder tab replaced on `currentChanged`). "Send to Sprite"
appears on the Image tab result context menu, the History tab context menu,
and the Video reference library; each emits `sendToSpriteRequested(Path)`
which `MainWindow._on_send_to_sprite` routes to
`SpriteTab.set_character_source(path)`.

### 4.6 Image route, retouch, engine exports

**`core/sprite/generation/image_route.py`**

```python
def sheet_prompt(action: ActionCard, frames: int, plate_color: str) -> str      # "6-frame side-view walk cycle, horizontal sprite sheet, …"
def generate_sheet(provider, character: Path, action, out_png: Path, *, frames: int, plate_color, model=None, log) -> Path
def edit_chain(provider, character: Path, action, out_dir: Path, *, frames: int, pose_instructions: Sequence[str], plate_color, model=None, log, token=None) -> List[Path]
def generate_pose_instructions(action, frames, *, completion_fn, ...) -> List[str]   # LLM contract "Sprite Pose Steps — Strict v1.0"
```

`edit_chain` uses `GoogleProvider.start_edit_session` + `edit_image` per
step (frame k is an edit of frame k−1). gpt-image models go through
`OpenAIProvider.edit_image` with the previous frame as the reference.

**`core/sprite/generation/retouch.py`**

```python
def retouch_frame(provider, frame: Path, instruction: str, out_png: Path, *, neighbors: Sequence[Path], region: Optional[Rect] = None, model=None, log) -> Path
```

Gemini → `edit_image_region` when `region` is given, else `edit_image` with
neighbors as extra references; OpenAI → `edit_image(mask=...)`.

**`core/sprite/exporters/godot_tres.py`**

```python
def export_godot_tres(meta: SheetMeta, out_tres: Path, *, atlas_res_path: str) -> Path
```

Emits `[gd_resource type="SpriteFrames" load_steps=N format=3]`, one
`AtlasTexture` sub-resource per frame (`region`, `margin` restoring trim),
and `animations` with `speed` from `timing.ms_to_fps`, `loop`, and per-frame
`duration` multipliers.

**`core/sprite/exporters/engine_presets.py`**

```python
@dataclass
class EnginePreset: id: str; label: str; formats: Tuple[str, ...]; grid: GridOptions; pivot: Tuple[float, float]; name_template: str; how_to_import: str
ENGINE_PRESETS: Dict[str, EnginePreset]   # unity, godot4, phaser3, pixijs, unreal, libgdx, rpgmaker_mz, web_preview
def export_with_preset(meta: SheetMeta, preset_id: str, out_dir: Path) -> List[Path]
def fps_reconciliation(meta: SheetMeta, target: str) -> List[str]   # rounding-drift notes for godot / gif
```

**`core/sprite/exporters/aseprite_native.py`**

```python
def export_aseprite(meta: SheetMeta, out_ase: Path) -> Path
```

Header magic `0xA5E0`, frame magic `0xF1FA`; chunks: Layer (0x2004), Cel
(0x2005, type 2 zlib RGBA), Tags (0x2018), Palette (0x2019 when quantized),
Color Profile (0x2007, sRGB). One layer, one cel per frame. Verified by a
byte-level reader test in the suite (`tests/sprite/test_aseprite_native.py`
parses the header and chunk sizes back).

### 4.7 CLI (`cli/commands/sprite.py`)

Argument group `sprite` in `cli/parser.py`:

| Flag | Meaning |
|---|---|
| `--sprite-cards BRIEF` | generate action cards → prints/saves JSON; `--sprite-genre` |
| `--sprite-render PROJECT` | render queued cards (`--sprite-actions a,b`) |
| `--sprite-process PROJECT` | run the pipeline (`--sprite-upto STAGE`, `--force`) |
| `--sprite-import-video PATH` / `--sprite-import-frames DIR` / `--sprite-import-sheet PATH --sprite-grid CxR` | external inputs (G9) |
| `--sprite-export PROJECT --sprite-preset ENGINE --sprite-profile hd\|pixel -o DIR` | export |
| `--sprite-new NAME --sprite-source IMAGE` | create a project |
| `--json` | one JSON object on stdout; humans read stderr |

Dispatch in `cli/runner.py` before the image path, after the video path.
Every output gets a `.json` sidecar. Cost estimate is part of the `--json`
payload for `--sprite-render`.

## 5. Testing strategy (G16)

- `tests/sprite/` mirrors `core/sprite/`; `tests/sprite/gui/` holds
  offscreen smoke tests for every widget and dialog (`qapp` fixture).
- Synthetic inputs: numpy-drawn RGBA frames (a moving square on green);
  a 12-frame synthetic MP4 written by ffmpeg in a session fixture, skipped
  when ffmpeg is unavailable.
- Golden files: `tests/sprite/golden/*.json|*.tres`; tests compare parsed
  structures (JSON) or normalized text (.tres), never raw bytes.
- GIF: write → reload with Pillow → assert `n_frames`, `disposal == 2`,
  transparency index present, durations ≥ 20 ms.
- Provider calls: injected callables / `MagicMock`; live tests marked `live`
  (`IMAGEAI_LIVE_TESTS=1`).
- Migration: `tests/migration/test_data_migration.py` gains
  `"sprites"` ∈ `GROUP_CONTENTS[Group.IMAGES]` and
  `"sprite_configs.json"` ∈ `SETTINGS_FILES`.
- Guard: `tests/test_no_hardcoded_paths.py` stays green — no path is built by
  hand in `core/sprite` or `gui/sprite`.

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Loops that do not close | Veo FIRST&LAST at 8 s; `trim_to_loop` seam search; seam meter in the preview |
| Character drift across clips | Turnaround refs on every render; shared locked palette; per-frame retouch |
| Cost surprises | Estimate per action + sheet before Render; ledger of actual spend; Omni default |
| Refusals on humanoid characters | `SafetyRefusal` with a clear message and a provider switch hint |
| GPL / non-commercial contamination | Never a hard dep; `REMBG_MODELS[...]["default_ok"]`; review checklist item |
| Pillow RGBA quantize trap | Quantize flattened RGB, carry alpha; unit test pins it |
| Transparent-GIF corruption | Tested helper (`disposal=2`, `optimize=False`) with a regression test |
| Qt cannot decode APNG; WebP stutters | Custom QTimer player only; no QMovie |
| Large intermediates | Optional sticky purge-after-export with confirmation; recycle bin |

## 7. Out-of-band follow-ups (not in this feature)

- Update `providers/openai.py` `MODEL_CAPS["gpt-image-2"]["supports_transparent_bg"]`
  once the preview stabilizes (needs alpha-threshold + defringe post-pass).
- Frame interpolation, onion skin, packed atlas, APNG/WebP, palette I/O, and
  the rest of the deselected catalog stay in `catalog.json` for a later pick.
