"""Guard tests: no source file may hardcode a developer-specific path."""
import pathlib

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
