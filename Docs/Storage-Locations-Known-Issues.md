# Configurable Storage Locations — Known Issues

**Feature:** relocate the Images, Video, Models and Settings data groups from
the Settings tab (`core/paths.py`, `core/data_migration.py`,
`gui/storage_settings_widget.py`).
**Branch:** `feat/storage-locations`. **Status:** implemented, not pushed.
**Last updated:** 2026-08-11.

The implementation plan was executed in full, then reviewed in five adversarial
rounds. Each round ran isolated repro scripts against the real code, and each
one refuted the previous round's claims. This file records what those rounds
did **not** close, so the next person does not have to rediscover it.

Nothing in this list is a silent total loss of a whole group. Those paths —
`config.json` losing `data_roots` on an ordinary shutdown, abort cleanup
deleting unrelated user files, a partial rename stranding the only copy — were
found and closed in rounds 1 through 4, each with a regression test.

## How to read this list

- **LOST** — the bytes are gone.
- **STRANDED** — the bytes are on disk, but nothing points at them.
- Every item names the file and the writer, so it can be verified before it is
  worked on.

## Open — ranked

### 1. Recovery trusts the journal's source paths over the current config

**STRANDED, and reported as success.** `core/data_migration.py` recovery renames
entries back to the paths the journal recorded, without checking where
`config.json` now points. Sequence: a rename move is interrupted → a later
cross-volume move rewrites `data_roots` → the next start renames the stranded
folder back to the *old* root and reports "Your data is where it was."

### 2. An entry that moved but was not marked reads as "still home"

**STRANDED, with the evidence destroyed.** A crash in the gap between
`os.rename` and `_mark_moved` leaves the entry unmarked. If anything re-creates
that source non-empty before the next start, recovery classifies it as "source",
reports "interrupted before it moved anything. Your data is unchanged", and
deletes the journal. The tree stays at the destination, unreferenced.

The same misclassification follows any `_mark_moved` write failure (logged, move
continues) and any journal whose `moved` list is dropped as malformed.

### 3. Rollback overwrites a newer file at the source

**LOST.** Loose Settings files only — `details.jsonl`, `*_history.json`,
`*_session.json`. The half-done rollback does `os.rename(target, source)`, and
POSIX rename replaces the destination file. A file re-created with newer content
at the source after the move renamed the old one away is silently overwritten,
with no backup and no mention in the message.

### 4. The journal is a same-volume mechanism only

**STRANDED.** `_write_intent` is called only in the rename fast path. A
cross-volume move — the headline use case, "move Models off the system drive" —
takes neither journal nor lock, so it runs to completion over an unrepaired
journal and rewrites `data_roots`. Two concurrent cross-volume moves of one
group both complete; the last `_write_root` wins and the loser's destination is
a full unreferenced duplicate.

### 5. A damaged config.json plus one ordinary save erases `data_roots`

**STRANDED, reported.** `save()` quarantines the unreadable file and writes this
session's document, so every relocated group reverts to the platform default and
the moved data becomes unreferenced. The `.corrupt-*` sidecar keeps the record
and the GUI reports the read failure within 20 seconds, so it is recoverable.
A *valid* JSON object with a bad `data_roots` shape triggers the same
whole-document replacement, which is disproportionate — a bad value *inside*
`data_roots` costs only that one group.

### 6. A half-done rollback cannot put a folder back over a re-created source

**STRANDED, correctly reported.** `ENOTEMPTY`. The group is left split across two
roots, the journal is kept, and the user is told to move it back by hand.

### 7. A symlink whose `readlink` fails is dropped, then deleted at the source

**LOST — the link only.** `_copy_link` skips it and the source tree is then
deleted, with `stranded=[]` and `ok=True`. The bytes survive if the target lives
outside the tree; the mapping does not.

### 8. A journal written by another host is repaired even when its pid is alive

**STRANDED/LOST, low likelihood.** Only reachable with a shared or roaming
config directory, where it would rename a live move's folders out from under it.

### 9. Unclaimed `cache/<name>` subdirectories are left behind

Currently harmless: `CACHE_OWNERS` covers every name a caller uses, pinned by a
test. It becomes stranding the day a new cache name is added without updating
the list.

### 10. Verification cannot detect content corruption that preserves length

Every file the copy wrote is re-read and its length checked against what was
written, before any source is deleted. A storage layer that silently rewrites
bytes without changing a file's length still passes. Detecting that needs a hash
of every byte, and the Models group is tens of gigabytes. The confirmation
dialog wording was corrected to match what the check actually guarantees.

### 11. PID recycling defers a repair for up to seven days

If a reboot gives a live unrelated process the pid the journal records, recovery
defers until `INTENT_STALE_SECONDS` (7 days) passes. The journal stays on disk
and every start logs a warning naming the pid and host, so nothing is lost
silently — but the app runs on the wrong root and refuses new moves meanwhile.

### 12. `_is_reachable` requires write access

A deliberately read-only Models root — weights on a read-only share — reads as
unreachable: fallback to the empty default, a warning, the Move button disabled,
and local SD re-downloads. A read-only root is legitimate for Models.

On Windows, `os.access(path, os.W_OK)` is close to meaningless for directories,
so an unwritable configured root reads as reachable there and the group fails at
first write instead.

### 13. Group membership is by name under a user-chosen root

`GROUP_CONTENTS` claims names such as `huggingface`, `images` and `generated`
under whatever root the user picks, and the collision guard runs only at move
time. Point the Models root at a shared cache directory, let another tool create
`<root>/huggingface` weeks later, and the next move annexes it. The shared
machine-wide `~/.cache/huggingface` is out of the group **by location**, not by
identity.

### 14. Three journal tests assert the fix exists, not the failure it prevents

`tests/migration/test_data_migration.py` AST-parses `main.py` and asserts call
presence and ordering. They pass even if the calls sit under `if False:` —
`ast.walk` does not see reachability. The justification is real (main.py
installs an import hook and replaces `builtins.print`, so it cannot be
imported); the durable fix is to extract the recovery block into an importable
`core` function and test its behaviour.

## Closed, with regression tests

For context, so none of these is re-litigated:

- `ConfigManager.save()` erasing `data_roots` on an ordinary shutdown.
- Abort cleanup deleting pre-existing user files, symlinks and junctions at the
  destination.
- A partial rename stranding the only copy, unnamed and unlogged.
- `_write_root` rewriting `config.json` as `{data_roots: ...}` alone on a read
  error, destroying stored API keys.
- Lost updates between `ConfigManager.save()` and the migrator, now serialised
  by `core/config_io.py` (thread lock plus an OS lock on a sidecar).
- A corrupt `config.json` overwritten with `{}` at startup.
- A malformed `config.json` stopping the application from starting.
- The migrator annexing the machine-wide `~/.cache/huggingface`.
- A failed or cancelled move leaving the Midjourney watcher and the video event
  stores dead for the rest of the session.
- The test suite writing debug images into the developer's real user directory.

## Suggested order of work

1. Items 1, 2 and 3 together — they are one subject: recovery believes the
   journal more than it believes the disk and the config.
2. Item 4 — journal the copy path too, and take the config lock for it.
3. Item 5 — narrow the whole-document replacement to the entry that is wrong.
4. Item 14 — extract the recovery block so its tests can exercise behaviour.
5. The rest are contained and individually cheap.
