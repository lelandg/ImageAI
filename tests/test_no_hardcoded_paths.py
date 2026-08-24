"""Guard tests: no source file may hardcode a developer-specific path."""
import pathlib
import re

SOURCE_DIRS = ("core", "gui", "cli", "providers")


def _python_files():
    for directory in SOURCE_DIRS:
        yield from pathlib.Path(directory).rglob("*.py")


def test_no_hardcoded_user_profile_paths():
    offenders = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            lowered = line.lower()
            if "c:/users/" in lowered or "c:\\\\users\\\\" in lowered:
                offenders.append(f"{path}:{lineno}: {line.strip()}")
    assert not offenders, "Hardcoded user-profile paths found:\n" + "\n".join(offenders)


# Paths that belong to other software and must keep their own resolution.
ALLOWED_PATTERNS = (
    r"gcloud",
    r"Cloud SDK",
    r"application_default_credentials",
    r"font",           # system font directories
    r"ffmpeg",
    r"\.cache.\s*.\s*.huggingface",  # shared hub read by character_animator
)

FORBIDDEN = (
    "AppData",
    "Application Support",
    "XDG_CONFIG_HOME",
    "APPDATA",
    ".imageai",
)

# Modules that own path knowledge by design.
#   core/paths.py         - the single runtime resolver.
#   core/data_migration.py - the migrator. It must name the pre-move legacy
#                            trees to move data away from them, and DataPaths
#                            deliberately has no concept of a legacy location.
EXEMPT_FILES = (
    "core/paths.py",
    "core/data_migration.py",
)


def _is_allowed(line: str) -> bool:
    return any(re.search(p, line, re.IGNORECASE) for p in ALLOWED_PATTERNS)


def test_no_module_builds_its_own_platform_data_dir():
    """core/paths.py is the only place allowed to compute the data directory."""
    offenders = []
    for path in _python_files():
        rel = path.as_posix()
        if rel in EXEMPT_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            if any(token in line for token in FORBIDDEN) and not _is_allowed(line):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, (
        "These lines build a data path without DataPaths:\n" + "\n".join(offenders)
    )


def test_get_user_data_dir_has_no_remaining_callers():
    """The shim exists for external scripts only; nothing in-tree may call it."""
    offenders = []
    for path in _python_files():
        rel = path.as_posix()
        if rel == "core/constants.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "get_user_data_dir(" in line:
                offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, (
        "Replace these with core.paths.get_data_paths():\n" + "\n".join(offenders)
    )
