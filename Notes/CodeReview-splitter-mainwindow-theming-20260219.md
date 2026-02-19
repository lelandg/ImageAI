# Code Review: Maestro UI Theming — Tasks 4 & 5
**Date:** 2026-02-19 10:17
**Reviewer:** Claude (code-reviewer agent)
**Files reviewed:**
- `gui/common/splitter_style.py`
- `gui/main_window.py` (import block and all inline-stylesheet sites)
**Plan reference:** `Plans/2026-02-19-maestro-ui-redesign.md` — Tasks 4 and 5
**Base SHA:** dd3b725 | **Head:** uncommitted working-tree changes

---

## Summary

Both files syntax-check cleanly. The overall direction is correct: all structural/widget-level stylesheets that used light-mode grays have been converted to dark-theme constants. The import placement is good. Several targeted issues are called out below; one is categorized Critical because it causes a visible inconsistency against the global QSS, the rest are Important or Suggestions.

---

## What Was Done Well

- All `setStyleSheet` calls for widget-level backgrounds and borders (`output_image_label`, `output_text`, `midjourney_command_display`, `social_size_label`, `quick_setup`, toggle buttons, etc.) are correctly converted to f-strings using theme constants.
- The three HTML template blocks (WebEngine branch, QTextBrowser branch, and `_basic_markdown_to_html`) are fully converted with no residual light-mode colors — this is a large surface area that was handled completely.
- `_append_to_console` default parameter is now `TEXT_SECONDARY` (plan Step 6 complete) and the error-color guard correctly accepts both `"#ff6666"` and `RED` (plan Step 6 complete).
- `ref_hint_label` is now `CYAN` instead of `#2196F3` (plan Step 9 complete).
- The `_update_ref_image_toggle_label` method at lines 7660 and 7676 uses theme constants correctly for the count-badge variant.
- `splitter_style.py` is clean: f-string, correct constants, correct relative import, docstring updated.

---

## Issues Found

### Critical

#### 1. `gcloud_status_label` and `discord_status_label` use bare CSS named colors (`"color: green;"`, `"color: blue;"`, `"color: red;"`) — 7 sites

**Lines:** 1830, 4486, 4500, 4510, 4581, 6515, 6581

These status labels set color via bare CSS names at runtime, bypassing the theme. On the Maestro dark background, `color: green` renders as web/system green (roughly `#008000`), which has poor contrast against `#050711` (NAVY_DARK) and clashes with the brand green `#4CAF50`. `color: blue` and `color: red` have the same problem.

The plan does not explicitly list these in a numbered step, but it does state in the preamble: "A small set of hardcoded light-mode inline stylesheets in `main_window.py` ... will be updated to use the theme constants." These are inline `setStyleSheet` calls with raw CSS color names, which fall squarely in-scope.

**Required fix — replace all 7 occurrences:**

```python
# Authenticated / connected (green)
self.gcloud_status_label.setStyleSheet(f"color: {GREEN};")
self.discord_status_label.setStyleSheet(f"color: {GREEN};")

# Checking / informational (blue -> CYAN is the brand accent; CYAN_DARK is a good calm tone)
self.gcloud_status_label.setStyleSheet(f"color: {CYAN_DARK};")

# Not authenticated / error (red)
self.gcloud_status_label.setStyleSheet(f"color: {RED};")
```

The Discord partial-connection warning at line 6586 uses `"color: #cc6600;"` — this should become `f"color: {AMBER};"`.

```python
# Line 6586 — Discord partial failure (orange)
self.discord_status_label.setStyleSheet(f"color: {AMBER};")
```

Note that `CYAN_DARK` is not currently imported in `main_window.py`. Either add it to the import on line 87–91, or use `CYAN` for informational states — both are acceptable. `AMBER` is already imported.

---

### Important

#### 2. `btn_insert_prompt` stylesheet at line 3091 is not an f-string — no plan coverage gap but inconsistent style

**Lines:** 3091–3096

```python
self.btn_insert_prompt.setStyleSheet("""
    QPushButton {
        padding: 8px;
        font-weight: bold;
    }
""")
```

This stylesheet carries no color properties, so it does not contradict the dark theme (the global QSS will paint this button cyan as any other `QPushButton`). It is not a color regression. However, the Task 5 plan listed line 3080 as one of the toggle-button sites to fix; this is nearby and may have been mistakenly skipped or conflated.

Verify that this button's appearance is acceptable under the global QSS. If it renders correctly as a themed `QPushButton`, no change is needed. If it needs special treatment, add theme constants consistent with the toggle-button pattern used at lines 882 and 1092.

**Verdict:** Low risk, but worth a visual check at runtime.

---

#### 3. `_append_to_console` call sites still pass 69 raw hex literals for message coloring — not a regression, but consider future work

**Pattern:** `self._append_to_console(message, "#66ccff")`, `"#00ff00"`, `"#ff6666"`, `"#ffaa00"`, `"#9966ff"`, `"#888888"`, `"#7289DA"`, `"#aaaaaa"`, `"#ffcc00"`, `"#9966ff"`, `"#ffff66"`, `"#ff9966"`, `"#ffcc66"`, `"#ffcc00"`

The plan's Task 5, Step 6 only required changing the method signature default and the error-color guard — it did not require converting all call sites. Those colors are the per-message semantic palette for the console terminal (progress=blue, success=green, error=red, etc.) and are intentionally kept as distinct named literals to make log triage easier.

This is not a bug for the current scope, but as a forward note: if a formal console palette were added to `theme.py` (e.g., `CONSOLE_PROGRESS`, `CONSOLE_SUCCESS`, `CONSOLE_ERROR`, `CONSOLE_WARN`), these 69 call sites could be unified without breaking anything. This would be a separate task.

**Verdict:** Out of scope for Tasks 4 and 5. Log as a future suggestion (Task 7 candidate).

---

#### 4. `image_settings_toggle` and `ref_image_toggle` diverge from the plan's specified pattern

**Lines:** 882–893, 1092–1103

The plan (Step 7) specified a pattern with an explicit `QPushButton:checked` state showing `rgba(0, 212, 255, 0.15)` border and a border on both normal and hover states. The implementation uses `background: transparent` with no border:

```python
# Actual (lines 882-893)
QPushButton {
    text-align: left;
    padding: 5px;
    border: none;          # <-- plan had border: 1px solid BORDER_CYAN
    background: transparent;
    color: {TEXT_PRIMARY};
}
QPushButton:hover {
    background: {NAVY};
}
# <-- plan also added QPushButton:checked { ... }
```

The deviation — using `border: none; background: transparent` — is a defensible design choice. For a collapsible-section toggle button, a borderless transparent look is cleaner than a card-style bordered button. The global QSS would otherwise give these a solid cyan background, which is wrong for a toggle arrow.

However, the `QPushButton:checked` state is entirely absent. When the panel is expanded (checked=True), there is no visual feedback beyond the arrow character changing in the text. Consider whether this is intentional or an oversight.

**Verdict:** The deviation from the plan's specified style is justifiable, but the missing `:checked` state should be confirmed as intentional. If users need visual feedback when these sections are open, add the checked variant.

---

### Suggestions

#### 5. `help_browser.setStyleSheet("QTextBrowser { font-size: 13pt; }")` at line 2509 has no color properties

**Line:** 2509

This is a pre-existing one-liner on the fallback `QTextBrowser` path that sets only font-size. It does not override colors, so it will inherit the global QSS correctly. No action required, but if the Help tab's `QTextBrowser` needs explicit dark styling (it may not, given `setHtml` injects the full CSS template), keep this in mind.

---

#### 6. `splitter_style.py` import is relative (`from ..theme import`) while `main_window.py` uses absolute (`from gui.theme import`)

**Files:** `gui/common/splitter_style.py` line 9 vs `gui/main_window.py` line 87

Both are valid Python. The relative import in `splitter_style.py` is correct for a sub-package. The absolute import in `main_window.py` matches the project's established convention (all other `from gui.*` imports in `main_window.py` are absolute). This is consistent and not an issue, but worth noting for future contributors: files inside `gui/common/` should use relative imports; files directly in `gui/` should use absolute imports.

---

## Plan Compliance Summary

| Plan Step | Description | Status |
|-----------|-------------|--------|
| Task 4, Step 1 | Replace `splitter_style.py` content with Maestro colors | Complete |
| Task 5, Step 1 | Add `from gui.theme import (...)` to `main_window.py` | Complete |
| Task 5, Step 2 | `output_image_label` stylesheet | Complete |
| Task 5, Step 3 | `output_text` console stylesheet | Complete |
| Task 5, Step 4 | `quick_setup` label stylesheet | Complete |
| Task 5, Step 5 | Secondary hint/info labels (`#888`, `#666`, gray) | Complete |
| Task 5, Step 6 | `_append_to_console` default param + error guard | Complete |
| Task 5, Step 7 | Toggle button stylesheets (transparent, uses theme constants) | Partial — `:checked` state absent; deviation from plan is defensible |
| Task 5, Step 8 | `midjourney_command_display` stylesheet | Complete |
| Task 5, Step 9 | `ref_hint_label` color | Complete |
| Implicit scope | Status labels using bare `"color: green/red/blue"` | MISSED — Critical |

---

## Required Actions Before Merge

1. **Fix the 7 status-label `setStyleSheet` calls** that use bare CSS named colors (`green`, `blue`, `red`) and the one that uses `#cc6600`. Replace them with `GREEN`, `RED`, `AMBER`, and `CYAN` / `CYAN_DARK` from `gui.theme`. Add `CYAN_DARK` to the import if using it.

2. **Confirm the toggle `:checked` state** is intentionally absent or add it per the plan's Step 7 pattern.

Once item 1 is resolved, these files are ready for commit.
