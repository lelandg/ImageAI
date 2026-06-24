@AGENTS.md

# CLAUDE.md — Claude Code specifics

The line above imports **`AGENTS.md`**, the canonical, tool-agnostic source of
truth for this repo (project overview, structure, commands, operational rules,
LLM integration guidelines, provider notes, version management). Everything there
applies. This file adds only the bits that are specific to **Claude Code**.

## Code map

When asked to update the code map / CodeMap, use the `update-code-map` skill, or
follow the instructions in `imageai_codemap_agent.md`. Check the "Last Updated"
timestamp first (per AGENTS.md §2) and offer to refresh if it's > 7 days old.

## Version bumps

The full list of files to touch when bumping the version is in
`.claude/VERSION_LOCATIONS.md` (summary in AGENTS.md §10).

## Skills & agents to prefer

- **Code review** → the `code-reviewer` agent (carries out the structured-review
  convention from AGENTS.md §12).
- **Documentation** → the documentation skills (`project-documenter` /
  `technical-documenter`).
- Prefer a specialized agent/subagent whenever one fits the task. If a subagent
  reports creating a file, verify it exists; if not, create it with the Write
  tool from the subagent's output.
