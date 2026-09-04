# Video Tab Loading - Debug Logging Added

## Summary

I've added comprehensive logging to track down the video tab hang issue on Nick's Linux system (Pop! OS). The logging will help identify exactly where the application hangs when clicking the video tab.

## Where Logging Was Added

### 1. Main Window - Video Tab Loading (`gui/main_window.py`)

**Location:** `_load_video_tab()` method (lines 6429-6511)

**What it logs:**
- Thread ID and platform information
- Each step of the video tab loading process:
  - STEP 1: Importing VideoProjectTab
  - STEP 2: Preparing providers dictionary
  - STEP 3: Getting video tab index
  - STEP 4: Creating VideoProjectTab instance
  - STEP 5: Connecting signals
  - STEP 6: Replacing placeholder tab
  - STEP 7: Updating internal references
  - STEP 8: Syncing LLM provider settings

### 2. VideoProjectTab Initialization (`gui/video/video_project_tab.py`)

**Location:** `__init__()` method (lines 1250-1282)

**What it logs:**
- Thread ID
- INIT STEP 1: Storing config and providers
- INIT STEP 2: Creating VideoConfig
- INIT STEP 3: Creating ProjectManager
- INIT STEP 4: Initializing project state
- INIT STEP 5: Calling init_ui()

**Location:** `init_ui()` method (lines 1284-1368)

**What it logs:**
- UI STEP 1-12: Each major UI component creation:
  - Main layout
  - QTabWidget
  - WorkspaceWidget
  - HistoryTab
  - ReferenceLibraryWidget
  - Signal connections
  - Tab additions

### 3. WorkspaceWidget Initialization (`gui/video/workspace_widget.py`)

**Location:** `__init__()` method (lines 264-318)

**What it logs:**
- Thread ID
- WORKSPACE STEP 1-9: Each initialization step:
  - FFmpeg environment configuration
  - Config and providers storage
  - VideoConfig creation
  - ProjectManager creation
  - Workspace state initialization
  - ImageHoverPreview creation
  - UI state tracking initialization
  - init_ui() call
  - Timer scheduling for auto-load

**Location:** `auto_load_last_project()` method (lines 1644-1688)

**What it logs:**
- Thread ID
- Widget visibility status
- AUTO-LOAD STEP 1-4: Project loading process:
  - Importing get_last_project_path
  - Getting last project path
  - Loading project (if exists)
  - Restoring UI state (splitters, columns, scrollbars)

## Where to Find the Logs

### Log File Location

The application writes logs to:
- **Linux:** `~/.config/ImageAI/logs/imageai_YYYYMMDD_HHMMSS.log` (timestamped files)
  - Example: `~/.config/ImageAI/logs/imageai_20250131_143022.log`
  - New log file created each time app starts
  - Keeps last 5 log files (10MB each, rotated)
- **Current Directory:** `./imageai_current.log` (copied automatically on exit)
  - This is the most recent log, copied when app closes
  - Easiest to find and share

### Log File Analysis

When Nick clicks the video tab and it hangs:

1. **Last completed step** - Look for the last "STEP X complete" message
2. **Missing step** - The step that DIDN'T log means that's where it hung
3. **Thread information** - Check if thread IDs are consistent

### Example Log Pattern (Normal)

```
INFO: === TAB CHANGED to index 2 ===
INFO: Current widget: QWidget
INFO: Is video tab: True
INFO: Video tab loaded: False
INFO: Triggering video tab lazy load...
INFO: === _LOAD_VIDEO_TAB CALLED ===
INFO: Thread ID: 139876543210
INFO: Current platform: linux
INFO: STEP 1: Importing VideoProjectTab...
INFO: STEP 1: Import successful
INFO: STEP 2: Preparing providers dictionary...
INFO: STEP 2: Available providers: ['google', 'openai']
INFO: STEP 2: Providers dictionary created
INFO: STEP 3: Getting video tab index...
INFO: STEP 3: Video tab index = 2
INFO: STEP 4: Creating VideoProjectTab instance...
INFO: === VideoProjectTab.__init__ CALLED ===
INFO: Thread ID: 139876543210
INFO: INIT STEP 1: Storing config and providers...
[... and so on ...]
```

### Example Log Pattern (Hang)

If it hangs at WorkspaceWidget creation:

```
INFO: UI STEP 3: Creating WorkspaceWidget...
[APPLICATION HANGS - NO MORE LOGS]
```

This would tell us the WorkspaceWidget constructor is where it hangs.

## How to Collect Logs for Nick

### Instructions for Nick:

1. **Start the application** from terminal:
   ```bash
   cd /path/to/ImageAI
   source .venv/bin/activate  # or .venv_linux if that's what you're using
   python main.py
   ```

2. **Click the Video tab** - Wait for it to hang (or become unresponsive)

3. **Force quit the application** (Ctrl+C in terminal or close window)

4. **Collect the log file**:
   ```bash
   # EASIEST: Check the current directory for the auto-copied log
   # (Only exists if app exited cleanly)
   cat imageai_current.log

   # OR: Get the most recent timestamped log from config directory
   ls -lt ~/.config/ImageAI/logs/imageai_*.log | head -1
   # Then copy that file:
   cat ~/.config/ImageAI/logs/imageai_20250131_143022.log > video_tab_hang.log

   # OR: Just look at the latest log directly
   less ~/.config/ImageAI/logs/imageai_$(ls -t ~/.config/ImageAI/logs/ | head -1)
   ```

5. **Send the log file** - Share `video_tab_hang.log` so we can see exactly where it hung

## Expected Behavior

### On Working System (VirtualBox):
- All STEP messages should appear in sequence
- Should end with "=== _LOAD_VIDEO_TAB COMPLETE ==="
- Auto-load messages should appear after 100ms

### On Nick's System (If Hanging):
- Log will stop at a specific STEP
- The step that's missing is where the hang occurs
- Common suspects:
  - WorkspaceWidget creation (has QMediaPlayer)
  - QTabWidget operations
  - Signal connections
  - Auto-load project functionality

## Next Steps

Once we get Nick's log file, we'll know:
1. **Exact line/component** where it hangs
2. **Whether it's Qt-related** (e.g., QMediaPlayer on Pop! OS)
3. **Whether it's project loading** (auto-load feature)
4. **Whether it's a deadlock** (thread ID comparison)

Then we can add a workaround or fix the specific issue.

## Potential Issues by Platform

### Linux-Specific Qt Issues:
- **QMediaPlayer/QVideoWidget** - Some Linux distros have codec/backend issues
- **Qt platform plugins** - Different behavior on X11 vs Wayland
- **FFmpeg integration** - Qt multimedia backend differences

### Pop! OS Specific:
- Uses Wayland by default (not X11)
- Different Qt platform plugin behavior
- May need different multimedia backend configuration

## Quick Fix to Test

If Nick wants to test immediately, he can try forcing X11 mode:

```bash
export QT_QPA_PLATFORM=xcb  # Force X11 instead of Wayland
python main.py
```

This sometimes fixes Qt multimedia issues on Wayland-based systems.
