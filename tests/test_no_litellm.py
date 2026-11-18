"""Guard: application code must not import or use the litellm library."""

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
ALL_ROOTS = ["core", "gui", "cli", "providers", "scripts", "main.py"]
CORE_ROOTS = ["core"]

# A real attribute use of the library module: ``litellm.`` not preceded by a
# word character, so ``chameleon_llm.completion`` and ``self.litellm_x`` never match.
_ATTR_USE = re.compile(r"(?<![\w.])litellm\.")


def _python_files(roots):
    for root in roots:
        path = REPO / root
        if path.is_file():
            yield path
        elif path.is_dir():
            for f in path.rglob("*.py"):
                if "__pycache__" not in f.parts:
                    yield f


def _import_offenders(roots):
    offenders = []
    for f in _python_files(roots):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            if any(n == "litellm" or n.startswith("litellm.") for n in names):
                offenders.append(f"{f.relative_to(REPO)}:{node.lineno}")
    return offenders


def _attribute_offenders(roots):
    offenders = []
    for f in _python_files(roots):
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(lines, 1):
            if line.lstrip().startswith("#"):
                continue
            if _ATTR_USE.search(line.split("#", 1)[0]):
                offenders.append(f"{f.relative_to(REPO)}:{i}")
    return offenders


@pytest.mark.xfail(strict=True, reason="gui/ and scripts/ migrate in Task 8")
def test_no_litellm_import_in_application_code():
    assert _import_offenders(ALL_ROOTS) == []


@pytest.mark.xfail(strict=True, reason="gui/ and scripts/ migrate in Task 8")
def test_no_litellm_attribute_use():
    assert _attribute_offenders(ALL_ROOTS) == []


def test_no_litellm_in_core():
    assert _import_offenders(CORE_ROOTS) == []
    assert _attribute_offenders(CORE_ROOTS) == []
