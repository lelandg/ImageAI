# AI Layout Designer — Phase 2 (AI Designer + History) Completion Summary

**Last Updated:** 2026-06-24 12:15
**Branch:** `feat/layout-ai-designer-phase2` (based on merged `main` incl. Phase 1)
**Status:** ✅ Phase 2 complete — all 7 tasks implemented, reviewed, and green.
**Spec:** `Plans/2026-06-24-layout-ai-designer-design.md` (§5 AI designer, §6 history)
**Plan:** `Plans/2026-06-24-layout-ai-designer-phase2-designer.md`

---

## What shipped

The Layout tab can now **design itself with AI**: describe a page (or type a change), the
text LLM proposes a structured layout (and/or asks clarifying questions) rendered on the
canvas, and you iterate in a loop — with a browsable **history** of every iteration
(snapshot / restore / branch), persisted with the project.

| Area | Module(s) |
|---|---|
| Snapshot model + history persistence | `core/layout/models.py` (`Snapshot`, `DocumentSpec.history`), `core/layout/schema.py` |
| History manager (append/restore/branch) | `core/layout/history.py` |
| Designer prompt builder | `core/layout/designer.py` (`build_messages`) |
| Response parse + fallback + run_design + LLM call | `core/layout/designer.py` (`DesignerResult`, `parse_response`, `fallback_result`, `run_design`, `run_completion`) |
| Designer panel + QThread worker + status console | `gui/layout/designer_panel.py` |
| Browsable history window | `gui/layout/history_window.py` |
| Tab integration (design button, apply+snapshot, restore, History…) | `gui/layout/layout_tab.py` |

## Architecture

- **Network isolation:** the only LLM network call is `designer.run_completion`. Every other
  layer (`build_messages` / `parse_response` / `run_design` / worker / panel / tab) takes an
  injectable `completion_fn`, so all designer logic is unit-tested **headless without a
  network**. The production worker runs on a `QThread`; the injected/test path runs inline.
- **Robust + graceful:** markdown-fenced JSON parsed via the shared `LLMResponseParser`;
  non-list `questions` guarded; LLM geometry clamped into the page via `normalize_region`;
  empty/garbage responses degrade to a fallback layout (spec §5), never crash.
- **History hygiene:** snapshots never nest their own timeline (no unbounded growth); restore
  re-attaches the live timeline so branching works; persists in the project JSON and is
  backward-compatible with Phase-1 files.
- **§8 LLM logging:** the full request (provider/model/temperature/messages) and full response
  are logged to the file logger and surfaced in the designer status console.

## Tests

21 new tests (56 total under `tests/layout/`), headless offscreen Qt, **56 passed, 0
warnings**. Reuses the existing `LiteLLMHandler` / `LLMResponseParser` / `DialogStatusConsole`
and the model registry (`get_provider_models` / `get_provider_prefix`); no new runtime deps.

## Process

Subagent-driven TDD (implementer + reviewer per task, fix loops) + a final whole-branch review
(opus; verdict: *ready to merge with fixes* — applied). Review-loop catches included
non-list-`questions` parsing, parsed-dict mutation, the design-button wiring (caught in Task 5,
fixed in the Task-7 plan), and the §8 full-prompt/response logging gap.

## Deferred / carry-forward (documented decisions)

- **Provider display-name→id threading** (`designer_panel` + `run_completion`): correct for all
  five registered providers and mirrors the proven `text_gen_dialog` two-map pattern. NOT
  refactored here because the naive "pass the registry id" fix would **break Google gcloud/key
  auth** (the app stores Google's key under `"google"` while the registry id is `"gemini"`). A
  proper fix is a **repo-wide** provider-id refactor (touching `text_gen_dialog` too) and is out
  of Phase-2 scope.
- Minor polish logged in `.superpowers/sdd/progress.md` (e.g. `snapshots()` defensive copy,
  `json.dumps(indent=0)`→`None` token trim) — non-blocking.

## Next

Phase 3 — project style system (fonts/colors/roles by content kind) + template export/import —
gets its own spec→plan→PR cycle. Then Phase 4 (content MVP: import images + edit text) and
Phase 5 (AI content + bundles).
