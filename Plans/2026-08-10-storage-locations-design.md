# Configurable Storage Locations — Design

**Date:** 2026-08-10
**Status:** Approved design, not yet implemented
**Author:** Claude Code (with Leland Green)

## Problem

ImageAI writes every persistent file under one platform directory. On Windows
that directory is `%APPDATA%\ImageAI`. The directory holds 8.2 GB on the
author's machine. The user cannot move any part of it. The roaming profile
grows without limit, and the user cannot put large output on a second drive.

Measured breakdown of `C:\Users\aboog\AppData\Roaming\ImageAI` on 2026-08-10:

| Directory | Size |
|---|---|
| `musetalk/` | 4.1 GB |
| `generated/` | 3.7 GB |
| `video_projects/` | 239 MB |
| `logs/` | 76 MB |
| `midjourney_web_cache/` | 73 MB |
| `images/` | 32 MB |
| `composites/` | 25 MB |
| `styles/` | 8.3 MB |
| `midjourney_web_storage/` | 7.9 MB |
| loose JSON files, `layout/` | < 1 MB |

## Goal

Add four **Move** buttons to the Settings tab. Each button relocates one group
of data to a directory that the user selects. The application then reads and
writes that group at the new location.

## Non-goals

- Per-directory relocation. The design moves groups, not single directories.
- Cloud or network destinations. The design supports local filesystem paths only.
- CLI flags for storage roots. The CLI reads the same `config.json`, so it
  follows the moved roots without new flags.

## 1. Groups

The design defines four groups. Each group has its own root. The user moves
each root independently. Each group keeps its existing subdirectory names under
the new root. Example: after a move of Images to `D:\ImageAI\Images`, the
generated images live in `D:\ImageAI\Images\generated`.

| Group | Contains | Size today |
|---|---|---|
| **Images** | `generated/`, `images/`, `composites/`, `styles/`, `Characters/`, `midjourney_web_cache/`, `midjourney_web_storage/` | 3.85 GB |
| **Video** | `video_projects/` | 239 MB |
| **Models** | `musetalk/`, `weights/`, `cache/` | 4.1 GB |
| **Settings** | `details.jsonl`, `*_history.json`, `*_session.json`, `batch_jobs.json`, `layout/`, `template_cache/`, `logs/` | 77 MB |

Notes on two placements:

- `styles/` holds user-authored style presets, not generated output. The design
  places `styles/` in Images because the user groups it there.
- `logs/` moves with Settings. `AGENTS.md` tells an agent to read the log first
  during an investigation. The log path must therefore follow the Settings root.
- `Characters/` holds Character Animator puppet output
  (`gui/character_animator/puppet_wizard.py:930`). The directory holds user
  output, not model weights, so it belongs to Images and not to Models. The
  directory does not exist on the author's machine yet, so it adds 0 bytes to
  the measured total.

### Verified: `generated/` is images only

The initial request listed `generated` under both Images and Video. Inspection
of the directory shows 2,938 files: PNG, JPG, PSD, and JSON sidecars. The
directory holds zero video files. Video output stays inside
`video_projects/<name>/{assets,exports,logs}`. The one video reference to
`generated/` is a debug-frame dump at `core/video/veo_client.py:461`, not clip
output. `generated/` therefore belongs to Images.

## 2. Path resolution layer

### 2.1 New module `core/paths.py`

A single resolver owns every data path.

```python
class Group(Enum):
    IMAGES, VIDEO, MODELS, SETTINGS

class DataPaths:
    def root(self, group: Group) -> Path       # config override, else platform default
    def images(self) -> Path                   # root(IMAGES) / "generated"
    def composites(self) -> Path
    def styles(self) -> Path
    def video_projects(self) -> Path
    def models(self) -> Path
    def logs(self) -> Path
    ...
```

`root()` reads an override from `config.json`. `root()` returns the platform
default when no override exists. The platform default matches today's value, so
an existing installation sees no change.

**Initialization order.** The file logger needs a log path, so the logger calls
`DataPaths`. `DataPaths` must therefore start before the logger. `core/paths.py`
must not import `core/logging_config.py`, and it must not import
`core/config.py`. `DataPaths` reads `config.json` directly with `json.loads`,
because `ConfigManager.__init__` runs key migrations and writes log records.
`DataPaths` reports its own errors through a deferred buffer that the logger
drains after the logger starts.

### 2.2 Config schema

```json
{
  "data_roots": {
    "images":   "D:\\ImageAI\\Images",
    "video":    null,
    "models":   "E:\\ImageAI\\Models",
    "settings": null
  }
}
```

A `null` value means "use the platform default".

### 2.3 `config.json` stays at the platform default

`config.json` records where every other group lives. The application must read
`config.json` before it can resolve any root. `config.json` therefore cannot
move. The Settings group moves every file **except** `config.json`.

This is the one asymmetry in the design. The cost is small: the file is 8 KB.

### 2.4 Call sites to rewrite

The audit on 2026-08-10 found:

- **36 call sites across 19 files** that build paths from `config_dir` or
  `get_user_data_dir()`. These change to `DataPaths` calls.
- **10 inline path builders across 7 files** that bypass both helpers and
  compute the platform directory themselves:
  - `core/logging_config.py:32`, `core/logging_config.py:146`
  - `core/video/config.py:107`
  - `core/video/project_manager.py:35`
  - `core/video/project_enhancements.py:325`
  - `core/video/veo_client.py:461`
  - `core/musetalk_installer.py:59`
  - `gui/history_widget.py:238`, `gui/history_widget.py:255`
  - `gui/midjourney_dialog.py:144`

This layer is most of the implementation work. The buttons are a thin surface
on top of it.

### 2.5 Bug found during the audit

`core/musetalk_installer.py:59` builds its own platform paths and disagrees
with `core/constants.py:140`:

- Windows: uses `Path.home() / "AppData" / "Roaming"` and ignores the `APPDATA`
  environment variable. A redirected profile therefore breaks.
- Linux: uses `~/.cache/imageai/musetalk`, but every other subsystem uses
  `$XDG_CONFIG_HOME/ImageAI`.

The rewrite to `DataPaths` fixes both. The Linux change moves the default
MuseTalk location. The installer must detect an existing `~/.cache/imageai`
directory and keep using it, so no user re-downloads 4 GB of weights.

## 3. Move operation

### 3.1 Module `core/data_migration.py`

The module is headless and imports no Qt. A GUI layer calls it.

```python
def move_group(group, dest, progress_cb, cancel_flag) -> MoveResult
```

### 3.2 Steps

1. **Validate the destination.** The destination exists or the application can
   create it. The destination is writable. The destination is not inside the
   source. The destination differs from the source. Free space exceeds the
   source size plus a margin (`shutil.disk_usage`).
2. **Copy the tree.** The function reports progress per file. The function
   checks the cancel flag between files.
3. **Verify the copy.** File count and total byte size must match. A mismatch or
   a cancel aborts the move. An abort removes the partial destination and
   leaves the source untouched.
4. **Write the new root** to `config.json` and `fsync` the file.
5. **Delete the source tree.**

### 3.3 Why the config write precedes the delete

A crash between step 4 and step 5 leaves a working application that points at
good data, plus a stale copy the user can delete. The reverse order can destroy
the only copy. The design therefore fixes this order.

### 3.4 Restart

The application prompts for a restart after a successful move. A restart avoids
the re-point of open file handles, the log writer, the video project manager,
the Midjourney watcher, and in-flight generation jobs. A live re-point of those
components has many more failure modes for no user-visible gain.

The prompt reads: `Moved 3.85 GB to D:\ImageAI\Images. Restart ImageAI to use
the new location?` The dialog offers **Restart Now** and **Later**.

## 4. Settings tab UI

`_init_settings_tab` at `gui/main_window.py:1606` gains a **Storage Locations**
group box with four rows:

```
Images    D:\ImageAI\Images                 3.85 GB   [Move…] [Open]
Video     C:\Users\aboog\AppData\Roaming…   239 MB    [Move…] [Open]
Models    C:\Users\aboog\AppData\Roaming…   4.10 GB   [Move…] [Open]
Settings  C:\Users\aboog\AppData\Roaming…   77 MB     [Move…] [Open]
```

- A worker thread computes each size. A walk of 8 GB blocks the UI thread
  otherwise. Each row shows `Calculating…` until its worker returns.
- **Move…** opens `QFileDialog.getExistingDirectory`. The dialog starts at
  `QStandardPaths.PicturesLocation` for Images, `MoviesLocation` for Video, and
  `AppDataLocation` for Models and Settings, each with an `ImageAI` subfolder
  appended.
- A confirmation dialog then shows the source, the destination, the size to
  copy, and the free space at the destination. No file moves before the user
  confirms.
- A modal progress dialog shows the current file and a percentage. The dialog
  offers **Cancel**.
- **Open** opens the directory in the platform file manager.

### 4.1 Defaults

The platform defaults do not change. A new installation writes to
`%APPDATA%\ImageAI` exactly as it does today.

The rationale: a changed default strands every existing installation and forces
a migration that nobody requested. Windows also redirects Pictures and Videos to
OneDrive on many machines. A default that writes 3.7 GB of generated images into
a synced Pictures folder is a poor default for other users. The folder picker
starts at Pictures and Videos, so the user gets the convenience without the
application making the decision.

## 5. Errors and logging

Every failure path logs through the standard logger, per the project rule that
all errors reach the log. Each failure shows a specific message:

| Condition | Message |
|---|---|
| No write permission at destination | Names the destination and the OS error. |
| Insufficient free space | States the required size and the available size. |
| Destination inside source | Explains that the destination cannot be a subdirectory of the source. |
| Source file disappears mid-copy | Names the file and aborts. |
| Verify mismatch | States the expected and the actual counts, and confirms that the source is intact. |
| User cancel | Confirms that the source is intact and that the partial copy is removed. |

## 6. Testing

Unit tests, all against `tmp_path`, no GUI:

- `DataPaths` returns the platform default for each group when no override
  exists, on Windows, macOS, and Linux.
- `DataPaths` returns the override when `config.json` sets one.
- `move_group` completes a happy-path move and updates `config.json`.
- `move_group` restores state after a cancel and removes the partial copy.
- `move_group` aborts on a verify mismatch and leaves the source intact.
- `move_group` rejects a destination with insufficient free space.
- `move_group` rejects a destination inside the source.
- `move_group` rejects a destination equal to the source.
- `DataPaths` falls back to the platform default for one unreachable root, and
  it leaves the other roots and `config.json` unchanged.
- The MuseTalk installer keeps an existing `~/.cache/imageai` directory on Linux.

One GUI smoke test confirms that the Storage Locations group box constructs.
This test matches the existing dialog smoke-test pattern.

## 7. Risks

| Risk | Mitigation |
|---|---|
| A missed call site writes to the old location after a move. | Grep for `config_dir` and `get_user_data_dir()` after the rewrite. The count must reach zero outside `core/paths.py`. |
| A move of 4 GB takes minutes and looks frozen. | Per-file progress plus a working Cancel button. |
| Data loss during the delete step. | Verify before delete. Write config before delete. |
| The Linux MuseTalk default changes and triggers a 4 GB re-download. | The installer detects and keeps an existing `~/.cache/imageai` directory. |
| A user selects a removable drive that later disappears. | The resolver falls back to the platform default and logs a warning when a configured root is unreachable at startup. The application warns the user in the Settings tab. |

## 8. Unreachable root at startup

A configured root can disappear. A removable drive can be absent, or a network
share can be offline. The application must not block on this condition, because
the CLI runs without a user present.

The rule: `DataPaths.root()` tests each configured root once at startup. When a
root is unreachable, `DataPaths` falls back to the platform default for that
group only, and it records a warning. The application never rewrites
`config.json` in this case, so the configured path returns when the drive
returns.

Each surface reports the fallback differently:

- The logger writes a warning for every unreachable root.
- The GUI shows a warning icon and the text `Unavailable — using default` in
  that group's row in the Storage Locations box. No modal dialog appears.
- The CLI writes one warning line per unreachable root to `stderr`. The CLI
  keeps `stdout` clean, per the existing `--json` output contract.
