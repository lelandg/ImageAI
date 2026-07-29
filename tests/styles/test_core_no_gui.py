"""Style pipeline must import and parse without PySide6 (issue #37)."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_style_pipeline_importable_without_pyside6():
    code = (
        "import sys\n"
        "sys.modules['PySide6'] = None\n"  # any 'import PySide6' now raises
        "from core.styles.analyzer import parse_descriptor\n"
        "from core.styles.applicator import apply_style\n"
        "d = parse_descriptor('{\"summary\": \"s\"}')\n"
        "assert d and d['summary'] == 's'\n"
        "print('OK')\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, cwd=REPO)
    assert out.returncode == 0, out.stderr
    assert "OK" in out.stdout
