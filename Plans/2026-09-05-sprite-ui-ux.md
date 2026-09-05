# Sprite UI/UX Implementation Checklist

**Last Updated:** 2026-09-05 09:55
**Status:** Sizing complete; follow-up improvements planned
**Progress:** 3/10 tasks complete

## Overview

Make reference and preview images use their available pane space, retaining proportions and the complete image. The remaining items are a prioritized, code-based improvement plan; they are not included in this sizing change. No live provider jobs or production project edits are needed to validate the UI.

## Current change

- [x] Replace the 200-pixel reference thumbnail with a cached, proportional image that follows splitter resizing, including shrinking again (`gui/sprite/character_panel.py:47`).
- [x] Default the preview to automatic fit and add Original size (1×) / Fit to panel. Original size supports scrolling; manual zoom and Ctrl+0 leave fit mode (`gui/sprite/preview_player.py:121`, `gui/sprite/pixel_view.py:150`).
- [x] Verify splitter resizing, aspect ratio, large-frame downscaling, original-size persistence across frames, empty images, existing pixel tools, and directional zoom limits. Completed scoped lint, typecheck comparison, compilation, and offscreen visual inspection. See Notes/2026-09-05-sprite-ui-sizing.md for results.

## Follow-up implementation tasks (proposed)

- [ ] **P1: Preserve inspection state during unrelated refreshes.** `frames_workspace.py:_on_project_changed` reloads the same project's frames; `PreviewPlayer.set_frames` pauses and resets to frame zero. Retain frame identity/index, selected tag, and playback for an unchanged sequence. Reset deliberately when switching actions and clamp after deletions. Acceptance: editing another card or receiving queue updates does not interrupt playback or move the selected frame; deleted frames select a valid neighbor. Validate in workspace integration tests.
- [ ] **P1: Make bulk frame edits explicit.** `frame_strip.py:apply_duration` applies the displayed duration to all selected frames, but `_on_current_changed` displays only the current frame's value and editingFinished commits it. Show selection count and a Mixed state for differing durations/overrides; require an intentional edit or Apply to N frames. Acceptance: focusing and leaving a mixed-value field does not homogenize frames; an explicit change affects exactly the selection and remains undoable.
- [ ] **P1: Show preview freshness and next steps.** `_reload_player` loads profile metadata with warnings suppressed; changed processing settings do not have a persistent adjacent status. Reuse existing pipeline freshness checks to show Current, Needs processing, or No frames yet, with the relevant action. Give sources readable names (Editable frames, HD output, Pixel output). Acceptance: changing key/background/profile settings marks affected outputs; processing clears the indicator; existing export validation remains authoritative.
- [ ] **P2: Reveal relevant processing controls.** `processing_panel.py:_sync_enabled` broadly enables actions while extraction modes and key methods share visible parameter rows. Disable/hide inactive sampling values and method-specific settings, retaining their values. Group advanced edge cleanup settings. Acceptance: each extraction mode has one active sampling value; ML and chroma settings follow the selected method; disabled duplicate/jitter options disable their dependent inputs without erasing saved settings.
- [ ] **P2: Clarify render and queue actions.** `SpriteTab._on_render_requested` queues and starts immediately, while queue Start/Retry are enabled for any project and validate applicability after clicking. Render all only targets draft/failed cards. Use accurate labels such as Render pending, Start queued (N), and Retry failed selection; preserve selection during queue refresh. Acceptance: enabled controls have eligible work and operate on the rows their labels describe; queue progress does not discard selection.
- [ ] **P2: Make action editing usable in narrow panes.** `action_cards_panel.py` uses seven content-sized columns, a stretched prompt column, and multiple per-row buttons. Keep Render visible, move secondary actions to a row menu, and provide a multiline prompt editor and bounded numeric delegates. Acceptance: full prompts can be inspected and edited without horizontal scrolling; numeric fields reject invalid ranges before commit; test keyboard navigation and 125%/150% scaling.
- [ ] **P2: Expose undo and make card removal recoverable.** Frame undo already exists in `undo_controller.py` and shortcuts, while `_remove_selected` removes cards and autosaves outside that stack. Add visible frame Undo/Redo with labels and enabled state; design a separate reversible card-removal operation. Acceptance: mouse-only users can undo frame edits; restoring a card preserves identity, order, selection, and generated asset references. Keep the undo scope clear and do not delete assets as part of removal.

## Delivery order and validation

Implement the three P1 items individually, with scoped GUI/integration checks after each; then processing/queue clarity, narrow-pane editing, and undo discoverability. Use mocked providers, synthetic frames, temporary project storage, and explicit temporary INI preferences. Check empty, busy, failed, and completed states. Preserve native pixel picking, selection, nearest-neighbor rendering, and project serialization.

## Notes

Findings were checked against current source, including existing queue auto-start and export safeguards. This plan does not propose duplicate safety machinery. The sizing change only affects display, not stored frame dimensions or exports.

`Docs/CodeMap.md` is older than seven days and predates the current Sprite code. A separate refresh is recommended; symbol references above were checked directly against source.

