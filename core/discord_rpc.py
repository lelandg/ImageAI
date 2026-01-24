"""Discord Rich Presence integration for ImageAI.

This module provides Discord Rich Presence support, allowing users to display
their ImageAI activity in their Discord status (similar to how Steam shows games).

Features:
- Shows current activity (Generating, Idle, etc.)
- Displays provider and model being used
- Elapsed time tracking
- Privacy controls (full, activity_only, minimal)
- Graceful handling when Discord isn't running

Usage:
    from core.discord_rpc import discord_rpc

    # Enable and connect
    discord_rpc.set_enabled(True)

    # Update presence when generating
    discord_rpc.update_presence(
        ActivityState.GENERATING,
        provider="google",
        model="Gemini 2.5 Flash"
    )

    # Reset to idle
    discord_rpc.update_presence(ActivityState.IDLE)
"""

import logging
import threading
import time
from enum import Enum
from typing import Optional, Callable, List

from .constants import (
    DISCORD_CLIENT_ID,
    DISCORD_UPDATE_INTERVAL,
    DISCORD_GITHUB_URL,
    DISCORD_SERVER_URL,
    DISCORD_ASSETS,
    DISCORD_PRIVACY_LEVELS,
    APP_NAME,
    VERSION,
)

logger = logging.getLogger(__name__)

# Try to import pypresence - it's optional
try:
    from pypresence import Presence
    from pypresence.exceptions import DiscordNotFound, DiscordError
    PYPRESENCE_AVAILABLE = True
except ImportError:
    PYPRESENCE_AVAILABLE = False
    Presence = None
    DiscordNotFound = Exception
    DiscordError = Exception
    logger.info("pypresence not installed - Discord Rich Presence disabled")


class ActivityState(Enum):
    """Represents the user's current activity state in ImageAI."""
    IDLE = "idle"
    GENERATING = "generating"
    UPSCALING = "upscaling"
    EDITING = "editing"
    VIDEO_PROJECT = "video_project"
    BROWSING_HISTORY = "browsing_history"
    SETTINGS = "settings"
    CHARACTER_GENERATOR = "character_generator"  # In character animator/generator
    CHATTING_WITH_AI = "chatting_with_ai"        # Using LLM dialogs


# Human-readable activity descriptions
ACTIVITY_DESCRIPTIONS = {
    ActivityState.IDLE: "Idle",
    ActivityState.GENERATING: "Generating an image",
    ActivityState.UPSCALING: "Upscaling an image",
    ActivityState.EDITING: "Editing an image",
    ActivityState.VIDEO_PROJECT: "Working on video project",
    ActivityState.BROWSING_HISTORY: "Browsing image history",
    ActivityState.SETTINGS: "Configuring settings",
    ActivityState.CHARACTER_GENERATOR: "Creating character puppets",
    ActivityState.CHATTING_WITH_AI: "Chatting with AI",
}


class DiscordRPCManager:
    """Manages Discord Rich Presence connection and updates.

    This class handles all Discord RPC communication, including:
    - Connection management with automatic reconnection
    - Presence updates with rate limiting
    - Privacy level enforcement
    - Graceful error handling

    The manager is designed as a singleton - use the module-level `discord_rpc`
    instance rather than creating new instances.
    """

    def __init__(self):
        """Initialize the Discord RPC manager."""
        self._rpc: Optional[Presence] = None
        self._connected = False
        self._enabled = False
        self._session_start: Optional[int] = None
        self._current_state = ActivityState.IDLE
        self._current_provider = ""
        self._current_model = ""
        self._lock = threading.Lock()
        self._status_callbacks: List[Callable[[bool, str], None]] = []

        # Settings (will be loaded from config)
        self._privacy_level = "full"
        self._show_elapsed_time = True
        self._show_model = True
        self._show_buttons = True

        # Rate limiting
        self._last_update_time = 0

    @property
    def is_available(self) -> bool:
        """Check if Discord RPC is available (pypresence installed)."""
        return PYPRESENCE_AVAILABLE and bool(DISCORD_CLIENT_ID)

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to Discord."""
        return self._connected

    @property
    def is_enabled(self) -> bool:
        """Check if Discord RPC is enabled by user."""
        return self._enabled

    def add_status_callback(self, callback: Callable[[bool, str], None]) -> None:
        """Add a callback to be notified of connection status changes.

        Args:
            callback: Function that takes (connected: bool, message: str)
        """
        self._status_callbacks.append(callback)

    def remove_status_callback(self, callback: Callable[[bool, str], None]) -> None:
        """Remove a status callback."""
        if callback in self._status_callbacks:
            self._status_callbacks.remove(callback)

    def _notify_status(self, connected: bool, message: str) -> None:
        """Notify all callbacks of status change."""
        for callback in self._status_callbacks:
            try:
                callback(connected, message)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable Discord Rich Presence.

        Args:
            enabled: True to enable, False to disable
        """
        if enabled == self._enabled:
            return

        self._enabled = enabled

        if enabled:
            self.connect()
        else:
            self.disconnect()

    def configure(
        self,
        privacy_level: str = "full",
        show_elapsed_time: bool = True,
        show_model: bool = True,
        show_buttons: bool = True
    ) -> None:
        """Configure Discord RPC settings.

        Args:
            privacy_level: One of "full", "activity_only", "minimal"
            show_elapsed_time: Whether to show session elapsed time
            show_model: Whether to show model name (if privacy allows)
            show_buttons: Whether to show GitHub and Discord buttons
        """
        self._privacy_level = privacy_level
        self._show_elapsed_time = show_elapsed_time
        self._show_model = show_model
        self._show_buttons = show_buttons

        # Update presence with new settings if connected
        if self._connected:
            self._do_update()

    def connect(self) -> bool:
        """Establish connection to Discord.

        Returns:
            True if connection successful, False otherwise
        """
        if not self.is_available:
            if not PYPRESENCE_AVAILABLE:
                logger.info("pypresence not installed - cannot connect to Discord")
                self._notify_status(False, "pypresence not installed")
            elif not DISCORD_CLIENT_ID:
                logger.info("Discord Client ID not configured")
                self._notify_status(False, "Client ID not configured")
            return False

        with self._lock:
            if self._connected:
                return True

            try:
                self._rpc = Presence(DISCORD_CLIENT_ID)
                self._rpc.connect()
                self._connected = True
                self._session_start = int(time.time())

                logger.info("Connected to Discord Rich Presence")
                self._notify_status(True, "Connected to Discord")

                # Send initial presence
                self._do_update()

                return True

            except DiscordNotFound:
                logger.info("Discord not running - Rich Presence unavailable")
                self._notify_status(False, "Discord not running")
                self._rpc = None
                return False

            except DiscordError as e:
                logger.warning(f"Discord RPC error: {e}")
                self._notify_status(False, f"Connection error: {e}")
                self._rpc = None
                return False

            except Exception as e:
                logger.error(f"Unexpected error connecting to Discord: {e}")
                self._notify_status(False, f"Error: {e}")
                self._rpc = None
                return False

    def disconnect(self) -> None:
        """Disconnect from Discord."""
        with self._lock:
            if self._rpc is not None:
                try:
                    self._rpc.clear()
                    self._rpc.close()
                except Exception as e:
                    logger.debug(f"Error during disconnect: {e}")
                finally:
                    self._rpc = None

            self._connected = False
            self._session_start = None
            logger.info("Disconnected from Discord Rich Presence")
            self._notify_status(False, "Disconnected")

    def update_presence(
        self,
        state: ActivityState,
        provider: str = "",
        model: str = "",
        details: str = "",
        batch_progress: Optional[tuple] = None
    ) -> None:
        """Update Discord presence with current activity.

        Args:
            state: Current activity state
            provider: Provider name (e.g., "google", "openai")
            model: Model name (e.g., "Gemini 2.5 Flash")
            details: Optional additional details
            batch_progress: Optional tuple of (current, total) for batch operations
        """
        self._current_state = state
        self._current_provider = provider
        self._current_model = model
        logger.debug(f"Updating presence: {state.value}, {provider}, {model}")

        if not self._enabled or not self._connected:
            logger.debug(f"[Discord RPC] Skipping update - enabled={self._enabled}, connected={self._connected}")
            return

        # Rate limiting
        now = time.time()
        time_since_last = now - self._last_update_time
        if time_since_last < DISCORD_UPDATE_INTERVAL:
            logger.info(f"[Discord RPC] RATE LIMITED: State '{state.value}' blocked. "
                       f"Only {time_since_last:.1f}s since last update (need {DISCORD_UPDATE_INTERVAL}s)")
            return

        self._do_update(details, batch_progress)

    def _do_update(
        self,
        extra_details: str = "",
        batch_progress: Optional[tuple] = None
    ) -> None:
        """Internal method to perform the actual presence update."""
        if not self._connected or self._rpc is None:
            return

        self._last_update_time = time.time()

        try:
            # Build presence data based on privacy level
            update_kwargs = self._build_presence_data(extra_details, batch_progress)

            # Log what we're sending to Discord
            logger.info(f"[Discord RPC] Sending update to Discord...")
            logger.info(f"[Discord RPC] Client ID: {DISCORD_CLIENT_ID}")

            # Capture Discord's response
            response = self._rpc.update(**update_kwargs)
            if response:
                logger.info(f"[Discord RPC] Discord Response: {response}")
                # Check if response indicates success or failure
                if isinstance(response, dict):
                    if response.get('assets'):
                        assets = response['assets']
                        logger.info(f"[Discord RPC] Discord confirmed assets:")
                        logger.info(f"  - large_image: {assets.get('large_image', '(not returned)')}")
                        logger.info(f"  - small_image: {assets.get('small_image', '(not returned)')}")
            logger.info(f"[Discord RPC] Presence updated successfully: {self._current_state.value}")

        except DiscordError as e:
            logger.warning(f"Failed to update Discord presence: {e}")
            # Try to reconnect on next update
            self._connected = False
            self._notify_status(False, "Connection lost")

        except Exception as e:
            logger.error(f"Unexpected error updating presence: {e}")

    def _build_presence_data(
        self,
        extra_details: str = "",
        batch_progress: Optional[tuple] = None
    ) -> dict:
        """Build the presence data dictionary based on current settings.

        Returns:
            Dictionary of kwargs for RPC.update()
        """
        data = {}

        # === LARGE IMAGE RESOLUTION ===
        # Check for activity-specific image first, then fall back to default
        activity_assets = DISCORD_ASSETS.get("activities", {})
        default_large_image = DISCORD_ASSETS.get("large_image", "")
        activity_specific_image = activity_assets.get(self._current_state.value)

        # Log the image resolution process
        logger.info(f"[Discord RPC] Image Resolution for state '{self._current_state.value}':")
        logger.info(f"  - Activity-specific assets configured: {list(activity_assets.keys())}")
        logger.info(f"  - Activity '{self._current_state.value}' specific image: {activity_specific_image or '(none)'}")
        logger.info(f"  - Default large_image: '{default_large_image}'")

        # Use activity-specific image if available, otherwise fall back to default
        if activity_specific_image:
            large_image_key = activity_specific_image
            logger.info(f"  → Using ACTIVITY-SPECIFIC image: '{large_image_key}'")
        else:
            large_image_key = default_large_image
            logger.info(f"  → Using DEFAULT image: '{large_image_key}'")

        if large_image_key:
            data["large_image"] = large_image_key
            data["large_text"] = f"{APP_NAME} v{VERSION}"
            logger.info(f"[Discord RPC] large_image = '{large_image_key}' (must exist in Discord Developer Portal → Rich Presence → Art Assets)")
        else:
            # No custom asset - Discord will use the App Icon from General Information
            logger.warning("[Discord RPC] No large_image configured - Discord will use App Icon from General Information")
            data["large_text"] = f"{APP_NAME} v{VERSION}"

        # Privacy level: minimal - just show we're using ImageAI
        if self._privacy_level == "minimal":
            data["details"] = "Using ImageAI"
            if self._show_elapsed_time and self._session_start:
                data["start"] = self._session_start
            return data

        # Activity description (details line)
        activity_desc = ACTIVITY_DESCRIPTIONS.get(
            self._current_state,
            "Using ImageAI"
        )

        # For AI dialogs, use "AI <dialog name>" format (e.g., "AI Prompt Enhancer")
        if extra_details:
            if self._current_state == ActivityState.CHATTING_WITH_AI:
                activity_desc = f"AI {extra_details}"
            else:
                activity_desc = f"{activity_desc}: {extra_details}"

        # Add batch progress if available
        if batch_progress and batch_progress[1] > 1:
            current, total = batch_progress
            activity_desc = f"{activity_desc} ({current}/{total})"

        data["details"] = activity_desc

        # Privacy level: activity_only - show activity but not provider/model
        if self._privacy_level == "activity_only":
            if self._show_elapsed_time and self._session_start:
                data["start"] = self._session_start
            return data

        # Privacy level: full - show everything
        # State line (provider and model)
        state_parts = []

        if self._current_provider:
            provider_display = self._current_provider.replace("_", " ").title()
            if provider_display == "Local Sd":
                provider_display = "Local SD"
            state_parts.append(f"Using {provider_display}")

            # === SMALL IMAGE (PROVIDER) RESOLUTION ===
            provider_assets = DISCORD_ASSETS.get("providers", {})
            provider_asset = provider_assets.get(self._current_provider)

            logger.info(f"[Discord RPC] Provider Image Resolution for '{self._current_provider}':")
            logger.info(f"  - Available provider assets: {provider_assets}")
            logger.info(f"  - Provider '{self._current_provider}' asset: {provider_asset or '(none)'}")

            if provider_asset:
                data["small_image"] = provider_asset
                data["small_text"] = provider_display
                logger.info(f"[Discord RPC] small_image = '{provider_asset}' (must exist in Discord Developer Portal → Rich Presence → Art Assets)")
            else:
                logger.warning(f"[Discord RPC] No small_image configured for provider '{self._current_provider}'")

        if self._show_model and self._current_model:
            # Shorten model name if needed
            model_display = self._current_model
            if len(model_display) > 30:
                model_display = model_display[:27] + "..."
            state_parts.append(model_display)

        if state_parts:
            data["state"] = " - ".join(state_parts)

        # Elapsed time
        if self._show_elapsed_time and self._session_start:
            data["start"] = self._session_start

        # Buttons (GitHub + Discord server) - max 2 allowed
        if self._show_buttons:
            data["buttons"] = [
                {"label": "GitHub", "url": DISCORD_GITHUB_URL},
                {"label": "Join Discord", "url": DISCORD_SERVER_URL}
            ]

        # === FINAL SUMMARY ===
        logger.info("=" * 60)
        logger.info("[Discord RPC] PRESENCE DATA SUMMARY:")
        logger.info(f"  State: {self._current_state.value}")
        logger.info(f"  Provider: {self._current_provider or '(none)'}")
        logger.info(f"  Privacy Level: {self._privacy_level}")
        logger.info(f"  large_image: '{data.get('large_image', '(not set - using App Icon)')}'")
        logger.info(f"  small_image: '{data.get('small_image', '(not set)')}'")
        logger.info(f"  details: '{data.get('details', '(not set)')}'")
        logger.info(f"  state: '{data.get('state', '(not set)')}'")
        logger.info("=" * 60)
        logger.info("[Discord RPC] REQUIRED ASSETS IN DISCORD DEVELOPER PORTAL:")
        logger.info("  Go to: https://discord.com/developers/applications")
        logger.info(f"  Select App ID: {DISCORD_CLIENT_ID}")
        logger.info("  Navigate to: Rich Presence → Art Assets")
        if data.get('large_image'):
            logger.info(f"  ✓ Must have asset named: '{data['large_image']}'")
        if data.get('small_image'):
            logger.info(f"  ✓ Must have asset named: '{data['small_image']}'")
        logger.info("=" * 60)

        return data

    def test_connection(self) -> tuple:
        """Test the Discord connection.

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not PYPRESENCE_AVAILABLE:
            return False, "pypresence library not installed. Run: pip install pypresence"

        if not DISCORD_CLIENT_ID:
            return False, "Discord Client ID not configured in constants.py"

        # Try to connect
        was_connected = self._connected
        was_enabled = self._enabled

        try:
            if not self._connected:
                self._enabled = True
                success = self.connect()

                if success:
                    # Disconnect if we weren't connected before
                    if not was_connected:
                        self.disconnect()
                    self._enabled = was_enabled
                    return True, "Successfully connected to Discord!"
                else:
                    self._enabled = was_enabled
                    return False, "Could not connect. Is Discord running?"
            else:
                return True, "Already connected to Discord"

        except Exception as e:
            self._enabled = was_enabled
            return False, f"Connection test failed: {e}"

    def print_diagnostics(self) -> None:
        """Print diagnostic information for troubleshooting Discord Rich Presence.

        This method prints all relevant configuration to help debug asset issues.
        """
        print("\n" + "="*60)
        print("DISCORD RICH PRESENCE DIAGNOSTICS")
        print("="*60)
        print(f"pypresence available: {PYPRESENCE_AVAILABLE}")
        print(f"Client ID: {DISCORD_CLIENT_ID}")
        print(f"Enabled: {self._enabled}")
        print(f"Connected: {self._connected}")
        print(f"Privacy level: {self._privacy_level}")
        print()
        print("Asset Configuration:")
        print(f"  large_image key: '{DISCORD_ASSETS['large_image']}'")
        print(f"  Provider assets: {DISCORD_ASSETS['providers']}")
        print()
        print("Button URLs:")
        print(f"  GitHub: {DISCORD_GITHUB_URL}")
        print(f"  Discord Server: {DISCORD_SERVER_URL}")
        print()
        large_image_key = DISCORD_ASSETS.get('large_image', '')
        print("TROUBLESHOOTING CHECKLIST:")
        print("1. Go to Discord Developer Portal: https://discord.com/developers/applications")
        print(f"2. Select application with ID: {DISCORD_CLIENT_ID}")
        print()
        print("*** CRITICAL: App Icon ≠ Rich Presence Art Assets ***")
        print("- 'General Information → App Icon' = Shows when NO Rich Presence data sent")
        print("- 'Rich Presence → Art Assets' = Used by large_image/small_image params")
        print()
        if large_image_key:
            print(f"3. Navigate to: Rich Presence → Art Assets (LEFT sidebar)")
            print(f"4. Upload an asset named EXACTLY: '{large_image_key}'")
            print("5. Asset must be PNG/JPG, at least 512x512 pixels")
            print("6. Click 'Save Changes' and wait 5-10 minutes")
            print("7. Restart Discord (Ctrl+R) and restart ImageAI")
        else:
            print("3. large_image is empty - using default App Icon (no Rich Presence asset needed)")
            print("4. Just ensure you have an App Icon in General Information")
        print()
        print("COMMON ISSUES:")
        print("- Question mark = Discord can't find the asset in Rich Presence → Art Assets")
        print("- Asset name case sensitivity: 'ImageAI_Logo' ≠ 'imageai_logo'")
        print("- Uploaded to 'App Icon' instead of 'Rich Presence → Art Assets'")
        print("- Forgot to click 'Save Changes' after uploading")
        print()
        print("QUICK FIX: Set large_image to '' in constants.py to use App Icon instead")
        print("="*60 + "\n")

        # Log to file as well
        logger.info("Discord RPC Diagnostics printed to console")


# Module-level singleton instance
discord_rpc = DiscordRPCManager()
