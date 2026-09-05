# ImageAI CodeMap

Last Updated: 2026-09-05 11:27:46

## Quick Navigation
- Main Application: `main.py`
- GUI Launch: `gui/__init__.py`
- CLI Parser: `cli/parser.py`
- CLI Runner: `cli/runner.py`
- Provider Factory: `providers/__init__.py`

## Project Structure

```text
ImageAI/
├── .superpowers/
│   └── sdd/
│       ├── HANDOFF.md  # 93 lines
│       ├── final-fixes-report.md  # 103 lines
│       ├── implementer-contract.md  # 27 lines
│       ├── phase2-final-fixes-report.md  # 81 lines
│       ├── phase2-task-1-report.md  # 197 lines
│       ├── phase2-task-2-report.md  # 114 lines
│       ├── phase2-task-3-report.md  # 100 lines
│       ├── phase2-task-4-report.md  # 198 lines
│       ├── phase2-task-5-report.md  # 88 lines
│       ├── phase2-task-6-report.md  # 76 lines
│       ├── phase2-task-7-report.md  # 78 lines
│       ├── phase3-final-fixes-report.md  # 120 lines
│       ├── phase3-task-1-report.md  # 153 lines
│       ├── phase3-task-2-report.md  # 84 lines
│       ├── phase3-task-3-report.md  # 69 lines
│       ├── phase3-task-4-report.md  # 183 lines
│       ├── phase3-task-5-report.md  # 91 lines
│       ├── progress-subproject1-complete.md  # 39 lines
│       ├── progress.md  # 38 lines
│       ├── remove-sora-report.md  # 106 lines
│       ├── reviewer-contract.md  # 21 lines
│       ├── task-1-brief.md  # 206 lines
│       ├── task-1-report.md  # 98 lines
│       ├── task-2-brief.md  # 55 lines
│       ├── task-2-report.md  # 104 lines
│       ├── task-3-brief.md  # 93 lines
│       ├── task-3-report.md  # 181 lines
│       ├── task-4-brief.md  # 206 lines
│       ├── task-4-report.md  # 70 lines
│       ├── task-5-brief.md  # 125 lines
│       ├── task-5-report.md  # 159 lines
│       ├── task-6-brief.md  # 116 lines
│       ├── task-6-report.md  # 103 lines
│       ├── task-7-brief.md  # 78 lines
│       ├── task-7-report.md  # 111 lines
│       ├── task-8-brief.md  # 50 lines
│       └── task-8-report.md  # 150 lines
├── Characters/
├── Discord/
│   ├── 2026-06-30-gemini-omni-video.md  # 20 lines
│   ├── 2026-07-01-imageai-cli-and-skill.md  # 23 lines
│   ├── 2026-07-03-fifth-fox-comic.md  # 18 lines
│   └── 2026-09-04-sprite-tab.md  # 25 lines
├── Docs/
│   ├── Features/
│   │   ├── README.md  # 29 lines
│   │   ├── character-animator.md  # 108 lines
│   │   ├── font-generator.md  # 100 lines
│   │   ├── history-settings.md  # 117 lines
│   │   ├── image-generation.md  # 91 lines
│   │   ├── layout-books.md  # 87 lines
│   │   ├── prompt-tools.md  # 101 lines
│   │   ├── reference-images.md  # 82 lines
│   │   ├── site-navigation.md  # 93 lines
│   │   └── video-projects.md  # 130 lines
│   ├── superpowers/
│   │   ├── plans/
│   │   │   └── 2026-04-22-gpt-image-2-integration.md  # 2356 lines
│   │   └── specs/
│   │       └── 2026-04-22-gpt-image-2-integration-design.md  # 245 lines
│   ├── Character-Animator-Guide.md  # 199 lines
│   ├── ChatGPT Lyric Generator for aisonggenerator.ai.md  # 153 lines
│   ├── Claude Desktop Instructions.md  # 361 lines
│   ├── CodeMap.md  # 1234 lines
│   ├── CodeMap_Generator.md  # 24 lines
│   ├── CodeReview-2025-10-19.md  # 169 lines
│   ├── CodeReview-2025-11-14.md  # 499 lines
│   ├── CustomStyles.md  # 214 lines
│   ├── FAQ.md  # 3034 lines
│   ├── Features.md  # 280 lines
│   ├── Font-Generator-Guide.md  # 249 lines
│   ├── Frame-Accurate-Video-Prompt-Transitions.md  # 315 lines
│   ├── GeminiCodeReview_20251113.md  # 70 lines
│   ├── ImageAI-CLI-Guide.md  # 675 lines
│   ├── ImageAI-Installation-Guide.md  # 153 lines
│   ├── ImageAI_Features.md  # 305 lines
│   ├── ImageAI_Social_Media_Post.md  # 122 lines
│   ├── LLM-Contracts.md  # 103 lines
│   ├── LLM-Logging-Full-Content.md  # 136 lines
│   ├── Linux-VM-Setup.md  # 185 lines
│   ├── Operation-Guard-System.md  # 281 lines
│   ├── ProjectReview.md  # 183 lines
│   ├── Reference-Image-Composite-Feature.md  # 190 lines
│   ├── Reference-Image-System.md  # 535 lines
│   ├── Reference-Image-Usage.md  # 207 lines
│   ├── Reference-System-Implementation-Summary.md  # 520 lines
│   ├── Reference-UI-Implementation.md  # 647 lines
│   ├── Scene-Batching-Implementation.md  # 269 lines
│   ├── Sprite-CLI-Guide.md  # 244 lines
│   ├── Storage-Locations-Known-Issues.md  # 172 lines
│   ├── Suno-Package-Support.md  # 333 lines
│   ├── UI-Improvements-TODO.md  # 342 lines
│   ├── Veo-3.1-Batching-Implementation.md  # 227 lines
│   ├── Veo-Wizard-Integration-Guide.md  # 647 lines
│   ├── Veo3-Duration-Update-Summary.md  # 104 lines
│   ├── Veo3-Frame-Continuity-Guide.md  # 871 lines
│   ├── Video-Prompt-Lyrics-Context-Fix.md  # 246 lines
│   ├── Video-Tab-Guide.md  # 1054 lines
│   ├── Wizard-Integration-Steps.md  # 528 lines
│   ├── discord-beta-announcement.md  # 58 lines
│   └── gcloud-install-guide.md  # 592 lines
├── Fonts/
├── Layouts/
├── Notes/
│   ├── PostPrism.ai/
│   │   ├── ImageAI_PostPrism - Transform Audio into Ready-to-Publish Content_files/
│   │   ├── ImageAI_PostPrism_BlogPost.md  # 24 lines
│   │   ├── ImageAI_PostPrism_CarouselOutline.md  # 41 lines
│   │   ├── ImageAI_PostPrism_KeyQuotes.md  # 16 lines
│   │   ├── ImageAI_PostPrism_KeyTakeaways.md  # 9 lines
│   │   ├── ImageAI_PostPrism_NewsletterIntro.txt  # 6 lines
│   │   └── ImageAI_PostPrism_ShowNotes.md  # 30 lines
│   ├── discord-rich-presence-kit-AgentReady/
│   │   ├── agent_tools/
│   │   ├── assets/
│   │   ├── docs/
│   │   │   ├── AGENT.md  # 52 lines
│   │   ├── examples/
│   │   │   ├── example_app.py  # 28 lines
│   │   │   ├── presence_cli.py  # 78 lines
│   │   │   ├── presence_server.py  # 12 lines
│   │   │   └── presence_stdio.py  # 52 lines
│   │   ├── src/
│   │   │   └── discord_presence_helper/
│   │   │       ├── __init__.py  # 9 lines
│   │   │       ├── agent_api.py  # 104 lines
│   │   │       ├── client.py  # 160 lines
│   │   │       └── encryption.py  # 24 lines
│   │   ├── README.md  # 59 lines
│   │   ├── requirements.txt  # 6 lines
│   ├── fable5-comic/
│   │   ├── fable5-ace-music/
│   │   │   ├── Samples/
│   │   │   ├── autosave/
│   │   ├── images/
│   │   ├── video/
│   │   ├── README.md  # 46 lines
│   ├── sprite-tab-archive/
│   │   ├── README.md  # 23 lines
│   │   ├── core-spine-final-review.md  # 409 lines
│   │   ├── core-spine-ledger-archive.md  # 42 lines
│   │   ├── final-fix-A-report.md  # 157 lines
│   │   ├── final-fix-B-report.md  # 119 lines
│   │   ├── final-fix-C-report.md  # 165 lines
│   │   ├── final-fix-D-report.md  # 336 lines
│   │   ├── final-review-context.md  # 187 lines
│   │   ├── global-constraints.md  # 25 lines
│   │   ├── gui-a-final-review.md  # 425 lines
│   │   ├── gui-a-ledger-archive.md  # 55 lines
│   │   ├── gui-b-final-review.md  # 501 lines
│   │   ├── gui-b-ledger-archive.md  # 96 lines
│   │   ├── image-route-final-review.md  # 537 lines
│   │   ├── image-route-ledger-archive.md  # 98 lines
│   │   ├── image-route-rereview.md  # 93 lines
│   │   ├── implementer-contract.md  # 27 lines
│   │   ├── keying-final-review.md  # 265 lines
│   │   ├── keying-ledger-archive.md  # 41 lines
│   │   ├── pixel-art-final-review.md  # 267 lines
│   │   ├── pixel-art-ledger-archive.md  # 23 lines
│   │   ├── preflight-scan.md  # 145 lines
│   │   ├── rereview-context.md  # 75 lines
│   │   ├── reviewer-contract.md  # 21 lines
│   │   ├── task-1-brief.md  # 294 lines
│   │   ├── task-1-report.md  # 145 lines
│   │   ├── task-10-brief.md  # 606 lines
│   │   ├── task-10-report.md  # 372 lines
│   │   ├── task-10-rereview.md  # 250 lines
│   │   ├── task-10-review.md  # 228 lines
│   │   ├── task-11-brief.md  # 57 lines
│   │   ├── task-2-brief.md  # 419 lines
│   │   ├── task-2-report.md  # 189 lines
│   │   ├── task-3-brief.md  # 488 lines
│   │   ├── task-3-report.md  # 88 lines
│   │   ├── task-4-brief.md  # 360 lines
│   │   ├── task-4-report.md  # 158 lines
│   │   ├── task-5-brief.md  # 348 lines
│   │   ├── task-5-report.md  # 164 lines
│   │   ├── task-6-brief.md  # 422 lines
│   │   ├── task-6-report.md  # 171 lines
│   │   ├── task-7-brief.md  # 247 lines
│   │   ├── task-7-report.md  # 228 lines
│   │   ├── task-8-brief.md  # 374 lines
│   │   ├── task-8-report.md  # 146 lines
│   │   ├── task-9-brief.md  # 459 lines
│   │   ├── task-9-report.md  # 249 lines
│   │   ├── video-route-final-review.md  # 338 lines
│   │   └── video-route-ledger-archive.md  # 42 lines
│   ├── 2026-04-08-GA-migration-notes.md  # 82 lines
│   ├── 2026-06-25-layout-tab-ux-fixes.md  # 48 lines
│   ├── 2026-07-29-issue11-ux-research-report.md  # 206 lines
│   ├── 2026-08-29-sprite-tab-planning-summary.md  # 64 lines
│   ├── 2026-08-30-sprite-gui-a-complete.md  # 22 lines
│   ├── 2026-08-30-sprite-gui-b-complete.md  # 20 lines
│   ├── 2026-08-30-sprite-image-route-complete.md  # 113 lines
│   ├── 2026-09-01-sprite-export-crop-and-dialog-fixes.md  # 168 lines
│   ├── 2026-09-01-video-last-project-and-sora-coercion.md  # 34 lines
│   ├── 2026-09-02-sprite-fix-plan.md  # 192 lines
│   ├── 2026-09-04-pr45-review-fixes.md  # 39 lines
│   ├── 2026-09-04-sprite-background-implementation.md  # 46 lines
│   ├── 2026-09-04-sprite-dejitter-crop-fix.md  # 70 lines
│   ├── 2026-09-04-sprite-gif-background-and-artifacts.md  # 80 lines
│   ├── 2026-09-05-Sprite-CLI-Validation.md  # 79 lines
│   ├── 2026-09-05-rock-3-export-dimensions.md  # 38 lines
│   ├── 2026-09-05-sprite-projects-and-startup.md  # 75 lines
│   ├── 2026-09-05-sprite-release.md  # 27 lines
│   ├── 2026-09-05-sprite-ui-sizing.md  # 28 lines
│   ├── BUGFIX_veo_duration_handling.md  # 195 lines
│   ├── Bot_Animation_Ideas.md  # 66 lines
│   ├── CharacterAnimator_BugFixes_20260112.md  # 75 lines
│   ├── CharacterAnimator_BugFixes_Round2_20260112.md  # 214 lines
│   ├── Claude Addons.md  # 79 lines
│   ├── Claude-Interactions-colored.md  # 175 lines
│   ├── Claude-Interactions.md  # 206 lines
│   ├── CodeReview-splitter-mainwindow-theming-20260219.md  # 172 lines
│   ├── CodeReview-theme-py-20260219.md  # 174 lines
│   ├── Codex CLI Authorization.md  # 25 lines
│   ├── Context-Hog-Analysis-Prompts.md  # 553 lines
│   ├── DialogUX-Audit-Findings-2026-07-06.md  # 735 lines
│   ├── Dictation.txt  # 7 lines
│   ├── Discord_FontGenerator_Options.md  # 63 lines
│   ├── Discord_Logo_Prompts.md  # 27 lines
│   ├── Discord_RPC_Dialog_Updates.md  # 52 lines
│   ├── Discord_v0.32_Release.md  # 42 lines
│   ├── EXTRACT_FRAMES_README.md  # 121 lines
│   ├── Features - Agent interactions and more.md  # 141 lines
│   ├── FontGenerator_Flow.md  # 202 lines
│   ├── HF_Auth_UI_Guide.md  # 83 lines
│   ├── HistoryTabOverhaul_20260218.md  # 45 lines
│   ├── HuggingFace_Auth_Guide.md  # 99 lines
│   ├── LINUX_VIDEO_TAB_FIX.md  # 72 lines
│   ├── LLM-Based-Tempo-Descriptors-Implementation.md  # 355 lines
│   ├── Lyric timing success.md  # 30 lines
│   ├── MIDI_KARAOKE_FEATURES.md  # 170 lines
│   ├── Model-Specific-Prompting-Fixes.md  # 434 lines
│   ├── Nano Banana for Backslash Glyphs.md  # 59 lines
│   ├── OLLAMA_SETUP.md  # 162 lines
│   ├── PopOS-Lockup-Analysis.md  # 655 lines
│   ├── PromptBuilder_SemanticSearch_Research.md  # 2055 lines
│   ├── RealESRGAN_Cheatsheet.md  # 79 lines
│   ├── Testing.md  # 473 lines
│   ├── Toyota-method-prompt.md  # 26 lines
│   ├── VIDEO_TAB_LOGGING.md  # 213 lines
│   ├── Veo 3 Features.md  # 19 lines
│   ├── Veo3_Tempo_Rhythm_Research.md  # 875 lines
│   ├── Vibe_Lab_Animated_Emoji_Ideas.md  # 135 lines
│   ├── WSL-Migration-to-G-Drive.md  # 113 lines
│   ├── api_keys_comparison.md  # 114 lines
│   ├── doc-report-2026-02-27.md  # 26 lines
│   ├── google-genai-imageconfig-fix.md  # 69 lines
│   ├── hermes-claude-config-sync-2026-07-29.md  # 55 lines
│   ├── repo_error_check_2026-04-27.md  # 174 lines
│   ├── session-2026-05-31-merge-and-skill-expansion.md  # 37 lines
│   ├── session-2026-06-14-model-registry-migration.md  # 58 lines
│   └── ₿ Bitcoin Wealth Builder.md  # 33 lines
├── Plans/
│   ├── 2026-08-24-sprite-tab-research/
│   ├── ImageAI-Prompt-Enhancer-Pack/
│   │   ├── ImageAI_Prompt_Enhancer_GPT5.md  # 453 lines
│   ├── ImageAI_Layout_Starter/
│   │   ├── Core/
│   │   ├── Docs/
│   │   ├── Fonts/
│   │   └── Templates/
│   ├── issue-11-ux-proposals/
│   │   ├── exports/
│   │   ├── aggregate_exports.py  # 90 lines
│   ├── litellm_gpt5_conversation/
│   │   ├── README.txt  # 9 lines
│   │   ├── basic_example.py  # 45 lines
│   │   └── full_features_example.py  # 119 lines
│   ├── providers/
│   ├── samples/
│   │   └── mycountry_project/
│   │       ├── assets/
│   │       ├── exports/
│   │       └── logs/
│   ├── 2026-01-27-font-segmentation-row-column.md  # 915 lines
│   ├── 2026-01-28-generate-missing-glyphs.md  # 120 lines
│   ├── 2026-02-18-history-tab-implementation.md  # 1206 lines
│   ├── 2026-02-18-history-tab-overhaul-design.md  # 93 lines
│   ├── 2026-02-19-maestro-ui-redesign.md  # 807 lines
│   ├── 2026-04-08-GA-endpoint-migration.md  # 801 lines
│   ├── 2026-06-24-layout-ai-designer-design.md  # 286 lines
│   ├── 2026-06-24-layout-ai-designer-phase1-completion.md  # 58 lines
│   ├── 2026-06-24-layout-ai-designer-phase1-foundation.md  # 1537 lines
│   ├── 2026-06-24-layout-ai-designer-phase2-completion.md  # 71 lines
│   ├── 2026-06-24-layout-ai-designer-phase2-designer.md  # 1089 lines
│   ├── 2026-06-24-layout-ai-designer-phase3-completion.md  # 64 lines
│   ├── 2026-06-24-layout-ai-designer-phase3-style.md  # 830 lines
│   ├── 2026-06-24-layout-ai-designer-phase4-completion.md  # 71 lines
│   ├── 2026-06-24-layout-ai-designer-phase4-content.md  # 465 lines
│   ├── 2026-06-25-layout-ai-designer-phase5a-completion.md  # 73 lines
│   ├── 2026-06-25-layout-ai-designer-phase5a-content.md  # 178 lines
│   ├── 2026-06-25-layout-ai-designer-phase5b-completion.md  # 90 lines
│   ├── 2026-06-25-layout-ai-designer-phase5b-content.md  # 139 lines
│   ├── 2026-06-27-comic-layout-ai-designer-design.md  # 230 lines
│   ├── 2026-06-27-comic-layout-ai-designer-plan.md  # 834 lines
│   ├── 2026-06-27-comic-layout-geometry-core-design.md  # 216 lines
│   ├── 2026-06-27-comic-layout-geometry-core-plan.md  # 966 lines
│   ├── 2026-06-27-comic-layout-manual-editor-design.md  # 186 lines
│   ├── 2026-06-27-comic-layout-manual-editor-plan.md  # 1054 lines
│   ├── 2026-06-27-comic-layout-text-overlays-design.md  # 312 lines
│   ├── 2026-06-27-comic-layout-text-overlays-plan.md  # 1063 lines
│   ├── 2026-06-27-comic-layout-tiling-engine-design.md  # 177 lines
│   ├── 2026-06-27-comic-layout-tiling-engine-plan.md  # 1069 lines
│   ├── 2026-06-28-comic-layout-overlay-editing-design.md  # 122 lines
│   ├── 2026-06-28-comic-layout-overlay-editing-plan.md  # 1189 lines
│   ├── 2026-06-28-comic-layout-region-ops-design.md  # 174 lines
│   ├── 2026-06-28-comic-layout-region-ops-plan.md  # 890 lines
│   ├── 2026-06-28-layout-cli-design.md  # 180 lines
│   ├── 2026-06-28-layout-cli-plan.md  # 960 lines
│   ├── 2026-06-30-cli-video-implementation-plan.md  # 830 lines
│   ├── 2026-06-30-cli-video-support.md  # 207 lines
│   ├── 2026-06-30-gemini-omni-video-support.md  # 466 lines
│   ├── 2026-07-01-omni-docs-parity.md  # 978 lines
│   ├── 2026-07-26-custom-styles-design.md  # 303 lines
│   ├── 2026-07-26-custom-styles-plan.md  # 3452 lines
│   ├── 2026-07-27-custom-styles-followups-plan.md  # 680 lines
│   ├── 2026-07-29-issue11-ux-simplification-design.md  # 220 lines
│   ├── 2026-07-29-layout-curved-text-design.md  # 148 lines
│   ├── 2026-07-29-layout-curved-text-plan.md  # 1236 lines
│   ├── 2026-08-10-storage-locations-design.md  # 438 lines
│   ├── 2026-08-11-storage-locations-implementation.md  # 2730 lines
│   ├── 2026-08-24-sprite-tab-research.md  # 91 lines
│   ├── 2026-08-29-sprite-cli-release-plan.md  # 3693 lines
│   ├── 2026-08-29-sprite-core-spine-plan.md  # 5641 lines
│   ├── 2026-08-29-sprite-gui-a-plan.md  # 4304 lines
│   ├── 2026-08-29-sprite-gui-b-plan.md  # 5300 lines
│   ├── 2026-08-29-sprite-image-route-exports-plan.md  # 4149 lines
│   ├── 2026-08-29-sprite-keying-plan.md  # 2492 lines
│   ├── 2026-08-29-sprite-pixel-art-plan.md  # 1521 lines
│   ├── 2026-08-29-sprite-tab-design.md  # 889 lines
│   ├── 2026-08-29-sprite-video-route-plan.md  # 4581 lines
│   ├── 2026-09-04-sprite-background-modes.md  # 31 lines
│   ├── 2026-09-05-sprite-cli.md  # 46 lines
│   ├── 2026-09-05-sprite-ui-ux.md  # 36 lines
│   ├── AICharacterGenerator.md  # 310 lines
│   ├── CharacterAnimatorPuppetAutomation.md  # 419 lines
│   ├── CharacterAnimatorPuppetAutomation_LLM.md  # 180 lines
│   ├── CharacterAnimator_LayerExport_v3.md  # 129 lines
│   ├── Comprehensive Style Presets for AI Image & Video Generation - Research Report-Claude.md  # 871 lines
│   ├── ComprehensiveSettings.md  # 560 lines
│   ├── Custom emojis from Cathy Schmidt.md  # 9 lines
│   ├── Dall-e-3 Image Continuity.md  # 77 lines
│   ├── Development.md  # 6 lines
│   ├── DialogUX-TLC-Plan.md  # 278 lines
│   ├── DiscordRichPresence.md  # 322 lines
│   ├── GPT_Image_API_ImageAI.md  # 117 lines
│   ├── Gemini Nano Banana Guide.md  # 120 lines
│   ├── GeminiFullFeatures.md  # 416 lines
│   ├── Generating Continuous Video Scenes from Lyrics for Veo 3-Gemini.md  # 200 lines
│   ├── Generating Continuous Video Scenes from Lyrics for Veo 3-OpenAI.md  # 215 lines
│   ├── Google-Imagen3-Multi-Reference-Implementation.md  # 1261 lines
│   ├── GoogleCloudAuth.md  # 76 lines
│   ├── HistoryAndVideoTabImprovements.md  # 358 lines
│   ├── HistoryTabReferenceImages.md  # 269 lines
│   ├── Ideas.md  # 49 lines
│   ├── ImageAI-VideoProject-PRD.md  # 1603 lines
│   ├── ImageAI_Layout_Implementation_Plan.md  # 998 lines
│   ├── ImageAI_OpenAI_vs_Gemini.md  # 113 lines
│   ├── LLM-Params-Standardization.md  # 153 lines
│   ├── LLMSceneSuggestion.md  # 161 lines
│   ├── LTX-Video-Implementation-Plan.md  # 770 lines
│   ├── LTX_VIDEO_INTEGRATION_PLAN.md  # 814 lines
│   ├── LipSyncImplementationChecklist.md  # 353 lines
│   ├── LipSyncIntegration.md  # 512 lines
│   ├── Lyrics-TimeSync-Prompt-ASL-Gemini.md  # 103 lines
│   ├── Lyrics-TimeSync-Prompt-ASL-gpt-5.md  # 199 lines
│   ├── Lyrics-to-Image-Prompt-Guide.md  # 102 lines
│   ├── Lyrics-to-Prompts-Usage.md  # 269 lines
│   ├── MIDI_Timing_Sync_Design.md  # 360 lines
│   ├── Midjourney_V7_Implementation_Plan.md  # 503 lines
│   ├── NANO_BANANA_PRO_PLAN.md  # 349 lines
│   ├── Nano Banana Pro.md  # 55 lines
│   ├── NewProviders.md  # 236 lines
│   ├── OpenAI-API-Upgrade-and-Sora-2-Integration.md  # 428 lines
│   ├── Optimal path for integrating LTX Video into your PySide6 desktop application.md  # 191 lines
│   ├── Phase1-Completion-Summary.md  # 182 lines
│   ├── Phase1_Completion_Summary.md  # 212 lines
│   ├── Phase2_Completion_Summary.md  # 351 lines
│   ├── Phase3-Completion-Summary.md  # 296 lines
│   ├── PromptBuilder_Preset_Catalog.md  # 754 lines
│   ├── PromptBuilder_SmartSearch_Implementation.md  # 492 lines
│   ├── ProviderIntegration.md  # 229 lines
│   ├── README_midjourney_provider.md  # 24 lines
│   ├── RefactoringPlan.md  # 244 lines
│   ├── Reference-Images-Unlimited-And-History-Improvements.md  # 369 lines
│   ├── Sora2-Research-Notes.md  # 93 lines
│   ├── Strict-Lyric-Timing-Contract-v1.0.md  # 187 lines
│   ├── Strict-Lyric-Timing-Gemini.md  # 127 lines
│   ├── Style-Presets-Community-Features.md  # 617 lines
│   ├── Style-Presets-Core-Implementation.md  # 341 lines
│   ├── TimeHintsAndVideoExtension.md  # 108 lines
│   ├── VEO3_FIXES.md  # 128 lines
│   ├── VEO_3_1_INTEGRATION_PLAN.md  # 483 lines
│   ├── VectorizedFontGeneration.md  # 147 lines
│   ├── Veo3-Continuity-Research.md  # 811 lines
│   ├── Veo3-Music-Sync-Strategy.md  # 1200 lines
│   ├── Veo3.1-FramesToVideo.md  # 891 lines
│   ├── Veo3.1-TableRefactor-Spec.md  # 649 lines
│   ├── Veo3_Reference_Images_Implementation.md  # 380 lines
│   ├── WhisperIntegratedLipSync.md  # 219 lines
│   ├── common-sizes.md  # 80 lines
│   ├── favicon-sizes.md  # 55 lines
│   ├── social-media-image-sizes-2025-table-only-manual.md  # 44 lines
│   ├── social-media-image-sizes-2025.md  # 62 lines
│   ├── sprite-tab-feature-selector.md  # 101 lines
│   └── veo_3_inspirational_continuity.md  # 65 lines
├── Prompt Library/
├── Sample/
│   ├── Veo3_Reference_Workflow_Kit_Full_Grandpa_Was_A_Democrat/
│   │   ├── Prompts/
│   │   │   ├── Grandpa_Was_a_Democrat_Image_Prompts.txt  # 336 lines
│   │   │   └── Grandpa_Was_a_Democrat_Image_Prompts_Details.md  # 330 lines
│   │   ├── Grandpa Was A Democrat-Lyrics.txt  # 87 lines
│   │   └── Placement_Guide.md  # 75 lines
│   ├── Video Project image descriptions.md  # 20 lines
│   └── midjourney_provider.py  # 99 lines
├── SampleData/
│   ├── SpriteCLI/
│   │   ├── README.md  # 35 lines
│   │   └── rebuild.py  # 51 lines
│   └── ice_ice_baby_heavymetal.md  # 91 lines
├── assets/
├── cache/
│   ├── ai_visemes/
│   ├── exported_puppet/
│   │   ├── Mouth/
│   │   ├── manifest.txt  # 25 lines
│   └── visemes/
├── cli/
│   ├── commands/
│   │   ├── __init__.py  # 0 lines
│   │   ├── layout.py  # 258 lines
│   │   ├── sprite.py  # 562 lines
│   │   ├── sprite_generation.py  # 707 lines
│   │   ├── sprite_media.py  # 519 lines
│   │   ├── sprite_utilities.py  # 233 lines
│   │   ├── style.py  # 149 lines
│   │   └── video.py  # 288 lines
│   ├── __init__.py  # 6 lines
│   ├── parser.py  # 328 lines
│   ├── runner.py  # 618 lines
│   └── sprite_schema.py  # 243 lines
├── core/
│   ├── character_animator/
│   │   ├── __init__.py  # 62 lines
│   │   ├── ai_face_editor.py  # 1071 lines
│   │   ├── availability.py  # 304 lines
│   │   ├── constants.py  # 463 lines
│   │   ├── face_generator.py  # 539 lines
│   │   ├── installer.py  # 384 lines
│   │   ├── models.py  # 399 lines
│   │   ├── psd_exporter.py  # 723 lines
│   │   ├── segmenter.py  # 608 lines
│   │   └── svg_exporter.py  # 636 lines
│   ├── font_generator/
│   │   ├── __init__.py  # 106 lines
│   │   ├── font_builder.py  # 599 lines
│   │   ├── glyph_generator.py  # 530 lines
│   │   ├── glyph_identifier.py  # 946 lines
│   │   ├── metrics.py  # 563 lines
│   │   ├── row_column_segmenter.py  # 543 lines
│   │   ├── row_detector.py  # 399 lines
│   │   ├── segmentation.py  # 1392 lines
│   │   └── vectorizer.py  # 687 lines
│   ├── layout/
│   │   ├── __init__.py  # 83 lines
│   │   ├── balloons.py  # 204 lines
│   │   ├── batch_fill.py  # 114 lines
│   │   ├── bundle_io.py  # 188 lines
│   │   ├── designer.py  # 344 lines
│   │   ├── engine.py  # 433 lines
│   │   ├── fill_plan.py  # 39 lines
│   │   ├── font_manager.py  # 212 lines
│   │   ├── geometry.py  # 63 lines
│   │   ├── history.py  # 61 lines
│   │   ├── image_processor.py  # 305 lines
│   │   ├── layout_algorithms.py  # 389 lines
│   │   ├── models.py  # 241 lines
│   │   ├── overlay_ops.py  # 70 lines
│   │   ├── page_sizes.py  # 53 lines
│   │   ├── polygon.py  # 310 lines
│   │   ├── project_io.py  # 51 lines
│   │   ├── prompt_helper.py  # 126 lines
│   │   ├── qt_renderer.py  # 578 lines
│   │   ├── region_ops.py  # 114 lines
│   │   ├── schema.py  # 290 lines
│   │   ├── styles.py  # 79 lines
│   │   ├── svg_path.py  # 135 lines
│   │   ├── template_engine.py  # 301 lines
│   │   ├── template_io.py  # 22 lines
│   │   ├── template_manager.py  # 559 lines
│   │   ├── text_path.py  # 66 lines
│   │   ├── text_renderer.py  # 386 lines
│   │   └── tiling.py  # 217 lines
│   ├── model_registry/
│   │   ├── __init__.py  # 63 lines
│   │   └── client.py  # 220 lines
│   ├── reference/
│   │   ├── __init__.py  # 22 lines
│   │   ├── image_compositor.py  # 264 lines
│   │   └── imagen_reference.py  # 253 lines
│   ├── sprite/
│   │   ├── exporters/
│   │   │   ├── __init__.py  # 15 lines
│   │   │   ├── aseprite_json.py  # 78 lines
│   │   │   ├── aseprite_native.py  # 220 lines
│   │   │   ├── engine_presets.py  # 308 lines
│   │   │   ├── gif.py  # 178 lines
│   │   │   ├── godot_tres.py  # 131 lines
│   │   │   ├── grid.py  # 197 lines
│   │   │   ├── png_sequence.py  # 110 lines
│   │   │   └── texturepacker_json.py  # 63 lines
│   │   ├── generation/
│   │   │   ├── __init__.py  # 60 lines
│   │   │   ├── _common.py  # 53 lines
│   │   │   ├── action_cards.py  # 335 lines
│   │   │   ├── cost.py  # 161 lines
│   │   │   ├── errors.py  # 128 lines
│   │   │   ├── image_route.py  # 373 lines
│   │   │   ├── plate.py  # 110 lines
│   │   │   ├── pose_steps.py  # 182 lines
│   │   │   ├── prompts.py  # 95 lines
│   │   │   ├── queue.py  # 273 lines
│   │   │   ├── retouch.py  # 199 lines
│   │   │   ├── turnaround.py  # 120 lines
│   │   │   └── video_route.py  # 478 lines
│   │   ├── __init__.py  # 116 lines
│   │   ├── configs.py  # 140 lines
│   │   ├── extract.py  # 342 lines
│   │   ├── keying.py  # 618 lines
│   │   ├── matting.py  # 157 lines
│   │   ├── ml_install.py  # 46 lines
│   │   ├── models.py  # 162 lines
│   │   ├── pipeline.py  # 780 lines
│   │   ├── pixelart.py  # 462 lines
│   │   ├── presets.py  # 90 lines
│   │   ├── project.py  # 781 lines
│   │   ├── project_copy.py  # 64 lines
│   │   ├── slicing.py  # 158 lines
│   │   ├── source.py  # 106 lines
│   │   ├── stabilize.py  # 318 lines
│   │   ├── timing.py  # 117 lines
│   │   └── undo.py  # 81 lines
│   ├── style_presets/
│   ├── styles/
│   │   ├── __init__.py  # 10 lines
│   │   ├── analyzer.py  # 279 lines
│   │   ├── applicator.py  # 179 lines
│   │   ├── models.py  # 80 lines
│   │   └── store.py  # 325 lines
│   ├── video/
│   │   ├── renderers/
│   │   │   └── __init__.py  # 0 lines
│   │   ├── __init__.py  # 45 lines
│   │   ├── audio_segmenter.py  # 299 lines
│   │   ├── config.py  # 403 lines
│   │   ├── continuity_helper.py  # 90 lines
│   │   ├── end_prompt_generator.py  # 172 lines
│   │   ├── event_store.py  # 516 lines
│   │   ├── ffmpeg_renderer.py  # 753 lines
│   │   ├── ffmpeg_utils.py  # 345 lines
│   │   ├── image_continuity.py  # 315 lines
│   │   ├── image_generator.py  # 476 lines
│   │   ├── image_processing.py  # 346 lines
│   │   ├── karaoke_renderer.py  # 427 lines
│   │   ├── llm_sync.py  # 637 lines
│   │   ├── llm_sync_v2.py  # 1404 lines
│   │   ├── midi_processor.py  # 589 lines
│   │   ├── midi_utils.py  # 34 lines
│   │   ├── omni_client.py  # 566 lines
│   │   ├── project.py  # 1147 lines
│   │   ├── project_enhancements.py  # 516 lines
│   │   ├── project_manager.py  # 387 lines
│   │   ├── prompt_engine.py  # 1478 lines
│   │   ├── reference_manager.py  # 404 lines
│   │   ├── scene_suggester.py  # 405 lines
│   │   ├── storyboard.py  # 1210 lines
│   │   ├── storyboard_v2.py  # 1075 lines
│   │   ├── style_analyzer.py  # 406 lines
│   │   ├── suno_package.py  # 437 lines
│   │   ├── tag_parser.py  # 502 lines
│   │   ├── thumbnail_manager.py  # 364 lines
│   │   ├── timing_models.py  # 205 lines
│   │   ├── veo_client.py  # 1213 lines
│   │   ├── video_prompt_generator.py  # 637 lines
│   │   ├── whisper_analyzer.py  # 501 lines
│   │   └── workflow_wizard.py  # 594 lines
│   ├── __init__.py  # 69 lines
│   ├── batch_manager.py  # 492 lines
│   ├── config.py  # 676 lines
│   ├── config_io.py  # 498 lines
│   ├── constants.py  # 154 lines
│   ├── conversation_manager.py  # 258 lines
│   ├── data_migration.py  # 1692 lines
│   ├── discord_rpc.py  # 579 lines
│   ├── gcloud_utils.py  # 245 lines
│   ├── image_size.py  # 69 lines
│   ├── image_utils.py  # 220 lines
│   ├── llm_models.py  # 333 lines
│   ├── llm_params.py  # 532 lines
│   ├── llm_parsing.py  # 124 lines
│   ├── logging_config.py  # 325 lines
│   ├── lyrics_to_prompts.py  # 444 lines
│   ├── musetalk_installer.py  # 784 lines
│   ├── package_installer.py  # 624 lines
│   ├── paths.py  # 315 lines
│   ├── preset_loader.py  # 402 lines
│   ├── project_tracker.py  # 42 lines
│   ├── prompt_data_loader.py  # 150 lines
│   ├── prompt_enhancer.py  # 358 lines
│   ├── prompt_enhancer_llm.py  # 353 lines
│   ├── recycle_bin.py  # 290 lines
│   ├── security.py  # 283 lines
│   ├── tag_searcher.py  # 346 lines
│   ├── upscaling.py  # 275 lines
│   ├── utils.py  # 488 lines
│   ├── whisper_installer.py  # 226 lines
│   └── wikimedia_client.py  # 244 lines
├── data/
│   ├── prompts/
│   ├── style_presets/
│   │   ├── artist_signatures/
│   │   ├── cinematic/
│   │   ├── contemporary_digital/
│   │   ├── cultural_traditions/
│   │   └── historical_art/
├── generated_videos/
├── gui/
│   ├── character_animator/
│   │   ├── __init__.py  # 20 lines
│   │   ├── install_dialog.py  # 555 lines
│   │   └── puppet_wizard.py  # 1373 lines
│   ├── common/
│   │   ├── __init__.py  # 7 lines
│   │   ├── dialog_conventions.py  # 141 lines
│   │   ├── dialog_manager.py  # 225 lines
│   │   ├── markdown_tables.py  # 53 lines
│   │   └── splitter_style.py  # 44 lines
│   ├── font_generator/
│   │   ├── __init__.py  # 9 lines
│   │   └── font_wizard.py  # 2397 lines
│   ├── layout/
│   │   ├── __init__.py  # 5 lines
│   │   ├── canvas_widget.py  # 103 lines
│   │   ├── content_inspector.py  # 255 lines
│   │   ├── designer_panel.py  # 200 lines
│   │   ├── document_dialog.py  # 454 lines
│   │   ├── export_dialog.py  # 428 lines
│   │   ├── font_loader.py  # 48 lines
│   │   ├── geometry_editor.py  # 209 lines
│   │   ├── geometry_inspector.py  # 137 lines
│   │   ├── history_window.py  # 47 lines
│   │   ├── image_history_dialog.py  # 317 lines
│   │   ├── inspector_widget.py  # 484 lines
│   │   ├── layout_tab.py  # 1034 lines
│   │   ├── overlay_editor.py  # 160 lines
│   │   ├── overlay_inspector.py  # 193 lines
│   │   ├── page_setup_widget.py  # 144 lines
│   │   ├── prompt_worker.py  # 34 lines
│   │   ├── style_panel.py  # 95 lines
│   │   ├── template_selector.py  # 340 lines
│   │   └── text_gen_dialog.py  # 676 lines
│   ├── resources/
│   │   ├── fonts/
│   │   └── __init__.py  # 0 lines
│   ├── sprite/
│   │   ├── __init__.py  # 5 lines
│   │   ├── action_cards_panel.py  # 490 lines
│   │   ├── character_panel.py  # 393 lines
│   │   ├── engine_preset_box.py  # 94 lines
│   │   ├── export_dialog.py  # 765 lines
│   │   ├── export_formats.py  # 51 lines
│   │   ├── frame_strip.py  # 579 lines
│   │   ├── frames_workspace.py  # 401 lines
│   │   ├── generation_settings_dialog.py  # 367 lines
│   │   ├── image_route_dialog.py  # 452 lines
│   │   ├── ml_install_dialog.py  # 175 lines
│   │   ├── pixel_view.py  # 337 lines
│   │   ├── prefs.py  # 64 lines
│   │   ├── preview_player.py  # 397 lines
│   │   ├── processing_panel.py  # 1117 lines
│   │   ├── project_dialog.py  # 82 lines
│   │   ├── queue_panel.py  # 343 lines
│   │   ├── retouch_dialog.py  # 187 lines
│   │   ├── retouch_wiring.py  # 70 lines
│   │   ├── shortcuts.py  # 97 lines
│   │   ├── sprite_tab.py  # 522 lines
│   │   ├── undo_controller.py  # 103 lines
│   │   └── workers.py  # 409 lines
│   ├── styles/
│   │   ├── __init__.py  # 1 lines
│   │   ├── style_manager_dialog.py  # 550 lines
│   │   └── style_picker.py  # 105 lines
│   ├── utils/
│   │   └── stderr_suppressor.py  # 91 lines
│   ├── video/
│   │   ├── __init__.py  # 0 lines
│   │   ├── end_prompt_dialog.py  # 232 lines
│   │   ├── enhanced_workspace.py  # 609 lines
│   │   ├── frame_button.py  # 274 lines
│   │   ├── history_tab.py  # 589 lines
│   │   ├── lipsync_widget.py  # 682 lines
│   │   ├── musetalk_install_dialog.py  # 456 lines
│   │   ├── project_browser.py  # 294 lines
│   │   ├── project_dialog.py  # 452 lines
│   │   ├── prompt_field_widget.py  # 177 lines
│   │   ├── reference_generation_dialog.py  # 955 lines
│   │   ├── reference_images_widget.py  # 169 lines
│   │   ├── reference_library_widget.py  # 834 lines
│   │   ├── reference_selector_dialog.py  # 320 lines
│   │   ├── scene_image_selector_dialog.py  # 255 lines
│   │   ├── select_existing_video_dialog.py  # 295 lines
│   │   ├── start_prompt_dialog.py  # 467 lines
│   │   ├── suno_preprocess_dialog.py  # 341 lines
│   │   ├── variant_selector_dialog.py  # 182 lines
│   │   ├── video_button.py  # 253 lines
│   │   ├── video_project_tab.py  # 2171 lines
│   │   ├── video_prompt_dialog.py  # 304 lines
│   │   ├── whisper_install_dialog.py  # 410 lines
│   │   ├── wizard_widget.py  # 402 lines
│   │   └── workspace_widget.py  # 8045 lines
│   ├── __init__.py  # 126 lines
│   ├── batch_mode_widget.py  # 552 lines
│   ├── dialog_utils.py  # 319 lines
│   ├── dialogs.py  # 225 lines
│   ├── enhanced_prompt_dialog.py  # 868 lines
│   ├── file_attachment_widget.py  # 646 lines
│   ├── find_dialog.py  # 434 lines
│   ├── flow_layout.py  # 162 lines
│   ├── history_model.py  # 412 lines
│   ├── history_widget.py  # 290 lines
│   ├── image_crop_dialog.py  # 421 lines
│   ├── image_preview_popup.py  # 115 lines
│   ├── imagen_reference_widget.py  # 1071 lines
│   ├── install_dialog.py  # 529 lines
│   ├── llm_utils.py  # 185 lines
│   ├── local_sd_widget.py  # 476 lines
│   ├── main_window.py  # 9592 lines
│   ├── midjourney_dialog.py  # 1128 lines
│   ├── midjourney_match_dialog.py  # 280 lines
│   ├── midjourney_panel.py  # 286 lines
│   ├── midjourney_tab.py  # 687 lines
│   ├── midjourney_watcher.py  # 323 lines
│   ├── model_browser.py  # 449 lines
│   ├── prompt_builder.py  # 1839 lines
│   ├── prompt_generation_dialog.py  # 1611 lines
│   ├── prompt_question_dialog.py  # 949 lines
│   ├── prompt_question_dialog_old.py  # 1077 lines
│   ├── reference_image_dialog.py  # 1186 lines
│   ├── reference_selection_dialog.py  # 286 lines
│   ├── refine_image_dialog.py  # 549 lines
│   ├── settings_widgets.py  # 2198 lines
│   ├── shortcut_hint_widget.py  # 132 lines
│   ├── social_sizes_tree_dialog.py  # 548 lines
│   ├── storage_settings_widget.py  # 692 lines
│   ├── theme.py  # 696 lines
│   ├── upscaling_widget.py  # 328 lines
│   ├── wikimedia_search_dialog.py  # 502 lines
│   └── workers.py  # 245 lines
├── providers/
│   ├── video/
│   │   ├── __init__.py  # 66 lines
│   │   ├── base_lipsync.py  # 118 lines
│   │   └── musetalk_provider.py  # 467 lines
│   ├── __init__.py  # 199 lines
│   ├── base.py  # 265 lines
│   ├── google.py  # 2223 lines
│   ├── local_sd.py  # 494 lines
│   ├── midjourney.py  # 275 lines
│   ├── midjourney_provider.py  # 278 lines
│   ├── model_info.py  # 146 lines
│   ├── ollama.py  # 253 lines
│   ├── openai.py  # 1498 lines
│   └── stability.py  # 465 lines
├── scripts/
│   ├── export_cached_visemes.py  # 188 lines
│   ├── fetch_model_capabilities.py  # 1147 lines
│   └── generate_tags.py  # 642 lines
├── templates/
│   ├── layouts/
│   ├── video/
│   │   ├── lyric_prompt.j2  # 25 lines
│   │   ├── scene_description.j2  # 42 lines
│   │   ├── shot_prompt.j2  # 40 lines
│   │   └── sora_shot_prompt.j2  # 62 lines
│   └── __init__.py  # 2098 lines
├── tests/
│   ├── gui/
│   │   ├── test_dialog_conventions.py  # 229 lines
│   │   ├── test_gui_paths.py  # 46 lines
│   │   ├── test_provider_model_sync.py  # 154 lines
│   │   ├── test_startup_lazy_tabs.py  # 122 lines
│   │   └── test_storage_settings.py  # 1576 lines
│   ├── layout/
│   │   ├── test_balloons.py  # 127 lines
│   │   ├── test_batch_fill.py  # 82 lines
│   │   ├── test_bleed_render.py  # 40 lines
│   │   ├── test_bundle_io.py  # 110 lines
│   │   ├── test_canvas_tool_mode.py  # 18 lines
│   │   ├── test_canvas_widget.py  # 44 lines
│   │   ├── test_cli_layout_assemble.py  # 23 lines
│   │   ├── test_cli_layout_design.py  # 48 lines
│   │   ├── test_cli_layout_dispatch.py  # 26 lines
│   │   ├── test_cli_layout_export.py  # 50 lines
│   │   ├── test_cli_layout_fill.py  # 65 lines
│   │   ├── test_cli_layout_helpers.py  # 36 lines
│   │   ├── test_cli_layout_parser.py  # 38 lines
│   │   ├── test_content_inspector.py  # 151 lines
│   │   ├── test_designer.py  # 220 lines
│   │   ├── test_designer_panel.py  # 132 lines
│   │   ├── test_designer_text_path.py  # 36 lines
│   │   ├── test_export_qt.py  # 61 lines
│   │   ├── test_fill_plan.py  # 37 lines
│   │   ├── test_geometry.py  # 73 lines
│   │   ├── test_geometry_editor.py  # 61 lines
│   │   ├── test_geometry_editor_drag.py  # 68 lines
│   │   ├── test_geometry_inspector.py  # 52 lines
│   │   ├── test_history.py  # 82 lines
│   │   ├── test_history_window.py  # 26 lines
│   │   ├── test_image_clip_stroke.py  # 97 lines
│   │   ├── test_layout_lock_and_session.py  # 169 lines
│   │   ├── test_layout_tab.py  # 60 lines
│   │   ├── test_layout_tab_bundle.py  # 44 lines
│   │   ├── test_layout_tab_content.py  # 115 lines
│   │   ├── test_layout_tab_designer.py  # 73 lines
│   │   ├── test_layout_tab_designer_overlays.py  # 32 lines
│   │   ├── test_layout_tab_fill_all.py  # 49 lines
│   │   ├── test_layout_tab_orientation.py  # 95 lines
│   │   ├── test_layout_tab_prompt.py  # 84 lines
│   │   ├── test_layout_tab_send_to_image.py  # 58 lines
│   │   ├── test_layout_tab_style.py  # 74 lines
│   │   ├── test_models.py  # 38 lines
│   │   ├── test_overlay_editor.py  # 62 lines
│   │   ├── test_overlay_editor_text_path.py  # 80 lines
│   │   ├── test_overlay_inspector.py  # 39 lines
│   │   ├── test_overlay_inspector_curve.py  # 125 lines
│   │   ├── test_overlay_model.py  # 47 lines
│   │   ├── test_overlay_ops.py  # 48 lines
│   │   ├── test_overlay_render.py  # 84 lines
│   │   ├── test_overlay_render_rotation.py  # 27 lines
│   │   ├── test_overlay_rotation.py  # 30 lines
│   │   ├── test_overlay_schema.py  # 49 lines
│   │   ├── test_overlay_text_path_render.py  # 98 lines
│   │   ├── test_overlay_text_path_schema.py  # 59 lines
│   │   ├── test_overlay_wiring.py  # 56 lines
│   │   ├── test_page_setup_widget.py  # 68 lines
│   │   ├── test_page_sizes.py  # 68 lines
│   │   ├── test_polygon.py  # 132 lines
│   │   ├── test_project_io.py  # 96 lines
│   │   ├── test_prompt_helper.py  # 80 lines
│   │   ├── test_qt_renderer.py  # 157 lines
│   │   ├── test_region_ops.py  # 101 lines
│   │   ├── test_region_ops_gui.py  # 66 lines
│   │   ├── test_region_ops_wiring.py  # 71 lines
│   │   ├── test_region_path_builder.py  # 44 lines
│   │   ├── test_region_path_fields.py  # 22 lines
│   │   ├── test_schema.py  # 84 lines
│   │   ├── test_schema_path.py  # 35 lines
│   │   ├── test_style_panel.py  # 75 lines
│   │   ├── test_styles.py  # 64 lines
│   │   ├── test_svg_path.py  # 67 lines
│   │   ├── test_template_io.py  # 33 lines
│   │   ├── test_text_clip.py  # 24 lines
│   │   ├── test_text_path.py  # 67 lines
│   │   ├── test_tiling.py  # 76 lines
│   │   ├── test_tiling_apply.py  # 37 lines
│   │   ├── test_tiling_render.py  # 26 lines
│   │   └── test_writeback_move.py  # 34 lines
│   ├── migration/
│   │   ├── __init__.py  # 0 lines
│   │   ├── test_data_migration.py  # 2021 lines
│   │   ├── test_legacy_model_migration.py  # 78 lines
│   │   └── test_sprite_storage.py  # 40 lines
│   ├── sprite/
│   │   ├── generation/
│   │   │   ├── conftest.py  # 68 lines
│   │   │   ├── test_gen_action_cards.py  # 212 lines
│   │   │   ├── test_gen_cost.py  # 141 lines
│   │   │   ├── test_gen_errors.py  # 134 lines
│   │   │   ├── test_gen_package.py  # 39 lines
│   │   │   ├── test_gen_plate.py  # 133 lines
│   │   │   ├── test_gen_prompts.py  # 73 lines
│   │   │   ├── test_gen_queue.py  # 410 lines
│   │   │   ├── test_gen_turnaround.py  # 116 lines
│   │   │   └── test_gen_video_route.py  # 420 lines
│   │   ├── golden/
│   │   ├── gui/
│   │   │   ├── conftest.py  # 131 lines
│   │   │   ├── gui_synthetic.py  # 58 lines
│   │   │   ├── test_action_cards_panel.py  # 329 lines
│   │   │   ├── test_character_panel.py  # 290 lines
│   │   │   ├── test_export_dialog.py  # 849 lines
│   │   │   ├── test_export_dialog_engine_presets.py  # 162 lines
│   │   │   ├── test_frame_strip.py  # 286 lines
│   │   │   ├── test_generation_settings_dialog.py  # 199 lines
│   │   │   ├── test_image_route_dialog.py  # 586 lines
│   │   │   ├── test_main_window_sprite_wiring.py  # 180 lines
│   │   │   ├── test_ml_install_dialog.py  # 88 lines
│   │   │   ├── test_pixel_view.py  # 163 lines
│   │   │   ├── test_preview_player.py  # 187 lines
│   │   │   ├── test_processing_panel.py  # 592 lines
│   │   │   ├── test_project_library.py  # 126 lines
│   │   │   ├── test_queue_panel.py  # 267 lines
│   │   │   ├── test_retouch_dialog.py  # 294 lines
│   │   │   ├── test_shortcuts.py  # 155 lines
│   │   │   ├── test_sprite_prefs.py  # 54 lines
│   │   │   ├── test_sprite_tab_integration.py  # 691 lines
│   │   │   ├── test_sprite_tab_smoke.py  # 306 lines
│   │   │   ├── test_sprite_worker.py  # 521 lines
│   │   │   └── test_undo_controller.py  # 71 lines
│   │   ├── __init__.py  # 0 lines
│   │   ├── conftest.py  # 51 lines
│   │   ├── keying_fixtures.py  # 59 lines
│   │   ├── synth.py  # 45 lines
│   │   ├── test_aseprite_native.py  # 115 lines
│   │   ├── test_background_geometry.py  # 69 lines
│   │   ├── test_cli_generation.py  # 486 lines
│   │   ├── test_cli_history.py  # 84 lines
│   │   ├── test_cli_media.py  # 244 lines
│   │   ├── test_cli_project.py  # 177 lines
│   │   ├── test_cli_schema.py  # 102 lines
│   │   ├── test_cli_utilities.py  # 167 lines
│   │   ├── test_dejitter.py  # 227 lines
│   │   ├── test_engine_presets.py  # 203 lines
│   │   ├── test_exporters.py  # 353 lines
│   │   ├── test_extract.py  # 206 lines
│   │   ├── test_godot_tres.py  # 95 lines
│   │   ├── test_image_route.py  # 425 lines
│   │   ├── test_key_frame.py  # 149 lines
│   │   ├── test_keying_alpha.py  # 72 lines
│   │   ├── test_keying_auto.py  # 163 lines
│   │   ├── test_keying_cleanup.py  # 98 lines
│   │   ├── test_keying_despill.py  # 67 lines
│   │   ├── test_keying_ffmpeg.py  # 88 lines
│   │   ├── test_matting.py  # 194 lines
│   │   ├── test_matting_difference.py  # 39 lines
│   │   ├── test_ml_install.py  # 52 lines
│   │   ├── test_models.py  # 61 lines
│   │   ├── test_named_configs.py  # 118 lines
│   │   ├── test_package.py  # 48 lines
│   │   ├── test_pipeline.py  # 587 lines
│   │   ├── test_pipeline_background.py  # 130 lines
│   │   ├── test_pipeline_keying.py  # 319 lines
│   │   ├── test_pipeline_pixel.py  # 370 lines
│   │   ├── test_pixelart.py  # 449 lines
│   │   ├── test_pose_steps.py  # 149 lines
│   │   ├── test_presets.py  # 39 lines
│   │   ├── test_project.py  # 476 lines
│   │   ├── test_project_copy.py  # 37 lines
│   │   ├── test_retouch.py  # 217 lines
│   │   ├── test_slicing.py  # 121 lines
│   │   ├── test_sprite_paths.py  # 52 lines
│   │   ├── test_sprite_source.py  # 101 lines
│   │   ├── test_sprite_timing.py  # 105 lines
│   │   ├── test_stabilize.py  # 188 lines
│   │   └── test_undo.py  # 71 lines
│   ├── styles/
│   │   ├── test_analyzer.py  # 131 lines
│   │   ├── test_analyzer_service.py  # 82 lines
│   │   ├── test_applicator.py  # 194 lines
│   │   ├── test_cli_style_create.py  # 111 lines
│   │   ├── test_cli_style_dispatch.py  # 38 lines
│   │   ├── test_cli_style_generation.py  # 113 lines
│   │   ├── test_cli_style_parser.py  # 35 lines
│   │   ├── test_cli_style_video.py  # 129 lines
│   │   ├── test_cli_style_zip.py  # 42 lines
│   │   ├── test_core_no_gui.py  # 22 lines
│   │   ├── test_layout_style_integration.py  # 15 lines
│   │   ├── test_store.py  # 195 lines
│   │   ├── test_store_zip.py  # 166 lines
│   │   ├── test_style_analysis_worker.py  # 62 lines
│   │   ├── test_style_manager_dialog.py  # 360 lines
│   │   ├── test_style_models.py  # 41 lines
│   │   ├── test_style_picker.py  # 105 lines
│   │   └── test_video_style_integration.py  # 43 lines
│   ├── video/
│   │   ├── test_cli_video_config.py  # 110 lines
│   │   ├── test_cli_video_dispatch.py  # 78 lines
│   │   ├── test_cli_video_parser.py  # 55 lines
│   │   ├── test_cli_video_report.py  # 118 lines
│   │   ├── test_last_project_tracking.py  # 183 lines
│   │   ├── test_omni_cancel_hook.py  # 108 lines
│   │   ├── test_omni_client.py  # 477 lines
│   │   ├── test_project_reanchor.py  # 163 lines
│   │   ├── test_veo_cancel_hook.py  # 121 lines
│   │   ├── test_video_paths.py  # 130 lines
│   │   └── test_video_provider_persistence.py  # 128 lines
│   ├── conftest.py  # 67 lines
│   ├── test_cli_image_sidecars.py  # 155 lines
│   ├── test_config_data_roots.py  # 718 lines
│   ├── test_config_io.py  # 447 lines
│   ├── test_google_sizing.py  # 191 lines
│   ├── test_live_llm_params.py  # 257 lines
│   ├── test_llm_params.py  # 280 lines
│   ├── test_logging_redaction.py  # 186 lines
│   ├── test_no_hardcoded_paths.py  # 90 lines
│   ├── test_paths.py  # 551 lines
│   ├── test_provider_cache.py  # 355 lines
│   ├── test_readme_help_anchors.py  # 73 lines
│   └── test_utils_sidecar.py  # 57 lines
├── tools/
│   ├── generate_code_map.py  # 239 lines
├── utils/
│   ├── README.md  # 90 lines
│   ├── diagnose_references.py  # 116 lines
│   ├── recover_reference_metadata.py  # 286 lines
│   ├── test_paths.py  # 56 lines
│   ├── update_history_from_logs.py  # 321 lines
│   └── update_reference_metadata.py  # 282 lines
├── weights/
│   ├── character_animator/
├── AGENTS.md  # 73 lines
├── CHANGELOG.md  # 1832 lines
├── CLAUDE.md  # 6 lines
├── COMMIT_MESSAGE.txt  # 32 lines
├── CONTRIBUTING.md  # 62 lines
├── GEMINI.md  # 5 lines
├── Popular_Image_Prompts.md  # 47 lines
├── README.md  # 2965 lines
├── REFACTORING_NOTES.md  # 110 lines
├── Reference Image Prompts.md  # 19 lines
├── __init__.py  # 34 lines
├── check_avif_support.py  # 99 lines
├── check_durations.py  # 33 lines
├── diagnose_ollama.py  # 66 lines
├── diagnose_qt_multimedia.py  # 237 lines
├── download_models.py  # 161 lines
├── download_social_icons.py  # 173 lines
├── extract_all_last_frames.py  # 223 lines
├── imageai_codemap_agent.md  # 254 lines
├── install_log.txt  # 20 lines
├── main.py  # 269 lines # Main entry point
├── main_original.py  # 2646 lines
├── migrate_config.py  # 179 lines
├── migrate_history.py  # 304 lines
├── requirements-local-sd.txt  # 15 lines
├── requirements-sprite-ml.txt  # 8 lines
├── requirements.txt  # 57 lines
├── secure_keys.py  # 106 lines
├── test_aspect_ratio.py  # 59 lines
├── test_auth_mode.py  # 66 lines
├── test_enhanced_dialog_focus.py  # 61 lines
├── test_imagen_customization.py  # 450 lines
├── test_layout_phase1.py  # 236 lines
├── test_layout_phase2.py  # 369 lines
├── test_lyrics.txt  # 4 lines
├── test_ollama.py  # 202 lines
├── test_phase3_templates.py  # 296 lines
├── test_prompt_dialog_focus.py  # 59 lines
├── test_scaling.py  # 82 lines
├── test_tempo_descriptors.py  # 159 lines
├── test_veo_batching.py  # 177 lines
├── test_veo_duration_prompts.py  # 187 lines
└── verify_ollama_ui.py  # 117 lines
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
- `core\layout\template_io.py`
  - functions: export_template, import_template
- `core\video\midi_utils.py`
  - functions: check_midi_available, get_midi_processor
- `gui\layout\prompt_worker.py`
  - classes: PromptSuggestWorker
- `core\layout\fill_plan.py`
  - classes: FillPlan
- `core\project_tracker.py`
  - functions: set_current_project, copy_project_on_exit
- `gui\common\splitter_style.py`
  - functions: apply_splitter_style
- `core\sprite\ml_install.py`
  - functions: python_supports_rembg, sprite_ml_packages, requirements_file, parse_requirements
- `gui\layout\history_window.py`
  - classes: HistoryWindow
- `gui\layout\font_loader.py`
  - classes: FontLoader
  - functions: cached_families, _enumerate
- `core\layout\project_io.py`
  - functions: save_project, _resolve_image_refs, load_project
- `gui\sprite\export_formats.py`
  - functions: _stem, write_godot_tres, write_aseprite_native, register_extra_formats
- `core\layout\page_sizes.py`
  - functions: to_inches, preset_to_page_size, parse_size_text, load_custom_sizes, save_custom_size
- `core\sprite\generation\_common.py`
  - functions: emit, now_iso, redact_secrets
- `gui\common\markdown_tables.py`
  - functions: parse_markdown_table, extract_resolution_px
- `core\layout\history.py`
  - classes: History
- `core\layout\geometry.py`
  - functions: validate_segments, segments_bbox, translate_segments
- `core\model_registry\__init__.py`
  - functions: resolve, get_registry, context_window, available
- `core\sprite\exporters\texturepacker_json.py`
  - functions: frame_key, _frame_entry, texturepacker_document, export_texturepacker_json
- `core\sprite\project_copy.py`
  - functions: copy_project
- `gui\sprite\prefs.py`
  - functions: sprite_settings, _as_bool, get_pref, set_pref, purge_after_export_enabled, set_purge_after_export, confirm_purge
- `core\layout\text_path.py`
  - functions: validate_text_path, default_text_path, glyph_offsets
- `providers\video\__init__.py`
  - classes: LipSyncBackend
  - functions: get_lipsync_provider, get_available_lipsync_backends
- `core\image_size.py`
  - functions: validate_custom_size, parse_size_string
- `core\layout\overlay_ops.py`
  - functions: _bbox_contains, _bbox_center, overlay_anchor_stranded, nearest_region_center, reposition_stranded_overlays
- `gui\sprite\retouch_wiring.py`
  - functions: apply_retouch, open_retouch_dialog, install_retouch
- `core\sprite\exporters\aseprite_json.py`
  - functions: frame_key, _frame_entry, aseprite_document, export_aseprite_json
- `core\layout\styles.py`
  - functions: _role, default_style_for, effective_text_style
- `core\styles\models.py`
  - classes: StyleDescriptor, Style
- `core\sprite\undo.py`
  - classes: FrameListSnapshot, SnapshotStack
- `gui\sprite\project_dialog.py`
  - classes: SpriteProjectDialog
- `core\sprite\presets.py`
  - functions: parse_cell_size, format_cell_size, integer_scale, integer_scale_table
- `core\video\continuity_helper.py`
  - classes: ContinuityHelper
  - functions: get_continuity_helper
- `gui\utils\stderr_suppressor.py`
  - classes: SuppressStderr
- `gui\sprite\engine_preset_box.py`
  - classes: EnginePresetBox
  - functions: install_engine_presets
- `core\sprite\generation\prompts.py`
  - functions: _parse_hex, normalize_hex, color_name, strip_render_terms, inject_chroma, background_prompt
- `gui\layout\style_panel.py`
  - classes: StylePanel
- `gui\sprite\shortcuts.py`
  - functions: resolve_target, _shortcut_parent, install_shortcuts
- `gui\layout\canvas_widget.py`
  - classes: CanvasWidget
- `gui\sprite\undo_controller.py`
  - classes: UndoController
- `gui\styles\style_picker.py`
  - classes: StylePickerWidget

## Notes
- Refer to this map to quickly locate functions, classes, and modules.
- Line counts approximate; regenerate after refactors.