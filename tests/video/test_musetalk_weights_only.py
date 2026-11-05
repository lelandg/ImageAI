"""MuseTalk checkpoints load only through restricted unpickling on a patched torch.

torch >= 2.6 defaults ``torch.load`` to ``weights_only=True``, but the
``TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD`` environment variable reverts that default
to full pickle loading at every call site that leaves the argument implicit,
and below 2.6 ``weights_only=True`` itself is bypassable (CVE-2025-32434).
torch, transformers, diffusers and accelerate carry checkpoint-deserialization
advisories with no upstream fix (Docs/Snyk-Exceptions.md, 2026-11-05), so
restricted loading is the defence these loaders get.
"""

import contextlib
import importlib.util
import sys
import types

import pytest

from core.musetalk_installer import get_musetalk_model_path
from providers.video import musetalk_provider
from providers.video.musetalk_provider import MuseTalkProvider


def _make_fake_torch(version):
    """Build a stand-in torch module that records load calls and allowlists."""
    loads, allowlists = [], []
    torch = types.ModuleType("torch")
    torch.__version__ = version

    def load(path, *args, **kwargs):
        """Record the call instead of unpickling anything."""
        loads.append((path, kwargs))
        return {}

    @contextlib.contextmanager
    def safe_globals(allow):
        """Record the allowlist the loader asked for."""
        allowlists.append(list(allow))
        yield

    torch.load = load
    torch.serialization = types.SimpleNamespace(safe_globals=safe_globals)
    return torch, loads, allowlists


@pytest.fixture
def fake_torch(monkeypatch):
    """Patch a patched-version fake torch into sys.modules."""
    torch, loads, allowlists = _make_fake_torch("2.9.1+cu128")
    monkeypatch.setitem(sys.modules, "torch", torch)
    return loads, allowlists


@pytest.fixture
def provider(tmp_path):
    """A provider whose model directory holds empty placeholder checkpoints."""
    (tmp_path / "musetalk").mkdir()
    (tmp_path / "musetalk" / "musetalk.json").write_text("{}", encoding="utf-8")
    (tmp_path / "musetalk" / "pytorch_model.bin").write_bytes(b"")
    (tmp_path / "dwpose").mkdir()
    (tmp_path / "dwpose" / "dw-ll_ucoco_384.pth").write_bytes(b"")
    (tmp_path / "whisper").mkdir()
    (tmp_path / "whisper" / "tiny.pt").write_bytes(b"")
    p = MuseTalkProvider(model_path=tmp_path)
    p.device = "cpu"
    return p


LOADERS = ["_load_musetalk_model", "_load_dwpose_model", "_load_whisper_model"]


@pytest.mark.parametrize("loader", LOADERS)
def test_checkpoint_loads_pass_weights_only_true(provider, fake_torch, loader):
    """Every checkpoint load passes weights_only=True explicitly."""
    loads, _ = fake_torch
    getattr(provider, loader)()
    assert len(loads) == 1
    _, kwargs = loads[0]
    assert kwargs.get("weights_only") is True


@pytest.mark.parametrize(
    "loader,allows_history_buffer",
    [("_load_musetalk_model", False), ("_load_dwpose_model", True), ("_load_whisper_model", False)],
)
def test_only_dwpose_gets_an_allowlist(provider, fake_torch, loader, allows_history_buffer):
    """Only DWPose widens the allowlist; the other checkpoints load tensors only."""
    _, allowlists = fake_torch
    getattr(provider, loader)()
    assert len(allowlists) == 1
    names = [entry[1] for entry in allowlists[0] if isinstance(entry, tuple)]
    assert ("mmengine.logging.history_buffer.HistoryBuffer" in names) is allows_history_buffer
    if not allows_history_buffer:
        assert allowlists[0] == []


@pytest.mark.parametrize("loader", LOADERS)
def test_vulnerable_torch_is_refused_before_loading(provider, monkeypatch, loader):
    """torch below 2.6 is refused before any checkpoint byte is unpickled."""
    torch, loads, _ = _make_fake_torch("2.4.1")
    monkeypatch.setitem(sys.modules, "torch", torch)
    with pytest.raises(RuntimeError, match="CVE-2025-32434"):
        getattr(provider, loader)()
    assert loads == []


def test_history_buffer_stub_is_inert():
    """The stub claims mmengine's dotted name without importing mmengine."""
    stub = musetalk_provider._HistoryBuffer
    assert f"{stub.__module__}.{stub.__qualname__}" == "mmengine.logging.history_buffer.HistoryBuffer"
    assert "mmengine" not in sys.modules or sys.modules["mmengine"] is not stub


def _real_dwpose_checkpoint():
    """Return the installed DWPose checkpoint path, or None when it is absent."""
    if importlib.util.find_spec("torch") is None:
        return None
    path = get_musetalk_model_path() / "dwpose" / "dw-ll_ucoco_384.pth"
    return path if path.exists() else None


# Resolved at collection: tests/conftest.py redirects data paths to a temp
# dir while each test runs, which would hide the installed checkpoint.
REAL_DWPOSE = _real_dwpose_checkpoint()


@pytest.mark.skipif(REAL_DWPOSE is None, reason="DWPose checkpoint or torch not installed")
def test_real_dwpose_checkpoint_loads_restricted():
    """The real mmengine-format checkpoint loads under the restricted unpickler."""
    import torch
    from packaging.version import Version

    if Version(torch.__version__.split("+")[0]) < Version(musetalk_provider.MIN_SAFE_TORCH):
        pytest.skip(f"torch {torch.__version__} is below the patched floor")
    checkpoint = musetalk_provider._restricted_load(
        REAL_DWPOSE, "cpu", musetalk_provider._dwpose_safe_globals()
    )
    assert len(checkpoint["state_dict"]) > 0
    assert all(isinstance(v, torch.Tensor) for v in checkpoint["state_dict"].values())
