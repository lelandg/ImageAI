# Repo Error Check — `feat/gpt-image-2`

**Repo:** `/mnt/d/Documents/Code/GitHub/ImageAI`
**Branch:** `feat/gpt-image-2` (clean working tree)
**Date:** 2026-04-26 20:31 (local) / 2026-04-27 01:31 UTC
**Reviewer:** Claude Code (Opus 4.7, automated scan)

---

## TL;DR

Branch is in good shape. **Two real bugs** in the most recent commit (`5953069 chore(models): refresh Claude model IDs to current aliases`) — both are sloppy regex-rename artefacts, both fixable in minutes. Everything else is hygiene noise (bare `except:` clauses, a few stray `print()`s) that pre-dates this branch.

| Severity | Count | Notes |
|----------|-------|-------|
| 🔴 Bug   | 2     | duplicate-key collisions from the model-rename commit |
| 🟡 Watch | 3     | display_name/release_date drift, 48 bare excepts, 5 stray prints in libs |
| 🟢 Clean | 6     | compile, imports, secrets, debugger, deprecated Gemini IDs, gpt-image-2 wiring |

---

## 🔴 Real Bugs

### 1. `core/llm_models.py:73,77` — `claude-sonnet-4-6` listed twice in the anthropic model list

```python
LLM_PROVIDERS = {
    ...
    'anthropic': LLMProvider(
        ...
        models=[
            'claude-opus-4-5-20251101',
            'claude-sonnet-4-5-20250514',
            'claude-opus-4-20250514',
            'claude-sonnet-4-6',        # line 73 — was claude-sonnet-4-20250514
            'claude-3-7-sonnet-20250219',
            'claude-sonnet-4-6',        # line 77 — was claude-3-5-sonnet-20241022   ← DUPLICATE
            'claude-haiku-4-5-20251001',
        ],
        ...
    )
```

**Impact:** Wherever this list feeds a UI dropdown, "Claude Sonnet 4.6" appears twice. If any consumer turns it into a dict/set, one entry is silently dropped.

**Fix:** delete the second `'claude-sonnet-4-6'` entry on line 77 (and probably also remove the now-meaningless `# Claude 3.5 Series` comment block that introduced it).

---

### 2. `scripts/fetch_model_capabilities.py:882,911` — duplicate dict key `'claude-sonnet-4-6'` silently overwrites Sonnet 4 metadata

```python
'claude-sonnet-4-6': {                              # line 882 — was claude-sonnet-4-20250514
    'display_name': 'Claude Sonnet 4',
    'description': 'Excellent coding performance, balanced speed and capability',
    'context': 200000, 'output': 64000,
    'extended_context': 1000000,
    'extended_thinking': True,
    ...
},
...
'claude-sonnet-4-6': {                              # line 911 — was claude-3-5-sonnet-20241022   ← OVERWRITES ABOVE
    'display_name': 'Claude 3.5 Sonnet',
    'description': 'Best combination of speed and intelligence for most tasks',
    'context': 200000, 'output': 8192,              # NB: smaller output, no extended thinking
    'release_date': '2024-10-22',
    ...
},
```

**Impact:** Python merges duplicate dict keys silently, keeping the **last** value. The Sonnet 4 capability row (1M extended context, 64k output, extended thinking) is lost; the registry now describes "Sonnet 4.6" with Sonnet 3.5's specs.

**Fix:** delete the second block (lines 911-924), or merge the two into a single accurate entry that reflects Sonnet 4.6's real specs.

---

## 🟡 Watch List

### 3. Body-of-renamed-entries metadata drift (`scripts/fetch_model_capabilities.py:911-924, 922-933`)

The rename touched only the **dict keys**, leaving stale bodies:

| New key                          | Stale `display_name` | Stale `release_date` |
|---------------------------------|----------------------|----------------------|
| `claude-sonnet-4-6` (2nd entry) | "Claude 3.5 Sonnet"  | `2024-10-22`         |
| `claude-haiku-4-5-20251001`     | "Claude 3.5 Haiku"   | `2024-10-22`         |

Any UI/registry that displays these will show wrong names and dates.

### 4. 48 bare `except:` clauses across `core/`, `gui/`, `providers/`, `cli/`

Examples:

```
core/image_utils.py:219
core/video/llm_sync_v2.py:848
core/video/thumbnail_manager.py:263, 295, 324, 360
core/video/veo_client.py:277
providers/midjourney_provider.py:157
providers/__init__.py:21, 31
providers/stability.py:151, 218
cli/runner.py:114
gui/main_window.py:2234, 4928, 6261, 6278, 6291, 6660, 6731, 7041, 7875, 8654, 8667
... (35 more)
```

Pre-existing — not introduced on this branch — but PEP 8 and CLAUDE.md "all errors must be logged" both want these tightened to `except Exception as e:` with at least a `logger.exception(...)` call.

### 5. Stray `print()` in library modules (5 total worth checking)

```
core/project_tracker.py:36         print(f"Project copied to: {current_project.absolute()}")
providers/__init__.py:190           print(f"Loading provider: {name}...")
providers/openai.py:186             print("Loading OpenAI provider...")
providers/google.py:309             print("Loading Google AI provider...")
providers/google.py:341             print("Loading Google Cloud AI provider...")
```

Per CLAUDE.md ("All errors must be logged" / "use dual logging"), provider-load notices should go through the logger, not bare `print()`.

The other ~46 `print()` hits are in diagnostic/setup scripts (`diagnose_*`, `check_*`, `download_*`, `discord_rpc.py`'s diagnostics block, `logging_config.py`'s on-exit notice) — those are fine.

---

## 🟢 Clean Checks

| Check | Result |
|-------|--------|
| `python3 -m py_compile` on all 241 `.py` files (excluding venvs) | ✅ 0 SyntaxErrors |
| Import sanity for `main`, `core.*`, `providers.*`, `cli.*`, `gui` | ✅ All OK; `gui.main_window` skipped (PySide6 not in `.venv_linux`, expected) |
| `grep -E 'pdb\.set_trace\|breakpoint\(\)'` | ✅ None |
| Hardcoded API keys / secrets | ✅ None |
| Deprecated `gemini-2.5-flash-image-preview` (CLAUDE.md flagged) | ✅ None |
| gpt-image-2 wiring (`providers/openai.py`, `core/{constants,utils,image_size}.py`, `gui/main_window.py`) | ✅ Consistent — `MODEL_CAPS`, snapshot, sync support, custom-size pre-flight, edit/streaming/batch paths all present |
| Recent `_on_model_changed` `setVisible(str)` crash fix | ✅ Verified — `bool(...)` coercion in place at `gui/main_window.py:3973-3979` |

---

## TODOs found (4 — not blockers)

```
core/prompt_enhancer.py:244          # TODO: Integrate with actual LLM client
providers/google.py:2085             # TODO: Real implementation would look like this:
gui/main_window.py:6393              # TODO: Re-enable auto-crop after fixing the algorithm
gui/video/video_project_tab.py:523   # TODO: Calculate cost
```

---

## Branch Posture

* Only **1 commit ahead of main** (`5953069`, the model-ID refresh).
* The gpt-image-2 work is already merged on `main`; this branch sits on top with the model rename.
* Recommended next action: fix bugs #1 and #2 in a small follow-up commit on `feat/gpt-image-2` before opening a PR (or amend `5953069` if not yet pushed — it isn't on a public PR per `git log main..HEAD`).

---

## Tools used

```bash
git status --short && git log --oneline -10
git log main..HEAD --oneline
git diff --stat main...HEAD
git show 5953069
python3 -m compileall -q -x '...' .
python3 -c "import main / core.* / providers.* / cli.* / gui"   # in .venv_linux
grep -rn -E '^\s*except\s*:' core/ providers/ cli/ gui/
grep -rn -E 'TODO|FIXME|XXX|HACK' core/ providers/ cli/ gui/
grep -rn -E 'pdb\.set_trace|breakpoint\(\)' .
grep -rn -E '(api_key|API_KEY|secret|password)\s*=\s*["\x27][A-Za-z0-9_\-]{20,}' .
grep -rn 'gemini-2\.5-flash-image-preview' .
grep -rn 'gpt-image-2' .
grep -rn 'claude-sonnet-4-6\|claude-haiku-4-5-20251001\|claude-3-5-sonnet\|claude-3-5-haiku\|claude-sonnet-4-20250514' .
```
