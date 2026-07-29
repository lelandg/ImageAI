# Issue #11 — UX Simplification: Research & Weighted Design Proposals

**Status:** ⏳ Awaiting weighted exports (decision phase — no code changes yet)
**Last Updated:** 2026-07-29 18:11
**Issue:** [#11 — "[Suggestion] UI display - replicate Dzine/Renderzero Studio UI design"](https://github.com/lelandg/ImageAI/issues/11)
**Research report:** `Notes/2026-07-29-issue11-ux-research-report.md`
**Interactive pages:** `Plans/issue-11-ux-proposals/` (see §3)

---

## 1. Context

Nick (magickbeans) reported via Discord that ImageAI is "extremely complex and
techy / non user friendly," pointing at Dzine and "Renderzero Studio" as
references. The CL Issue Investigator's code-level diagnosis on the issue
verified the structural causes; this session added a full GUI structure map and
web research on the referenced products and on UX patterns used by leading AI
image studios.

Per the investigator's caution (and standing repo policy), **no third-party UI
is replicated** — trade-dress risk, and Qt ≠ web canvas. Competitor products
were researched for *feature sets and transferable patterns only*. Every
proposal below is an original ImageAI design using the existing Maestro theme
(`gui/theme.py`, issue #10) — the visual skin is already done; the gap is
layout hierarchy, progressive disclosure, and onboarding.

Verified complexity anchors (2026-07-29 checkout):

- Four provider/model dropdowns render **above the prompt box** (`gui/main_window.py:763-826`); the prompt gets 80 px of an 880 px splitter (`:1484`).
- **Generate is 6th of 10** identically-styled buttons in one row (`:894-946`).
- 8 top-level tabs (`:601-625`); the Video workspace opens on an LLM provider row plus three expanded accordions beside a **13-column** storyboard table (`gui/video/workspace_widget.py:863, :1578`).
- Layout tab: **11-button** flat toolbar and six untitled stacked dock panels (`gui/layout/layout_tab.py:59-170`); its `TemplateSelector` gallery exists but is not mounted in the tab (`gui/layout/template_selector.py:151`).
- **No onboarding/first-run flow anywhere** (repo-wide grep: zero hits); Ctrl+S/File menu act on video projects only (`gui/main_window.py:685`).

## 2. Research summary

Full cited report: `Notes/2026-07-29-issue11-ux-research-report.md` (deep-research
workflow: 24 sources, 115 claims extracted, 25 adversarially verified with 3 votes
each, 19 confirmed / 6 refuted, 11 synthesized findings; 106 agents).

- **Dzine** (dzine.ai) = the former **Stylar AI** (rebranded 2024-07-10): hosted
  freemium all-in-one image+video *web* studio. Organizes its UI **task-first**
  (14-tool carousel) with models as a secondary menu — the inverse of ImageAI's
  provider-first Generate tab. Flagship simplification: the **Chat Editor**
  ("no layers or tools required… Just type what you want") — conversational
  editing as the novice tier. Its in-app workspace layout could **not** be
  verified (login-gated), so no panel-arrangement claims are made.
- **"Renderzero Studio" = RenderZero AI Studio** (renderzerostudio.com, by the
  PromptGeek YouTube creator): a **lifetime-license Mac/Windows desktop app on
  exactly ImageAI's BYO-API-key model** — the closest true comparator. Verified
  patterns: numbered **guided prompt builder** over curated preset libraries
  feeding a live "constructed prompt" box (named presets, hand-editable result,
  zero raw CFG/seed/sampler exposure); **non-blocking render queue**;
  **per-image cost estimate before generating** ($0.09 vs $0.12 verified against
  Kie.ai's published prices); capability-aware graying of unsupported options;
  key-gate onboarding whose panel **deep-links to each provider's key-creation
  and billing pages**. Pitfall to avoid: its "generous free tier" marketing is
  contradicted by its own tutorial (free-tier Google keys don't work for the
  demoed paid models).
- **Norms (Midjourney, Leonardo.ai):** prompt-first layout with Generate on the
  prompt bar itself; **all parameters demoted to persistent defaults behind a
  single settings control** (typed overrides as the expert escape hatch);
  history integrated into the creation surface *in addition to* a management
  view (this one 2–1, medium confidence).
- **Coverage gaps:** research angles on desktop novice/expert-mode precedents
  (Blender/Resolve/Fooocus) and published onboarding evidence (NN/g) produced
  **no surviving claims** — nothing here cites them. Playground, Ideogram,
  Firefly, Canva, Krea were not verified. Open question for GLB-02/GLB-09
  wording: whether any Gemini image model still works on a free-tier AI Studio
  key as of mid-2026.

## 3. The three interactive proposal pages

All pages are self-contained HTML (open in any browser), share one option-ID
catalog (§5), and export weighted selections in a common JSON schema.

| # | Page | Windows path |
|---|------|--------------|
| 1 | Dzine-informed workspace proposal | `D:\Documents\Code\GitHub\ImageAI\Plans\issue-11-ux-proposals\dzine-informed-workspace-2026-07-29.html` |
| 2 | RenderZero-informed workspace proposal | `D:\Documents\Code\GitHub\ImageAI\Plans\issue-11-ux-proposals\renderzero-informed-workspace-2026-07-29.html` |
| 3 | Tab-by-tab recommendations (Image / Video / Layout / app-wide) + aggregator | `D:\Documents\Code\GitHub\ImageAI\Plans\issue-11-ux-proposals\tab-recommendations-2026-07-29.html` |

WSL equivalents live under `/mnt/d/Documents/Code/GitHub/ImageAI/Plans/issue-11-ux-proposals/`.

How to use each page:

1. **Click option cards** to select them (selections persist per page in the browser).
2. In the bottom export bar, give the bundle a **label** and a **weight 1–10**
   (10 = top choice), then **Copy JSON** or **Download**.
3. Repeat with different selections/weights as many times as you like — from
   any of the three pages. Save the JSON files to
   `Plans\issue-11-ux-proposals\exports\`.

## 4. Decision protocol — how multiple weighted exports become a plan

Export schema (`imageai-ux11-export/v1`):

```json
{
  "schema": "imageai-ux11-export/v1",
  "issue": 11,
  "page": "tab-recommendations",
  "label": "my top picks",
  "weight": 10,
  "exportedAt": "2026-07-29T23:59:00.000Z",
  "selections": [ { "id": "IMG-01", "title": "Prompt-first layout", "section": "image" } ]
}
```

Aggregation rule (implemented twice — section 07 of the recommendations page,
and `Plans/issue-11-ux-proposals/aggregate_exports.py`):

- For every option ID across all exports: **best** = max weight of any export
  containing it; **total** = sum of those weights; **hits** = number of exports.
- Rank by **best desc → total desc → hits desc → ID**. A single weight-10
  export therefore beats any pile of low-weight mentions: *weight 10 = top
  choice*, exactly as requested on the issue.

Offline aggregation (run from the repo root):

```bash
python3 Plans/issue-11-ux-proposals/aggregate_exports.py Plans/issue-11-ux-proposals/exports/*.json
```

The ranked table becomes the priority order for implementation. Follow-up
procedure once exports exist:

1. Paste the ranked table into this document under a new "§8 Decision" heading
   (or ask the agent to run the aggregator and update this doc).
2. Top-ranked S/M-effort options are batched into a single feature branch +
   PR ("UX simplification wave 1") with a version bump per repo rules.
3. Any selected L-effort option (GLB-05 workspace regrouping, VID-05
   storyboard columns, LAY-05 selection-driven inspector) gets its own design
   doc + plan in `Plans/` before code, per AGENTS.md §5/§12.

## 5. Option catalog (canonical IDs)

Effort: S ≤ 1 day · M = days · L = week+ (needs own plan doc). Full
descriptions with code anchors are on the pages; IDs are stable.

| ID | Title | Effort | Impact |
|----|-------|--------|--------|
| GLB-01 | Simple / Advanced UI mode (persisted `ui_mode`) | M | high |
| GLB-02 | First-run setup wizard (provider → key → test) | M | high |
| GLB-03 | Primary-action button style (one per surface) | S | high |
| GLB-04 | Consolidate AI prompt tools into one menu | S | high |
| GLB-05 | Workspace regrouping: 8 tabs → 4 workspaces | L | high |
| GLB-06 | Friendly model names (raw IDs → tooltips) | S | med |
| GLB-07 | Unify project/file semantics (Ctrl+S per workspace) | M | med |
| GLB-08 | Empty-state guidance on blank canvases | S | high |
| GLB-09 | Provider key deep-links & honest free-tier guidance | S | high |
| GLB-10 | Non-blocking generation queue | L | med |
| IMG-01 | Prompt-first layout (providers into Image Settings) | M | high |
| IMG-02 | Hero Generate row (break the 10-button row) | S | high |
| IMG-03 | Save/Copy/Show-Original move to the output | S | med |
| IMG-04 | Give the prompt real estate (splitter defaults) | S | med |
| IMG-05 | Aspect-ratio chips in Simple mode | M | med |
| IMG-06 | Recent-results thumbnail strip | M | med |
| IMG-07 | Simple-mode parameter hiding (Advanced/MJ groups) | S | med |
| IMG-08 | Provider status chip near Generate | M | low |
| IMG-09 | Conversational edit box (novice edit tier) | M | high |
| IMG-10 | Guided prompt builder v2 (steps + live prompt) | M | high |
| IMG-11 | Pre-generation cost estimate near Generate | M | med |
| VID-01 | Make the Workflow Guide the spine | S | high |
| VID-02 | New-project quick start dialog | M | high |
| VID-03 | Demote the LLM provider panel into settings | S | med |
| VID-04 | One primary render action (+ disabled-state reason) | S | med |
| VID-05 | Storyboard progressive columns (13 → core + drawer) | L | high |
| VID-06 | Collapse secondary groups by default | S | med |
| LAY-01 | Template-first entry (mount TemplateSelector) | M | high |
| LAY-02 | Toolbar consolidation (11 buttons → 2 menus + primary) | S | high |
| LAY-03 | Titled, collapsible dock panels | M | med |
| LAY-04 | Design → Fill → Export stepper | M | med |
| LAY-05 | Selection-driven inspector | L | high |

## 6. Suggested phasing (subject to the weighted ranking)

- **Wave 1 — visible wins, low risk (all S):** GLB-03, GLB-04, GLB-08, GLB-09,
  IMG-02, IMG-03, IMG-04, IMG-07, VID-01, VID-03, VID-04, VID-06, LAY-02.
- **Wave 2 — the mode + onboarding core (M):** GLB-01, GLB-02, IMG-01, IMG-05,
  IMG-06, IMG-09, IMG-10, IMG-11, LAY-01, LAY-03, VID-02, GLB-06, GLB-07,
  LAY-04, IMG-08.
- **Wave 3 — structural (L, each with its own design doc):** GLB-05, GLB-10,
  VID-05, LAY-05.

## 7. Risks & constraints

- **Hide, never delete:** dozens of methods reference these widgets
  (session save/restore persists the Image Settings toggle at
  `gui/main_window.py:7476-7481`); mode toggles must round-trip through
  session state.
- **Shortcuts/mnemonics:** moving buttons into menus changes Alt-access;
  keep `QShortcut` equivalents and update the hint strip (`:952`).
- **Power users:** Simple mode defaults on for *fresh installs only*; never
  removes capability. Existing users see zero change until they opt in.
- **Tab-index assumptions:** conditional Batch Jobs tab (`:625`) already
  shifts indices — audit `setCurrentIndex`/index math before hiding tabs.
- **Video tab cold-load:** the Video tab is a placeholder swapped on first
  click (`:7893`) — wizard/quick-start work must not force eager loading.
- **CLI unaffected**; GUI smoke tests that construct dialogs must be kept
  green (see `tests/`, 615 passing as of v0.42.0).
- **IP:** pattern adoption only; no pixel replication, no third-party marks in
  the app; ImageAI builds its own preset libraries (from `data/` and the
  existing Prompt Builder catalog), not RenderZero's curated contents.
- **Honesty in onboarding (GLB-02/GLB-09):** verify current Gemini free-tier
  viability before promising a zero-cost path — RenderZero's contradicted
  free-tier marketing is the documented anti-pattern.
- **Capability handling:** gray out + explain unsupported options; never
  silently switch the user's aspect/model (RenderZero's demo showed the silent
  variant — avoid it).
- **Qt-native affordances:** hover-only web patterns (hover-reveal actions)
  become persistent buttons or context menus for accessibility.

## 8. Next steps

1. ✅ Research + proposals delivered (this doc, the report, three pages).
2. ⏳ **Leland:** open the pages, make selections, export weighted bundles to
   `Plans/issue-11-ux-proposals/exports/` (multiple exports encouraged).
3. ⏳ Run the aggregator (§4) → record the ranked decision here → cut Wave 1
   branch per the decision protocol.
