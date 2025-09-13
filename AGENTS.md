# Repository Guidelines

## Project Structure & Module Organization
- `main.py` — entry point; launches GUI by default or CLI with args.
- `core/` — shared logic: `config.py` (ConfigManager), `security.py`, `utils.py`, logging, and `video/` pipeline modules.
- `gui/` — PySide6 UI (image tab, video project, dialogs) with `gui/video/` for project views.
- `cli/` — `parser.py` and `runner.py` for command-line usage; `commands/` for subcommands.
- `providers/` — provider adapters (`google`, `openai`, `stability`, `local_sd`) and base interface.
- `templates/` — Jinja2 prompt templates (e.g., `templates/video/*.j2`).
- Docs: `README.md`, `Docs/`, `Plans/`, `Screenshots/`, `CHANGELOG.md`.

## Build, Test, and Development Commands
- Create venv and install deps:
  - `python -m venv .venv && source .venv/bin/activate` (Windows: `\.venv\Scripts\Activate.ps1`)
  - `pip install -r requirements.txt` (plus `requirements-local-sd.txt` for local SD)
- Run GUI: `python main.py`
- CLI help: `python main.py -h`
- Auth test: `python main.py -t` (add `--provider openai|stability|local_sd` as needed)
- Generate: `python main.py -p "A sunset" -o out.png`

## Coding Style & Naming Conventions
- Python 3.9+; follow PEP 8 with 4‑space indentation and type hints.
- Names: modules/files `snake_case.py`, classes `PascalCase`, functions/vars `snake_case`, constants `UPPER_SNAKE`.
- Keep provider logic in `providers/` behind the base interface; UI-only code in `gui/`; shared logic in `core/`.
- Use `core.logging_config` for logs; avoid printing in library code. Never commit secrets.

## Testing Guidelines
- No formal test suite yet. Add `tests/` with `pytest` if contributing tests; name files `test_<module>.py` and functions `test_*`.
- Smoke tests:
  - Keys: `python main.py -t` (per provider)
  - Generation: `python main.py -p "test" -o test.png`
  - GUI: launch `python main.py` and verify image save + metadata sidecar.

## Commit & Pull Request Guidelines
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `test:`; optional scope (e.g., `feat(gui): ...`). See `COMMIT_MESSAGE.txt` for examples.
- Keep subject ≤72 chars; provide a concise body with rationale and impact. Reference issues (`#123`).
- PRs must include: summary, test plan (commands run), screenshots for UI changes (`Screenshots/`), and updates to `README.md`/`CHANGELOG.md` when user-visible.

## Security & Configuration Tips
- Manage keys via CLI (`--set-key`, `--api-key`, `--api-key-file`) or env vars: `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `STABILITY_API_KEY`.
- Keys are stored via `core.security.secure_storage` or config; never hardcode or log secrets.

## Agent-Specific Instructions
- Always consult `Docs/CodeMap.md` first to locate variables, functions, and modules before searching the tree.
- If the map seems outdated, regenerate it with `python tools/generate_code_map.py` and re-check locations.
