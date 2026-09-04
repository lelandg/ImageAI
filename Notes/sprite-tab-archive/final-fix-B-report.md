# Fix wave B report — pose-step model (Important 3)

**Implementer:** fix-ir-B
**Files owned:** `core/sprite/generation/pose_steps.py`, `tests/sprite/test_pose_steps.py`

## What changed

`core/sprite/generation/pose_steps.py`:
- Removed the `from core.llm_models import resolve_model` import.
- Added `from core.sprite.generation.action_cards import default_chat_model`.
- `generate_pose_instructions`: replaced `model = model or resolve_model(provider, "chat")`
  with `model = model or default_chat_model(provider)`.

This matches the review's prescribed fix exactly (Important 3, fix wave 1 item 2). The bug was
that `resolve_model(provider, "chat")` asked the registry for a family named `"chat"`, which
does not exist for gemini (`flash`, `flash-lite`, `pro`) or anthropic (`sonnet`, ...). The
registry client caught the resulting `LookupError`, logged a warning, and returned
`static_default or family` — with no static default, that's the literal string `"chat"`, which
then got sent to the provider as `model="gemini/chat"` and rejected.
`core.sprite.generation.action_cards.default_chat_model` already owns the correct
provider→family→static-default table (`_CHAT_FAMILY`) and normalizes the provider alias first,
so `pose_steps.py` now reuses it instead of duplicating or hardcoding a model literal.

## Import cycle check

Verified `action_cards.py`'s own imports (`core.llm_models`, `core.llm_params`,
`core.llm_parsing`, `core.sprite.generation._common`, `core.sprite.generation.errors`,
`core.sprite.generation.prompts`, `core.sprite.pipeline`, `core.sprite.project`) — none of
these is or imports `pose_steps`. Grepped the whole `core/sprite` tree for `pose_steps` inside
`action_cards.py`, `pipeline.py`, and `project.py`: no hits. No cycle. The import is a normal
top-of-module import (no local/function-scope import needed).

## Test added

`tests/sprite/test_pose_steps.py::test_generate_default_model_resolves_to_a_real_model_not_the_family_name`
— calls `generate_pose_instructions(..., provider="gemini", completion_fn=fake)` with **no**
`model=` kwarg and **no** monkeypatch of the resolver, so it exercises the real
`default_chat_model("gemini")` → real `resolve_model("gemini", "flash", static_default=...)`
path. Asserts the resolved model id is not the literal `"chat"`, and asserts it equals whatever
`default_chat_model("gemini")` independently returns (shape assertion, not a pinned model id, so
it won't rot when the registry's live gemini/flash id changes).

Also updated the pre-existing `test_generate_resolves_model_when_missing` test: it previously
monkeypatched `core.sprite.generation.pose_steps.resolve_model`, which no longer exists in this
module's namespace after the fix (the import was removed). Retargeted the monkeypatch to
`core.sprite.generation.pose_steps.default_chat_model` instead — same intent (verify the
"model omitted → resolver is consulted, and its result flows into the completion kwargs" wiring),
just patching the function this module now actually calls. Added the
`from core.sprite.generation.action_cards import default_chat_model` import to the test file for
the new test's assertion.

## Discriminating-test verification

1. Reverted the source fix (`model = model or resolve_model(provider, "chat")`, restored the
   `resolve_model` import) while keeping the new test.
2. Ran only the new test:
   ```
   QT_QPA_PLATFORM=offscreen .venv_linux/bin/python -m pytest tests/sprite/test_pose_steps.py::test_generate_default_model_resolves_to_a_real_model_not_the_family_name -q
   ```
   Result: **FAILED** —
   `AssertionError: assert 'chat' != 'chat'`, with the captured warning
   `registry resolve gemini/chat failed (no family gemini/chat in registry (known: ['flash', 'flash-lite', 'pro'])); using static default None`.
   Confirms the test is discriminating.
3. Restored the fix (`default_chat_model(provider)` + the correct import).
4. Re-ran the full file — all 12 tests pass (see Gate below).

## Gate (foreground, 600000 ms timeout)

```
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pose_steps.py -q -p no:cacheprovider
```
```
............                                                             [100%]
12 passed in 23.28s
```

```
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -q -p no:cacheprovider
```
```
...                                                                      [100%]
3 passed in 2.99s
```

Both runs are pristine — zero warnings.

Additionally ran the full `tests/sprite` directory once, per the implementer contract's rule to
run the sibling-test directory before reporting when a module with other sprite tests is touched:
```
QT_QPA_PLATFORM=offscreen /mnt/d/Documents/Code/GitHub/ImageAI/.venv_linux/bin/python -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite -q -p no:cacheprovider
```
```
812 passed, 2 warnings in 122.87s (0:02:02)
```
The 2 warnings are the pre-existing third-party `google._upb._message` `PyType_Spec` deprecation
warnings from `test_main_window_sprite_wiring.py`, unrelated to this change and already noted in
the final review's own baseline ("2 third-party warnings").

## Files changed

- `core/sprite/generation/pose_steps.py` — import + one-line fix, as prescribed.
- `tests/sprite/test_pose_steps.py` — import added, one existing monkeypatch target updated, one
  new discriminating test added.

## Self-review

- Completeness vs. brief: matches Important 3's prescribed fix exactly; `generate_pose_instructions`
  signature is unchanged, so the `image_route.py` re-export is unaffected (did not touch or open
  `image_route.py`).
- Names match the brief: `default_chat_model` imported and called exactly as specified.
- No overbuilding: one function call changed, one import swapped, one test added, one test's
  monkeypatch target updated (forced by the import removal, not scope creep).
- Test verifies real behavior: confirmed via the revert/restore discriminating check above.
- Output pristine: both gate commands show zero warnings.

## Concerns

None. No import cycle, no scope creep into `image_route.py` or other siblings' files, existing
test suite (sprite-wide, 812 tests) stays green.
