# Context Hog Analysis — OpenClaw & Claude Code

> **Purpose:** Help diagnose why a single command consumes most of your available token budget.
> Includes universal LLM-compatible analysis prompts, file inventories, and slim-down troubleshooting.
>
> Tested mentally against: Claude Code, OpenAI Codex/ChatGPT, Google Gemini, and any chat-based LLM.

---

## Table of Contents

1. [Quick Diagnostics](#1-quick-diagnostics)
2. [OpenClaw — File Inventory & Context Hogs](#2-openclaw--file-inventory--context-hogs)
3. [Claude Code — File Inventory & Context Hogs](#3-claude-code--file-inventory--context-hogs)
4. [Universal Analysis Prompts](#4-universal-analysis-prompts)
5. [Troubleshooting: Slim Down OpenClaw](#5-troubleshooting-slim-down-openclaw)
6. [Troubleshooting: Slim Down Claude Code](#6-troubleshooting-slim-down-claude-code)
7. [Quick Reference Table](#7-quick-reference-table)

---

## 1. Quick Diagnostics

### OpenClaw

```
/context list
```

Shows the biggest context contributors in the current session. Run this **first** — it may immediately reveal the culprit.

```
/compact
```

Summarizes older context and frees window space without starting a new session.

```
/new
```

Starts a completely fresh session (no previous context carried forward).

### Claude Code

```
/cost
```

Shows token cost and usage for the current session.

```
/clear
```

Wipes accumulated conversation history and file reads from context.

```
/compact
```

Claude Code also supports `/compact` to compress prior messages.

---

## 2. OpenClaw — File Inventory & Context Hogs

### Directory Map

```
~/.openclaw/
├── openclaw.json                   # Main config (JSON5)
├── credentials/                    # OAuth tokens, API keys (not loaded into context)
└── workspace/
    ├── AGENTS.md                   # ⚠️ LOADED AT BOOT — operating instructions
    ├── SOUL.md                     # ⚠️ LOADED AT BOOT — persona & boundaries
    ├── USER.md                     # ⚠️ LOADED AT BOOT — user preferences
    ├── IDENTITY.md                 # ⚠️ LOADED AT BOOT — agent name/theme
    ├── MEMORY.md                   # ⚠️ LOADED AT BOOT (private sessions) — curated memory
    ├── TOOLS.md                    # ⚠️ LOADED AT BOOT — tool notes
    ├── HEARTBEAT.md                # ⚠️ LOADED AT BOOT — heartbeat checklist
    ├── BOOT.md                     # ⚠️ LOADED AT BOOT — startup checklist
    └── memory/
        ├── YYYY-MM-DD.md           # ⚠️ Today's daily log — always loaded
        └── YYYY-MM-DD.md           # ⚠️ Yesterday's daily log — always loaded

~/.openclaw/agents/<agentId>/
├── sessions/                       # Session JSONL transcripts (background indexing)
├── qmd/                            # Vector index sidecar (SQLite)
└── ...
```

### Token Hog Rankings (OpenClaw)

| Rank | File/Feature | Why It Hogs Tokens |
|------|-------------|-------------------|
| 🔴 1 | `MEMORY.md` | Grows unbounded — every session appends. Always in context. |
| 🔴 2 | `AGENTS.md` | Operating instructions can be thousands of lines. |
| 🔴 3 | `memory/YYYY-MM-DD.md` (×2) | Today + yesterday always loaded together. |
| 🟠 4 | `SOUL.md` + `USER.md` | Persona files are often large and verbose. |
| 🟠 5 | `BOOT.md` + `HEARTBEAT.md` | Checklist files repeat the same structure every session. |
| 🟡 6 | Installed skills | Each enabled skill adds its definition to context. |
| 🟡 7 | Session transcripts | Background indexing across 100 KB / 50-message thresholds. |
| 🟢 8 | `openclaw.json` | Config not loaded as context (internal only). |

---

## 3. Claude Code — File Inventory & Context Hogs

### Files Loaded at Startup (in load order)

```
~/.claude/CLAUDE.md                 # ⚠️ Global user instructions — ALWAYS LOADED
<project>/CLAUDE.md                 # ⚠️ Project instructions — ALWAYS LOADED
<project>/.claude/CLAUDE.md         # ⚠️ Subdirectory instructions — if present
<project>/CLAUDE.local.md           # ⚠️ Local overrides — if present
~/.claude/agents/*.md               # ⚠️ ALL agent definitions loaded as subagents
<project>/.claude/agents/*.md       # ⚠️ Project agents — ALL loaded
~/.claude/settings.json             # Config (not context, but controls model/tools)
<project>/.claude/settings.json     # Project config
<project>/.claude/settings.local.json  # Local config overrides
~/.claude.json                      # Preferences, OAuth, MCP server list
```

### Token Hog Rankings (Claude Code)

| Rank | File/Feature | Why It Hogs Tokens |
|------|-------------|-------------------|
| 🔴 1 | `~/.claude/CLAUDE.md` | Global instructions — loaded in **every** project, every session. |
| 🔴 2 | Project `CLAUDE.md` | Project-specific rules. Can reference/import more files. |
| 🔴 3 | Agent files in `~/.claude/agents/` | Every `.md` file = agent definition loaded at startup. |
| 🟠 4 | Enabled MCP servers | Each server's tool list adds to context (capped at 25k tokens). |
| 🟠 5 | Extended thinking | Default 31,999 tokens consumed per thinking operation. |
| 🟡 6 | System reminder hooks | Auto-injected context from skills and session hooks. |
| 🟡 7 | Accumulated file reads | Large files read during session stay in context until `/clear`. |
| 🟢 8 | `settings.json` | Not injected into context (controls behavior only). |

---

## 4. Universal Analysis Prompts

These prompts work with **any LLM** — Claude, Codex, Gemini, Llama, Mistral, etc.
Copy the file contents into the prompt, or paste them as attachments.

---

### Prompt A — OpenClaw MEMORY.md Audit

```
You are a token efficiency expert. I am going to paste the contents of my OpenClaw
MEMORY.md file below. Please analyze it and identify:

1. **Duplicate entries** — facts or notes that say the same thing in different ways
2. **Stale entries** — information that is likely outdated or no longer relevant
3. **Verbose entries** — things that could be rewritten in fewer words without losing meaning
4. **Low-value entries** — facts so trivial they don't need to be in long-term memory
5. **Structural bloat** — sections that could be merged or eliminated entirely

For each problem you find, quote the relevant text, explain the issue, and suggest a
shorter replacement (or deletion). Also estimate the token savings.

At the end, provide a revised, trimmed MEMORY.md that I can use directly.

---MEMORY.md CONTENTS BELOW---

[PASTE YOUR ~/.openclaw/workspace/MEMORY.md HERE]
```

---

### Prompt B — OpenClaw Full Workspace Audit

```
You are a context window efficiency expert. I am going to paste the contents of my
OpenClaw workspace files. These files are all loaded into the context window at session
start, before I even type anything. My goal is to reduce token usage without losing
important functionality.

Files I am providing:
- AGENTS.md
- SOUL.md
- USER.md
- MEMORY.md
- BOOT.md / HEARTBEAT.md (if applicable)
- Recent memory/YYYY-MM-DD.md (today and/or yesterday)

For each file, analyze:
1. **Estimated token count** (rough character count ÷ 4)
2. **Duplicate or contradictory instructions** across files
3. **Verbose or overly elaborate sections** that could be condensed
4. **Information that could be moved to on-demand context** instead of always-loaded
5. **Sections that are effectively no-ops** (checklists never actually referenced)

Provide a prioritized list of changes, from highest token savings to lowest.
Then provide rewritten, trimmed versions of whichever files I ask you to fix.

---FILES BELOW---

### AGENTS.md
[PASTE CONTENTS]

### SOUL.md
[PASTE CONTENTS]

### USER.md
[PASTE CONTENTS]

### MEMORY.md
[PASTE CONTENTS]

### BOOT.md
[PASTE CONTENTS]

### memory/YYYY-MM-DD.md (today)
[PASTE CONTENTS]

### memory/YYYY-MM-DD.md (yesterday)
[PASTE CONTENTS]
```

---

### Prompt C — Claude Code CLAUDE.md Audit

```
You are a Claude Code configuration expert specializing in context window efficiency.
I will paste the contents of my CLAUDE.md files below. These are automatically loaded
into every Claude Code session before any work begins.

Please analyze each file and identify:

1. **Token cost estimate** — approximate tokens per file (characters ÷ 4)
2. **Redundant instructions** — rules that duplicate each other or are already implied
3. **Excessive examples** — code samples or tables that could be shortened
4. **Never-triggered rules** — instructions for edge cases that rarely apply
5. **Cross-file duplication** — the same instruction appearing in both global and project files
6. **Import opportunities** — sections that could be moved to separate files and lazy-loaded
   using the `# import path/to/file.md` syntax (Claude Code supports this)

For each file, give a rewrite score (1–10, where 10 = extremely bloated).
Then provide a trimmed rewrite of whichever files I request.

Note: Claude Code supports `# import path/to/file.md` in CLAUDE.md to lazy-load
sections only when relevant — this is the primary tool for reducing always-loaded context.

---FILES BELOW---

### ~/.claude/CLAUDE.md (Global)
[PASTE CONTENTS]

### <project>/CLAUDE.md (Project)
[PASTE CONTENTS]

### <project>/CLAUDE.local.md (Local overrides, if any)
[PASTE CONTENTS]
```

---

### Prompt D — Claude Code Agent File Audit

```
You are a Claude Code subagent efficiency expert. I will paste a list of agent
definition files from my ~/.claude/agents/ and .claude/agents/ directories.
ALL of these are loaded into the context window at startup.

For each agent file:
1. **Estimate the token cost** (characters ÷ 4 for a rough estimate)
2. **Identify overlap** with other agents (same tools, same purpose)
3. **Flag rarely-used agents** that I might not need active by default
4. **Suggest consolidations** — agents that could be merged

Then recommend which agents to keep, which to archive (move out of the agents folder),
and which to merge.

---AGENT FILES BELOW---

### agents/agent-name-1.md
[PASTE CONTENTS]

### agents/agent-name-2.md
[PASTE CONTENTS]

[Continue for each agent file...]
```

---

### Prompt E — Combined OC + CC Context Hog Report

```
You are a context window optimization expert for AI coding assistants. The user runs
both OpenClaw (OC) and Claude Code (CC) and wants to reduce token consumption.

I will provide:
- OpenClaw workspace files (loaded at OC session start)
- Claude Code CLAUDE.md files (loaded at CC session start)
- Claude Code agent files from ~/.claude/agents/

Your job:
1. Calculate estimated token usage for EACH file (characters ÷ 4 ≈ tokens)
2. Rank all files from most to least token-intensive
3. Identify the top 5 "context hogs" — files contributing the most unnecessary tokens
4. Flag cross-tool duplication (same instruction in both OC and CC configs)
5. Provide a prioritized action plan with expected token savings per action

Output format:
## Token Usage Summary
| Tool | File | Est. Tokens | Bloat Score (1-10) |
|------|------|------------|-------------------|
...

## Top 5 Context Hogs
...

## Action Plan (highest savings first)
...

---FILES BELOW---
[Paste all relevant files with clear section headers]
```

---

## 5. Troubleshooting: Slim Down OpenClaw

### Step 1 — Check what's actually being loaded

```bash
/context list
```

### Step 2 — Measure each workspace file

```bash
wc -c ~/.openclaw/workspace/MEMORY.md
wc -c ~/.openclaw/workspace/AGENTS.md
wc -c ~/.openclaw/workspace/SOUL.md
wc -c ~/.openclaw/workspace/USER.md
wc -c ~/.openclaw/workspace/BOOT.md
wc -c ~/.openclaw/workspace/memory/*.md | tail -5
```

Divide bytes by 4 for a rough token estimate.

### Step 3 — Trim MEMORY.md

MEMORY.md is the most common runaway hog. Strategies:

- **Delete outdated facts** — Anything more than 90 days old that's no longer actionable
- **Deduplicate** — Run Prompt A above and apply the rewrites
- **Impose a size limit** — Keep MEMORY.md under 2,000 tokens (~8 KB)
- **Move project notes to project-specific files** — Don't store project details in global memory

### Step 4 — Shorten daily notes

Daily notes (`memory/YYYY-MM-DD.md`) accumulate. OpenClaw loads today + yesterday at start.
If yesterday's note is long, that's a hidden cost.

- Configure shorter compaction summaries in `openclaw.json`:
  ```json5
  agents: {
    defaults: {
      compaction: {
        softThresholdTokens: 40000,   // lower to compact earlier
        memoryFlush: true             // write memory before compaction
      },
      memorySearch: {
        query: {
          hybrid: {
            mmr: true,                // avoid duplicate memory snippets
            temporalDecay: {
              enabled: true,
              halfLifeDays: 30        // old memories fade naturally
            }
          }
        }
      }
    }
  }
  ```

### Step 5 — Archive or remove unused skills

Skills in `~/.openclaw/workspace/skills/` are loaded on demand, but poorly configured
installs may pre-load them all. List and audit:

```bash
ls -lh ~/.openclaw/workspace/skills/
```

Remove skills you don't use.

### Step 6 — Audit AGENTS.md, SOUL.md, USER.md

These files are rarely updated once written, but often grow over time.
Apply **Prompt B** above, then:

- Merge SOUL.md personality traits into AGENTS.md if they're short
- Keep USER.md under 50 lines
- Remove redundant or contradictory instructions

### Step 7 — Use cheaper models for routine turns

In `openclaw.json`, set cheaper models as default and reserve expensive models for
specific tasks:

```json5
models: {
  default: "claude-haiku-4-5",        // cheap for routine turns
  reasoning: "claude-sonnet-4-6",     // use for complex reasoning only
  // expensive flagship stays in fallback, not default
}
```

### Step 8 — Fresh session for new tasks

Always use `/new` when switching to a completely different task. Never carry over a
long history session into unrelated work.

---

## 6. Troubleshooting: Slim Down Claude Code

### Step 1 — Measure your CLAUDE.md files

```bash
wc -c ~/.claude/CLAUDE.md
wc -c ./CLAUDE.md
wc -c ./.claude/CLAUDE.md 2>/dev/null
ls -lh ~/.claude/agents/
ls -lh .claude/agents/ 2>/dev/null
```

Divide bytes by 4 for token estimates.

### Step 2 — Split CLAUDE.md with lazy imports

Claude Code supports `# import path/to/file.md` to load sub-files only when referenced.
Move rarely-needed sections out of the main CLAUDE.md:

```markdown
<!-- In CLAUDE.md — instead of embedding everything: -->

# AWS Infrastructure
# import ./docs/aws-infrastructure.md

# Debug Procedures
# import ./docs/debugging.md
```

This keeps the main CLAUDE.md small; sections load only if the agent references them.

### Step 3 — Audit agent files

Every `.md` file in `~/.claude/agents/` is loaded at startup.

```bash
ls -lh ~/.claude/agents/
# Count and size them all
wc -c ~/.claude/agents/*.md
```

- Archive agents you rarely invoke (move them out of the agents folder)
- Merge agents with overlapping capabilities (apply **Prompt D** above)
- Keep agent definitions concise — one clear paragraph per agent is usually enough

### Step 4 — Disable unused MCP servers

Each enabled MCP server adds its full tool list to context (up to 25,000 tokens each).

In `~/.claude/settings.json`:
```json
{
  "enabledPlugins": [
    "only-the-plugins-you-actually-use"
  ]
}
```

Or use `~/.claude.json` to remove MCP servers you've added but don't need.

### Step 5 — Reduce global CLAUDE.md

The global `~/.claude/CLAUDE.md` is loaded in **every project**. It should contain only
truly universal instructions. Move project-specific rules to the project `CLAUDE.md`.

Target: global CLAUDE.md under 200 lines / ~5,000 tokens.

### Step 6 — Tune environment variables

Set these in your shell profile (`.bashrc`, `.zshrc`) to control token budgets:

```bash
# Compact earlier (before hitting context limit)
export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80

# Cap per-file reads
export CLAUDE_CODE_FILE_READ_MAX_OUTPUT_TOKENS=5000

# Cap MCP tool output
# (MAX_MCP_OUTPUT_TOKENS defaults to 25000 — can be set lower in settings)

# Reduce thinking budget if not using extended thinking
export MAX_THINKING_TOKENS=8000
```

### Step 7 — Use /clear aggressively

Every time you start a new subtask, run `/clear` first. File reads and conversation
history accumulate silently.

### Step 8 — Choose the right model

Some models have smaller default context windows. If you're on Sonnet 4.6 but only need
simple edits, use Haiku 4.5 (faster, cheaper, smaller default window footprint):

```bash
claude --model claude-haiku-4-5
```

---

## 7. Quick Reference Table

| Tool | Most Common Hog | Quick Fix |
|------|----------------|-----------|
| OpenClaw | `MEMORY.md` growing unbounded | Run `/context list`, trim with Prompt A |
| OpenClaw | Two daily notes loaded at boot | Shorten compaction summaries |
| OpenClaw | Long AGENTS.md / SOUL.md | Merge and trim with Prompt B |
| OpenClaw | Premium model as default | Set Haiku/cheap model as default in config |
| Claude Code | Huge global `CLAUDE.md` | Split with `# import` lazy loading |
| Claude Code | Too many agent files | Archive unused ones, merge overlaps |
| Claude Code | Too many MCP servers enabled | Disable servers not in active use |
| Claude Code | Long conversation history | Use `/clear` at start of each new task |
| Claude Code | Extended thinking on every turn | Reduce `MAX_THINKING_TOKENS` |

---

## Sources & Further Reading

- [OpenClaw Memory Concepts](https://docs.openclaw.ai/concepts/memory)
- [OpenClaw Mega Cheatsheet 2026](https://moltfounders.com/openclaw-mega-cheatsheet)
- [OpenClaw AGENTS.md on GitHub](https://github.com/openclaw/openclaw/blob/main/AGENTS.md)
- [OpenClaw Setup Guide](https://setupopenclaw.com/blog/claude-api-key-guide)
- [Claude Code Settings Docs](https://code.claude.com/docs/en/settings)
- [Claude Code Configuration Guide — ClaudeLog](https://claudelog.com/configuration/)
- [Creating the Perfect CLAUDE.md — Dometrain](https://dometrain.com/blog/creating-the-perfect-claudemd-for-claude-code/)
- [A developer's guide to settings.json in Claude Code](https://www.eesel.ai/blog/settings-json-claude-code)

---

*Created: 2026-02-21 | ImageAI Notes*
