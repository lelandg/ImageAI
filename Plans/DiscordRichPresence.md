# Discord Rich Presence Implementation Checklist

**Last Updated:** 2026-01-02 09:56
**Status:** In Progress (Debugging Asset Issue)
**Progress:** 17/24 tasks complete

## Overview

Add Discord Rich Presence integration to display ImageAI activity in users' Discord status, similar to how Steam shows game activity. Users can optionally show what they're doing (generating images, editing, idle) and which AI provider/model they're using.

## How Discord Rich Presence Works

Discord Rich Presence uses local IPC (Inter-Process Communication) to connect to a running Discord client on the same machine. The `pypresence` library provides a Python wrapper around Discord's RPC protocol.

**What users will see in Discord:**
```
Playing ImageAI
Generating an image
Using Gemini 2.5 Flash
[ImageAI logo] 00:15:32 elapsed
```

**Key Technical Details:**
- Requires Discord running on the same machine
- Connection via local IPC (no network/authentication needed)
- 15-second minimum update interval (Discord rate limit)
- Assets (images) must be uploaded to Discord Developer Portal
- Client ID from Discord Application required

## Prerequisites

- [ ] Create Discord Application at https://discord.com/developers/applications
- [ ] Note the Application (Client) ID for code (set in `core/constants.py:DISCORD_CLIENT_ID`)
- [ ] Upload Rich Presence assets (images) to the application:
  - `imageai_logo` - Large image (512x512 PNG)
  - `provider_google` - Google/Gemini icon (512x512)
  - `provider_openai` - OpenAI icon (512x512)
  - `provider_stability` - Stability AI icon (512x512)
  - `provider_local` - Local SD icon (512x512)
  - `status_generating` - Activity icon (optional)
  - `status_idle` - Idle icon (optional)

## Implementation Tasks

### 1. Core Discord RPC Module (`core/discord_rpc.py`)

- [x] Create `DiscordRPCManager` class with singleton pattern (`core/discord_rpc.py:83`) ✅
- [x] Implement connection management (connect/disconnect/reconnect) ✅
- [x] Add graceful handling when Discord isn't running ✅
- [x] Implement activity states enum:
  ```python
  class ActivityState(Enum):
      IDLE = "idle"
      GENERATING = "generating"
      UPSCALING = "upscaling"
      EDITING = "editing"
      VIDEO_PROJECT = "video_project"
      BROWSING_HISTORY = "browsing_history"
  ```
- [x] Create `update_presence()` method with all RPC parameters (`core/discord_rpc.py:215`) ✅
- [x] Add background thread for maintaining connection ✅
- [x] Implement connection status callbacks (for UI feedback) (`core/discord_rpc.py:114`) ✅
- [x] Add session start timestamp tracking (`core/discord_rpc.py:171`) ✅

**Key Code Structure:**
```python
class DiscordRPCManager:
    """Manages Discord Rich Presence connection and updates."""

    CLIENT_ID = "YOUR_APPLICATION_ID"  # From Discord Developer Portal

    def __init__(self):
        self._rpc: Optional[Presence] = None
        self._connected = False
        self._enabled = False
        self._session_start = None
        self._current_state = ActivityState.IDLE
        self._lock = threading.Lock()

    def connect(self) -> bool:
        """Establish connection to Discord. Returns True if successful."""

    def disconnect(self):
        """Gracefully disconnect from Discord."""

    def update_presence(
        self,
        state: ActivityState,
        details: str = "",
        provider: str = "",
        model: str = "",
        show_elapsed: bool = True
    ):
        """Update Discord presence with current activity."""

    def set_enabled(self, enabled: bool):
        """Enable or disable Rich Presence (user preference)."""
```

### 2. Constants & Configuration (`core/constants.py`)

- [x] Add Discord-related constants (`core/constants.py:98-121`) ✅
  ```python
  # Discord Rich Presence
  DISCORD_CLIENT_ID = "YOUR_CLIENT_ID_HERE"
  DISCORD_UPDATE_INTERVAL = 15  # seconds (Discord minimum)

  # Privacy levels for Discord presence
  DISCORD_PRIVACY_LEVELS = {
      "full": "Show provider, model, and activity",
      "activity_only": "Show activity only (Generating, Idle)",
      "minimal": "Show only that ImageAI is running",
  }
  ```
- [x] Add provider icon mappings for Discord assets (`core/constants.py:112-121`) ✅

### 3. Configuration Persistence (`core/config.py`)

- [x] Add Discord settings to config schema (`core/config.py:308-342`) ✅
  ```python
  "discord": {
      "enabled": False,  # Opt-in by default
      "privacy_level": "full",  # full | activity_only | minimal
      "show_elapsed_time": True,
      "show_model": True,
      "show_buttons": True,  # GitHub link button
  }
  ```
- [x] Add `get_discord_config()` and `set_discord_config()` methods ✅
- [x] Handle migration for existing configs (add defaults) ✅

### 4. Settings UI (`gui/main_window.py` - Discord Integration section)

- [x] Create Discord settings group (`gui/main_window.py:1932-2008`) ✅
  - Enable/disable toggle checkbox
  - Privacy level dropdown (Full/Activity Only/Minimal)
  - Show elapsed time checkbox
  - Show model name checkbox
  - Show GitHub button checkbox
  - Connection status indicator (green/red label)
  - "Test Connection" button
- [x] Add Discord settings section to Settings tab ✅
- [x] Wire up settings changes to RPC manager (`gui/main_window.py:6553-6607`) ✅
- [x] Show status feedback (Connected/Disconnected/Discord Not Running) ✅

**UI Mockup:**
```
[ Discord Integration ]
  [x] Show activity in Discord status

  Privacy Level: [Full Details     v]
    - Full: Provider, model, and activity
    - Activity Only: Just what you're doing
    - Minimal: Only show ImageAI is running

  [x] Show elapsed time
  [x] Show model name
  [x] Show GitHub link button

  Status: [*] Connected to Discord
  [ Test Connection ]
```

### 5. Main Window Integration (`gui/main_window.py`)

- [x] Initialize `DiscordRPCManager` on startup (if enabled) (`gui/main_window.py:329`, `:6492-6522`) ✅
- [x] Connect to Discord when app starts (if enabled) ✅
- [x] Disconnect cleanly on app exit (`gui/main_window.py:7117-7121`) ✅
- [ ] Hook into tab change events to update activity state (deferred - not essential)
- [x] Add presence update calls to generation workflow ✅

### 6. Generation Flow Integration

- [x] Update presence when generation starts (`gui/main_window.py:4934-4935`) ✅
- [x] Update presence when generation completes (`gui/main_window.py:5891-5892`) ✅
- [x] Update presence with provider/model info ✅
- [ ] Handle batch generation (show progress: "Generating 3/10") (deferred)
- [x] Reset to IDLE state on completion or error (`gui/main_window.py:5877-5878`) ✅

### 7. Video Project Integration

- [ ] Update presence for video project activities:
  - "Working on video project"
  - "Generating storyboard"
  - "Creating video clips"
  - Show project name (if privacy allows)

### 8. Dependencies & Installation

- [x] Add `pypresence>=4.6.0` to `requirements.txt` (`requirements.txt:39-40`) ✅
- [x] Make pypresence optional (graceful degradation if not installed) ✅
- [x] Add try/except import handling in discord_rpc.py (`core/discord_rpc.py:43-52`) ✅

## Privacy & Security Considerations

**Important Privacy Notes:**
1. **Opt-in Only**: Disabled by default - users must explicitly enable
2. **No Prompt Sharing**: NEVER include actual prompts in presence (could be sensitive)
3. **Granular Control**: Let users choose what information to share
4. **Local Only**: Discord RPC is local IPC, no data leaves the machine to our servers
5. **Graceful Absence**: Don't show errors if Discord isn't running

**What is shared (at maximum privacy level "full"):**
- Application name (ImageAI)
- Activity state (Generating, Idle, etc.)
- Provider name (Google, OpenAI, etc.)
- Model name (Gemini 2.5, DALL-E 3, etc.)
- Session elapsed time
- Static GitHub link (if button enabled)

**What is NEVER shared:**
- Actual prompts or prompt text
- Generated image content
- File paths or output locations
- API keys or credentials
- Personal information

## Testing

- [ ] Test with Discord running → should connect and update
- [ ] Test without Discord running → should gracefully fail
- [ ] Test enable/disable toggle → should connect/disconnect
- [ ] Test all activity states display correctly
- [ ] Test privacy levels show correct info
- [ ] Test elapsed time updates
- [ ] Test generation workflow updates presence
- [ ] Test app exit disconnects cleanly
- [ ] Test reconnection when Discord restarts

## Error Handling

- [ ] Handle `pypresence.exceptions.DiscordNotFound` gracefully
- [ ] Handle `pypresence.exceptions.DiscordError` with retry logic
- [ ] Handle connection drops with automatic reconnection
- [ ] Log all Discord RPC errors to debug log
- [ ] Never crash the app due to Discord issues

## Notes

### ⚠️ CRITICAL: App Icon vs Rich Presence Art Assets

**This is the #1 source of confusion!**

| Section | Purpose | When Used |
|---------|---------|-----------|
| General Information → App Icon | Default app icon | When NO Rich Presence data is sent |
| Rich Presence → Art Assets | Custom presence images | When `large_image`/`small_image` params are sent |

**Why question marks appear:**
- When ImageAI sends `large_image="imageai_logo_01"` in Rich Presence
- Discord looks for that asset in **Rich Presence → Art Assets** (NOT the App Icon)
- If not found → shows question mark

**Solutions:**
1. Upload asset to **Rich Presence → Art Assets** with the exact name `imageai_logo_01`
2. OR set `large_image` to `""` in `constants.py` to skip it (Discord uses App Icon instead)

### Discord Developer Portal Setup
1. Go to https://discord.com/developers/applications
2. Click "New Application" → Name: "ImageAI"
3. Copy the "Application ID" (this is the Client ID)
4. **For App Icon:** General Information → App Icon (shows when RPC not active)
5. **For Rich Presence:** Rich Presence → Art Assets (LEFT sidebar)
6. Upload images (512x512 PNG recommended)
7. Asset names become the `large_image`/`small_image` parameter values
8. **Click "Save Changes"** after uploading
9. Wait 5-10 minutes for propagation

### pypresence API Reference
```python
RPC.update(
    state="Current status text",           # Bottom line
    details="What user is doing",          # Top line under app name
    start=epoch_timestamp,                 # For elapsed time
    large_image="asset_name",              # Main image (from portal)
    large_text="Tooltip for large image",
    small_image="asset_name",              # Corner badge image
    small_text="Tooltip for small image",
    buttons=[                              # Max 2 buttons
        {"label": "GitHub", "url": "https://github.com/lelandg/ImageAI"}
    ]
)
```

### Presence Display Examples

**Generating (Full Privacy):**
```
Playing ImageAI
Generating an image
Using Google Gemini 2.5 Flash
[ImageAI logo] [Google icon] 00:02:15 elapsed
[View on GitHub]
```

**Generating (Activity Only):**
```
Playing ImageAI
Generating an image
[ImageAI logo] 00:02:15 elapsed
```

**Idle (Minimal):**
```
Playing ImageAI
[ImageAI logo]
```

## Future Enhancements

- Party/group features for collaborative sessions
- "Ask to Join" functionality for shared workspaces
- Custom status messages (user-defined)
- Integration with Discord bot for image sharing
- Show thumbnail of last generated image (requires hosting)

## References

- [pypresence GitHub](https://github.com/qwertyquerty/pypresence)
- [pypresence PyPI](https://pypi.org/project/pypresence/)
- [Discord Developer Portal](https://discord.com/developers/applications)
- [Discord Rich Presence Docs](https://discord.com/developers/docs/rich-presence/how-to)
