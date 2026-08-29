"""Sprite pipeline: pure Python, no Qt (design section 1).

Sub-project 1 (core spine) exports the data model, project persistence,
presets, undo, the stage pipeline, extraction, slicing, stabilisation and
the exporters. Later sub-projects add keying, pixel-art, generation, GUI and
CLI on top of this API.
"""

from .models import DIRECTIONS, FrameMeta, Rect, SheetMeta, Size, TagMeta
from .project import (
    PROJECT_FILE_NAME,
    ActionCard,
    ClipRecord,
    CostEntry,
    ExtractionSettings,
    GenerationSettings,
    KeySettings,
    OutputProfile,
    SpriteProject,
    SpriteProjectManager,
    StabilizeSettings,
    default_profiles,
)
from .presets import (
    CANVAS_PRESETS,
    CELL_PRESETS,
    CUSTOM_CELL_LABEL,
    DEFAULT_CELL,
    DEFAULT_FPS,
    DEFAULT_GENRE,
    FPS_PRESETS,
    GENRE_PRESETS,
    TARGET_RESOLUTIONS,
    format_cell_size,
    integer_scale,
    integer_scale_table,
    parse_cell_size,
)
from .undo import FrameListSnapshot, SnapshotStack
from .pipeline import (
    PROFILE_STAGES,
    STAGE_CODE_VERSION,
    STAGE_RUNNERS,
    STAGE_SETTINGS,
    STAGES,
    UPSTREAM,
    CancelToken,
    Cancelled,
    PipelineError,
    ProgressFn,
    SettingsFn,
    StageRunner,
    identity_runner,
    is_stage_current,
    list_frames,
    no_progress,
    record_fingerprint,
    register_external_frames,
    register_stage,
    run_pipeline,
    stage_dir,
    stage_fingerprint,
    stage_settings,
)
from .extract import ExtractResult, FFmpegError, cull_duplicates, estimate_frame_count, extract_frames, probe_video
from .slicing import GridGuess, foreground_mask, guess_grid, import_png_sequence, slice_sheet
from .stabilize import (
    ANCHORS,
    anchor_offset,
    crop_and_pad,
    fit_size,
    has_transparency,
    solid_border_bbox,
    union_alpha_bbox,
)
from .exporters import (
    GridOptions,
    export_aseprite_json,
    export_gif,
    export_grid,
    export_png_sequence,
    export_single_frame,
    export_texturepacker_json,
)

__all__ = [
    # models
    "DIRECTIONS", "FrameMeta", "Rect", "SheetMeta", "Size", "TagMeta",
    # project
    "PROJECT_FILE_NAME", "ActionCard", "ClipRecord", "CostEntry", "ExtractionSettings",
    "GenerationSettings", "KeySettings", "OutputProfile", "SpriteProject",
    "SpriteProjectManager", "StabilizeSettings", "default_profiles",
    # presets
    "CANVAS_PRESETS", "CELL_PRESETS", "CUSTOM_CELL_LABEL", "DEFAULT_CELL", "DEFAULT_FPS",
    "DEFAULT_GENRE", "FPS_PRESETS", "GENRE_PRESETS", "TARGET_RESOLUTIONS", "format_cell_size",
    "integer_scale", "integer_scale_table", "parse_cell_size",
    # undo
    "FrameListSnapshot", "SnapshotStack",
    # pipeline
    "PROFILE_STAGES", "STAGE_CODE_VERSION", "STAGE_RUNNERS", "STAGE_SETTINGS", "STAGES",
    "UPSTREAM", "CancelToken", "Cancelled", "PipelineError", "ProgressFn", "SettingsFn",
    "StageRunner", "identity_runner", "is_stage_current", "list_frames", "no_progress",
    "record_fingerprint", "register_external_frames", "register_stage", "run_pipeline",
    "stage_dir", "stage_fingerprint", "stage_settings",
    # extract / slicing / stabilize
    "ExtractResult", "FFmpegError", "cull_duplicates", "estimate_frame_count",
    "extract_frames", "probe_video", "GridGuess", "foreground_mask", "guess_grid",
    "import_png_sequence", "slice_sheet", "ANCHORS", "anchor_offset", "crop_and_pad",
    "fit_size", "has_transparency", "solid_border_bbox", "union_alpha_bbox",
    # exporters
    "GridOptions", "export_aseprite_json", "export_gif", "export_grid",
    "export_png_sequence", "export_single_frame", "export_texturepacker_json",
]
