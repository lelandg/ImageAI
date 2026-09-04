# Sprite tab — sub-project 5a (GUI-A) complete — 2026-08-30

**Branch:** `feat/sprite-tab` (not pushed; one PR after sub-project 7). **Range:** `64a9673..0ec7ce9` (17 commits).
**Suite:** 1639 passed / 19 skipped / 0 failures (`pytest -q`, offscreen). 5a added ~110 tests.

## What shipped
- `gui/sprite/` package: `workers.py` (SpriteWorker + WorkerHost), `prefs.py` (QSettings "ImageAI"/"Sprite"), `character_panel.py` (drop/browse → normalize → chroma plate → turnaround), `generation_settings_dialog.py` (named configs + live cost line), `action_cards_panel.py` (LLM brief → editable cards → Render/Refine, Cancel), `queue_panel.py` (drives ActionQueue, per-action + per-sheet cost labels), `sprite_tab.py` (assembly, project toolbar, status console, 5b hook slots).
- `core/sprite/configs.py`: `NamedConfigStore` (pure Python; the CLI reads the same file).
- `gui/main_window.py`: lazy Sprite tab; "Send to Sprite" from the Image tab, the History tab, and the Video reference library; `closeEvent` joins sprite workers.
- `core/sprite/generation/plate.py`, `action_cards.py`: optional cancel `token`.

## Review process
- Task-by-task SDD (10 tasks, each reviewed); final whole-branch review as a dynamic Workflow: 6 dimension reviewers + deferred-minor triage → 3-lens adversarial verification (58 agents). Result: 0 Critical, 2 Important, 12 Minor, 4 refuted.
- One fix wave (two parallel implementers): worker orphan handling (`shutdown()` never abandons a running QThread), `terminal_delivered` busy test, guarded progress, cancel checkpoints + Cancel button, `gemini → google` config-key map with `auth_mode`, `WA_DeleteOnClose` menus, refine pipeline failure → `card.error`, `NamedConfigStore` never overwrites an unreadable store, `SpriteProject.save()` RLock (interim).
- Scoped re-review (26 agents): all 12 closed; 1 new Important (second `shutdown()` reported all-clear while an orphan ran) + 5 Minor in the same window, fixed in `0ec7ce9` with regression tests.

## Owed / deferred
- **Leland (manual, Windows PowerShell):** click through the three "Send to Sprite" surfaces and the lazy tab load (plan Task 9 Step 7).
- Deferred to 5b/6 (listed in the 5b SDD ledger): CharacterPanel Ctrl+Enter binding (deviation 16), queue log levels in the console, GUI-only-writer save redesign, positional current-tab persistence, MainWindow wiring tests by source text, `deleteLater` on normally finished workers, `analyze_source` on the GUI thread.

## Next
Sub-project 5b (frame strip, preview, pixel view, processing, export panels): `.superpowers/sdd/2026-08-29-sprite-gui-b-plan/`, then 6 (image route + engine exports). Resume via `.superpowers/sdd/HANDOFF.md`.
