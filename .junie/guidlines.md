Project Guidelines — LelandGreenGenAI

Last updated: 2025-08-29

Overview
- LelandGreenGenAI is a Python 3.9+ CLI/GUI app that generates images and text via Google’s Gemini API (google-genai). GUI features are optional and require PySide6. Cross‑platform: Windows, macOS, Linux.

Golden Rule (must follow)
- Whenever you add, change, or remove a feature, you must:
  1) Update README.md (usage, options, screenshots, any changed behavior), and
  2) Update requirements.txt (add/remove/pin versions as needed).
  3) Always increment the __version__ in main.py.
- PRs that change features but do not update both README.md and requirements.txt will not be accepted.

Environment & Setup
- Use a virtual environment:
  - Windows PowerShell:
    - python -m venv .venv
    - .\.venv\Scripts\Activate.ps1
  - macOS/Linux:
    - python3 -m venv .venv
    - source .venv/bin/activate
- Install dependencies: pip install -r requirements.txt
- GUI requires PySide6 (already listed in requirements.txt). If you remove GUI elements, remove PySide6 from requirements and reflect that in README.md.

API Keys & Configuration
- Never commit secrets. The app uses per‑user config:
  - Windows: %APPDATA%\LelandGreenGenAI\config.json
  - macOS: ~/Library/Application Support/LelandGreenGenAI/config.json
  - Linux: $XDG_CONFIG_HOME/LelandGreenGenAI/config.json or ~/.config/LelandGreenGenAI/config.json
- Preserve existing resolution order (CLI > file > stored config > env var) unless you have a compelling reason to change it. If changed, document in README.md.

Coding Style & Quality
- Target Python 3.9+.
- Prefer typing annotations and small, cohesive functions.
- Keep CLI and GUI logic modular; import PySide6 lazily (as in main.py) to keep CLI working without GUI deps loaded.
- Handle errors gracefully with user‑friendly messages (especially around API keys, network, and file I/O).

Versioning
- Update __version__ in main.py when you introduce user‑visible changes.
- Use semantic versioning (MAJOR.MINOR.PATCH) when practical.
- Reflect version changes in README.md if relevant (e.g., new flags, changed defaults).

Dependencies Management
- requirements.txt is the single source of truth for runtime dependencies.
- When adding a new dependency:
  - Add it to requirements.txt.
  - Justify its need briefly in the PR description.
  - Consider pinning or minimum versions if needed for compatibility.
- When removing a dependency, ensure that all imports and transitive usage are cleaned up and update README.md accordingly.

Documentation
- Keep README.md accurate and beginner‑friendly:
  - Installation (venv + pip install -r requirements.txt)
  - Running (GUI default, CLI flags and examples)
  - API key setup and storage locations
  - Platform‑specific tips (Windows/macOS/Linux)
  - Screenshots and feature descriptions
- If you add new CLI flags, GUI tabs, models, or output formats, include examples and update the CLI reference section.

Testing & Validation
- Manual tests to cover:
  - Key resolution paths (CLI key, key file, stored config, env var)
  - CLI flows: help, test key, prompt generation, output files
  - GUI flows (if PySide6 installed): settings save/test, prompt generation, file dialogs
  - Error handling (missing API key, invalid key, network errors)
- Where feasible, add lightweight automated tests or scripts for repeatability.

Contribution Workflow
- Create a feature branch from main.
- Keep commits focused; use clear messages (Conventional style appreciated: feat:, fix:, docs:, refactor:, chore:).
- Run the app in both CLI and (when applicable) GUI modes before opening a PR.
- In your PR description, explicitly list:
  - What changed and why
  - Any new/removed dependencies
  - README.md and requirements.txt updates (link to sections/lines)
  - Manual test steps and results

Releases
- Update __version__ and tag releases when meaningful user‑facing changes accumulate.
- Consider including a brief CHANGELOG summary in the PR or README.

Housekeeping
- Do not add large binaries to the repo; store generated assets under the per‑user config directory when possible.
- Respect cross‑platform paths; use pathlib where convenient.

Checklist for any change (must pass)
- [ ] Code compiles/runs (CLI at minimum)
- [ ] New/changed behavior documented in README.md
- [ ] Dependencies updated in requirements.txt (added/removed/pinned as needed)
- [ ] __version__ updated if user‑visible change
- [ ] Basic manual tests done (CLI/GUI as applicable)
- [ ] No secrets committed
