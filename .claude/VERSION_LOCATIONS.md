# Version Update Locations for ImageAI

When the user says "increment version", update the VERSION in these locations:

## Primary Version Definition
1. **`core/constants.py`** - Line 7
   - `VERSION = "0.9.0"`  ← Update this version number
   - This is the single source of truth for the version

## Files That Need Manual Updates
1. **`README.md`** - Line 3
   - `**Version X.X.X**` - Update this to match
   - Also add changelog entry in section 14

## Files that Import VERSION
These files automatically use the version from `core/constants.py`:

2. **`core/__init__.py`** - Imports and re-exports VERSION
   - Line 7: imports `__version__` from constants
   - Line 35: re-exports as `__version__`

3. **`cli/parser.py`** - Line 4
   - Imports VERSION from core.constants
   - Used in CLI argument parser

4. **`gui/main_window.py`** - Line 22, 59
   - Line 22: Imports VERSION from core
   - Line 59: Uses in window title: `f"{APP_NAME} v{VERSION}"`

5. **`__init__.py`** (root) - Lines 10, 20, 27
   - Imports and re-exports __version__

## Version Increment Instructions
To increment the version:
1. Edit `core/constants.py` line 7
2. Change `VERSION = "0.9.0"` to the new version (e.g., `"0.9.1"` for patch, `"1.0.0"` for minor, `"2.0.0"` for major)
3. Update `README.md` line 3 with the new version
4. Add a changelog entry in `README.md` section 14
5. All other locations will automatically use the updated version from core/constants.py

## Version Format
- Follow semantic versioning: MAJOR.MINOR.PATCH
- MAJOR: Breaking changes
- MINOR: New features, backwards compatible
- PATCH: Bug fixes, backwards compatible

## Current Version
- **0.9.0** (as of last check)

## Notes
- No setup.py or pyproject.toml found (not a packaged distribution)
- The `.junie/guidelines.md` mentions updating `__version__ in main.py` but this appears outdated - the version is actually in `core/constants.py`