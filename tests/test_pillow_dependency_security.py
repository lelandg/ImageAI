"""Offline regression checks for the patched Pillow floor.

Each case crashes the interpreter on vulnerable Pillow, so it runs in a child
process; the test asserts the child survives. These test behavior, not just
installed version strings.
"""
import subprocess
import sys

import pytest

CASES = {
    # GHSA-cp9v-662q-vvx9: merge() never validated band 0; an I/F band 0 is NULL-dereferenced.
    "merge-unvalidated-band0": (
        "from PIL import Image\n"
        "bands = [Image.new('I', (2, 2)), Image.new('L', (2, 2)), Image.new('L', (2, 2))]\n"
        "Image.merge('RGB', bands)\n"
    ),
    # GHSA-27h8-gf7j-v5hc: rank filters on a zero-size image (e.g. an equal-edge crop).
    "rank-filter-zero-size": (
        "from PIL import Image, ImageFilter\n"
        "Image.new('L', (8, 8)).crop((3, 0, 3, 8)).filter(ImageFilter.MedianFilter(3))\n"
    ),
}

HARNESS = "try:\n{body}except ValueError:\n    pass\nprint('survived')\n"


@pytest.mark.parametrize("case", sorted(CASES))
def test_malformed_image_input_raises_instead_of_crashing(case):
    body = "".join(f"    {line}\n" for line in CASES[case].splitlines())
    result = subprocess.run(
        [sys.executable, "-c", HARNESS.format(body=body)],
        check=False, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"Pillow crashed (exit {result.returncode}): {result.stderr[-500:]}"
    assert result.stdout.strip() == "survived"
