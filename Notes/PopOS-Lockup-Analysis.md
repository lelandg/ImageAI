# Pop!_OS Lockup Analysis

**Date:** 2025-10-23
**Issue:** ImageAI application locks up when running on Pop!_OS (Ubuntu-based Linux distribution)
**Status:** ⚠️ **ROOT CAUSE IDENTIFIED** - Critical bug in Google Cloud authentication code

## Critical Information

**Problem:** App freezes completely on Pop!_OS startup (and sometimes tab switching)

**Root Cause:** Synchronous `subprocess.run()` calls on main GUI thread in `gui/main_window.py:3892`
- Introduced with Google Cloud authentication support
- Blocks main thread for up to 10+ seconds waiting for gcloud command
- **Happens even if gcloud IS installed** due to various gcloud issues (see below)

**Why X11 Workaround Doesn't Work:** The subprocess blocking happens regardless of Qt platform (X11/Wayland)

**Will the Fix Work?** **YES!** Moving subprocess to background thread will:
- Keep UI responsive even if gcloud hangs forever
- Allow user to close app, switch tabs, change settings during check
- Show "Checking..." status instead of frozen screen

**Quick Test:** Run this on Pop!_OS terminal to see if gcloud is the culprit:
```bash
time gcloud auth application-default print-access-token
# If this takes >2 seconds or hangs, that's why the app freezes
```

**The Fix:** See "CRITICAL FIX: Move Subprocess Calls Off Main Thread" section below

---

## Investigation Summary

Analyzed the ImageAI codebase for potential causes of GUI lockups on Pop!_OS. The investigation focused on threading issues, platform-specific Qt problems, blocking operations, and potential deadlock scenarios.

**Key Finding:** The primary cause is **synchronous subprocess calls on the main GUI thread**, NOT Qt platform issues.

## Root Causes Identified

### 1. **BLOCKING SUBPROCESS CALLS ON MAIN THREAD** ⚠️ **PRIMARY CAUSE**

**THIS IS THE MOST CRITICAL ISSUE** - Added with Google Cloud authentication support.

The application makes **synchronous subprocess calls on the main GUI thread** during startup, which can block for up to 10 seconds or hang indefinitely.

**Critical Code Paths:**

1. **`gui/main_window.py:3892`** - Called during auth mode initialization
   ```python
   def _on_auth_mode_changed(self, auth_mode: str):
       if auth_mode == "Google Cloud Account":
           if not self.config.get("gcloud_auth_validated", False):
               self._check_gcloud_status()  # ⚠️ BLOCKS MAIN THREAD UP TO 10 SECONDS
   ```

2. **`gui/main_window.py:3934-3941`** - Synchronous subprocess in check function
   ```python
   def _check_gcloud_status(self):
       from core.gcloud_utils import check_gcloud_auth_status, get_gcloud_project_id
       is_auth, status_msg = check_gcloud_auth_status()  # ⚠️ BLOCKS MAIN THREAD
       project_id = get_gcloud_project_id()  # ⚠️ BLOCKS MAIN THREAD
   ```

3. **`core/gcloud_utils.py:147-152`** - 10-second timeout subprocess
   ```python
   result = subprocess.run(
       [gcloud_cmd, "auth", "application-default", "print-access-token"],
       capture_output=True,
       text=True,
       timeout=10,  # ⚠️ Can block main thread for up to 10 seconds
       shell=(platform.system() == "Windows")
   )
   ```

**Why This Causes Complete Lockup:**

1. **On startup/tab switch**, if Google Cloud auth mode is selected
2. **Main GUI thread** executes `_check_gcloud_status()` synchronously
3. **subprocess.run()** is called with 10-second timeout
4. **If gcloud is:**
   - Not installed → searches multiple paths, filesystem operations
   - Slow to respond → waits up to 10 seconds
   - In bad state → can hang indefinitely
   - Network timeout → additional delays
5. **Main thread is frozen** → No UI updates, no event processing
6. **User sees:** Completely frozen application

**Pop!_OS Specific Impact:**

On Pop!_OS, this is worse because:
- `gcloud` is typically **not installed** on Linux desktop systems
- `find_gcloud_command()` searches **multiple paths** (lines 22-97 in gcloud_utils.py)
- Each path check triggers **filesystem operations**
- WSL detection code may behave differently on native Linux
- Subprocess shell mode has different behavior on Linux

**Even WITH gcloud installed, it can still hang because:**
- `gcloud auth application-default print-access-token` can trigger credential refresh flows
- On first run, gcloud may try to update components automatically
- The command may prompt for user input (which subprocess can't provide)
- Credential files might have wrong permissions causing gcloud to hang
- gcloud might be waiting for a lock file held by another process
- Network operations to Google's OAuth servers can timeout
- The 10-second timeout doesn't prevent hanging - it just makes subprocess wait longer

**Similar Issues Found:**

These locations also have synchronous subprocess calls that could cause lockups:
- `providers/google.py:194-203` - Project ID lookup in provider initialization
- `core/config.py:170-176` - Project ID lookup during config initialization
- Multiple clipboard operations throughout the codebase

**Introduced In Commits:**
- `ea13456` - Add Google Cloud auth support and template UI improvements
- `79edd2b` - Add Google Cloud authentication and update docs
- `2dad32c` - Enhance security and auth persistence; update docs

**SOLUTION:** All subprocess calls MUST be moved to background threads using QThread. See "Recommended Solutions" section below.

### Additional Issues When gcloud IS Installed on Linux

Even when gcloud is properly installed on Pop!_OS, these issues can cause the subprocess to hang:

**1. Component Updates**
```bash
# gcloud may try to update automatically on first run
# This can take minutes and requires user confirmation
gcloud auth application-default print-access-token
# Output: "Updates are available for some Google Cloud CLI components..."
# [HANGS waiting for user input]
```

**2. Credential File Permissions**
```bash
# If credential files have wrong permissions, gcloud fails silently
ls -la ~/.config/gcloud/
# If owned by wrong user or wrong permissions → gcloud hangs
```

**3. Lock Files**
```bash
# If another gcloud process is running, commands wait for lock
ls -la ~/.config/gcloud/.locks/
# If lock file exists → command hangs until lock is released
```

**4. Network Timeouts**
```python
# gcloud tries to contact Google's OAuth servers
# If network is slow/down, it waits for TCP timeout (can be 60+ seconds)
# subprocess timeout=10 doesn't help if network stack is hanging
```

**5. Interactive Prompts**
```bash
# gcloud may prompt for configuration choices
gcloud auth application-default print-access-token
# "Do you want to continue (Y/n)?"
# subprocess can't provide input → hangs forever
```

**Test if gcloud hangs on your system:**
```bash
# Open terminal on Pop!_OS and run:
time gcloud auth application-default print-access-token

# If this takes more than 2 seconds, that's why the app freezes
# Common outputs that cause hangs:
# - "Updates available..." (waiting for confirmation)
# - "Credential file not found" (waiting for login flow)
# - No output at all (network timeout)
```

### Why the X11 Workaround Doesn't Work

The workaround `QT_QPA_PLATFORM=xcb` was suggested to avoid Wayland issues, but **it doesn't fix the subprocess blocking problem** because:
- The subprocess calls happen **before** any Qt platform code runs
- The blocking occurs during `_on_auth_mode_changed()` which runs on **any** Qt platform
- X11 vs Wayland only affects modal dialogs and window management, not subprocess execution
- The 10-second subprocess timeout will block the main thread **regardless of Qt platform**

**The ONLY fix is to move subprocess calls to a background thread.**

### Will the Proposed Fix Actually Work? YES!

**Question:** If gcloud is installed but the app still locks up, will moving subprocess to background thread fix it?

**Answer:** **YES, absolutely.** Here's why:

1. **The issue is NOT gcloud itself** - it's that gcloud runs on the **main GUI thread**
2. **Even if gcloud takes 30 seconds** to respond (or hangs completely), it won't freeze the UI anymore
3. **Background thread = non-blocking** - The main thread continues processing events while the background thread waits for gcloud
4. **User sees "Checking..." status** instead of a frozen app
5. **If gcloud hangs forever**, the user can still:
   - Switch tabs
   - Close the app
   - Change settings
   - Do anything else in the UI

**What happens with the fix:**
```
WITHOUT FIX (Current):
Main Thread: Init → Check gcloud → [FROZEN 10+ seconds] → Update UI → App ready
User sees:   "Loading..." → [COMPLETELY FROZEN] → App ready

WITH FIX (Background thread):
Main Thread:     Init → Start thread → Update UI → App ready (responsive!)
Background Thread:      → Check gcloud [10+ seconds] → Signal result
User sees:       "Loading..." → "Checking..." → App ready + status updates
```

**Even if gcloud has these problems:**
- ✓ Not installed → Background thread searches, main thread stays responsive
- ✓ Taking 30 seconds → Background thread waits, main thread stays responsive
- ✓ Hangs forever → Background thread hangs, main thread stays responsive, user can close app
- ✓ Prompting for input → Background thread gets stuck, main thread stays responsive
- ✓ Waiting for network → Background thread waits, main thread stays responsive

**The key insight:** Moving to background thread doesn't make gcloud faster - it makes the **UI always responsive** regardless of what gcloud does.

---

### 2. **Modal Dialog Blocking** (Secondary Cause)

The application has **extensive use of modal dialogs** (`dialog.exec()` and `dialog.exec_()`) throughout the video project workspace. On Pop!_OS with Wayland or certain X11 configurations, modal dialogs can cause issues:

**Locations:**
- `workspace_widget.py:3484, 3592, 3642, 3898, 3955, 4069, 4331, 4463, 4523` - Multiple modal dialog calls
- These dialogs can block the main event loop if they interact with background threads
- Modal dialogs on Wayland can deadlock when combined with QThread operations

### 2. **QThread.wait() Calls**

Several locations call `thread.wait()` which blocks the main thread:
- `video_project_tab.py:1532` - `self.generation_thread.wait(1000)`
- `main_window.py:5338` - `self.gen_thread.wait()`
- `enhanced_prompt_dialog.py:742`
- `prompt_question_dialog.py:845`
- `reference_image_dialog.py:968`

**Problem:** If the thread is waiting on the main thread (for signals/slots), this creates a deadlock situation.

### 3. **QApplication.processEvents() Abuse**

Multiple calls to `processEvents()` indicate blocking operations on the main thread:
- `main_window.py:236, 244, 265, 270, 285, 4222, 4654, 5196`
- `workspace_widget.py:3292`

**Issues:**
- This is a code smell indicating blocking operations on the main thread
- On Linux, excessive `processEvents()` can cause event loop corruption
- Suggests improper threading architecture

### 4. **Wayland/X11 Platform Issues**

Pop!_OS defaults to **Wayland**, which has known issues with Qt applications:
- The code checks for `DISPLAY` environment variable (`gui/__init__.py:22`)
- Qt/PySide6 on Wayland can have threading issues with modal dialogs
- The application uses the Fusion Qt style by default, which may not be optimized for Wayland

**Evidence from code:**
```python
# gui/__init__.py:22
if "Unable to open monitor interface" in msg and "DISPLAY" in msg:
    return  # Silently ignore these benign errors
```

### 5. **Video Generation Thread Complexity**

The `VideoGenerationThread` in `video_project_tab.py` performs complex operations:
- Image generation with PIL/OpenCV
- File I/O operations (reading/writing images, videos)
- Network requests to Google APIs (Gemini, Veo)
- All while emitting signals back to the main thread

**Potential deadlock scenario:**
1. Main thread shows modal dialog (blocks event loop)
2. Background thread emits signal
3. Signal handler tries to update UI (requires event loop)
4. Deadlock: Main thread waiting for thread, thread waiting for event loop

## Recommended Solutions

### CRITICAL FIX: Move Subprocess Calls Off Main Thread

**Priority: CRITICAL - Must be fixed immediately**

The subprocess calls in `_check_gcloud_status()` MUST be moved to a background thread:

```python
# In gui/main_window.py

from PySide6.QtCore import QThread, Signal

class GCloudStatusChecker(QThread):
    """Background thread for checking gcloud auth status."""
    status_checked = Signal(bool, str)  # (is_authenticated, status_message)
    project_id_fetched = Signal(str)    # project_id

    def run(self):
        """Run in background thread - subprocess calls are safe here."""
        try:
            from core.gcloud_utils import check_gcloud_auth_status, get_gcloud_project_id

            # These blocking calls are OK in background thread
            is_auth, status_msg = check_gcloud_auth_status()
            self.status_checked.emit(is_auth, status_msg)

            if is_auth:
                project_id = get_gcloud_project_id()
                if project_id:
                    self.project_id_fetched.emit(project_id)
        except Exception as e:
            self.status_checked.emit(False, f"Error: {str(e)}")

# Update main_window.py methods:

def _check_gcloud_status(self):
    """Check Google Cloud CLI status asynchronously."""
    # Show "checking" status immediately (non-blocking)
    self.gcloud_status_label.setText("⟳ Checking...")
    self.gcloud_status_label.setStyleSheet("color: blue;")
    self.btn_check_status.setEnabled(False)  # Prevent multiple checks

    # Start background thread (non-blocking)
    self.gcloud_checker = GCloudStatusChecker()
    self.gcloud_checker.status_checked.connect(self._on_gcloud_status_checked)
    self.gcloud_checker.project_id_fetched.connect(self._on_project_id_fetched)
    self.gcloud_checker.finished.connect(lambda: self.btn_check_status.setEnabled(True))
    self.gcloud_checker.start()

def _on_gcloud_status_checked(self, is_auth: bool, status_msg: str):
    """Handle gcloud status check results (runs on main thread via signal)."""
    if is_auth:
        self.gcloud_status_label.setText("✓ Authenticated")
        self.gcloud_status_label.setStyleSheet("color: green;")
        self.config.set("gcloud_auth_validated", True)
    else:
        if len(status_msg) > 50:
            self.gcloud_status_label.setText("✗ Not authenticated")
        else:
            self.gcloud_status_label.setText(f"✗ {status_msg}")
        self.gcloud_status_label.setStyleSheet("color: red;")
        self.config.set("gcloud_auth_validated", False)
    self.config.save()

def _on_project_id_fetched(self, project_id: str):
    """Handle project ID fetch (runs on main thread via signal)."""
    self.project_id_edit.setText(project_id)
    self.config.set("gcloud_project_id", project_id)
    self.config.save()

def _on_auth_mode_changed(self, auth_mode: str):
    """Handle auth mode change."""
    auth_mode_internal = "gcloud" if auth_mode == "Google Cloud Account" else "api-key"
    self.config.set("auth_mode", auth_mode_internal)
    self._update_auth_visibility()

    # DON'T auto-check on mode change - let user click "Check Status" button
    # This prevents startup lockups
    # Old broken code:
    # if auth_mode == "Google Cloud Account":
    #     if not self.config.get("gcloud_auth_validated", False):
    #         self._check_gcloud_status()  # ⚠️ REMOVED - This blocked main thread
```

**Additional subprocess timeout protection:**

Update `core/gcloud_utils.py` to use shorter, safer timeouts:

```python
# In check_gcloud_auth_status()
result = subprocess.run(
    [gcloud_cmd, "auth", "application-default", "print-access-token"],
    capture_output=True,
    text=True,
    timeout=5,  # Reduced from 10 to 5 seconds
    shell=(platform.system() == "Windows")
)
```

---

### Immediate Fixes (Testing)

#### 1. Force X11 Backend
```bash
# Before running ImageAI
export QT_QPA_PLATFORM=xcb
python main.py
```

This bypasses Wayland and uses the more stable X11 backend.

#### 2. Test with Different Qt Platforms
```bash
#!/bin/bash
# Test script for different Qt backends

echo "Testing with XCB (X11)..."
QT_QPA_PLATFORM=xcb python main.py

echo "Testing with Wayland..."
QT_QPA_PLATFORM=wayland python main.py

echo "Testing with offscreen (headless)..."
QT_QPA_PLATFORM=offscreen python main.py
```

### Short-term Fixes (Code Changes)

#### 1. Remove QThread.wait() Calls

**Before:**
```python
self.generation_thread.wait(1000)  # Blocks main thread
self.generation_thread.deleteLater()
```

**After:**
```python
# Use signal-based completion
self.generation_thread.finished.connect(self.generation_thread.deleteLater)
# No blocking wait
```

#### 2. Convert Modal Dialogs to Non-Modal

**Before:**
```python
if dialog.exec() == QDialog.Accepted:
    # Handle result
```

**After:**
```python
dialog.accepted.connect(self.on_dialog_accepted)
dialog.rejected.connect(self.on_dialog_rejected)
dialog.show()  # Non-blocking
```

#### 3. Replace processEvents() with Proper Threading

**Before:**
```python
QApplication.processEvents()  # Code smell
# Do blocking work
QApplication.processEvents()
```

**After:**
```python
# Move blocking work to QThread
thread = QThread()
worker = Worker()
worker.moveToThread(thread)
thread.started.connect(worker.do_work)
thread.start()
```

### Long-term Fixes (Architecture)

#### 1. Implement Non-Blocking Dialog Pattern

Create a base class for all dialogs:
```python
class NonBlockingDialog(QDialog):
    """Base class for non-blocking dialogs"""

    def show_and_connect(self, accepted_callback, rejected_callback=None):
        """Show dialog non-blocking with callbacks"""
        self.accepted.connect(accepted_callback)
        if rejected_callback:
            self.rejected.connect(rejected_callback)
        self.show()
```

#### 2. Refactor Thread Cleanup

Use Qt's automatic cleanup:
```python
class VideoProjectTab(QWidget):
    def on_generation_complete(self, success, message):
        # Don't wait - let Qt handle cleanup
        if self.generation_thread:
            self.generation_thread.finished.connect(
                self.generation_thread.deleteLater
            )
            self.generation_thread = None
```

#### 3. Add Platform Detection and Warnings

Add startup check for Wayland:
```python
def check_platform_compatibility():
    """Check for known platform issues"""
    import os
    import logging
    logger = logging.getLogger(__name__)

    # Check if running on Wayland
    if os.environ.get('WAYLAND_DISPLAY'):
        logger.warning("Running on Wayland detected")
        if 'QT_QPA_PLATFORM' not in os.environ:
            logger.warning("Consider setting QT_QPA_PLATFORM=xcb for better stability")
            # Optionally show user dialog
```

## Debug Lockup Investigation

### Attach to Frozen Process

If the application locks up, use these debugging techniques:

```bash
# Find the frozen process
ps aux | grep python | grep imageai

# Attach gdb (requires gdb and python3-dbg)
gdb -p <PID>

# Get Python stack trace
(gdb) py-bt

# Get all thread stack traces
(gdb) thread apply all bt

# Detach without killing
(gdb) detach
(gdb) quit
```

### Enable Qt Debug Logging

```bash
# Enable Qt debug messages
export QT_LOGGING_RULES="qt.*=true"
export QT_DEBUG_PLUGINS=1
python main.py 2>&1 | tee qt_debug.log
```

### Check for Thread Deadlocks

```bash
# Install debugging tools
sudo apt install python3-dbg gdb

# Run with thread debugging
python3 -m trace --trace main.py 2>&1 | grep -i thread
```

## Testing Checklist

When testing fixes on Pop!_OS:

**Critical Tests for Subprocess Fix:**
- [ ] App starts normally on Pop!_OS **without** gcloud installed
- [ ] App starts normally on Pop!_OS **with** gcloud installed but not authenticated
- [ ] App starts normally with Google Cloud auth mode selected in settings
- [ ] Click "Check Status" button shows "Checking..." status
- [ ] UI remains **completely responsive** while checking gcloud status
- [ ] Status updates correctly when check completes (both success and failure)
- [ ] Test with network unplugged (should timeout gracefully, not hang)
- [ ] Test rapid clicking of "Check Status" button (should not crash)
- [ ] Switch between auth modes while check is running (should not crash)

**Platform Compatibility Tests:**
- [ ] Test with `QT_QPA_PLATFORM=xcb` (X11 backend)
- [ ] Test with `QT_QPA_PLATFORM=wayland` (native Wayland)
- [ ] Test on Windows with gcloud installed
- [ ] Test on macOS
- [ ] Test video generation workflow (most complex threading)
- [ ] Test multiple dialogs in sequence
- [ ] Test canceling operations mid-execution
- [ ] Monitor system resources (CPU, memory)
- [ ] Check for zombie threads (`ps -eLf | grep python`)
- [ ] Test with Qt debug logging enabled

## Platform-Specific Notes

### Pop!_OS Characteristics
- Based on Ubuntu 22.04 LTS (or newer)
- Uses Wayland by default (can switch to X11)
- GNOME desktop environment
- May have different Qt theme/platform plugins than stock Ubuntu

### Known Qt/Wayland Issues
- Modal dialogs can freeze with certain window managers
- Signal delivery can be delayed on Wayland
- Some Qt platform plugins are not Wayland-optimized
- Thread synchronization differs between X11 and Wayland

## Related Code Files

**Threading Implementation:**
- `gui/video/video_project_tab.py` - Main video generation thread
- `gui/main_window.py` - Image generation thread
- `gui/enhanced_prompt_dialog.py` - LLM prompt generation thread

**Modal Dialog Usage:**
- `gui/video/workspace_widget.py` - Heavy modal dialog usage
- `gui/video/reference_library_widget.py` - Reference selection dialogs
- `gui/video/wizard_widget.py` - Wizard dialogs

**Platform Detection:**
- `gui/__init__.py` - Qt platform initialization
- `core/config.py` - Platform-specific paths

## Conclusion

The lockup on Pop!_OS is caused by **multiple threading issues**, in order of severity:

### PRIMARY CAUSE: Synchronous Subprocess Calls on Main Thread ⚠️

**This is the most critical issue** introduced with Google Cloud authentication support:

1. **`_check_gcloud_status()`** called synchronously on main thread during startup
2. **`subprocess.run()`** with 10-second timeout **blocks the entire UI**
3. On Pop!_OS without gcloud installed, this causes searches through multiple filesystem paths
4. **Result: Complete application freeze** for up to 10+ seconds

**CRITICAL FIX REQUIRED:**
- Move ALL subprocess calls to background QThread
- Remove auto-check on auth mode change
- Only check when user explicitly clicks "Check Status" button
- Show "Checking..." status during background operation

### SECONDARY CAUSES:

2. **Wayland compatibility issues** - Pop!_OS uses Wayland by default, Qt/PySide6 has known threading issues on Wayland
3. **Modal dialog deadlocks** - Extensive use of `exec()` blocking dialogs interacting with background threads
4. **Thread synchronization problems** - `QThread.wait()` calls can deadlock if threads are waiting on each other
5. **Main thread blocking** - Multiple `QApplication.processEvents()` calls indicate blocking operations on the main thread

**Quick Fix (Testing):** Force X11 backend with `QT_QPA_PLATFORM=xcb`

**Required Fix (Production):**
1. **CRITICAL**: Refactor all subprocess calls to background threads
2. **Important**: Refactor modal dialogs to non-blocking
3. **Cleanup**: Remove all `QThread.wait()` calls in favor of signal-based completion

## Prevention Guidelines

To prevent similar issues in the future:

1. ⚠️ **NEVER call `subprocess.run()`, `subprocess.Popen()`, or `subprocess.call()` on the main GUI thread**
2. ⚠️ **ALWAYS use QThread or async for subprocess operations in GUI code**
3. Add code review checkpoint: Search for `subprocess\.(run|call|Popen)` in `gui/` directory
4. Limit subprocess timeout to max 5 seconds (not 10+)
5. Test on Linux desktop **without** required CLI tools installed
6. Test with network disconnected to simulate slow/hanging subprocess calls
7. Use QThread signals for all background→main thread communication
8. Never use `QThread.wait()` in the main thread
