"""Tests for core/sprite/generation/cost.py (G12 cost source + ledger)."""
import re

import pytest

from core.sprite.generation import cost
from core.sprite.project import CostEntry, GenerationSettings

VEO_STD = "veo-3.1-generate-001"
VEO_FAST = "veo-3.1-fast-generate-001"


@pytest.fixture(autouse=True)
def _no_overrides(monkeypatch):
    monkeypatch.setattr(cost, "price_overrides", lambda: {})


def test_price_table_verified_is_date_or_unverified():
    assert cost.PRICE_TABLE_VERIFIED == "unverified" or re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", cost.PRICE_TABLE_VERIFIED)
    if cost.PRICE_TABLE_VERIFIED == "unverified":
        assert cost.OMNI_USD_PER_SECOND is None
    else:
        assert isinstance(cost.OMNI_USD_PER_SECOND, float)


def test_veo_rates_reuse_veo_client_table():
    from core.video.veo_client import VeoClient, VeoGenerationConfig, VeoModel
    stub = VeoClient.__new__(VeoClient)
    expected = VeoClient.estimate_cost(
        stub, VeoGenerationConfig(model=VeoModel.VEO_3_1_GENERATE, duration=8,
                                  include_audio=False)) / 8
    assert cost.price_per_second("veo", VEO_STD, include_audio=False) == pytest.approx(expected)
    assert cost.price_per_second("veo", "", include_audio=False) == pytest.approx(expected)
    with_audio = cost.price_per_second("veo", VEO_STD, include_audio=True)
    assert with_audio > expected
    fast = cost.price_per_second("veo", VEO_FAST, include_audio=False)
    assert fast < expected


def test_unknown_models_and_providers_return_none():
    assert cost.price_per_second("veo", "veo-9.9-imaginary", include_audio=False) is None
    assert cost.price_per_second("sora", "", include_audio=False) is None


def test_omni_rate_follows_module_constant(monkeypatch):
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", None)
    assert cost.price_per_second("omni", "", include_audio=False) is None
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", 0.05)
    assert cost.price_per_second("omni", "any", include_audio=True) == 0.05


def test_config_override_wins(monkeypatch):
    monkeypatch.setattr(cost, "price_overrides",
                        lambda: {"omni": 0.07, "veo/" + VEO_FAST: 0.01})
    assert cost.price_per_second("omni", "", include_audio=False) == 0.07
    assert cost.price_per_second("veo", VEO_FAST, include_audio=True) == 0.01
    assert cost.price_per_second("veo", VEO_STD, include_audio=False) is not None


def test_price_overrides_reads_both_config_shapes(monkeypatch):
    monkeypatch.undo()  # use the real reader below
    class _Cfg:
        def __init__(self, data): self._d = data
        def get(self, key, default=None): return self._d.get(key, default)
    monkeypatch.setattr(cost, "_config_manager", lambda: _Cfg({"sprite.price_overrides": {"omni": "0.5"}}))
    assert cost.price_overrides() == {"omni": 0.5}
    monkeypatch.setattr(cost, "_config_manager", lambda: _Cfg({"sprite": {"price_overrides": {"veo": 0.2, "bad": "x"}}}))
    assert cost.price_overrides() == {"veo": 0.2}


def test_estimate_action_uses_snapped_duration(make_action, monkeypatch):
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", 0.10)
    action = make_action(duration_s=5)
    omni = GenerationSettings(provider="omni")
    assert cost.estimate_action(omni, action) == pytest.approx(0.5)
    veo = GenerationSettings(provider="veo", model=VEO_STD, include_audio=False,
                             loop_conditioning=True)
    rate = cost.price_per_second("veo", VEO_STD, include_audio=False)
    assert cost.estimate_action(veo, action) == pytest.approx(rate * 8)


def test_estimate_action_unknown_rate_is_none(make_action, monkeypatch):
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", None)
    assert cost.estimate_action(GenerationSettings(provider="omni"), make_action()) is None


def test_estimate_project_sums_and_counts_unknown(make_project, make_action, monkeypatch):
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", 0.10)
    project = make_project(actions=[make_action(id="a", duration_s=4),
                                    make_action(id="b", name="run", duration_s=6)])
    assert cost.estimate_project(project) == (pytest.approx(1.0), 0)
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", None)
    assert cost.estimate_project(project) == (None, 2)
    empty = make_project(actions=[])
    assert cost.estimate_project(empty) == (0.0, 0)


def test_record_actual_appends_ledger_row_and_updates_clip(make_project, make_action, monkeypatch):
    from core.sprite.project import ClipRecord
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", 0.10)
    action = make_action(duration_s=4)
    project = make_project(actions=[action])
    action.clip = ClipRecord(path=project.project_dir / "clips" / "a1.mp4", provider="omni",
                             model="m", operation_id="int-1",
                             params={"duration_s": 4, "aspect_ratio": "16:9"},
                             prompt="p", generated_at="2026-08-29T10:00:00",
                             estimated_usd=0.4, actual_usd=None)
    entry = cost.record_actual(project, action, 0.42, note="billing export")
    assert isinstance(entry, CostEntry)
    assert project.cost_ledger[-1] is entry
    assert entry.action_id == "a1" and entry.action_name == "walk"
    assert entry.provider == "omni" and entry.model == "m"
    assert entry.seconds == 4 and entry.estimated_usd == 0.4 and entry.actual_usd == 0.42
    assert entry.note == "billing export" and "T" in entry.timestamp
    assert action.clip.actual_usd == 0.42


def test_record_actual_without_clip_uses_settings(make_project, make_action, monkeypatch):
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", 0.10)
    action = make_action(duration_s=4)
    project = make_project(actions=[action])
    entry = cost.record_actual(project, action, None)
    assert entry.provider == "omni" and entry.actual_usd is None
    assert entry.estimated_usd == pytest.approx(0.4)


def test_record_actual_overrides_for_other_routes(make_project, make_action, monkeypatch):
    monkeypatch.setattr(cost, "OMNI_USD_PER_SECOND", 0.10)
    action = make_action(duration_s=4)
    project = make_project(actions=[action])
    entry = cost.record_actual(project, action, None, note="image route: 6 edits",
                               provider="google", model="image-model", seconds=6)
    assert entry.provider == "google" and entry.model == "image-model"
    assert entry.seconds == 6.0
    assert entry.estimated_usd is None          # video estimate must not leak in
    assert entry.note == "image route: 6 edits"
    explicit = cost.record_actual(project, action, 0.12, provider="google",
                                  model="image-model", seconds=6, estimated_usd=0.1)
    assert explicit.estimated_usd == 0.1 and explicit.actual_usd == 0.12
    assert len(project.cost_ledger) == 2
