@AGENTS.md

# CLAUDE.md — Claude Code specifics

The line above imports **`AGENTS.md`**, the canonical, tool-agnostic source of
truth for this repo. This file adds only Claude Code mechanics.

- **Code map** → the `update-code-map` skill (or `imageai_codemap_agent.md`).
- **Code review** → the `code-reviewer` agent.
- **Documentation** → the `project-documenter` / `technical-documenter` skills.
- Prefer a specialized agent/skill whenever one fits the task.
