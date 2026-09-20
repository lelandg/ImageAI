"""Code-map traversal is independent of the checkout's ancestor directories."""
from pathlib import Path

import pytest

from tools import generate_code_map as code_map


@pytest.mark.parametrize("ancestor", ["workspace", ".codex"])
def test_repository_sources_and_symbols_survive_excluded_ancestor(tmp_path, ancestor):
    root = tmp_path / ancestor / "worktrees" / "ImageAI"
    sources = {
        "core/feature.py": "class Feature:\n    pass\n\ndef run():\n    pass\n",
        "cli/command.py": "def command():\n    pass\n",
        "README.md": "Project overview\n",
        "core/.codex/hidden.py": "def hidden():\n    pass\n",
        "core/nested/__pycache__/cached.py": "def cached():\n    pass\n",
        ".venv/site-packages/dependency.py": "def dependency():\n    pass\n",
        "core/test_output/generated.py": "def generated():\n    pass\n",
    }
    for relative, content in sources.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    assert {path.relative_to(root).as_posix() for path in code_map.list_source_files(root)} == {
        "core/feature.py", "cli/command.py", "README.md",
    }
    symbols = {
        Path(relative).as_posix(): (classes, functions)
        for relative, classes, functions in code_map.collect_symbol_index(root)
    }
    assert symbols == {
        "core/feature.py": (["Feature"], ["run"]),
        "cli/command.py": ([], ["command"]),
    }
