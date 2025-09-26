"""Midjourney Manual Provider - Generates Discord commands only."""

import logging
import webbrowser
import subprocess
import platform
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import io
from PIL import Image, ImageDraw, ImageFont

from .base import ImageProvider

logger = logging.getLogger(__name__)


class MidjourneyProvider(ImageProvider):
    """Midjourney provider - manual mode only, generates Discord commands."""

    # Track if we've shown the first-time message
    _first_time_shown = False

    def __init__(self, config: Dict[str, Any]):
        """Initialize Midjourney provider."""
        super().__init__(config)
        self.mode = "manual"
        self.last_command = None
        # You can customize these with your Midjourney server/channel IDs
        self.discord_server_id = config.get('discord_server_id', '662267976984297473')  # Official Midjourney server
        self.discord_channel_id = config.get('discord_channel_id', '')  # Add your channel ID

    def generate(self, prompt: str, **kwargs) -> bytes:
        """Generate a Discord command and instruction image.

        Args:
            prompt: The image generation prompt
            **kwargs: Additional parameters like model_version, aspect_ratio, etc.

        Returns:
            PNG image bytes with instructions
        """
        # Extract Midjourney-specific parameters
        model_version = kwargs.get('model_version', 'v7')
        aspect_ratio = kwargs.get('aspect_ratio', '1:1')
        stylize = kwargs.get('stylize', 100)
        chaos = kwargs.get('chaos', 0)
        weird = kwargs.get('weird', 0)
        quality = kwargs.get('quality', 1)
        seed = kwargs.get('seed', None)
        negative_prompt = kwargs.get('negative_prompt', None)

        # Build Midjourney command
        mj_params = []

        # Add negative prompt if provided
        if negative_prompt:
            prompt += f" --no {negative_prompt}"

        if aspect_ratio != '1:1':
            mj_params.append(f'--ar {aspect_ratio}')
        if stylize != 100:
            mj_params.append(f'--s {stylize}')
        if chaos > 0:
            mj_params.append(f'--chaos {chaos}')
        if weird > 0:
            mj_params.append(f'--weird {weird}')
        if quality != 1:
            mj_params.append(f'--q {quality}')
        if seed and seed >= 0:
            mj_params.append(f'--seed {seed}')
        # Always specify version (V7 is default but explicit is better)
        if model_version:
            # Handle version format (v7 -> --v 7, v6.1 -> --v 6.1, niji6 -> --niji 6)
            if model_version.startswith('niji'):
                version_num = model_version.replace('niji', '')
                mj_params.append(f'--niji {version_num}')
            else:
                version_num = model_version.replace('v', '')
                mj_params.append(f'--v {version_num}')

        full_prompt = f"{prompt} {' '.join(mj_params)}".strip()
        self.last_command = f"/imagine prompt: {full_prompt}"

        # Copy to clipboard
        self._copy_to_clipboard(self.last_command)

        # Open Discord (only show message first time)
        if not MidjourneyProvider._first_time_shown:
            MidjourneyProvider._first_time_shown = True
            logger.info("Midjourney: Command copied to clipboard. Opening Discord...")

        # Open Discord if we have channel info
        if self.discord_channel_id:
            self._open_discord_channel()
        else:
            self._open_discord()

        # Generate instruction image
        return self._generate_instruction_image(full_prompt)

    def _copy_to_clipboard(self, text: str):
        """Copy text to system clipboard."""
        system = platform.system()
        try:
            if system == "Windows":
                subprocess.run("clip", text=True, input=text, check=True)
            elif system == "Darwin":  # macOS
                subprocess.run("pbcopy", text=True, input=text, check=True)
            else:  # Linux
                # Try xclip first, then xsel, then wl-copy for Wayland
                clipboard_cmds = [
                    ["xclip", "-selection", "clipboard"],
                    ["xsel", "--clipboard", "--input"],
                    ["wl-copy"]
                ]
                for cmd in clipboard_cmds:
                    try:
                        subprocess.run(cmd, text=True, input=text, check=True)
                        break
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        continue
            logger.debug(f"Copied to clipboard: {text[:50]}...")
        except Exception as e:
            logger.warning(f"Could not copy to clipboard: {e}")

    def _open_discord(self):
        """Open Discord in browser."""
        url = "https://discord.com/channels/@me"
        try:
            webbrowser.open_new_tab(url)
            logger.debug("Opened Discord in browser")
        except Exception as e:
            logger.warning(f"Could not open Discord: {e}")

    def _open_discord_channel(self):
        """Open specific Discord channel."""
        url = f"https://discord.com/channels/{self.discord_server_id}/{self.discord_channel_id}"
        try:
            webbrowser.open_new_tab(url)
            logger.debug(f"Opened Discord channel: {self.discord_channel_id}")
        except Exception as e:
            logger.warning(f"Could not open Discord channel: {e}")
            self._open_discord()  # Fall back to general Discord

    def _generate_instruction_image(self, prompt: str) -> bytes:
        """Generate an instruction image showing the Discord command."""
        # Create instruction image
        width, height = 800, 600
        img = Image.new('RGB', (width, height), color='#2C2F33')  # Discord dark theme
        draw = ImageDraw.Draw(img)

        # Try to use nice fonts, fall back to default
        try:
            title_font = ImageFont.truetype("arial.ttf", 28)
            body_font = ImageFont.truetype("arial.ttf", 18)
            mono_font = ImageFont.truetype("consolas.ttf", 14)
        except:
            # Fall back to default font
            title_font = ImageFont.load_default()
            body_font = title_font
            mono_font = title_font

        y_pos = 30

        # Title with Midjourney branding colors
        draw.text((width//2, y_pos), "Midjourney Command Ready!",
                 fill='#FFFFFF', font=title_font, anchor='mt')
        y_pos += 60

        # Success message
        draw.text((width//2, y_pos), "✅ Command copied to clipboard",
                 fill='#57F287', font=body_font, anchor='mt')  # Discord green
        y_pos += 40

        draw.text((width//2, y_pos), "📋 Discord opened in your browser",
                 fill='#7289DA', font=body_font, anchor='mt')  # Discord blurple
        y_pos += 60

        # Instructions
        instructions = [
            "Instructions:",
            "1. Switch to Discord in your browser",
            "2. Navigate to a Midjourney bot channel",
            "3. Paste (Ctrl+V or Cmd+V) and press Enter",
        ]

        for instruction in instructions:
            draw.text((50, y_pos), instruction, fill='#FFFFFF', font=body_font)
            y_pos += 35

        y_pos += 20

        # Show the command in a box
        draw.text((50, y_pos), "Your command:", fill='#99AAB5', font=body_font)
        y_pos += 35

        # Command box with Discord styling
        box_margin = 40
        box_top = y_pos
        box_height = 80

        # Draw rounded rectangle for command
        draw.rounded_rectangle(
            [(box_margin, box_top), (width - box_margin, box_top + box_height)],
            radius=8,
            fill='#40444B',
            outline='#7289DA',
            width=2
        )

        # Wrap and display command
        command_text = self.last_command
        if len(command_text) > 80:
            # Wrap long commands
            lines = []
            words = command_text.split()
            current_line = []
            for word in words:
                test_line = ' '.join(current_line + [word])
                if len(test_line) > 75:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        lines.append(word)
                        current_line = []
                else:
                    current_line.append(word)
            if current_line:
                lines.append(' '.join(current_line))

            # Draw wrapped text
            text_y = box_top + 15
            for line in lines[:3]:  # Max 3 lines
                draw.text((box_margin + 15, text_y), line,
                         fill='#7289DA', font=mono_font)
                text_y += 20
        else:
            # Single line
            draw.text((box_margin + 15, box_top + 30), command_text,
                     fill='#7289DA', font=mono_font)

        y_pos = box_top + box_height + 40

        # Footer tip
        draw.text((width//2, height - 40),
                 "💡 Tip: Make sure you're in a Midjourney bot channel!",
                 fill='#FFA500', font=body_font, anchor='mt')

        # Convert to bytes
        output = io.BytesIO()
        img.save(output, format='PNG')
        return output.getvalue()

    def get_models(self):
        """Get list of supported Midjourney models."""
        return [
            "v7",      # Latest version as of June 2025
            "v6.1",
            "v6",
            "v5.2",
            "v5.1",
            "v5",
            "niji6",
            "niji5"
        ]

    def get_default_model(self):
        """Get the default model."""
        return "v7"  # V7 is now the default

    def validate_auth(self) -> Tuple[bool, str]:
        """Validate authentication - always valid for manual mode."""
        return True, "Midjourney manual mode ready - commands will be copied to clipboard"

    def get_last_command(self) -> Optional[str]:
        """Get the last generated Discord command."""
        return self.last_command