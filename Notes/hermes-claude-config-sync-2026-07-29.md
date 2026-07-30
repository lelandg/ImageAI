# Hermes Claude-config sync — 2026-07-29 11:30

`/sync-claude-config hermes` run from the WSL dev machine. Remote: `agent@ip-172-31-79-234`
(Hermes, Ubuntu EC2 ops worker). End-to-end verify returned `CONFIG OK`.

## Backup

`~/.claude/backups/sync-20260729/` on hermes — CLAUDE.md, settings.json,
statusline-command.sh, full `agents/` copy. Plus `~/.config/agents/AGENTS.md` had no
prior copy (dir didn't exist).

## What synced

| Item | Result |
|------|--------|
| `~/.config/agents/AGENTS.md` | **Created** (didn't exist). Merged from local house rules with Hermes adaptations: `~/code/` root, `agent` user / no sudo, `~/downloads`, headless-GUI note, aws-admin-absent rule, Hermes-pipeline-runs-here note, Sol-review-only kept (with note that hermes' `~/.codex/config.toml` pins no default model). |
| `~/.claude/CLAUDE.md` | **Rewritten** from old monolith → `@/home/agent/.config/agents/AGENTS.md` line 1 + Claude-specific extras (skill/agent triggers incl. `/version-manager`, `/update-hermes`; codex plugin mechanics). All old content preserved via AGENTS.md or `instructions/`. |
| `instructions/` | Full overwrite — now has the complete post-2026-07-28-split set (10 files; hermes had 4). |
| `tools/` | Synced `config-secrets-guard.py` + `safe-config-reader.py`, chmod +x. |
| `agents/` | `rsync -aL --delete` — cl-* symlinked agents materialized; sets were identical otherwise. |
| `skills/` | Additive sync. New on hermes: disk-doctor, html-doc, publish-claude-config, unify-agents-md, version-manager. Fixed **dangling `cl-concierge` symlink** (now materialized dir). `imageai-cli` symlinked to `~/code/ImageAI/.claude/skills/imageai-cli`. Remote-only skills preserved: claude-config-review, product-manager, time.md. |
| `commands/` | Pushed portable: unify-agents-md, feature-team, rename-code, sync-claude-config, update-hermes, yt-transcript. **Skipped** all `aws-db-*`/`aws-env-*` (need local aws-admin venv). Remote-only `marketing/` preserved. |
| `settings.json` | Merged: model → `claude-fable-5[1m]`, effort high, thinking on, teammate in-process; plugin `claude-security` enabled + installed; guard PreToolUse hook added (`~`-relative); remote OTEL/telemetry env + all remote plugins/marketplaces preserved. |
| `statusline-command.sh` | Old grep/sed version replaced with the jq two-line script; path-shortening adapted to `$HOME/` → `~/`. Smoke-tested on hermes (renders model/ctx/branch). `jq` present. Old copy in backup. |
| Claude Code | Updated 2.1.216 → 2.1.220 (matches local). |

## Cross-CLI wiring (CLIs detected: codex, agy, pi — no copilot, no gemini)

- **Codex:** `~/.codex/AGENTS.md` → symlink to shared AGENTS.md (new). `~/.codex/hooks.json` created with the config-secrets-guard PreToolUse entry.
- **agy:** `~/.gemini/AGENTS.md` → symlink (new). `~/.gemini/config/hooks.json` created with the named guard hook (`--agy` protocol).
- **Pi:** `config-secrets-guard.ts` copied to `~/.pi/agent/extensions/`.
- **GEMINI.md:** not created — no gemini CLI on hermes and no Gemini memories to preserve; agy reads the AGENTS.md symlink.
- **Guard fixture tests on hermes:** Claude protocol → `permissionDecision: deny` ✓; agy protocol → `{"decision": "deny"}` ✓.

## Dropped permission rules (machine-bound / write-capable — not copied)

`Read(//home/leland/.claude/**)`, `Read(//mnt/e/Pictures/Screenshots/2025/**)`,
`Read(//mnt/d/Documents/Code/GitHub/ImageAI/**)`, `Bash(clip.exe:*)`,
`Bash(aws iam create-access-key:*)`, `Bash(aws iam delete-access-key:*)`,
`Bash(aws amplify update-app:*)`. (Remote already had every portable local rule.)

## Plugins & MCP

- `claude-security@claude-plugins-official` installed (scope: user). All other local-enabled plugins were already enabled on hermes; remote extras (pm-skills etc.) untouched.
- `obsidian-cli-skill` marketplace skipped (machine-bound vault); `~/code/plugins` marketplace clone already up to date (its dirty marketplace.json/.gitignore are the expected hermes-local wiring, left alone).
- **MCP: nothing to re-create.** Local servers are all account-bound (Adobe, PubMed, Gmail, Calendar, Drive — auto-connect on login), plugin-provided (context7, playwright, discord — ride with plugins), or machine-bound (ACE-Studio at localhost:21572 on the dev machine — skipped).

## ACTION REQUIRED

- **Codex hook trust (per-host):** run `/hooks` in an interactive `codex` session **on hermes** and trust `config-secrets-guard`. Until then Codex silently skips the guard (headless timers included). Re-trust after any future change to the script.

## Repo housekeeping noticed (not fixed)

- `~/code/plugins` on hermes: untracked `README.md.hermes-local`, `index1.html`, `social-posts.md` + modified marketplace wiring — pre-existing, deliberate, left alone.
- Local ImageAI: `fix/custom-styles-followups` branch still exists locally though its content appears merged to main; `backup/pre-media-scrub` also present.
