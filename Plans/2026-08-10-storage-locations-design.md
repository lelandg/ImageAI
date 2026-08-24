# Configurable Storage Locations — Design

**Date:** 2026-08-10 — amended 2026-08-11 after a full path audit
**Status:** Approved design, not yet implemented
**Author:** Claude Code (with Leland Green)

## Problem

ImageAI writes every persistent file under one platform directory. On Windows
that directory is `%APPDATA%\ImageAI`. The directory holds 8.2 GB on the
author's machine. The user cannot move any part of it. The roaming profile
grows without limit, and the user cannot put large output on a second drive.

ImageAI writes to **three** separate trees, not one. A full audit on 2026-08-11
found the following. The `%APPDATA%` tree is the smallest of the three.

| Tree | Size | Notes |
|---|---|---|
| `~/.cache/huggingface` | **67 GB** | Stable Diffusion weights that ImageAI downloads. `models--stabilityai--stable-diffusion-2-1` alone holds 34 GB. |
| `%APPDATA%\ImageAI` | 8.2 GB | The tree named in the original request. |
| `~/.imageai` | 327 MB | `cache/` (248 MB) plus a `video_projects/` tree that holds the video events database. |
| **Total** | **~75.5 GB** | |

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
| **Video** | `video_projects/`, `~/.imageai/cache/{video,thumbnails,veo_videos}`, `~/.imageai/video_projects/events.db` | 566 MB |
| **Models** | `musetalk/`, `weights/`, `cache/`, the HuggingFace cache | 71.1 GB |
| **Settings** | `details.jsonl`, `*_history.json`, `*_session.json`, `batch_jobs.json`, `layout/`, `template_cache/`, `logs/` | 77 MB |

Notes on two placements:

- `styles/` holds user-authored style presets, not generated output. The design
  places `styles/` in Images because the user groups it there.
- `logs/` moves with Settings. `AGENTS.md` tells an agent to read the log first
  during an investigation. The log path must therefore follow the Settings root.
- The HuggingFace cache is the largest single item in the application at 67 GB,
  and it drives most of the reported disk pressure. Section 2.6 covers it.
- `~/.imageai/` is a second tree outside `%APPDATA%`. The video caches and the
  video events database live there. Both move with Video, because both belong to
  video work. Section 2.7 covers the move.
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

The full audit on 2026-08-11 found four classes of path source. All four change
to `DataPaths` calls.

**Class 1 — resolver-based.** 36 call sites across 19 files build paths from
`config_dir` or `get_user_data_dir()`.

**Class 2 — inline platform-directory builders.** These bypass both helpers:

- `core/logging_config.py:32`, `core/logging_config.py:146`
- `core/video/config.py:107`
- `core/video/project_manager.py:35`
- `core/video/project_enhancements.py:325`
- `core/video/veo_client.py:461`
- `core/musetalk_installer.py:71`
- `gui/history_widget.py:238`, `gui/history_widget.py:255`
- `gui/midjourney_dialog.py:143` (uses `QStandardPaths.AppDataLocation`)

**Class 3 — the `~/.imageai` tree.** Seven call sites across four files:

- `core/video/image_generator.py:54` → `~/.imageai/cache/video`
- `core/video/thumbnail_manager.py:30` → `~/.imageai/cache/thumbnails`
- `core/video/veo_client.py:917`, `core/video/veo_client.py:987` → `~/.imageai/cache/veo_videos`
- `gui/video/history_tab.py:195` → `~/.imageai/video_projects/events.db`
- `gui/video/video_project_tab.py:1827`, `gui/video/video_project_tab.py:2013` → same database

**Class 4 — the HuggingFace cache.** Four call sites, described in section 2.6.

### 2.5 Paths that must NOT move

The rewrite must leave these alone. They belong to other software:

- gcloud SDK and credentials: `core/gcloud_utils.py:46`,
  `core/gcloud_utils.py:75`, `providers/google.py:408`,
  `providers/google.py:1511`.
- System font directories: `core/layout/font_manager.py:85-98`.
- The bundled ffmpeg search path: `core/video/audio_segmenter.py:40`.
- The shared HuggingFace hub path in
  `core/character_animator/installer.py:254`. Section 2.6 explains why this one
  differs from the Local SD cache.

This layer is most of the implementation work. The buttons are a thin surface
on top of it.

### 2.6 The HuggingFace cache

`providers/local_sd.py:122` already reads a `cache_dir` key from the config:

```python
self.cache_dir = config.get("cache_dir", Path.home() / ".cache" / "huggingface")
```

Two other call sites ignore that key and hardcode the same default:
`gui/local_sd_widget.py:68` and `gui/model_browser.py:100`. The mechanism
therefore exists but works only on one of three paths. A user who set
`cache_dir` by hand would still see the model browser download to the old
location.

The fix routes all four download sites through `DataPaths.models() / "huggingface"`:

- `providers/local_sd.py:240`
- `gui/local_sd_widget.py:44`
- `gui/model_browser.py:63`
- `core/model_browser` install flow, wherever it calls `snapshot_download`

Each call already accepts an explicit `cache_dir=` argument, so no environment
variable is required. The design does **not** set `HF_HOME` or
`HF_HUB_CACHE`, because those variables affect every HuggingFace tool on the
machine, not just ImageAI.

**Character Animator is excluded.** `core/character_animator/installer.py:254`
reads `~/.cache/huggingface/hub` to detect models that other tools already
downloaded. That path stays fixed, because ImageAI does not own it.

**Existing weights are not re-downloaded.** The Models move relocates the
current `~/.cache/huggingface` content to the new root, so the 67 GB transfers
once rather than downloading again.

### 2.7 The `~/.imageai` tree

`~/.imageai` predates the `%APPDATA%` layout and holds two things: video caches
and a `video_projects/events.db` database. Both move with the Video group.

The database is the only SQLite file in the design. The migrator checkpoints
every database with `PRAGMA wal_checkpoint(TRUNCATE)` before it copies, which
folds the write-ahead log into the main file. The GUI closes its own
connections through the `pre_move` hook. Detecting a foreign process's
connection is not reliably possible, so the design does not attempt it. The
migrator must also copy any `-wal` and `-shm` sidecar files alongside the
database. A copy of a live SQLite database without its write-ahead log produces
a corrupt destination.

The empty `~/.imageai` directory is removed after a successful move.

### 2.8 Bugs found during the audit

**Hardcoded developer username.** `providers/google.py:1083` and
`providers/google.py:1292` both contain:

```python
debug_dir = Path("C:/Users/aboog/AppData/Roaming/ImageAI/generated")
```

This is the author's own username, shipped in released code. On any other
Windows machine the write fails or creates a stray `C:\Users\aboog` tree. The
rewrite replaces both with `DataPaths.images()`. This fix is independent of the
Move feature and should land first.

**Inconsistent MuseTalk platform paths.**
`core/musetalk_installer.py:71` builds its own platform paths and disagrees
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

   **Same-volume fast path.** The function compares the source volume and the
   destination volume first. On a match, the function calls `os.rename` and
   skips steps 2 and 3 entirely. A rename within one volume completes in
   milliseconds. This matters most for the Models group, where a cross-volume
   copy of 67 GB runs for many minutes but a same-volume move is instant. On
   Windows the function compares drive letters. On POSIX the function compares
   `st_dev`.
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
Video     C:\Users\aboog\AppData\Roaming…   566 MB    [Move…] [Open]
Models    C:\Users\aboog\AppData\Roaming…   71.1 GB   [Move…] [Open]
Settings  C:\Users\aboog\AppData\Roaming…   77 MB     [Move…] [Open]
```

A group can span more than one source tree. Models spans `%APPDATA%\ImageAI`
and `~/.cache/huggingface`. Video spans `%APPDATA%\ImageAI` and `~/.imageai`.
The row shows the combined size, and the row shows the new unified root once
the user moves the group. Until the first move, the row shows
`Default (2 locations)` with a tooltip that lists both.

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
- `move_group` takes the `os.rename` fast path when source and destination share
  a volume, and it takes the copy path when they do not.
- `move_group` merges two source trees into one destination root for the Models
  group and for the Video group.
- `move_group` copies `events.db` together with its `-wal` and `-shm` sidecars.
- `move_group` runs `PRAGMA wal_checkpoint(TRUNCATE)` on every database before
  it copies, and it calls the `pre_move` hook so the GUI can close its own
  connections first.
- `DataPaths.models()` supplies the `cache_dir` argument at all four
  HuggingFace download sites.
- `core/character_animator/installer.py` still reads the shared
  `~/.cache/huggingface/hub` path after the Models group moves.
- No source file contains the string `C:/Users/aboog`.

One GUI smoke test confirms that the Storage Locations group box constructs.
This test matches the existing dialog smoke-test pattern.

## 7. Risks

| Risk | Mitigation |
|---|---|
| A missed call site writes to the old location after a move. | Grep for `config_dir` and `get_user_data_dir()` after the rewrite. The count must reach zero outside `core/paths.py`. |
| A cross-volume move of 67 GB runs for many minutes and looks frozen. | Same-volume moves use `os.rename` and finish instantly. Cross-volume moves show per-file progress, a running byte count, and a working Cancel button. |
| A copy of a live `events.db` produces a corrupt destination. | Close the connection before the copy. Copy the `-wal` and `-shm` sidecars. Refuse the move while a connection is open. |
| The HuggingFace cache holds weights that other tools also use. | ImageAI moves only the cache that ImageAI passes as `cache_dir`. The shared hub path that Character Animator reads stays fixed. |
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
