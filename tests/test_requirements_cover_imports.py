"""requirements.txt declares the packages the app imports that LiteLLM used to bring.

LiteLLM depended on jsonschema, jinja2 and (through tokenizers and
huggingface_hub) tqdm. Removing it removed them from fresh installs, while
the app still imports them directly: core/layout/template_manager.py
(jsonschema; without it template validation silently falls back to a basic
check), core/video/prompt_engine.py (jinja2) and scripts/generate_tags.py
(tqdm; the script exits without it). Each must be a direct requirement.
"""
import re
from pathlib import Path

import pytest

REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements.txt"


def _declared() -> set:
    names = set()
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name = re.split(r"[<>=!~;\[\s]", line, maxsplit=1)[0]
        names.add(re.sub(r"[-_.]+", "-", name).lower())
    return names


@pytest.mark.parametrize("package", ["jsonschema", "tqdm", "jinja2"])
def test_formerly_transitive_import_is_a_direct_requirement(package):
    assert package in _declared(), f"{package} is imported by the app; declare it"
