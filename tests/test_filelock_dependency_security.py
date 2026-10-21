"""Offline regression check for the patched filelock floor.

filelock reaches ImageAI through huggingface-hub (tokenizers, local SD models).
This tests behavior, not just the installed version string.
"""
import os
import stat

import pytest
from filelock import FileLock


@pytest.mark.skipif(os.name != "posix", reason="UnixFileLock open/truncate path")
def test_lock_leaves_a_file_it_did_not_create_untouched(tmp_path):
    """GHSA-69hj-f68j-2879: a file renamed onto the lock path keeps its data and mode."""
    lock_path = tmp_path / "models.lock"
    lock_path.write_bytes(b"another user's data")
    lock_path.chmod(0o640)

    with FileLock(str(lock_path), mode=0o666):
        pass

    assert lock_path.read_bytes() == b"another user's data"
    assert stat.S_IMODE(lock_path.stat().st_mode) == 0o640
