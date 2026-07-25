# Version Manager — Design

**Last Updated:** 2026-07-25 09:09
**Status:** Approved design, not yet implemented
**Deliverable:** a global skill at `~/.claude/skills/version-manager/`, plus one rule added to `~/.config/agents/AGENTS.md`

---

## 1. Problem

Version numbers and changelogs drift across every project because the two records
that describe a release — the version-defining file and `CHANGELOG.md` — are
maintained by hand, independently, with nothing reconciling them.

A survey of the eight projects in `~/.claude/my-projects.yaml` on 2026-07-25:

| Project | Version lives in | Value | Changelog | Tags |
|---|---|---|---|---|
| ImageAI | `core/constants.py` | 0.40.0 | Keep a Changelog, current to 0.40.0 | 0 |
| ChatMaster | `VERSION` file (+ empty `package.json`) | 0.2.0 | none | 0 |
| Heimdallr | `app/__init__.py` | 0.1.0 | last entry 0.2.0 | 0 |
| ChameleonLabs | `package.json` | 0.1.0 | none | 0 |
| HealthCheck | `package.json` | 0.1.0 | none | 0 |
| LelandGreenProductions | `package.json` | 0.0.0 | none | 0 |
| QuickStock | `package.json` | 1.1.0 | none | 0 |
| RealtyShield | `src/version.py` **0.9.0**; `VERSION` **0.2.0**; `pyproject.toml` **0.2.0**; `setup.py` (imports) | **disagree** | last entry 0.2.0 | 0 |

Four concrete failures this produces:

1. **No git tags in any of the eight repositories.** Nothing machine-readable
   records which commit was which release, so "what changed since the last
   version" cannot be answered by any tool.
2. **Live disagreement between version locations.** RealtyShield's
   `src/version.py` says `0.9.0` while `VERSION` and `pyproject.toml` say
   `0.2.0` — even though both of those files carry comments declaring
   `src/version.py` to be the canonical source.
3. **Version behind changelog.** Heimdallr's `app/__init__.py` is `0.1.0`, but
   its changelog shipped `0.2.0` on 2025-12-07.
4. **Incomplete and incorrect changelog history.** In ImageAI, git and the
   changelog are each a *partial* record — 46 versions appear in git history,
   54 in the changelog, and neither is a superset of the other:
   - Missing from the changelog but present in git: `0.29.0` (2025-12-02),
     `0.30.0` (2025-12-05).
   - Present in the changelog but never in `core/constants.py`: `0.3.0`,
     `0.4.0`, `0.6.0` (the version lived in `main.py` as `__version__` before
     2025-09-07), plus `0.10.2`, `0.13.1`, `0.15.0`, `0.15.1`, `0.16.1`,
     `0.18.1`, `0.23.1` (shipped without any version-file bump).
   - Wrong dates: `0.19.1` (changelog 2025-09-22, git 2025-09-26), `0.20.1`
     (2025-11-06 vs 2025-10-06), `0.22.0` (2025-11-07 vs 2025-10-15), `0.23.0`
     (2025-11-08 vs 2025-10-16). The last three are month-number slips.

A fifth failure is structural: ImageAI's `.claude/VERSION_LOCATIONS.md` is a
hand-maintained list of places to edit, and it has rotted exactly as duplicated
data does. It states the current version is `0.9.0` (actually `0.40.0`), points
at `core/constants.py` line 7 (actually line 9), and at `README.md` line 3
(actually line 5). **A hand-maintained index of version locations is itself a
source of drift and must not be part of the solution.**

## 2. Goals and non-goals

**Goals**

- One command performs a release correctly in any project, whatever its stack.
- Every version location in a repository ends a release holding the same value.
- The changelog is never silently behind the code.
- Existing hand-written changelog prose is preserved, never regenerated.
- The standard binds every CLI (Claude Code, Codex, Copilot, Gemini, Pi), not
  just Claude Code.

**Non-goals**

- No git hooks, no CI checks, no GitHub Actions. Enforcement is a house rule in
  `~/.config/agents/AGENTS.md` under the pull-request section.
- **No cross-repo sweep.** There is no `--all` verb. The tool operates on one
  repository at a time, the one you are working in.
- No fully automated changelog prose. Entries are generated as a draft and
  curated by hand before a version is cut.
- No new binaries or package-manager dependencies. Python standard library only.

### Scope assumption to confirm on review

"We don't need the `--all`. I just want it going forward." is read as: drop the
cross-repo sweep verb; the tool applies per-repository from now on. **`backfill`
is retained**, per the earlier explicit decision to reconstruct tags and fill
changelog gaps — it is simply run once per repository when that repository
adopts the tool, rather than swept across all eight at once. If the intent was
instead to drop history repair entirely, say so on review and §6 comes out.

## 3. Surface

A global skill at `~/.claude/skills/version-manager/`:

```
~/.claude/skills/version-manager/
├── SKILL.md            # trigger + usage, in the house style
├── version_tool.py     # stdlib-only implementation
└── tests/              # pytest, synthetic git repos in tmp
```

It operates on repositories from the outside, so it adds no per-repository
files, nothing to vendor, and nothing to keep in sync. It rides the existing
`/sync-claude-config` skill to other machines and is mirrored by
`publish-config-repo`.

Three verbs, all operating on the current repository:

| Verb | Writes? | Purpose |
|---|---|---|
| `/version check` | no | Report drift: version-location disagreement, version-vs-changelog gap, commits since last tag, untagged versions |
| `/version backfill` | yes, on confirmation | One-time history repair: reconstruct tags, fill changelog gaps, correct dates |
| `/version release <major\|minor\|patch>` | yes | Bump every location, promote a curated `[Unreleased]`, tag, commit |

`check` is the default when no verb is given.

## 4. Detection

There is **no manifest**. Version locations are auto-detected on every run. The
first match becomes *canonical*; every other location found becomes a *mirror*
that is synced to the canonical value on release.

Ladder, in priority order:

1. **An explicit pointer comment** — a line matching
   `version is (managed|maintained) in <path>` in any candidate file.
   RealtyShield's `pyproject.toml` and `setup.py` both name `src/version.py`
   this way, so the ambiguity resolves itself from data already in the repo.
2. **Packaging manifest with a real version** — `pyproject.toml`
   `[project].version` or `[tool.poetry].version`; `package.json` `.version`.
3. **Module constant** — `**/version.py`, `*/constants.py` with `VERSION =`,
   or `<pkg>/__init__.py` with `__version__ =`.
4. **A bare `VERSION` file.**
5. **Nothing found → create one.** Seeded from the highest version in the
   changelog if one exists (Heimdallr → `0.2.0`), otherwise `0.1.0`. Placed
   per ecosystem: `pyproject.toml` if present, else `package.json` if present,
   else a new `VERSION` file.

Additional rules:

- **Empty stubs are skipped, not filled.** ChatMaster's `package.json` is `{}`;
  it is not a version location, so the `VERSION` file (`0.2.0`) is canonical and
  the stub is left alone.
- **Display strings are mirrors.** A `**Version X.Y.Z**` line in `README.md` is
  detected by pattern and updated on release. This replaces
  `.claude/VERSION_LOCATIONS.md` entirely; that file should be deleted once the
  tool is in use, since a detector that reads the repository cannot go stale
  against it the way a hand-written list does.
- Every run prints what it detected, which location is canonical, and what it
  would write, before writing anything.
- On genuine disagreement between locations (RealtyShield today) the tool stops
  and asks which value is correct. **No state is persisted**: once `release`
  writes one value to every location, the disagreement is gone permanently, so
  the ambiguity is self-healing and only arises once. This is why there is no
  separate `sync` verb — mirror syncing is a step of `release`, not a mode.

## 5. The version ledger

The ledger is the union of two partial records. Building it is what lets the
tool answer "are all versions in the changelog?"

**Git-derived.** Walk history for *every* version-location pattern across *all*
of history, not only the location in use today. For each commit that changed a
version value, record `(version, commit, committer-date)`. Walking historical
locations is what recovers ImageAI's `0.3.0`/`0.4.0`/`0.6.0` from `main.py`,
which held `__version__` before the value moved to `core/constants.py` on
2025-09-07.

**Changelog-declared.** Every `## [x.y.z] - YYYY-MM-DD` heading.

The ledger is the union, with each entry tagged by provenance: `git`,
`changelog`, or `both`. Reconciliation output is exactly the four categories
that make up `check`:

- in both, dates agree → nothing to do
- in both, dates disagree → report both values (§6)
- in git only → missing from the changelog, gap to fill (§6)
- in changelog only → no locatable bump commit, reported as untagged (§6)

## 6. Backfill

Run once per repository, on adoption. Order matters: tags are written before the
changelog, so a failure mid-run leaves a re-runnable state.

1. **Reconstruct tags.** Create an annotated tag at each ledger entry that has a
   locatable bump commit, message `Version <x.y.z>` and the original committer
   date. Existing tags are never overwritten.
2. **Fill changelog gaps.** For each version present in git but absent from the
   changelog, insert a dated section generated from the commits in that version's
   range, grouped by conventional-commit type. In ImageAI this is `0.29.0` and
   `0.30.0`.
3. **Report unlocatable versions.** Versions in the changelog with no bump
   commit anywhere in history are listed as untagged and left alone.
   **They are not tagged at a guessed commit** — a documented hole is better
   than invented history. In ImageAI this is `0.10.2`, `0.13.1`, `0.15.0`,
   `0.15.1`, `0.16.1`, `0.18.1`, `0.23.1`.
4. **Correct dates on confirmation.** Where a version exists in both records
   with different dates, the git bump-commit date is the fact and the changelog
   date is the typo — but the changelog entry is hand-written prose, so the tool
   shows the diff and applies corrections only when approved. Nothing already
   written changes silently.

Backfill never rewrites the body of an existing changelog entry. It only inserts
missing sections and, on confirmation, edits a date on a heading.

## 7. Release flow

`/version release <major|minor|patch>`:

1. **Preconditions.** Clean working tree; the computed tag does not already
   exist; all detected version locations agree (else stop and ask, per §4).
2. **Bump.** Compute the next version from the canonical value and the requested
   level. Write it to the canonical location and every mirror — including the
   `README.md` version display.
3. **Draft.** Derive entries from `git log <last-tag>..HEAD`, grouped by
   conventional-commit type (`feat` → Added, `fix` → Fixed, `docs`/`refactor`/
   `chore` → Changed), each with its short SHA.
4. **Curate.** Present the draft for rewriting into prose before it is written.
   This is the deliberate manual step: generated draft, curated release.
5. **Write.** Insert the curated section as `## [x.y.z] - YYYY-MM-DD` beneath
   `## [Unreleased]`, using the real current date.
6. **Tag and commit.** One commit containing the version-location changes and
   the changelog section, then an annotated tag `v<x.y.z>`.

The bump level is always explicit. The report *suggests* a level from the commit
types present (`feat` → minor, `fix` → patch, `!` or `BREAKING CHANGE` → major)
but never selects one silently.

`[Unreleased]` is derived on demand from `git log`, never materialised into the
file between releases. There is nothing to keep in sync, so it cannot drift.

## 8. Enforcement

A short rule added to `~/.config/agents/AGENTS.md` in the pull-request section.
That file is imported by `~/.claude/CLAUDE.md`, `GEMINI.md`, and the Codex,
Copilot and Pi wiring, so one edit binds every CLI:

> **Versioning.** Before opening a PR, run `/version release <level>`: bump every
> version location and add the changelog entry in the same commit. Small changes
> that go straight to `main` get a `patch` release. Never hand-edit a version
> number or a changelog heading — the tool owns both, and hand edits are how the
> two records drifted apart in the first place.

## 9. Error handling

- Every verb is read-only until it has printed its plan.
- `release` refuses on a dirty working tree, on an existing tag, and on
  unresolved disagreement between version locations.
- `backfill` writes tags before the changelog and is idempotent — existing tags
  and existing changelog sections are skipped, so a re-run after failure is safe.
- A repository with no `CHANGELOG.md` gets one created from the Keep a Changelog
  header used by ImageAI, Heimdallr and RealtyShield.
- Detecting zero version locations is not an error; it triggers creation (§4.5).
- All git invocations use explicit `-C <repo>` absolute paths, never `cd`.

## 10. Testing

pytest against synthetic git repositories built in tmp, one fixture per
real-world shape found in the survey:

| Fixture | Models | Asserts |
|---|---|---|
| `multi_location_disagree` | RealtyShield | Pointer comment wins; disagreement stops the run and asks |
| `version_behind_changelog` | Heimdallr | `check` reports code 0.1.0 vs changelog 0.2.0 |
| `relocated_version_home` | ImageAI | Ledger recovers versions from a prior file |
| `empty_package_json` | ChatMaster | Stub skipped, `VERSION` file canonical |
| `no_version_anywhere` | greenfield | Location created, seeded from changelog |
| `changelog_gaps` | ImageAI | `0.29.0`/`0.30.0` identified and filled |
| `date_mismatch` | ImageAI | Reported with both dates; unchanged without confirmation |
| `unlocatable_versions` | ImageAI | Reported untagged, never tagged at a guess |

Plus a release round-trip: bump → every location including the README holds the
new value → changelog section written with the real date → annotated tag exists
→ working tree clean.

## 11. Rollout

1. Build and test the skill.
2. Adopt in ImageAI first — `check`, then `backfill`, then delete
   `.claude/VERSION_LOCATIONS.md` and update `AGENTS.md` §10 to point at the tool.
3. Add the house rule to `~/.config/agents/AGENTS.md`.
4. Adopt in the remaining repositories individually as work touches them.
   RealtyShield needs its `0.9.0` / `0.2.0` split resolved by hand on first run;
   Heimdallr needs its version advanced to `0.2.0` to match its changelog.
