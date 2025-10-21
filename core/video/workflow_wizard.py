"""
Video Generation Workflow Wizard

This module provides a smart, resumable wizard system for guiding users through
the video generation process. It tracks progress and suggests next steps based
on what's available in the project.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from .project import VideoProject, Scene, SceneStatus


class WorkflowStep(Enum):
    """Steps in the video generation workflow"""
    INPUT_TEXT = "input_text"
    MIDI_FILE = "midi_file"  # Optional
    AUDIO_FILE = "audio_file"  # Optional
    GENERATE_STORYBOARD = "generate_storyboard"
    ENHANCE_PROMPTS = "enhance_prompts"  # Optional
    GENERATE_MEDIA = "generate_media"  # Images or videos
    REVIEW_APPROVE = "review_approve"
    EXPORT_VIDEO = "export_video"


class StepStatus(Enum):
    """Status of a workflow step"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OPTIONAL_SKIPPED = "optional_skipped"


@dataclass
class WorkflowStepInfo:
    """Information about a workflow step"""
    step: WorkflowStep
    status: StepStatus
    title: str
    description: str
    is_optional: bool = False
    is_blocking: bool = True  # Must complete before moving to next step
    help_text: Optional[str] = None
    estimated_time: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "step": self.step.value,
            "status": self.status.value,
            "title": self.title,
            "description": self.description,
            "is_optional": self.is_optional,
            "is_blocking": self.is_blocking,
            "help_text": self.help_text,
            "estimated_time": self.estimated_time
        }


class WorkflowWizard:
    """
    Smart wizard for video generation workflow.

    Tracks progress through steps and provides contextual guidance based
    on project state. Fully resumable - analyzes project to determine
    current step.
    """

    # Step definitions with user-friendly information
    STEP_DEFINITIONS = {
        WorkflowStep.INPUT_TEXT: WorkflowStepInfo(
            step=WorkflowStep.INPUT_TEXT,
            status=StepStatus.NOT_STARTED,
            title="1. Input Text/Lyrics",
            description="Add the text or lyrics you want to turn into a video",
            is_optional=False,
            is_blocking=True,
            help_text=(
                "Enter your lyrics or text line-by-line. Each line will become a scene in your video.\n\n"
                "**Formats Supported:**\n"
                "- Plain text (one line per scene)\n"
                "- Timestamped lyrics (e.g., [00:12.50]Line text)\n"
                "- Structured sections (e.g., [Verse], [Chorus])\n\n"
                "**Tip:** Use clear, descriptive phrases that will work well for image generation."
            ),
            estimated_time="2-5 minutes"
        ),

        WorkflowStep.MIDI_FILE: WorkflowStepInfo(
            step=WorkflowStep.MIDI_FILE,
            status=StepStatus.NOT_STARTED,
            title="2. MIDI File (Optional)",
            description="Upload a MIDI file for precise music synchronization",
            is_optional=True,
            is_blocking=False,
            help_text=(
                "Upload a MIDI file that matches your audio track for:\n"
                "- Precise beat and measure timing\n"
                "- Automatic scene duration alignment\n"
                "- Karaoke-style lyric overlays\n\n"
                "**If you skip this:** Scene durations will be calculated based on your timing preset "
                "(fast, medium, slow).\n\n"
                "**Tip:** MIDI files can be created from audio using tools like AnthemScore or Basic Pitch."
            ),
            estimated_time="1 minute"
        ),

        WorkflowStep.AUDIO_FILE: WorkflowStepInfo(
            step=WorkflowStep.AUDIO_FILE,
            status=StepStatus.NOT_STARTED,
            title="3. Audio Track (Optional)",
            description="Upload audio/music to accompany your video",
            is_optional=True,
            is_blocking=False,
            help_text=(
                "Upload an audio file (MP3, WAV, etc.) to add music to your video.\n\n"
                "**Supported Formats:** MP3, WAV, OGG, FLAC, M4A\n\n"
                "**If you skip this:** Video will be generated without music. "
                "You can add audio later in video editing software.\n\n"
                "**Tip:** For best results, use a MIDI file that matches your audio track."
            ),
            estimated_time="1 minute"
        ),

        WorkflowStep.GENERATE_STORYBOARD: WorkflowStepInfo(
            step=WorkflowStep.GENERATE_STORYBOARD,
            status=StepStatus.NOT_STARTED,
            title="4. Generate Storyboard",
            description="Create scenes from your input text with timing",
            is_optional=False,
            is_blocking=True,
            help_text=(
                "Click 'Generate Storyboard' to:\n"
                "- Parse your input text into individual scenes\n"
                "- Calculate scene durations (using MIDI if available, or timing preset)\n"
                "- Create initial image generation prompts\n\n"
                "**With MIDI:** Scenes will align to musical measures/beats\n"
                "**Without MIDI:** Scenes will use even timing based on preset\n\n"
                "**After Generation:** You can review, edit, and reorder scenes before proceeding."
            ),
            estimated_time="<10 seconds"
        ),

        WorkflowStep.ENHANCE_PROMPTS: WorkflowStepInfo(
            step=WorkflowStep.ENHANCE_PROMPTS,
            status=StepStatus.NOT_STARTED,
            title="5. Enhance Prompts (Optional)",
            description="Use AI to enhance prompts for better image generation",
            is_optional=True,
            is_blocking=False,
            help_text=(
                "Use an LLM (GPT-4, Claude, Gemini) to enhance your prompts with:\n"
                "- Rich visual descriptions\n"
                "- Cinematic details\n"
                "- Consistent style across scenes\n\n"
                "**If you skip this:** You can generate with basic prompts, or enhance manually.\n\n"
                "**Requirements:** API key for your chosen LLM provider.\n\n"
                "**Tip:** Enhanced prompts usually produce significantly better results."
            ),
            estimated_time="30-60 seconds"
        ),

        WorkflowStep.GENERATE_MEDIA: WorkflowStepInfo(
            step=WorkflowStep.GENERATE_MEDIA,
            status=StepStatus.NOT_STARTED,
            title="6. Generate Images/Videos",
            description="Generate images or video clips for each scene",
            is_optional=False,
            is_blocking=True,
            help_text=(
                "Click 'Generate Video Prompts' to create visuals for your scenes.\n\n"
                "**Generation Options:**\n"
                "- **Images (Gemini/DALL-E):** Fast, cheaper - combine with Ken Burns effect\n"
                "- **Video Clips (Veo 3):** Native motion, higher quality, more expensive\n\n"
                "**For Veo 3 Videos:**\n"
                "- Durations are automatically set to 4, 6, or 8 seconds based on MIDI timing\n"
                "- With MIDI sync, clips align to musical measures\n"
                "- Generate multiple variants per scene for review\n\n"
                "**Estimated Time:** Varies by provider\n"
                "- Images: 5-30 seconds per scene\n"
                "- Veo videos: 1-6 minutes per scene"
            ),
            estimated_time="Varies (5 min - 2 hours)"
        ),

        WorkflowStep.REVIEW_APPROVE: WorkflowStepInfo(
            step=WorkflowStep.REVIEW_APPROVE,
            status=StepStatus.NOT_STARTED,
            title="7. Review & Approve",
            description="Review generated content and select favorites",
            is_optional=False,
            is_blocking=True,
            help_text=(
                "Review each scene's generated images/videos:\n\n"
                "**Actions Available:**\n"
                "- Approve best variant for each scene\n"
                "- Regenerate scenes you're not happy with\n"
                "- Edit prompts and re-generate specific scenes\n"
                "- Reorder scenes if needed\n\n"
                "**Tip:** You must approve at least one variant per scene before exporting.\n\n"
                "**Quality Check:** Preview the timeline to see how scenes flow together."
            ),
            estimated_time="5-15 minutes"
        ),

        WorkflowStep.EXPORT_VIDEO: WorkflowStepInfo(
            step=WorkflowStep.EXPORT_VIDEO,
            status=StepStatus.NOT_STARTED,
            title="8. Export Final Video",
            description="Render and export your finished video",
            is_optional=False,
            is_blocking=False,
            help_text=(
                "Click 'Export Video' to render your final output.\n\n"
                "**Export Options:**\n"
                "- Resolution: 720p, 1080p, 4K\n"
                "- Video codec: H.264, H.265\n"
                "- Quality preset: Fast, Medium, Slow\n"
                "- Add karaoke overlay (if MIDI available)\n\n"
                "**Output Files:**\n"
                "- Final video (.mp4)\n"
                "- Lyric files (.lrc, .srt, .ass) if karaoke enabled\n"
                "- Project file (.iaproj.json) for future editing\n\n"
                "**Estimated Time:** 1-10 minutes depending on video length and quality settings"
            ),
            estimated_time="1-10 minutes"
        )
    }

    def __init__(self, project: VideoProject):
        """
        Initialize workflow wizard with a video project.

        Args:
            project: Video project to track workflow for
        """
        self.project = project
        self.logger = logging.getLogger(__name__)

        # Analyze project to determine current state
        self._analyze_project_state()

    def _analyze_project_state(self):
        """
        Analyze project to determine which steps are completed and what's next.

        This makes the workflow fully resumable - user can close and reopen
        the project and pick up where they left off.
        """
        self.logger.info("Analyzing project state for workflow wizard")

        # Create fresh step info dictionary
        self.steps = {step: WorkflowStepInfo(**info.__dict__)
                     for step, info in self.STEP_DEFINITIONS.items()}

        # Check INPUT_TEXT
        if self.project.input_text and self.project.input_text.strip():
            self.steps[WorkflowStep.INPUT_TEXT].status = StepStatus.COMPLETED
            self.logger.debug("✓ Input text present")

        # Check MIDI_FILE (optional)
        if self.project.midi_file_path and self.project.midi_file_path.exists():
            self.steps[WorkflowStep.MIDI_FILE].status = StepStatus.COMPLETED
            self.logger.debug("✓ MIDI file uploaded")
        elif self.steps[WorkflowStep.INPUT_TEXT].status == StepStatus.COMPLETED:
            # User has input but no MIDI - either skipped or not reached yet
            # We'll mark as skipped if they've moved past storyboard generation
            if len(self.project.scenes) > 0:
                self.steps[WorkflowStep.MIDI_FILE].status = StepStatus.OPTIONAL_SKIPPED
                self.logger.debug("- MIDI file skipped")

        # Check AUDIO_FILE (optional)
        if self.project.audio_tracks and self.project.audio_tracks[0].file_path:
            if self.project.audio_tracks[0].file_path.exists():
                self.steps[WorkflowStep.AUDIO_FILE].status = StepStatus.COMPLETED
                self.logger.debug("✓ Audio file uploaded")
        elif len(self.project.scenes) > 0:
            self.steps[WorkflowStep.AUDIO_FILE].status = StepStatus.OPTIONAL_SKIPPED
            self.logger.debug("- Audio file skipped")

        # Check GENERATE_STORYBOARD
        if len(self.project.scenes) > 0:
            self.steps[WorkflowStep.GENERATE_STORYBOARD].status = StepStatus.COMPLETED
            self.logger.debug(f"✓ Storyboard generated ({len(self.project.scenes)} scenes)")

        # Check ENHANCE_PROMPTS (optional - check if prompts look enhanced)
        if len(self.project.scenes) > 0:
            # Heuristic: enhanced prompts are typically longer and more detailed
            avg_prompt_length = sum(len(s.prompt) for s in self.project.scenes) / len(self.project.scenes)
            if avg_prompt_length > 100:  # Arbitrary threshold
                self.steps[WorkflowStep.ENHANCE_PROMPTS].status = StepStatus.COMPLETED
                self.logger.debug("✓ Prompts appear enhanced")
            else:
                self.steps[WorkflowStep.ENHANCE_PROMPTS].status = StepStatus.OPTIONAL_SKIPPED
                self.logger.debug("- Prompts not enhanced")

        # Check GENERATE_MEDIA
        scenes_with_media = sum(1 for s in self.project.scenes
                               if s.images or s.video_clip)
        if scenes_with_media == len(self.project.scenes) and len(self.project.scenes) > 0:
            self.steps[WorkflowStep.GENERATE_MEDIA].status = StepStatus.COMPLETED
            self.logger.debug(f"✓ Media generated for all {len(self.project.scenes)} scenes")
        elif scenes_with_media > 0:
            self.steps[WorkflowStep.GENERATE_MEDIA].status = StepStatus.IN_PROGRESS
            self.logger.debug(f"⚠ Media generated for {scenes_with_media}/{len(self.project.scenes)} scenes")

        # Check REVIEW_APPROVE
        scenes_approved = sum(1 for s in self.project.scenes if s.approved_image or s.video_clip)
        if scenes_approved == len(self.project.scenes) and len(self.project.scenes) > 0:
            self.steps[WorkflowStep.REVIEW_APPROVE].status = StepStatus.COMPLETED
            self.logger.debug(f"✓ All {len(self.project.scenes)} scenes approved")
        elif scenes_approved > 0:
            self.steps[WorkflowStep.REVIEW_APPROVE].status = StepStatus.IN_PROGRESS
            self.logger.debug(f"⚠ {scenes_approved}/{len(self.project.scenes)} scenes approved")

        # Check EXPORT_VIDEO
        if self.project.export_path and self.project.export_path.exists():
            self.steps[WorkflowStep.EXPORT_VIDEO].status = StepStatus.COMPLETED
            self.logger.debug(f"✓ Video exported to {self.project.export_path}")

    def get_current_step(self) -> WorkflowStep:
        """
        Get the current/next step user should work on.

        Returns:
            Next incomplete required step, or last step if all complete
        """
        for step in WorkflowStep:
            step_info = self.steps[step]

            # Skip optional steps that were skipped
            if step_info.status == StepStatus.OPTIONAL_SKIPPED:
                continue

            # Return first not-started or in-progress step
            if step_info.status in [StepStatus.NOT_STARTED, StepStatus.IN_PROGRESS]:
                return step

        # All steps complete
        return WorkflowStep.EXPORT_VIDEO

    def get_next_action(self) -> Dict[str, Any]:
        """
        Get suggested next action for user with helpful context.

        Returns:
            Dictionary with action details:
            - step: Current/next workflow step
            - action: What user should do
            - button_text: Suggested button label
            - can_proceed: Whether user can move to next step
            - blocking_reason: Why user is blocked (if applicable)
        """
        current_step = self.get_current_step()
        step_info = self.steps[current_step]

        action_info = {
            "step": current_step.value,
            "step_title": step_info.title,
            "action": step_info.description,
            "help_text": step_info.help_text,
            "estimated_time": step_info.estimated_time,
            "is_optional": step_info.is_optional,
            "button_text": self._get_button_text(current_step),
            "can_proceed": self._can_proceed(current_step),
            "blocking_reason": self._get_blocking_reason(current_step),
            "progress_percent": self._calculate_progress(),
            "choices": self._get_step_choices(current_step)
        }

        return action_info

    def _get_button_text(self, step: WorkflowStep) -> str:
        """Get appropriate button text for a step"""
        button_texts = {
            WorkflowStep.INPUT_TEXT: "Continue to MIDI/Audio →",
            WorkflowStep.MIDI_FILE: "Upload MIDI File (or Skip)",
            WorkflowStep.AUDIO_FILE: "Upload Audio File (or Skip)",
            WorkflowStep.GENERATE_STORYBOARD: "Generate Storyboard",
            WorkflowStep.ENHANCE_PROMPTS: "Enhance with AI (or Skip)",
            WorkflowStep.GENERATE_MEDIA: "Generate Video Prompts",
            WorkflowStep.REVIEW_APPROVE: "Review Scenes",
            WorkflowStep.EXPORT_VIDEO: "Export Final Video"
        }
        return button_texts.get(step, "Continue")

    def _can_proceed(self, step: WorkflowStep) -> bool:
        """Check if user can proceed from current step"""
        step_info = self.steps[step]

        # Completed or skipped steps can be proceeded from
        if step_info.status in [StepStatus.COMPLETED, StepStatus.OPTIONAL_SKIPPED]:
            return True

        # Optional in-progress steps can be skipped
        if not step_info.is_blocking and step_info.is_optional:
            return True

        # Required steps must be completed
        return False

    def _get_blocking_reason(self, step: WorkflowStep) -> Optional[str]:
        """Get reason why user is blocked at this step"""
        step_info = self.steps[step]

        if step_info.status == StepStatus.COMPLETED:
            return None

        blocking_reasons = {
            WorkflowStep.INPUT_TEXT: "Please enter your lyrics or text to continue",
            WorkflowStep.GENERATE_STORYBOARD: "Please generate storyboard from your input text",
            WorkflowStep.GENERATE_MEDIA: "Please generate images or videos for your scenes",
            WorkflowStep.REVIEW_APPROVE: "Please review and approve at least one variant per scene"
        }

        return blocking_reasons.get(step)

    def _calculate_progress(self) -> int:
        """Calculate overall workflow progress percentage"""
        # Weight required steps more heavily than optional
        total_weight = 0
        completed_weight = 0

        for step, info in self.steps.items():
            weight = 2 if not info.is_optional else 1
            total_weight += weight

            if info.status == StepStatus.COMPLETED:
                completed_weight += weight
            elif info.status == StepStatus.IN_PROGRESS:
                completed_weight += weight * 0.5
            elif info.status == StepStatus.OPTIONAL_SKIPPED:
                completed_weight += weight  # Count skipped optional as complete

        return int((completed_weight / total_weight) * 100)

    def _get_step_choices(self, step: WorkflowStep) -> Optional[Dict[str, Any]]:
        """
        Get user choices available at this step.

        Returns explanations for different paths user can take.
        """
        choices = {}

        if step == WorkflowStep.MIDI_FILE:
            choices = {
                "upload": {
                    "label": "Upload MIDI File",
                    "description": "For precise music synchronization and karaoke",
                    "benefits": [
                        "Scene durations align to musical measures/beats",
                        "Enable karaoke-style lyric overlays",
                        "Better sync for music videos"
                    ]
                },
                "skip": {
                    "label": "Skip (Use Timing Preset)",
                    "description": "Scenes will use even timing based on preset",
                    "benefits": [
                        "Faster - no MIDI required",
                        "Good for non-musical content",
                        "Can add music later in editing"
                    ]
                }
            }

        elif step == WorkflowStep.AUDIO_FILE:
            choices = {
                "upload": {
                    "label": "Upload Audio File",
                    "description": "Add music or narration to your video",
                    "benefits": [
                        "Final video includes soundtrack",
                        "Can trim/fade audio in export",
                        "Volume control available"
                    ]
                },
                "skip": {
                    "label": "Skip (Silent Video)",
                    "description": "Generate video without audio track",
                    "benefits": [
                        "Faster export",
                        "Add music later in video editor",
                        "Useful for previews"
                    ]
                }
            }

        elif step == WorkflowStep.ENHANCE_PROMPTS:
            choices = {
                "enhance": {
                    "label": "Enhance with AI",
                    "description": "Use LLM to create detailed, cinematic prompts",
                    "benefits": [
                        "Richer visual descriptions",
                        "Consistent style across scenes",
                        "Better image generation results"
                    ],
                    "requirements": ["API key for LLM provider (GPT-4, Claude, Gemini)"]
                },
                "skip": {
                    "label": "Use Basic Prompts",
                    "description": "Generate with your input text as prompts",
                    "benefits": [
                        "Faster - no LLM calls",
                        "Free (no LLM API costs)",
                        "You have full control over prompts"
                    ]
                }
            }

        elif step == WorkflowStep.GENERATE_MEDIA:
            choices = {
                "images": {
                    "label": "Generate Images (with Ken Burns)",
                    "description": "Create still images, add motion in post",
                    "benefits": [
                        "Fast generation (5-30s per scene)",
                        "Lower cost",
                        "Ken Burns effect adds motion"
                    ],
                    "providers": ["Gemini", "DALL-E", "Stability AI"]
                },
                "videos": {
                    "label": "Generate Video Clips (Veo 3)",
                    "description": "Native video with realistic motion",
                    "benefits": [
                        "Natural motion and camera work",
                        "Higher quality output",
                        "MIDI-synced durations (4, 6, or 8s)"
                    ],
                    "drawbacks": [
                        "Slower (1-6 min per scene)",
                        "Higher cost ($0.10/second)",
                        "Requires Google API key"
                    ]
                }
            }

        return choices if choices else None

    def get_all_steps(self) -> List[WorkflowStepInfo]:
        """Get all workflow steps with current status"""
        return [self.steps[step] for step in WorkflowStep]

    def mark_step_complete(self, step: WorkflowStep):
        """Manually mark a step as complete"""
        self.steps[step].status = StepStatus.COMPLETED
        self.logger.info(f"Marked step {step.value} as complete")

    def mark_step_skipped(self, step: WorkflowStep):
        """Mark an optional step as skipped"""
        if self.steps[step].is_optional:
            self.steps[step].status = StepStatus.OPTIONAL_SKIPPED
            self.logger.info(f"Skipped optional step {step.value}")
        else:
            raise ValueError(f"Cannot skip required step: {step.value}")

    def get_summary(self) -> str:
        """
        Get human-readable workflow summary.

        Returns:
            Multi-line string summarizing current progress
        """
        summary_lines = [
            f"Project: {self.project.name}",
            f"Progress: {self._calculate_progress()}%",
            "",
            "Status by Step:"
        ]

        for step in WorkflowStep:
            info = self.steps[step]
            status_symbol = {
                StepStatus.NOT_STARTED: "○",
                StepStatus.IN_PROGRESS: "◐",
                StepStatus.COMPLETED: "●",
                StepStatus.OPTIONAL_SKIPPED: "─"
            }.get(info.status, "?")

            optional_tag = " (optional)" if info.is_optional else ""
            summary_lines.append(f"  {status_symbol} {info.title}{optional_tag}")

        current_step = self.get_current_step()
        summary_lines.append("")
        summary_lines.append(f"Next Step: {self.steps[current_step].title}")
        summary_lines.append(f"Action: {self.steps[current_step].description}")

        return "\n".join(summary_lines)
