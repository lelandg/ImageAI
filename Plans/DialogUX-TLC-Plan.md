# Dialog & Tab UX TLC — Implementation Plan

**Last Updated:** 2026-07-06 09:46
**Branch:** `feat/dialog-ux-tlc`
**Audit findings:** `Notes/DialogUX-Audit-Findings-2026-07-06.md` (291 findings: 59 high / 142 medium / 90 low)

## Goal

Standardize splitters (visible, non-collapsible, persisted), expanding primary inputs,
status consoles for all LLM/long ops, app-wide hotkeys, and accessibility (focus,
mnemonics, keyboard parity) across every dialog and tab, per the standards below.

## App-wide hotkey standard

### `Ctrl+Return AND Ctrl+Enter (bind both sequences, always together)`
Primary action of the current dialog/tab (Generate, Enhance, Ask, Analyze, Export, Submit, or Accept-result after a successful run). After a result exists, the pair may be rebound to accept — but must rebind back when inputs change, and both sequences must move together.

**Current conflicts/gaps:** Keypad gap in every dialog that binds only 'Ctrl+Return' (prompt_generation_dialog.py:852, enhanced_prompt_dialog.py:431, prompt_question_dialog.py:552, reference_image_dialog.py:723, prompt_builder.py:1571 keyPressEvent, text_gen_dialog.py:451). INVERTED in midjourney_dialog.py:389 which binds 'Ctrl+Enter' only — dead on laptops without a numpad. Rewire gap: enhanced_prompt_dialog.py:655 and text_gen_dialog.py:435 leave stale bindings after generation (Ctrl+Enter accepts stale enhancement / re-generates over edits). MISSING entirely in ~25 surfaces: all 4 install dialogs, all 4 video-project dialogs, 3 video prompt dialogs, reference_generation_dialog, layout export/image-history/history_window, ExamplesDialog, SocialSizesDialog, WikimediaSearchDialog, RefineImageDialog, MidjourneyTab, BatchModeWidget, LipSyncWidget, DesignerPanel, both wizards' in-page primary buttons.

### `Enter / Return (default button)`
Activates exactly ONE explicit default button per dialog — the primary action (or the safe action for destructive dialogs). Every dialog must call setDefault(True) on it, setAutoDefault(False) on utility buttons, and give it initial focus. Inside a QTextEdit, Enter always inserts a newline (use Ctrl+Enter to submit).

**Current conflicts/gaps:** ExamplesDialog: hint says 'Enter to use' but Enter clicks Cancel (dialogs.py:103). MidjourneyWebDialog: Enter hits 'Copy Command Again' (midjourney_dialog.py:366). ProjectBrowserDialog: Enter hits Refresh, not Open (project_browser.py:106). ReferenceGenerationDialog: Enter in the style combo opens a file picker (reference_generation_dialog.py:362). Install confirm dialogs (install_dialog.py:110, character_animator/install_dialog.py:179, musetalk:131, whisper:132): initial focus lands on Cancel so Enter cancels despite Install being default. Install progress dialogs: no default/focus after completion, Enter dead (install_dialog.py:219 et al). MidjourneyMatchDialog.keyPressEvent accepts on bare Enter regardless of focus (midjourney_match_dialog.py:274) — drop, keep default-button semantics. SocialSizesTreeDialog binds bare 'Return' window-wide via btn_use.setShortcut (social_sizes_tree_dialog.py:193) — fires while typing in the search box; remove, setDefault already covers it. ReferenceImageDialog: analyze_btn default vs QDialogButtonBox OK ambiguity (reference_image_dialog.py:674). ImageHistoryDialog / HistoryWindow: no default, Enter resolution by accident (image_history_dialog.py:195, history_window.py:25).

### `Escape`
Close/cancel the dialog via QDialog reject — but ALL cleanup (worker stop/quit/wait, settings/geometry/splitter save, Discord presence reset) must live in an overridden done(result) (or the DialogCleanupMixin hook), never only in closeEvent. Permitted exceptions: context-sensitive Escape that cancels an inner edit mode first (prompt_question_dialog.py:560), and install progress dialogs that block Escape while work runs.

**Current conflicts/gaps:** Semantic conflict class, 12+ dialogs: prompt_generation_dialog.py:1489, enhanced_prompt_dialog.py:745, prompt_question_dialog.py:896, wikimedia_search_dialog.py:486, social_sizes_tree_dialog.py:547 (state loss), text_gen_dialog.py:621, export_dialog.py:404, reference_generation_dialog.py:929, select_existing_video_dialog.py:292 (audio keeps playing), video_prompt/start_prompt/end_prompt dialogs (presence stuck, threads running), refine_image_dialog.py:249 (no closeEvent at all). Also install_dialog.py:415: the Escape block checks only the installer, not the model downloader — Escape closes mid-download.

### `Ctrl+S`
Save Project — single owner: the File-menu QAction, window-wide, with tab-aware routing (image project / video project / layout session decided inside _save_project).

**Current conflicts/gaps:** CONFIRMED AMBIGUITY: File-menu 'Save Project' Ctrl+S (main_window.py:657) vs QShortcut(StandardKey.Save) for save-image (main_window.py:1475) — currently neither fires, though tooltips advertise it. Video workspace binds its own Ctrl+S/Ctrl+Shift+S (workspace_widget.py:318/320) — ambiguous with the menu action whenever the Video tab is loaded; must be removed or scoped WidgetWithChildrenShortcut with the menu action routing instead. Routing itself is broken: _save_project checks tab index 3 and nonexistent self.video_tab (main_window.py:7216) so Layout-tab Ctrl+S silently does nothing. Resolution: delete the :1475 image-save QShortcut; keyboard path to save-image is Alt+S (after mnemonic dedupe) plus the Save button.

### `Ctrl+Shift+S`
Save Project As (File menu QAction, window-wide, tab-routed).

**Current conflicts/gaps:** Duplicate binding in workspace_widget.py:320 — same ambiguity family as Ctrl+S; remove in favor of the routed menu action.

### `Ctrl+O`
Open Project (File menu, window-wide, tab-routed).

**Current conflicts/gaps:** None as a key; the tab-routing bug (main_window.py:7305/7318 video_tab/index-3 checks) breaks Open on the Video/Layout tabs.

### `Ctrl+Shift+C`
Copy generated image to clipboard (Image tab).

**Current conflicts/gaps:** None — but the button it guards is never connected until the Size Presets dialog opens (main_window.py:1560), so the shortcut works while the button doesn't.

### `Ctrl+F / F3 / Shift+F3`
Find (open Find dialog or focus help search) / find next / find previous.

**Current conflicts/gaps:** No key conflict. The prompt_edit Ctrl+F handling in the first eventFilter is dead code shadowed by the second definition (main_window.py:7448 vs :7759) — works only via the backup window QShortcut at :1487; merge the eventFilters.

### `F1`
Switch to the Help tab (StandardKey.HelpContents).

**Current conflicts/gaps:** None.

### `Alt+Left / Alt+Right / Backspace`
Help-browser back / forward / back — scoped Qt.WidgetWithChildrenShortcut to the Help tab ONLY.

**Current conflicts/gaps:** Currently WindowShortcut context despite comments claiming help-tab-only (main_window.py:2157): Backspace/Alt+Left anywhere in the app silently navigates the hidden help browser. Alt+Left/Right also fight the menu-mnemonic system while menus are open.

### `Delete`
Remove selected item(s) from editable lists (batch queue, reference lists), scoped Qt.WidgetWithChildrenShortcut to the list widget.

**Current conflicts/gaps:** Currently unbound everywhere (e.g. BatchModeWidget queue, batch_mode_widget.py:174 finding) — no conflicts, pure gap.

### `Enter / double-click on list items (itemActivated)`
Choose/apply the item — always connect QListWidget/QTableWidget itemActivated (fires for BOTH keyboard Enter and double-click), not itemDoubleClicked alone.

**Current conflicts/gaps:** Mouse-only today: ExamplesDialog list (dialogs.py:103 — Enter advertised but unwired), MidjourneyTab history (midjourney_tab.py:312), ProjectBrowserDialog table (project_browser.py:106), HistoryWindow (history_window.py:43), SocialSizesDialog table (social_sizes_dialog.py:103), ImageHistoryDialog cards (image_history_dialog.py:98).

### `Ctrl+E`
Reserved dialog-local: toggle edit mode on an otherwise read-only field (currently PromptQuestionDialog edit-prompt, prompt_question_dialog.py:556).

**Current conflicts/gaps:** None.

### `Alt+<letter> (mnemonics)`
One accelerator per frequently-used control, UNIQUE within the set of simultaneously visible widgets (menus count on every tab). Every field label gets '&' + setBuddy; every primary button gets a mnemonic.

**Current conflicts/gaps:** Alt+G: '&Generate' menu (main_window.py:717) vs '&Generate' button (:874). Alt+I: 'Ask About F&iles' (:861) vs '&Image Settings' (:913); also Templates-tab '&Insert' (:3172). Alt+S: '&Save' image (:895) vs '&Size Presets…' (:1046); Settings '&Save && Test' (:1659) vs 'Check &Status' (:1725). Alt+F/Alt+H: &File/&Help menus vs Help-tab '&Forward'/'&Home' buttons (:2139/:2161). Alt+C: model_browser '&Cancel Download' (:171) vs 'Download &Custom Model' (:279) — on-screen hint 'Alt+C to cancel' broken during downloads. Alt+O: &File-menu items vs 'Show &Original' (:889). Resolution map: menu Generate→'Ge&nerate', Image Settings→'I&mage Settings', Size Presets→'Si&ze Presets…', Check Status→'Check Stat&us', Help-tab Forward/Home→'For&ward'/'Ho&me', custom model download→'Download Custo&m Model'.

### `Ctrl+V (and all native editing keys)`
Native paste/undo/copy — NEVER shadowed by app QShortcuts.

**Current conflicts/gaps:** midjourney_dialog.py:387 binds window-level Ctrl+V to a placeholder that only logs a message, breaking paste in all the dialog's Qt widgets while the on-screen instructions tell users to press Ctrl+V. Remove it.


## Standards

# ImageAI GUI Standards (splitters, sizing, status consoles, accessibility)

These standards codify what the best existing code already does (`gui/main_window.py:796`, `gui/video/reference_generation_dialog.py:286`, `gui/llm_utils.py:127`) and extend the two existing helpers. **One new shared module is proposed: `gui/common/dialog_conventions.py`** — everything else builds on `gui/common/splitter_style.py` and `gui/llm_utils.py`.

## New helper module: `gui/common/dialog_conventions.py`

The audit shows the same five fixes are needed in 30+ files; a small helper makes each a one-liner and prevents regression:

```python
def standard_splitter(orientation, parent=None, *, handle_width=6) -> QSplitter
    # QSplitter + apply_splitter_style() + setChildrenCollapsible(False)

def persist_splitter(settings: QSettings, key: str, splitter) / restore_splitter(...)
    # saveState()/restoreState() under an explicit named key — never findChildren()[0]

def bind_primary_action(widget, slot, *, context=Qt.WindowShortcut) -> PrimaryAction
    # Creates BOTH QShortcut('Ctrl+Return') and QShortcut('Ctrl+Enter') wired to slot.
    # PrimaryAction.retarget(new_slot) rebinds both together (for accept-after-result
    # dialogs like EnhancedPromptDialog); .set_enabled(bool) for busy states.

def set_default_button(dialog, button, *, others_auto_default=False)
    # button.setDefault(True) + setFocus(); setAutoDefault(False) on every other
    # QPushButton in the dialog.

class DialogCleanupMixin:
    # Overrides done(result): calls self.on_dialog_close() exactly once (idempotent),
    # then super().done(result). closeEvent also routes through it. Subclasses put
    # worker shutdown / QSettings saves / presence resets in on_dialog_close().
    # Fixes the pervasive "cleanup only in closeEvent" bug (Escape/Cancel/OK bypass it).
```

Also in Batch 1: fix `OperationGuardMixin` in the existing `gui/dialog_utils.py` — the input-blocking event filter is installed on the dialog object only, so it never sees children's key/mouse events (dialog_utils.py:196). Install on `QApplication.instance()` scoped by `self.isAncestorOf(obj)`, or disable the content pane.

## Splitters

1. **Every** `QSplitter` is created via `standard_splitter()` (or, in existing code, immediately gets `apply_splitter_style(splitter)` + `splitter.setChildrenCollapsible(False)`). No pane may be collapsible to zero — the status console and control docks must be unlosable.
2. Store splitters as **named attributes** (`self.main_splitter`, `self.console_splitter`). Never look them up with `findChildren(QSplitter)[0]` — dialogs embedding `DialogHistoryWidget` contain a second splitter and the index lookup is order-dependent (prompt_generation_dialog.py:1476, enhanced_prompt_dialog.py:755, prompt_question_dialog.py:845).
3. **Persist** each user-adjustable splitter's state under its own QSettings key via `persist_splitter()/restore_splitter()`, saved from `on_dialog_close()` (never only closeEvent). Apply hardcoded `setSizes()` defaults only when no saved state exists (layout_tab.py:176 orientation-reset rule).
4. Never `setMaximumHeight`/`setFixedHeight` a widget that is a splitter pane — it silently defeats the drag (prompt_question_dialog.py:436, reference_image_dialog.py:702, history_widget.py:81). Use `setSizes()` for the initial proportion and `setMinimumHeight` for floors.
5. When two independently-resizable content areas are stacked in a fixed layout (list + details, text + preview), put them in a standard splitter instead (project_browser.py:76, wikimedia_search_dialog.py:224, prompt_builder.py:574).

## Expanding inputs (sizing)

1. **Primary text inputs never get a max-height cap.** No `setMaximumHeight()`/`setFixedHeight()` on the QTextEdit/QPlainTextEdit the user actually types their prompt/description/question into. Use `setMinimumHeight(~80)` + `QSizePolicy(Expanding)` and/or a stretch factor, or make it a splitter pane. (17 confirmed offenders: prompt_generation 755/870, enhanced_prompt 220, prompt_question 287/337, refine_image 207, reference_image 584, midjourney_tab 197, designer_panel 77, text_gen 504, reference_generation 305, font_wizard 1774, puppet_wizard 618, …)
2. **No `addStretch()` below a capped content area.** If a layout ends in stretch while a text/log widget above it is capped, the cap is wrong — give the content widget the stretch (midjourney_tab.py:274, midjourney_dialog.py:345, midjourney_match_dialog.py:152).
3. Caps are acceptable only for genuinely secondary, short, read-only strips (a 1–2 line hint label). Read-only *content* (commands, prompts, logs, details panes) follows rule 1.
4. **Pixmap previews rescale on resize.** Keep the original QPixmap and rescale in `resizeEvent` with `KeepAspectRatio` — scaled, never cropped/distorted (project rule). Copy the `_original_pixmap` pattern from `gui/font_generator/font_wizard.py:196-219`. Offenders: refine_image 269, midjourney_match 232, wikimedia 401, image_crop 301, enhanced_workspace 150, puppet_wizard 283.
5. Resizable dialogs that users enlarge repeatedly persist geometry (`saveGeometry()/restoreGeometry()` in QSettings, saved via `on_dialog_close()`).

## Status consoles

1. **Any dialog/widget performing LLM calls or long-running provider/network/install operations uses `DialogStatusConsole`** (`gui/llm_utils.py:127`) — not an ad-hoc QTextEdit (install dialogs, workspace_widget 748, model_browser 148, puppet_wizard 616), not a one-line QLabel (batch_mode 167, lipsync 367, reference_generation 422, wikimedia 248).
2. Placement: **bottom of the dialog, bottom pane of a `standard_splitter(Qt.Vertical)`** (AGENTS.md §8). No max-height cap on the console (its own design removes it — llm_utils.py:143); initial proportion via `setSizes()`.
3. The console is **visible while an operation runs** — never hidden-by-default during a normal run (designer_panel.py:91) and never hidden again on completion while errors may need reading.
4. Log per AGENTS.md §8: provider/model/temperature, the full outgoing prompt, the full response or error — with `log(..., level=...)` colors, plus `separator()` between runs. Every message accumulates (scrollback); one-line overwriting labels are not compliant.
5. **Long operations run in QThread workers.** No synchronous provider/network calls on the GUI thread (batch_mode 345, main_window _save_and_test 4590, workspace batch-enhance 3330, font_wizard identify 1514) and **no `QApplication.processEvents()`** as a substitute (workspace 4477, font_wizard 1514). Follow the existing `SceneSuggesterWorker`/`GCloudStatusChecker` pattern: progress signals → console.
6. Every long operation has a **cancel path** (Stop button or repurposed primary button) that actually stops the worker, and worker shutdown lives in `on_dialog_close()` so Escape/Cancel can't orphan a thread.

## Accessibility

1. **Initial focus goes to the primary input** (`setFocus()` at the end of init/showEvent): the prompt box, question box, search field, or name field — never whatever widget was created first. For confirm dialogs the *default button* takes focus (install confirm dialogs currently focus Cancel).
2. **Every field label gets a mnemonic + buddy:** `QLabel("&Provider:")` + `label.setBuddy(combo)`. This is both the Alt-accelerator and the screen-reader association. Mnemonics unique per visible scope (see hotkey table conflict map).
3. **No anonymous interactive controls.** Glyph-only buttons ('←', '◀', '⟳') get `setToolTip` + `setAccessibleName`. Card checkboxes/radios get `setAccessibleName` naming the item they control (reference_selection 59, reference_selector 45, variant_selector 78, scene_image_selector 162).
4. **Keyboard parity for every mouse gesture.** No monkey-patched `mousePressEvent` on QLabels/QFrames as the only interaction path (image_history 98, font_wizard 1088, enhanced_workspace 193): use focusable widgets (checkable QToolButton, or StrongFocus + Space/Enter in keyPressEvent) or list widgets with `itemActivated`. Tables users must read get focus + arrow navigation (workspace scene_table 1549).
5. **Theme-aware colors only.** No hardcoded light backgrounds/borders or `#666` text — use `gui/theme.py` constants or palette roles so text stays readable under the Maestro dark theme (prompt_builder 987, social_sizes_tree 133, history_tab 279, select_existing_video 79, suno 87). Never set a background without setting the foreground.
6. Destructive actions (Clear History, Clear Old Events) require a confirmation dialog, matching `BatchModeWidget._clear_queue`.

## Fix batches

Batch 1 must land first (shared helpers); batches 2+ have disjoint file sets and run in parallel.

### Batch 1 [P1]: Shared helpers: dialog_conventions module + dialog_utils guard fix + shared history widget ⏳
**Files:** `gui/common/dialog_conventions.py`, `gui/dialog_utils.py`, `gui/history_widget.py`

CREATE gui/common/dialog_conventions.py per the standards doc: standard_splitter() (apply_splitter_style + setChildrenCollapsible(False)), persist_splitter()/restore_splitter() (named QSettings keys), bind_primary_action() returning a PrimaryAction that binds BOTH 'Ctrl+Return' and 'Ctrl+Enter' with retarget()/set_enabled(), set_default_button() (setDefault + focus + setAutoDefault(False) on siblings), and DialogCleanupMixin whose done() override runs an idempotent on_dialog_close() hook (fixes the app-wide 'cleanup only in closeEvent' class). FIX gui/dialog_utils.py:196: OperationGuardMixin installs InputBlockerEventFilter on the dialog only, so child widgets never get blocked — install on QApplication.instance() filtered by self.isAncestorOf(obj), or disable the content pane during operations. FIX gui/history_widget.py (embedded in 4 LLM dialogs): apply standard splitter treatment to the :37 splitter (style + non-collapsible), remove detail_view.setMaximumHeight(150) at :81, persist splitter state via the already-created but unused QSettings at :27, wrap refresh_table population in setSortingEnabled(False)/(True) (:128), and add a QMessageBox.question confirmation to clear_history (:201). All later batches consume this module; commit it first (batches 2+ can then run fully in parallel — no file overlaps).

### Batch 2 [P2]: Generate Prompts dialog (gui/prompt_generation_dialog.py) ✅ COMPLETE
**Last Updated:** 2026-07-06 09:52 — done in working tree (477 tests green + offscreen
smoke test): standard/named/persisted splitters (main, results, and a NEW
`generate_splitter` making "Your Idea" draggable vs. the rest), input/preview caps
removed, DialogCleanupMixin with `on_dialog_close()` (worker stop + presence reset +
session/settings saves on every exit path), `save_settings` rewritten to persist named
splitters (was a `findChildren(QSplitter)[0]` NameError after the import removal),
`bind_primary_action` + `retarget()` replacing three stale `self.ctrl_enter_shortcut`
references that crashed after generation / on history load,
`set_default_button(generate_btn)`, mnemonics+buddies, Generate↔Stop cancel-in-flight
via `_on_generate_clicked` dispatcher + `_cancel_generation`, temperature/max_tokens
first-run defaults (`settings.value("temperature", 0.8, type=float)`). ALSO:
`gui/common/splitter_style.py` handles now visible at rest (center grip line, 8px
default) — app-wide fix for "invisible splitter" complaints; and repaired
`gui/layout/layout_tab.py` left broken mid-edit (QHBoxLayout/QSplitter import removal
with no body changes — 81 test failures), applying `standard_splitter` to its main split.
**Files:** `gui/prompt_generation_dialog.py`

Splitter (:734): replace with standard_splitter (styled + non-collapsible), keep as self.main_splitter, and persist it by reference — deleting the findChildren(QSplitter)[0] lookup at :1476/:901. Sizing: remove input_text.setMaximumHeight(100) (:755) with min-height + Expanding policy/stretch; remove preview_text cap (:870) and put results_list + preview_text in a nested standard splitter. Exit paths: adopt DialogCleanupMixin — override accept() (or on_dialog_close) so the OK/double-click/Ctrl+Enter path saves session, settings, geometry, and splitter state (:1304 finding); factor worker shutdown out of closeEvent (:1509-1531) into _stop_worker() used by every exit (:1489 finding). Cancel-in-flight: during generation, repurpose the Generate button as Stop wired to worker.stop() + thread.quit() + end_operation() (:1089, :724). Settings: restore temperature with settings.value('temperature', 0.8, type=float) (:1406 first-run 0.0 bug). Hotkeys: replace the single Ctrl+Return QShortcut (:852) with bind_primary_action, keeping the generate↔accept retarget logic at :1007/:1191/:1296 via PrimaryAction.retarget so keypad Enter follows. Accessibility: mnemonics + setBuddy for the settings-row labels (:766-820), '&Generate Prompts' accelerator, initial focus on input_text.

### Batch 3 [P2]: Main window: dead buttons, Ctrl+S ambiguity, tab-routing bugs, mnemonic dedupe, splitters ⏳
**Files:** `gui/main_window.py`

Correctness: move btn_save_image/btn_copy_image clicked.connect out of _open_social_sizes_dialog into _init_generate_tab (:1560 — buttons dead until the presets dialog opens, then multiply-connected); fix _submit_current_as_batch to use self.prompt_edit + self.batch_selector (:6652 — batch menu unreachable); fix _save_project/_save_project_as/_open_project video-tab delegation to compare self.tabs.currentWidget() is self.tab_video instead of index==3 + nonexistent video_tab (:7216, :7305, :7318); fix _open_midjourney_external_browser cbo_model→model_combo (:6790); fix error-report URL to https://github.com/lelandg/ImageAI/issues, hoisted to a constant shared with :2169 (:9052). Hotkeys: DELETE the StandardKey.Save QShortcut (:1475) so the File-menu Ctrl+S is the single owner (resolves the ambiguous-shortcut deadlock; update Save-button tooltip/hint bar); scope Alt+Left/Alt+Right/Backspace help shortcuts with Qt.WidgetWithChildrenShortcut (:2157); scope the Ctrl+Return/Meta+Return generate shortcuts to tab_generate WidgetWithChildrenShortcut per the standard (:1467); merge the two eventFilter definitions into one dispatcher (:7448 dead code vs :7759). Mnemonics per the conflict-resolution map in the hotkey table: Ge&nerate menu, I&mage Settings, Si&ze Presets…, Check Stat&us, For&ward/Ho&me on the Help tab (:913 finding set). Splitters: apply_splitter_style + setChildrenCollapsible(False) on image_console_splitter (:1337) and apply_splitter_style on ref_splitter (:1197); store all three Generate-tab splitters as named attributes and persist each in _save_ui_state/_restore_ui_state (:8616). Long ops: move _save_and_test validate_auth() into a QThread worker mirroring GCloudStatusChecker, disable the button while running (:4590). Sizing/accessibility: drop midjourney_command_display 120px cap (:1363), prompt_edit initial focus (:824), buddies/mnemonics for LLM Provider/Model/Image Provider rows (:736).

### Batch 4 [P3]: Prompt dialogs: Enhanced Prompt + Ask About Prompt ⏳
**Files:** `gui/enhanced_prompt_dialog.py`, `gui/prompt_question_dialog.py`

enhanced_prompt_dialog.py: standard_splitter on the main splitter (:205 — style + non-collapsible, fixes both :205 findings); remove prompt_display 100px cap (:220); named-splitter persistence replacing findChildren[0] (:755); DialogCleanupMixin so reject() runs the worker shutdown now only in closeEvent (:745); forward reasoning_effort/verbosity into enhance_with_llm or hide the combos (:124); replace the Ctrl+Return QShortcut with bind_primary_action and retarget on textChanged after enhancement so editing re-arms Enhance (:655, :431); disable OK until a result exists and enable in on_enhancement_finished/load_history_item (:689), fixing the dead use_button guard (:742) to self.ok_button; label buddies/mnemonics (:231). prompt_question_dialog.py: route ALL providers through litellm.completion with the built messages list — adds the missing Anthropic branch (:123 dead-end) and gives Gemini its conversation history + temperature (:170); pass reasoning/verbosity for gpt-5 or hide the row (:129); standard_splitter on the conversation splitter (:266, :440); remove question_input 80px cap (:337) and prompt_input 80px cap (:287); delete status_console.setMaximumHeight(150) (:436); DialogCleanupMixin for reject-path worker shutdown (:896); named splitter persistence (:845); bind_primary_action for Ask (:552); initial focus on question_input (:333); rebuild quick-questions combo only when has_prompt flips (:540); copy GPT-5 tooltips + buddies (:373).

### Batch 5 [P3]: Video workspace: eventFilter merge, threaded LLM ops, column constants ⏳
**Files:** `gui/video/workspace_widget.py`, `gui/video/enhanced_workspace.py`

workspace_widget.py: merge the THREE eventFilter definitions (:340, :3939, :4319) into one dispatcher — restores scene-table hover preview, video-button double-click regenerate, wheel scrolling, and context-menu hiding; define COL_* constants and fix the Start-Prompt widget lookup column 8→11 (:5863) and default_widths {8,9,10}→{10,11,12} (:4038); move batch_enhance, video-prompt, end-prompt, and LLM-sync calls into QThread workers on the SceneSuggesterWorker pattern and delete the processEvents() in _log_to_console (:3330, :4477); replace the bespoke console QTextEdit with DialogStatusConsole kept as the bottom pane of image_console_splitter (:748); persist left_splitter as self.left_splitter alongside the other three and add setChildrenCollapsible(False) to left_splitter/h_splitter (:443, :479); give scene_table StrongFocus + Up/Down/Enter navigation mapped to the preview logic (:1549); remove the duplicate Ctrl+S/Ctrl+Shift+S QShortcuts (:318/:320) in favor of the routed menu actions (coordinates with the Batch-3 Ctrl+S standard); replace bare QInputDialog refine/extend prompts with a small Ctrl+Enter-capable dialog (:4642); input_text initial focus (:885); ManageStylesDialog default-button cleanup (:144). enhanced_workspace.py: wire or hide the dead Preview/Set-Start/Set-End/Regenerate/Apply-to-All buttons (:548, :305, :445); make delete_current's protected-frame guard real by passing the project in (:235); replace monkey-patched thumbnail labels with checkable QToolButtons (KeepAspectRatio icons — fixes distortion) with tooltips/accessibleName (:193); tooltips/accessibleName on ◀/▶ (:54); preview rescale on resizeEvent (:150).

### Batch 6 [P3]: Small dialogs: Examples, Find, Prompt Builder, Model Browser ⏳
**Files:** `gui/dialogs.py`, `gui/find_dialog.py`, `gui/prompt_builder.py`, `gui/model_browser.py`

dialogs.py ExamplesDialog: set_default_button(btnOK) + listw.itemActivated→_on_ok so Enter matches the on-screen hint instead of clicking Cancel (:103); bind_primary_action (:30); QSettings geometry + initial list focus/selection (:33). find_dialog.py: restore last_search under blockSignals so init doesn't paint orphaned highlights, and move highlighting to setExtraSelections (systemic fix — stops corrupting the document/undo stack) (:417); disable 'Whole words' with tooltip for webviews (:67); button mnemonics + Find-label buddy (:86). prompt_builder.py: remove preview_text/notes_edit caps and give the preview a splitter/stretch (:518); History tab list+details into a standard splitter, drop the 200px cap, persist state (:574); delete the hardcoded light-theme button stylesheets or move accent styling into gui/theme.py (:987); fix keyPressEvent to match Key_Enter + mask KeypadModifier (:1571); Ctrl+Enter on SavePresetDialog (:44); initial focus + button/label mnemonics (:551). model_browser.py: wire real download progress (per-file hf_hub_download loop or tqdm_class) and check _should_stop between files so Cancel works (:53); standard_splitter + persistence on the popular-models splitter (:200); replace the capped status QTextEdit with DialogStatusConsole in a bottom splitter (:148); make non-modal + closeEvent guard for the running downloader (:104); returnPressed→download + per-tab default button + bind_primary_action (:272); fix Alt+C collision → 'Download Custo&m Model' (:279); QSettings geometry (:105).

### Batch 7 [P4]: Midjourney family: dead Ctrl+Enter, splitters, consoles, param persistence ⏳
**Files:** `gui/midjourney_dialog.py`, `gui/midjourney_tab.py`, `gui/midjourney_match_dialog.py`

midjourney_dialog.py: replace the keypad-only QShortcut('Ctrl+Enter') with bind_primary_action→on_image_ready (:389 — primary shortcut currently dead on laptops); REMOVE the Ctrl+V placeholder shortcut (:387); set_default_button(ready_btn) with setAutoDefault(False) on the six utility buttons (:366); add DialogStatusConsole at the bottom in a standard splitter and route download/login/import feedback into it (:242); standard splitter treatment + state/geometry persistence (:245, :239); relax command_display cap in favor of stretch (:301). midjourney_tab.py: remove prompt_edit 200px cap + trailing addStretch, give prompt group the stretch (:197, :274); remove command_display cap (:224); bind_primary_action→copy_command scoped to the tab + tooltip (:245); standard splitter + persistence on the 3-pane splitter (:54); itemActivated for history restore + tooltip (:312); add the 4 missing template entries (:287); reset all param widgets before _parse_parameters in restore_from_history (:490); persist the full parameter set + history (:681). midjourney_match_dialog.py: drop the bare-Enter accept branch from keyPressEvent, set accept_btn default + setAutoDefault(False) on Skip/Not-This (:274); standard splitter treatment (:59); remove prompt_display cap, give prompt_group the stretch (:126); rescale preview on resizeEvent (:232). DEFERRED (touches main_window.py, owned by the priority-2 batch): renaming the shadowing accepted/rejected signals (:22) — apply as a follow-up line item after both batches merge.

### Batch 8 [P4]: Image dialogs: Refine, Reference Analysis, Crop, Reference Selection ⏳
**Files:** `gui/refine_image_dialog.py`, `gui/reference_image_dialog.py`, `gui/image_crop_dialog.py`, `gui/reference_selection_dialog.py`

refine_image_dialog.py: standard splitter treatment on the image/chat splitter (:149 both findings); remove prompt_input 120px cap via nested splitter or Expanding policy (:207); ADD DialogStatusConsole at the bottom in a splitter and route RefineWorker traffic + full prompts/responses into it (:211); bind_primary_action→_on_refine_clicked (:224); QSettings geometry+splitter persistence mirroring ReferenceImageDialog (:130); rescale image on resizeEvent (:269); DialogCleanupMixin + cancel/confirm for the running worker (:249); initial focus + truncation tooltips (:136, :326). reference_image_dialog.py: apply_splitter_style + setChildrenCollapsible(False) on the :541 splitter; remove analysis_prompt 80px cap (:584); delete status_console.setMaximumHeight(150) (:702); add 'Ctrl+Enter' companion shortcut + resolve analyze-vs-OK default ambiguity (rename OK to 'Use Description') (:674); label buddies + initial focus (:577). image_crop_dialog.py: fix the help label rich-text \n collapse with <br> (:196); re-fit view in resizeEvent/showEvent (:301); QSettings geometry (:169); Ctrl+Enter→accept_crop for consistency (:231). reference_selection_dialog.py: allow 1..max selections instead of exact-quota (:250); grid/flow layout for cards (:204); deselect the just-clicked card instead of highest-index on overflow (:239); accessibleName/tooltip per card checkbox (:59).

### Batch 9 [P4]: Social sizes + Wikimedia dialogs: broken tree filter, stale highlights, worker cleanup ⏳
**Files:** `gui/social_sizes_tree_dialog.py`, `gui/social_sizes_dialog.py`, `gui/wikimedia_search_dialog.py`

social_sizes_tree_dialog.py: rewrite _apply_filter to walk all three tree levels and expand category+platform on match (:329 — search currently empties the tree); fix _clear_all_highlights to the size-item level or track the last-highlighted item, using theme selection colors instead of hardcoded light blue (:403 — unreadable white-on-white rows); save expansion/selection state in an overridden done() so Close/Esc persist it (:547); remove the window-wide bare-Return btn_use.setShortcut, keep setDefault + add bind_primary_action (:193); theme-aware info panel + font-metrics height (:133); persist geometry (:73); '&Search:' buddy + button mnemonics (:149). social_sizes_dialog.py: it is dead code — DELETE it, moving the shared _parse_markdown_table/_extract_resolution_px helpers into a module the tree dialog imports (:66; supersedes the :103 hotkey finding). wikimedia_search_dialog.py: standard splitter treatment + persistence on the results/details splitter (:198); move worker cancel/quit/wait cleanup into done() (accept and Escape currently leak threads) (:486); add DialogStatusConsole at the bottom logging search/download/thumbnail results incl. per-file failures (:248); bind_primary_action→_download_selected + itemDoubleClicked download (:255); details_text+preview into a nested standard splitter (:224); geometry persistence (:175); rescale preview on resize (:401); search-label buddy (:149).

### Batch 10 [P4]: Video project dialogs: clear-events crash, stale-path lockout, playback leak ⏳
**Files:** `gui/video/history_tab.py`, `gui/video/project_dialog.py`, `gui/video/project_browser.py`, `gui/video/select_existing_video_dialog.py`

history_tab.py: fix clear_old_events AttributeError (all_events→current_events, _apply_filters→apply_filter) and implement real EventStore deletion (preserving restore points) before claiming 'Cleanup Complete' (:499); standard splitter treatment + persistence (:53); implement or remove the no-op 'Show Details' checkbox (:427); theme-aware date-group and event-type colors (:279); honor the second QInputDialog's cancel in create_restore_point (:379); real events.db size for the Storage label (:444). project_dialog.py: reset/re-derive selected_project on failed validation so one stale path doesn't lock the dialog (:326); try/except + encoding='utf-8' in update_info (:299); Ctrl+Enter primary-action shortcuts in all three dialogs (:158); list+info group into a standard splitter (:218); name_edit initial focus (:53). project_browser.py: set_default_button(open_btn) + setAutoDefault(False) on Refresh/Cancel + bind_primary_action→open_selected (:106); table+details into a standard splitter persisted in the existing QSettings (:76); geometry + header-state persistence (:35). select_existing_video_dialog.py: override done() to stop media playback on every exit (:292); standard splitter treatment + persistence (:83); video+context_info into a nested splitter, drop the 150px cap and the 100-char prompt truncation (:136); theme-aware info banner (:79).

### Batch 11 [P4]: Wizards: font-export data loss, threaded AI identify, keyboard glyph selection ⏳
**Files:** `gui/font_generator/font_wizard.py`, `gui/character_animator/puppet_wizard.py`

font_wizard.py: add unsaved-export protection — override accept()/reject()/closeEvent to warn when glyphs exist but exported_path is None (Enter on the last page currently discards paid AI-generated glyphs silently), and bind Ctrl+Enter→export_font on the ExportPage (:2348); move identify_with_ai into a QThread worker (reuse GlyphGenerationWorker pattern), add a DialogStatusConsole at the bottom of the mapping page in a standard splitter streaming per-glyph results, with Cancel (:1514, shared with :1363's generate-missing-glyphs feedback); run AI-assisted segmentation in a worker with progress (:712); preview_image+status_text into a standard splitter, drop the 120px cap (:402); remove sample_edit 80px cap via splitter with the preview (:1774); restore saved sample_text or delete the dead setting (:2322); glyph tiles: TabFocus + Space toggle + accessibleName instead of monkey-patched mousePressEvent (:1088); buddies/mnemonics + per-page initial focus (:1590); persist wizard geometry (:2335). puppet_wizard.py: standard splitter treatment + setSizes + persistence on the segmentation splitter (:323); remove output_text 150px cap so the generation log fills its stretch (:618); replace it with DialogStatusConsole at the bottom of a styled splitter (:616); per-page Ctrl+Enter→start_generation/export_puppet (:627); preview rescale on resizeEvent copying font_wizard's pattern (:283); buddies/mnemonics + initializePage focus (:543); persist geometry (:1234).

### Batch 12 [P5]: Layout tab + designer panel ⏳
**Files:** `gui/layout/layout_tab.py`, `gui/layout/designer_panel.py`

layout_tab.py: standard splitter treatment on _main_split (:100 both findings — style + non-collapsible); persist split.sizes() per orientation and only apply the hardcoded defaults when no saved sizes exist (:176); move the 13-button toolbar to a QToolBar with overflow (or menu-group the export/import actions) and add the missing tooltips (:58); severity-styled status messages via a _set_status(msg, level) API (:184). designer_panel.py: replace prompt_edit setFixedHeight(70) with min-height + Expanding, and put prompt_edit + console into a standard vertical splitter (fixes both the :77 sizing and :92 console-splitter findings); auto-expand the status console when start_design/suggest begins so LLM progress is visible (:91); bind_primary_action('Ctrl+Return' both keys)→design_btn.click scoped to the panel (:80); 'Model:' label or tooltip+accessibleName on model_combo (:62); mnemonics/buddies on Kind/Provider/Model (:52); initial focus to prompt_edit on first show of the Layout tab (:74).

### Batch 13 [P5]: Layout dialogs: text gen, export, image history, document props, history window ⏳
**Files:** `gui/layout/text_gen_dialog.py`, `gui/layout/export_dialog.py`, `gui/layout/image_history_dialog.py`, `gui/layout/document_dialog.py`, `gui/layout/history_window.py`

text_gen_dialog.py: apply_splitter_style + setChildrenCollapsible(False) on the :416 splitter (both findings); remove custom_prompt_edit 100px cap (:504); move worker/Discord cleanup into done() (:621); after generation retarget the PrimaryAction + default button to Apply, restore to Generate on settings change, add shortcut tooltips/hint label (:435); implement geometry/splitter/temperature persistence in the empty stubs (:529); initial + on-toggle focus (:411). export_dialog.py: DialogStatusConsole at the bottom in a standard splitter fed by ExportWorker signals (:234); done()-based cleanup + in-progress confirmation + cooperative cancel flag in the worker loop (:404); bind_primary_action→start_export (:247); disable DPI/page-range groups for JSON (:175). image_history_dialog.py: keyboard-accessible cards — StrongFocus + Space/Return + focus ring + accessibleName, or QListWidget IconMode (:98 accessibility); async thumbnail loading, drop dead QThread/QSplitter imports (:208); set_default_button(select_btn) + cancel autoDefault off + guarded Ctrl+Enter (:195); responsive column count (:272); double-click accept + geometry persistence (:98 usability). document_dialog.py: tooltip + accessibleName + hex text on the five theme color swatches (:198). history_window.py: disable Restore until selection + itemDoubleClicked→restore (:43); explicit default button + Ctrl+Enter (:25).

### Batch 14 [P5]: Install-dialog family: Escape-during-download bug, consoles, focus, modality ⏳
**Files:** `gui/install_dialog.py`, `gui/character_animator/install_dialog.py`, `gui/video/musetalk_install_dialog.py`, `gui/video/whisper_install_dialog.py`

install_dialog.py: extend reject() to also block while self.downloader.isRunning(), mirroring character_animator/install_dialog.py:537 (:415 — Escape currently orphans a multi-GB download); replace the output QTextEdit with DialogStatusConsole as the bottom pane of a standard splitter (:194); make the progress dialog non-modal OR remove the contradictory 'runs in background' messaging (:131); install_btn.setFocus() in the confirm dialog + optional Ctrl+Enter (:110); default+focus on restart/close when completion buttons appear (:219, :469). character_animator/install_dialog.py: same console-in-splitter conversion (:279); same non-modal/messaging decision (:208); confirm-dialog focus (:179); stop elapsed_timer on the failure branch (:384); completion default+focus (:487). musetalk_install_dialog.py: console conversion (:216); non-modal/show() decision (:152); confirm focus (:131); completion default+focus (:349). whisper_install_dialog.py: console conversion (:215); non-modal decision (:153); confirm focus (:132); reconcile the 'ready to use' vs 'restart required' messaging (:306); completion default+focus (:310). Apply one consistent modality decision across all four (recommended: non-modal show() + the existing reject() guards).

### Batch 15 [P5]: Video prompt dialogs: status consoles, done()-cleanup, OK-during-generation ⏳
**Files:** `gui/video/start_prompt_dialog.py`, `gui/video/video_prompt_dialog.py`, `gui/video/end_prompt_dialog.py`, `gui/video/reference_generation_dialog.py`, `gui/video/reference_selector_dialog.py`

All three prompt dialogs (start_prompt_dialog.py, video_prompt_dialog.py, end_prompt_dialog.py): add DialogStatusConsole at the bottom inside a standard vertical splitter, streaming progress_update/complete/failed plus full prompts/responses (:331, :122, :99); move context+generated-prompt groups into that splitter and drop the 80px caps (:230, :124, :101); bind_primary_action→accept (:295, :174, :167); disable OK while the generation thread runs (:184 covers all three); move Discord presence reset + thread quit/wait into done() (:232 covers all three); initial focus on generated_prompt_edit (:130); geometry persistence via the reference_selector pattern (:114). reference_generation_dialog.py: remove description_edit 100px cap + stretch (:305); DialogCleanupMixin so Close/Escape run worker shutdown + save_settings + presence reset (:929); replace the mid-dialog status_label with a DialogStatusConsole at the bottom of the existing styled splitter (:422); generate_btn default via set_default_button (:362) + bind_primary_action→start_generation (:412); splitter setChildrenCollapsible(False) + geometry/splitter persistence (:285); wire quality_combo into the worker or remove it (:337); initial focus + buddies (:303). reference_selector_dialog.py: checkbox accessibleName + whole-card click target (:45); wrapping grid layout (:162); Ctrl+Enter→accept (:216).

### Batch 16 [P6]: Batch mode widget: threaded jobs + status console ⏳
**Files:** `gui/batch_mode_widget.py`

Move create_batch_job, get_job_status polling, and get_job_results into QThread/QThreadPool workers with progress signals (:345 — submission/poll/download currently freeze the GUI); add a DialogStatusConsole at the bottom inside a standard vertical splitter and log submissions, per-job polls, and FULL error text instead of the 50-char status label (:167); apply standard splitter treatment + QSettings persistence to the queue/jobs splitter (:68, :134); bind_primary_action→_submit_batch and a widget-scoped Delete shortcut→_remove_selected (:174); ExtendedSelection on queue_list with descending-index removal (:76); 'Batch &Size:' buddy, button mnemonics, tooltips on refresh/download/submit (:145).

### Batch 17 [P6]: Video misc: lipsync, suno preprocess, variant/scene selectors ⏳
**Files:** `gui/video/lipsync_widget.py`, `gui/video/suno_preprocess_dialog.py`, `gui/video/variant_selector_dialog.py`, `gui/video/scene_image_selector_dialog.py`

lipsync_widget.py: standard splitter treatment (style + non-collapsible, :235 both findings) + QSettings state persistence (:393); replace the one-line output_status with a DialogStatusConsole at the bottom of a styled splitter fed by LipSyncGenerationThread progress (:367); widget-scoped Ctrl+Enter→start_generation (:398); real status_icon glyphs or remove the label (:428); tooltip on the disabled D-ID item (:322). suno_preprocess_dialog.py: bind_primary_action→_validate_and_accept (:170); right-align buttons Cancel-then-primary to match siblings (:189); cancellable/determinate merge progress or documented rationale (:312); theme-aware #666 text (:87). variant_selector_dialog.py: disable Select until a selection exists, matching SceneImageSelectorDialog (:137); radio accessibleName/tooltips (:78); Ctrl+Enter→accept (:138). scene_image_selector_dialog.py: radio accessibleName per scene/type/file (:162); guarded Ctrl+Enter (:95); thumbnail tooltips/focusable cards (:193); geometry persistence for all three dialogs (:35).
