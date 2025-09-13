# ImageAI CodeMap

Last Updated: 2025-09-13 11:07:54

## Quick Navigation
- Main Application: `main.py`
- GUI Launch: `gui/__init__.py`
- CLI Parser: `cli/parser.py`
- CLI Runner: `cli/runner.py`
- Provider Factory: `providers/__init__.py`

## Project Structure

``
ImageAI/
├── Docs/
│   ├── ChatGPT Lyric Generator for aisonggenerator.ai.md  # 153 lines
│   ├── CodeMap.md  # 186 lines
│   ├── CodeMap_Generator.md  # 24 lines
│   └── ProjectReview.md  # 183 lines
├── Notes/
│   ├── Dictation.md  # 0 lines
│   └── Lyric timing success.md  # 30 lines
├── Plans/
│   ├── samples/
│   │   └── mycountry_project/
│   │       ├── assets/
│   │       ├── exports/
│   │       └── logs/
│   ├── ComprehensiveSettings.md  # 560 lines
│   ├── Dall-e-3 Image Continuity.md  # 77 lines
│   ├── Gemini Nano Banana Guide.md  # 107 lines
│   ├── GeminiFullFeatures.md  # 416 lines
│   ├── Generating Continuous Video Scenes from Lyrics for Veo 3-Gemini.md  # 200 lines
│   ├── Generating Continuous Video Scenes from Lyrics for Veo 3-OpenAI.md  # 215 lines
│   ├── GoogleCloudAuth.md  # 76 lines
│   ├── Ideas.md  # 49 lines
│   ├── ImageAI-VideoProject-PRD.md  # 1603 lines
│   ├── Lyrics-TimeSync-Prompt-ASL-Gemini.md  # 103 lines
│   ├── Lyrics-TimeSync-Prompt-ASL-gpt-5.md  # 199 lines
│   ├── NewProviders.md  # 236 lines
│   ├── ProviderIntegration.md  # 229 lines
│   ├── RefactoringPlan.md  # 244 lines
│   ├── Strict-Lyric-Timing-Contract-v1.0.md  # 187 lines
│   ├── Strict-Lyric-Timing-Gemini.md  # 127 lines
│   ├── social-media-image-sizes-2025-table-only-manual.md  # 44 lines
│   └── social-media-image-sizes-2025.md  # 57 lines
├── Sample/
│   └── Veo3_Reference_Workflow_Kit_Full_Grandpa_Was_A_Democrat/
│       ├── Prompts/
│       │   ├── Grandpa_Was_a_Democrat_Image_Prompts.txt  # 336 lines
│       │   └── Grandpa_Was_a_Democrat_Image_Prompts_Details.md  # 330 lines
│       ├── Grandpa Was A Democrat-Lyrics.txt  # 87 lines
│       └── Placement_Guide.md  # 75 lines
├── _screenshots/
├── cli/
│   ├── commands/
│   │   └── __init__.py  # 0 lines
│   ├── __init__.py  # 6 lines
│   ├── parser.py  # 103 lines
│   └── runner.py  # 238 lines
├── core/
│   ├── video/
│   │   ├── renderers/
│   │   │   └── __init__.py  # 0 lines
│   │   ├── __init__.py  # 0 lines
│   │   ├── config.py  # 293 lines
│   │   ├── continuity_helper.py  # 88 lines
│   │   ├── event_store.py  # 516 lines
│   │   ├── ffmpeg_renderer.py  # 568 lines
│   │   ├── image_continuity.py  # 315 lines
│   │   ├── image_generator.py  # 429 lines
│   │   ├── image_processing.py  # 346 lines
│   │   ├── karaoke_renderer.py  # 412 lines
│   │   ├── llm_sync.py  # 416 lines
│   │   ├── llm_sync_v2.py  # 898 lines
│   │   ├── midi_processor.py  # 445 lines
│   │   ├── midi_utils.py  # 34 lines
│   │   ├── project.py  # 451 lines
│   │   ├── project_enhancements.py  # 522 lines
│   │   ├── project_manager.py  # 394 lines
│   │   ├── prompt_engine.py  # 553 lines
│   │   ├── storyboard.py  # 630 lines
│   │   ├── storyboard_v2.py  # 503 lines
│   │   ├── thumbnail_manager.py  # 362 lines
│   │   └── veo_client.py  # 471 lines
│   ├── __init__.py  # 69 lines
│   ├── config.py  # 178 lines
│   ├── constants.py  # 84 lines
│   ├── gcloud_utils.py  # 179 lines
│   ├── logging_config.py  # 168 lines
│   ├── project_tracker.py  # 42 lines
│   ├── security.py  # 283 lines
│   └── utils.py  # 341 lines
├── gui/
│   ├── common/
│   │   ├── __init__.py  # 7 lines
│   │   └── dialog_manager.py  # 205 lines
│   ├── video/
│   │   ├── __init__.py  # 0 lines
│   │   ├── enhanced_workspace.py  # 557 lines
│   │   ├── history_tab.py  # 534 lines
│   │   ├── project_browser.py  # 278 lines
│   │   ├── project_dialog.py  # 452 lines
│   │   ├── video_project_tab.py  # 529 lines
│   │   ├── video_project_tab_old.py  # 955 lines
│   │   └── workspace_widget.py  # 2059 lines
│   ├── __init__.py  # 32 lines
│   ├── dialog_utils.py  # 74 lines
│   ├── dialogs.py  # 195 lines
│   ├── local_sd_widget.py  # 474 lines
│   ├── main_window.py  # 4056 lines
│   ├── model_browser.py  # 443 lines
│   ├── settings_widgets.py  # 1013 lines
│   └── workers.py  # 51 lines
├── providers/
│   ├── video/
│   │   └── __init__.py  # 0 lines
│   ├── __init__.py  # 154 lines
│   ├── base.py  # 145 lines
│   ├── google.py  # 474 lines
│   ├── local_sd.py  # 491 lines
│   ├── model_info.py  # 146 lines
│   ├── openai.py  # 349 lines
│   └── stability.py  # 446 lines
├── templates/
│   ├── video/
│   │   ├── lyric_prompt.j2  # 25 lines
│   │   ├── scene_description.j2  # 42 lines
│   │   └── shot_prompt.j2  # 40 lines
│   └── __init__.py  # 2098 lines
├── tools/
│   └── generate_code_map.py  # 237 lines
├── AGENTS.md  # 46 lines
├── CHANGELOG.md  # 212 lines
├── CLAUDE.md  # 120 lines
├── COMMIT_MESSAGE.txt  # 32 lines
├── GEMINI.md  # 46 lines
├── HF_Auth_UI_Guide.md  # 83 lines
├── HuggingFace_Auth_Guide.md  # 99 lines
├── MIDI_KARAOKE_FEATURES.md  # 170 lines
├── README.md  # 1523 lines
├── REFACTORING_NOTES.md  # 110 lines
├── __init__.py  # 34 lines
├── check_durations.py  # 33 lines
├── download_models.py  # 161 lines
├── main.py  # 72 lines # Main entry point
├── main_original.py  # 2646 lines
├── migrate_config.py  # 179 lines
├── requirements-local-sd.txt  # 15 lines
├── requirements.txt  # 34 lines
├── secure_keys.py  # 106 lines
```

## Core Exports
- ConfigManager (from core.config)
- get_api_key_url (from core.config)
- APP_NAME (from core.constants)
- VERSION (from core.constants)
- __version__ (from core.constants)
- __author__ (from core.constants)
- __email__ (from core.constants)
- __license__ (from core.constants)
- __copyright__ (from core.constants)
- DEFAULT_MODEL (from core.constants)
- DEFAULT_PROVIDER (from core.constants)
- PROVIDER_MODELS (from core.constants)
- PROVIDER_KEY_URLS (from core.constants)
- sanitize_filename (from core.utils)
- read_key_file (from core.utils)
- extract_api_key_help (from core.utils)
- read_readme_text (from core.utils)
- images_output_dir (from core.utils)
- sidecar_path (from core.utils)
- write_image_sidecar (from core.utils)
- read_image_sidecar (from core.utils)
- detect_image_extension (from core.utils)
- sanitize_stub_from_prompt (from core.utils)
- auto_save_images (from core.utils)
- scan_disk_history (from core.utils)
- find_cached_demo (from core.utils)
- default_model_for_provider (from core.utils)

## Module Symbols (Top-Level)
- `gui/__init__.py`
  - functions: launch_gui
- `core/video/midi_utils.py`
  - functions: check_midi_available, get_midi_processor
- `core/project_tracker.py`
  - functions: set_current_project, copy_project_on_exit
- `gui/workers.py`
  - classes: GenWorker
- `gui/dialog_utils.py`
  - functions: show_error, show_warning, show_info, show_question
- `core/video/continuity_helper.py`
  - classes: ContinuityHelper
  - functions: get_continuity_helper
- `cli/parser.py`
  - functions: build_arg_parser
- `providers/base.py`
  - classes: ImageProvider
- `providers/model_info.py`
  - classes: ModelInfo
- `providers/__init__.py`
  - functions: _get_providers, get_provider, list_providers, clear_provider_cache, preload_provider
- `core/logging_config.py`
  - classes: ErrorLogger
  - functions: setup_logging, get_error_report_info
- `core/config.py`
  - classes: ConfigManager
  - functions: get_api_key_url
- `core/gcloud_utils.py`
  - functions: find_gcloud_command, get_gcloud_project_id, check_gcloud_auth_status
- `gui/dialogs.py`
  - classes: ExamplesDialog
- `gui/common/dialog_manager.py`
  - classes: DialogManager
  - functions: get_dialog_manager, set_dialog_manager_parent
- `cli/runner.py`
  - functions: resolve_api_key, store_api_key, run_cli
- `gui/video/project_browser.py`
  - classes: ProjectBrowserDialog
  - functions: get_last_project_path
- `core/security.py`
  - classes: PathValidator, SecureKeyStorage, RateLimiter
- `core/video/config.py`
  - classes: VideoConfig
- `core/video/image_continuity.py`
  - classes: ContinuityMethod, ContinuityContext, ImageContinuityManager
- `core/utils.py`
  - functions: sanitize_filename, read_key_file, read_readme_text, extract_api_key_help, generate_timestamp, format_file_size, parse_image_size, images_output_dir, sidecar_path, write_image_sidecar, read_image_sidecar, detect_image_extension, sanitize_stub_from_prompt, auto_save_images, scan_disk_history, find_cached_demo, default_model_for_provider
- `core/video/image_processing.py`
  - classes: ImageProcessor
- `providers/openai.py`
  - classes: OpenAIProvider
- `core/video/thumbnail_manager.py`
  - classes: ThumbnailManager
- `core/video/project_manager.py`
  - classes: ProjectManager
- `core/video/karaoke_renderer.py`
  - classes: KaraokeConfig, KaraokeRenderer
- `core/video/llm_sync.py`
  - classes: TimedLyric, LLMSyncAssistant
- `core/video/image_generator.py`
  - classes: ImageGenerationResult, ImageGenerator
- `gui/model_browser.py`
  - classes: ModelDownloader, ModelBrowserDialog
- `core/video/midi_processor.py`
  - classes: MidiTimingData, MidiProcessor
- `providers/stability.py`
  - classes: StabilityProvider
- `core/video/project.py`
  - classes: VideoProvider, SceneStatus, AudioTrack, ImageVariant, Scene, VideoProject
- `gui/video/project_dialog.py`
  - classes: NewProjectDialog, OpenProjectDialog, ProjectSettingsDialog
- `core/video/veo_client.py`
  - classes: VeoModel, VeoGenerationConfig, VeoGenerationResult, VeoClient
- `gui/local_sd_widget.py`
  - classes: ModelDownloadThread, LocalSDWidget
- `providers/google.py`
  - classes: GoogleProvider
- `providers/local_sd.py`
  - classes: DeviceManager, LocalSDProvider
- `core/video/storyboard_v2.py`
  - classes: StoryboardApproach, SceneSpec, StyleGuide, EnhancedStoryboardGenerator
- `core/video/event_store.py`
  - classes: EventType, ProjectEvent, EventStore
- `core/video/project_enhancements.py`
  - classes: VersioningMode, CropMode, AudioHandling, CropSettings, KenBurnsSettings, ProjectSettings, ImageVariant, SceneVariants, KenBurnsPresets, EnhancedProjectManager
- `gui/video/video_project_tab.py`
  - classes: VideoGenerationThread, VideoProjectTab
- `gui/video/history_tab.py`
  - classes: HistoryTab
- `core/video/prompt_engine.py`
  - classes: PromptStyle, PromptTemplate, UnifiedLLMProvider, PromptEngine
- `gui/video/enhanced_workspace.py`
  - classes: ImageVariantSelector, CropControlWidget, KenBurnsControlWidget
- `core/video/ffmpeg_renderer.py`
  - classes: RenderSettings, FFmpegRenderer
- `core/video/storyboard.py`
  - classes: InputFormat, ParsedLine, LyricParser, TimingEngine, StoryboardGenerator
- `core/video/llm_sync_v2.py`
  - classes: TimedLyric, LLMSyncAssistant
- `gui/video/video_project_tab_old.py`
  - classes: VideoGenerationThread, VideoProjectTab
- `gui/settings_widgets.py`
  - classes: AspectRatioSelector, ResolutionSelector, QualitySelector, BatchSelector, AdvancedSettingsPanel, CostEstimator
- `gui/video/workspace_widget.py`
  - classes: WorkspaceWidget
- `gui/main_window.py`
  - classes: MainWindow

## Notes
- Refer to this map to quickly locate functions, classes, and modules.
- Line counts approximate; regenerate after refactors.