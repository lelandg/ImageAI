# Task 5 report: Sprite Pose Steps LLM contract

## What I implemented

Created `core/sprite/generation/pose_steps.py`, the LLM contract "Sprite Pose
Steps — Strict v1.0" used by the edit-chain image route to turn one
`ActionCard` into N per-frame pose sentences.

Public surface (matches the brief exactly):
- `CONTRACT_NAME`, `CONTRACT_VERSION`, `POSE_STEPS_SCHEMA`, `SYSTEM_PROMPT`
- `PoseStepsContractError(ValueError)`
- `build_pose_messages(action, frames, character_notes="") -> List[Dict[str, str]]`
  — system message names the contract and embeds the JSON Schema; user
  message states `frames=N` and reiterates the action/character notes.
- `parse_pose_steps(text, frames) -> List[str]` — validates version, step
  count, index order (1..N contiguous), and non-empty pose text; strips
  `FORBIDDEN_WORDS` (`transparent`, `checkerboard`, `alpha`) from the
  rendered sentence; raises `PoseStepsContractError` on any violation
  (including non-JSON input).
- `fallback_pose_steps(action, frames) -> List[str]` — generic evenly spaced
  poses, with a "returns toward the starting pose" hint on the last step
  when the action loops.
- `generate_pose_instructions(action, frames, *, provider="google",
  model=None, api_key=None, auth_mode=None, character_notes="",
  completion_fn=None, log=logger.info) -> List[str]` — resolves the model via
  `resolve_model()` when not given, builds kwargs via
  `build_completion_kwargs()`, logs the full request (redacted of
  `api_key`/`messages` in the summary line, but the full message bodies are
  logged too) and the full response to both the module logger and the `log`
  sink, wraps any `completion_fn` exception with `classify_provider_error`,
  and falls back to `fallback_pose_steps()` on any contract violation so the
  caller always gets exactly `frames` strings.

I transcribed the brief's verified prototype verbatim — no deviations were
needed; every consumed signature (`resolve_model`, `LLMParams`,
`build_completion_kwargs`, `LLMResponseParser.parse_json_response`,
`FORBIDDEN_WORDS`, `classify_provider_error`, `ActionCard`) was checked
against the real source first and matched the brief's description exactly.

## Tests

`tests/sprite/test_pose_steps.py`, transcribed verbatim from the brief — 10
tests covering message construction, parsing (valid, fenced, wrong
count/version/order/empty, forbidden-word stripping), the fallback
generator, and `generate_pose_instructions` (completion_fn usage + full
request/response logging with no leaked `api_key`, plain-string replies,
fallback on contract violation, provider-error wrapping, and model
resolution when `model` is omitted).

Command + result:
```
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pose_steps.py -v
```
```
10 passed in 24.15s
```
No warnings.

## Gate

```
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -q
```
```
3 passed in 2.85s
```

`pose_steps.py` touches `core/sprite/generation/`, which has other tests
under `tests/sprite/`, so per the gate I ran the full `tests/sprite` suite
once before committing (in the foreground, per the team lead's course
correction — a prior background-monitor wait for this same run was killed
and re-run in the foreground):
```
QT_QPA_PLATFORM=offscreen $PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite -q -p no:cacheprovider
```
```
737 passed, 34 warnings in 127.57s (0:02:07)
```
All 34 warnings are pre-existing and unrelated to this task (a
`google._upb` `DeprecationWarning` in `tests/sprite/gui/test_main_window_sprite_wiring.py`
and a Pillow `mode`-argument `DeprecationWarning` in
`tests/sprite/test_engine_presets.py`). None originate from
`pose_steps.py` or `test_pose_steps.py`.

`grep -n "Qt\|PySide" core/sprite/generation/pose_steps.py tests/sprite/test_pose_steps.py` — no matches.

## Files changed

- `core/sprite/generation/pose_steps.py` (new, 184 lines)
- `tests/sprite/test_pose_steps.py` (new, 121 lines)

Commit: `2892732` — `feat(sprite): Sprite Pose Steps strict v1.0 LLM contract with fallback`
(verified `git show --stat` touches only these two files).

## Self-review

- Names match the brief exactly (`CONTRACT_NAME`, `POSE_STEPS_SCHEMA`,
  `SYSTEM_PROMPT`, `PoseStepsContractError`, `build_pose_messages`,
  `parse_pose_steps`, `fallback_pose_steps`, `generate_pose_instructions`).
- No overbuilding: no dict-response support, no extra helper exports beyond
  what the brief lists — the sibling `action_cards.py` module has a richer
  `_response_text` and a private `emit()` logging helper, but the brief's
  interface for this task does not call for either, so I kept the simpler
  prototype implementation as given.
- Contract violations never raise to the caller — `generate_pose_instructions`
  catches `PoseStepsContractError` internally and returns
  `fallback_pose_steps()`, per `Docs/LLM-Contracts.md`.
- Full request (provider, model, params, prompts) and full response are
  logged to both the module logger and the injected `log` sink, per
  `Docs/LLM-Logging-Full-Content.md`.
- Model IDs are never hardcoded; `resolve_model(provider, "chat")` is used
  when `model` is not supplied.
- Test output is pristine (no warnings from this task's test file).

## Concerns

None as of the fix round below. (Original report noted the double-logging
issue this fix round resolves; see below.)

## Fix round 1: route logging through the shared emit helper

**Finding (plan-mandated Important, ruled FIX):** `pose_steps.py` was the
only module in `core/sprite/generation/` bypassing the shared
`_common.emit(logger, log, message)` helper — it called `logger.info(...)`
then `log(...)` directly at each request/response/error/fallback log site.
With the default `log=logger.info`, every full-content message (including
the embedded JSON Schema in the request and the full model response) was
written twice.

**What changed:**
- `core/sprite/generation/pose_steps.py`: imported `emit` from
  `core.sprite.generation._common` and replaced every `logger.info(...)` +
  `log(...)` / `logger.error(...)` + `log(...)` / `logger.warning(...)` +
  `log(...)` pair with a single `emit(logger, log, message)` call (default
  `level="info"`, `level="error"` for the completion-failure line,
  `level="warning"` for the contract-violation/fallback line) — mirroring
  `action_cards.py`'s usage exactly. Message content is byte-for-byte
  identical to before; only the duplication is gone (`emit` skips the `log`
  sink when it is a bound method of the module logger itself, and always
  calls the module logger once).
- The public default parameter stays `log: Callable[[str], None] =
  logger.info` — this matches `action_cards.generate_action_cards`'s own
  default exactly, so no signature change was needed.
- `tests/sprite/test_pose_steps.py`: added
  `test_generate_default_log_writes_each_full_content_message_once`, which
  uses `caplog` at INFO level with `log` left at its default and asserts the
  request-log and response-log messages each appear exactly once in the
  captured records.

**Covering tests + command + output:**
```
$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_pose_steps.py /mnt/d/Documents/Code/GitHub/ImageAI/tests/test_no_hardcoded_paths.py -q -p no:cacheprovider
```
```
14 passed in 25.73s
```
Pristine — no warnings. (11 tests in `test_pose_steps.py`, the original 10
plus the new dedup test, + 3 in `test_no_hardcoded_paths.py`.)

Commit: `66c7c88` — `fix(sprite): route pose-steps logging through the
shared emit helper` (`git show --stat` confirms only `pose_steps.py` and
`test_pose_steps.py` changed, +19/-8 lines).

**Concerns:** none.
