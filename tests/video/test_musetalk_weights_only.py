"""MuseTalk checkpoints must load with an explicit ``weights_only=True``.

torch >= 2.6 defaults ``torch.load`` to ``weights_only=True``, which refuses
pickled code objects. But the ``TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD`` environment
variable silently flips that default back to full pickle loading at every call
site that leaves the argument implicit. Only an explicit argument is immune.
torch, transformers, diffusers and accelerate carry checkpoint-deserialization
advisories with no upstream fix (Docs/Snyk-Exceptions.md, 2026-11-05), so the
argument is the defence these loaders get.
"""

import sys
import types

import pytest

from providers.video.musetalk_provider import MuseTalkProvider


@pytest.fixture
def fake_torch(monkeypatch):
    calls = []
    torch = types.ModuleType("torch")

    def load(path, *args, **kwargs):
        calls.append((path, kwargs))
        return {}

    torch.load = load
    monkeypatch.setitem(sys.modules, "torch", torch)
    return calls


@pytest.fixture
def provider(tmp_path):
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


@pytest.mark.parametrize(
    "loader", ["_load_musetalk_model", "_load_dwpose_model", "_load_whisper_model"]
)
def test_checkpoint_loads_pass_weights_only_true(provider, fake_torch, loader):
    getattr(provider, loader)()
    assert len(fake_torch) == 1
    _, kwargs = fake_torch[0]
    assert kwargs.get("weights_only") is True
