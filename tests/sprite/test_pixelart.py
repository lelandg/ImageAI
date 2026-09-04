import io
import sys
import types
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from core.sprite import pixelart
from core.sprite.pixelart import (
    FLOYD_WARNING, anchor_offset, bayer_matrix, build_shared_palette,
    ensure_palette, fit_pad_integer, hex_to_palette, integer_fit_scale,
    nearest_palette_indices, palette_spread, palette_to_hex,
    quantize_to_palette, rebuild_palette, remap_to_locked, resolution_check,
    upscale_then_fit,
)


def square_frame(size, square, color=(200, 40, 40, 255), origin=(0, 0)):
    """RGBA frame of ``size`` with one opaque square of ``square`` px at ``origin``."""
    arr = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    x0, y0 = origin
    arr[y0:y0 + square[1], x0:x0 + square[0]] = color
    return Image.fromarray(arr)


def opaque_pixels(image):
    arr = np.asarray(image.convert("RGBA"))
    return int((arr[..., 3] > 0).sum())


def install_fake_upscaler(monkeypatch, calls):
    """Stand in for core.upscaling (its real import pulls torchvision, ~23 s)."""
    fake = types.ModuleType("core.upscaling")

    def upscale_image(image_data, target_width, target_height, method="lanczos", **kwargs):
        calls.append((target_width, target_height, method))
        img = Image.open(io.BytesIO(image_data))
        img.load()
        out = io.BytesIO()
        img.resize((target_width, target_height), Image.Resampling.LANCZOS).save(out, format="PNG")
        return out.getvalue()

    fake.upscale_image = upscale_image
    monkeypatch.setitem(sys.modules, "core.upscaling", fake)


# --- Task 1 -------------------------------------------------------------------------

def test_integer_fit_scale_exact_multiple():
    assert integer_fit_scale((256, 256), (64, 64)) == 4


def test_integer_fit_scale_rounds_up_to_fit():
    assert integer_fit_scale((500, 500), (64, 64)) == 8
    assert integer_fit_scale((100, 800), (64, 64)) == 13


def test_integer_fit_scale_is_one_when_source_fits():
    assert integer_fit_scale((64, 64), (64, 64)) == 1
    assert integer_fit_scale((10, 10), (64, 64)) == 1


def test_integer_fit_scale_rejects_zero():
    with pytest.raises(ValueError):
        integer_fit_scale((0, 10), (64, 64))


def test_anchor_offsets():
    assert anchor_offset((10, 20), (64, 64), "bottom_center") == (27, 44)
    assert anchor_offset((10, 20), (64, 64), "center") == (27, 22)
    assert anchor_offset((10, 20), (64, 64), "top_left") == (0, 0)
    assert anchor_offset((10, 20), (64, 64), "top_center") == (27, 0)
    assert anchor_offset((10, 20), (64, 64), "bottom_left") == (0, 44)


def test_anchor_offset_rejects_unknown_and_oversize():
    with pytest.raises(ValueError):
        anchor_offset((10, 10), (64, 64), "middle")
    with pytest.raises(ValueError):
        anchor_offset((65, 10), (64, 64), "center")


def test_fit_pad_integer_downscales_by_box_filter_and_pads():
    src = square_frame((256, 256), (128, 256), origin=(64, 0))
    out = fit_pad_integer(src, (64, 64), "bottom_center")
    assert out.size == (64, 64)
    assert out.mode == "RGBA"
    arr = np.asarray(out)
    assert arr[..., 3].sum() // 255 == 32 * 64
    assert (arr[:, 16:48, 3] == 255).all()
    assert (arr[:, :16, 3] == 0).all() and (arr[:, 48:, 3] == 0).all()


def test_fit_pad_integer_never_upscales_small_source():
    src = square_frame((16, 16), (16, 16))
    out = fit_pad_integer(src, (64, 64), "bottom_center")
    assert out.size == (64, 64)
    assert opaque_pixels(out) == 16 * 16
    arr = np.asarray(out)
    assert (arr[48:64, 24:40, 3] == 255).all()


def test_fit_pad_integer_honors_forced_scale():
    src = square_frame((64, 64), (64, 64))
    out = fit_pad_integer(src, (64, 64), "top_left", scale=2)
    assert opaque_pixels(out) == 32 * 32


def test_fit_pad_integer_box_filter_blends_alpha_edge():
    src = square_frame((8, 8), (4, 8))
    out = fit_pad_integer(src, (2, 2), "top_left")
    arr = np.asarray(out)
    assert tuple(arr[0, 0]) == (200, 40, 40, 255)
    assert tuple(arr[0, 1]) == (0, 0, 0, 0)


def test_fit_pad_integer_non_multiple_fits():
    src = square_frame((500, 300), (500, 300))
    out = fit_pad_integer(src, (64, 64), "bottom_center")
    assert out.size == (64, 64)
    assert opaque_pixels(out) == 63 * 38


# --- Task 2 -------------------------------------------------------------------------

def test_resolution_check_none_when_source_large_enough():
    assert resolution_check((64, 64), (64, 64)) is None
    assert resolution_check((256, 256), (64, 64)) is None
    assert resolution_check((100, 40), (64, 64)) is None


def test_resolution_check_warns_when_smaller_in_both_axes():
    text = resolution_check((40, 30), (64, 64))
    assert text is not None
    assert "40x30" in text and "64x64" in text
    assert "upscale_small" in text
    assert "128x128" in text


def test_upscale_then_fit_upscales_small_source_proportionally(monkeypatch):
    calls = []
    install_fake_upscaler(monkeypatch, calls)
    src = square_frame((16, 8), (16, 8))
    out = upscale_then_fit(src, (64, 64), "bottom_center", method="lanczos")
    assert calls == [(64, 32, "lanczos")]
    assert out.size == (64, 64)
    arr = np.asarray(out)
    rows = np.where(arr[..., 3] > 0)[0]
    cols = np.where(arr[..., 3] > 0)[1]
    assert cols.min() == 0 and cols.max() == 63
    assert rows.max() == 63 and rows.min() == 32


def test_upscale_then_fit_is_fit_pad_when_source_large_enough():
    src = square_frame((128, 128), (128, 128))
    out = upscale_then_fit(src, (64, 64), "top_left", method="lanczos")
    assert np.array_equal(np.asarray(out), np.asarray(fit_pad_integer(src, (64, 64), "top_left")))


def test_upscale_then_fit_pads_when_upscaler_returns_original(monkeypatch):
    calls = []
    fake = types.ModuleType("core.upscaling")
    fake.upscale_image = lambda data, w, h, method="lanczos", **kw: (calls.append((w, h, method)), data)[1]
    monkeypatch.setitem(sys.modules, "core.upscaling", fake)
    src = square_frame((10, 20), (10, 20))
    out = upscale_then_fit(src, (64, 64), "center", method="lanczos")
    assert calls == [(32, 64, "lanczos")]
    assert out.size == (64, 64)
    assert opaque_pixels(out) == 10 * 20


def test_upscale_then_fit_rejects_unknown_method():
    with pytest.raises(ValueError):
        upscale_then_fit(square_frame((8, 8), (8, 8)), (64, 64), "center", method="magic")


# --- Task 3 -------------------------------------------------------------------------

def test_bayer2_values():
    m = bayer_matrix(2)
    expected = (np.array([[0, 2], [3, 1]], dtype=np.float64) + 0.5) / 4.0
    assert np.allclose(m, expected)


def test_bayer_matrices_are_permutations_with_mean_half():
    for n in (2, 4, 8):
        m = bayer_matrix(n)
        assert m.shape == (n, n)
        ranks = np.round(m * n * n - 0.5).astype(int)
        assert sorted(ranks.flatten().tolist()) == list(range(n * n))
        assert abs(m.mean() - 0.5) < 1e-12
        assert m.min() > 0.0 and m.max() < 1.0


def test_bayer4_top_left_block_is_scaled_bayer2():
    m4 = bayer_matrix(4)
    ranks = np.round(m4 * 16 - 0.5).astype(int)
    assert ranks[:2, :2].tolist() == [[0, 8], [12, 4]]


def test_bayer_rejects_other_sizes():
    for bad in (1, 3, 16):
        with pytest.raises(ValueError):
            bayer_matrix(bad)


# --- Task 4 -------------------------------------------------------------------------

def test_hex_round_trip():
    pal = hex_to_palette(["#FF0000", "#00ff00", "0000FF"])
    assert pal.shape == (3, 3)
    assert pal.tolist() == [[255, 0, 0], [0, 255, 0], [0, 0, 255]]
    assert palette_to_hex(pal) == ["#FF0000", "#00FF00", "#0000FF"]
    assert hex_to_palette([]).shape == (0, 3)


def test_pillow_mediancut_raises_on_rgba_but_our_path_does_not():
    rgba = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
    with pytest.raises(ValueError):
        rgba.quantize(colors=4, method=Image.Quantize.MEDIANCUT)
    with pytest.raises(ValueError):
        rgba.quantize(colors=4, method=Image.Quantize.MAXCOVERAGE)
    assert build_shared_palette([rgba], 4) == ["#FF0000"]


def test_build_shared_palette_unions_frames_and_sorts_dark_to_light():
    f1 = square_frame((8, 8), (8, 8), color=(255, 0, 0, 255))
    f2 = square_frame((8, 8), (8, 8), color=(0, 0, 255, 255))
    f3 = square_frame((8, 8), (8, 8), color=(255, 255, 255, 255))
    assert build_shared_palette([f1, f2, f3], 8) == ["#0000FF", "#FF0000", "#FFFFFF"]


def test_build_shared_palette_ignores_transparent_and_fringe_pixels():
    arr = np.zeros((4, 4, 4), dtype=np.uint8)
    arr[:, :2] = (0, 255, 0, 255)
    arr[:, 2:] = (255, 0, 255, 100)
    frame = Image.fromarray(arr)
    assert build_shared_palette([frame], 8) == ["#00FF00"]


def test_build_shared_palette_empty_when_nothing_opaque():
    assert build_shared_palette([Image.new("RGBA", (4, 4), (0, 0, 0, 0))], 8) == []


def test_build_shared_palette_respects_color_budget_and_is_deterministic():
    rng = np.random.default_rng(7)
    arr = rng.integers(0, 256, (32, 32, 4), dtype=np.uint8)
    arr[..., 3] = 255
    frame = Image.fromarray(arr)
    pal_a = build_shared_palette([frame], 16)
    pal_b = build_shared_palette([frame], 16)
    assert pal_a == pal_b
    assert 1 <= len(pal_a) <= 16
    assert len(set(pal_a)) == len(pal_a)


def test_build_shared_palette_rejects_bad_sizes():
    frame = square_frame((4, 4), (4, 4))
    for bad in (0, 257):
        with pytest.raises(ValueError):
            build_shared_palette([frame], bad)


def test_build_shared_palette_subsamples_large_inputs(monkeypatch):
    monkeypatch.setattr(pixelart, "MAX_PALETTE_SAMPLES", 64)
    frame = square_frame((32, 32), (32, 32), color=(10, 200, 30, 255))
    assert build_shared_palette([frame], 4) == ["#0AC81E"]


# --- Task 5 -------------------------------------------------------------------------

PALETTE = ["#000000", "#FF0000", "#00FF00", "#0000FF", "#FFFFFF"]


def test_nearest_palette_indices_exact_and_tie_to_lowest():
    pal = hex_to_palette(PALETTE)
    rgb = np.array([[250, 5, 5], [0, 0, 0], [100, 100, 100], [10, 250, 10]], dtype=np.uint8)
    idx = nearest_palette_indices(rgb, pal)
    assert idx.tolist() == [1, 0, 0, 2]
    pal2 = hex_to_palette(["#000000", "#FFFFFF"])
    mid = np.array([[127, 127, 127], [128, 128, 128]], dtype=np.uint8)
    assert nearest_palette_indices(mid, pal2).tolist() == [0, 1]


def test_nearest_palette_indices_chunks_agree():
    rng = np.random.default_rng(3)
    rgb = rng.integers(0, 256, (1000, 3), dtype=np.uint8)
    pal = hex_to_palette(PALETTE)
    assert np.array_equal(nearest_palette_indices(rgb, pal, chunk=7),
                          nearest_palette_indices(rgb, pal, chunk=100000))


def test_palette_spread():
    assert palette_spread(hex_to_palette(["#000000"])) == 0.0
    assert palette_spread(hex_to_palette(["#000000", "#0000FF"])) == pytest.approx(255.0)


def test_quantize_none_maps_to_nearest_and_keeps_alpha():
    arr = np.zeros((2, 2, 4), dtype=np.uint8)
    arr[0, 0] = (250, 5, 5, 255)
    arr[0, 1] = (5, 250, 5, 128)
    arr[1, 0] = (5, 5, 250, 255)
    arr[1, 1] = (77, 77, 77, 0)
    out = quantize_to_palette(Image.fromarray(arr), PALETTE, "none")
    res = np.asarray(out)
    assert tuple(res[0, 0]) == (255, 0, 0, 255)
    assert tuple(res[0, 1]) == (0, 255, 0, 128)
    assert tuple(res[1, 0]) == (0, 0, 255, 255)
    assert tuple(res[1, 1]) == (0, 0, 0, 0)


def test_quantize_output_colors_are_subset_of_palette():
    rng = np.random.default_rng(11)
    arr = rng.integers(0, 256, (16, 16, 4), dtype=np.uint8)
    arr[..., 3] = 255
    src = Image.fromarray(arr)
    pal_set = {tuple(c) for c in hex_to_palette(PALETTE).tolist()}
    for mode in ("none", "bayer2", "bayer4", "bayer8", "floyd"):
        out = np.asarray(quantize_to_palette(src, PALETTE, mode))
        colors = {tuple(px[:3]) for px in out.reshape(-1, 4)}
        assert colors <= pal_set, mode
        assert (out[..., 3] == 255).all(), mode


def test_quantize_bayer_produces_a_checker_on_a_midtone():
    src = Image.new("RGBA", (4, 4), (128, 128, 128, 255))
    out = np.asarray(quantize_to_palette(src, ["#000000", "#FFFFFF"], "bayer2"))
    assert (out[..., 3] == 255).all()
    assert out[0, 0, 0] != out[0, 1, 0]
    assert out[0, 0, 0] == out[1, 1, 0]
    none = np.asarray(quantize_to_palette(src, ["#000000", "#FFFFFF"], "none"))
    assert (none[..., 0] == none[0, 0, 0]).all()


def test_quantize_floyd_uses_pillow_diffusion():
    src = Image.new("RGBA", (8, 8), (128, 128, 128, 255))
    out = np.asarray(quantize_to_palette(src, ["#000000", "#FFFFFF"], "floyd"))
    values = set(out[..., 0].flatten().tolist())
    assert values == {0, 255}


def test_quantize_floyd_transparent_pixels_do_not_bleed():
    arr = np.zeros((4, 4, 4), dtype=np.uint8)
    arr[:, 2:] = (250, 250, 250, 255)
    out = np.asarray(quantize_to_palette(Image.fromarray(arr), ["#000000", "#FFFFFF"], "floyd"))
    assert (out[:, :2] == 0).all()
    assert (out[:, 2:, :3] == 255).all()


def test_quantize_empty_palette_returns_copy_and_bad_dither_raises():
    src = square_frame((4, 4), (4, 4))
    out = quantize_to_palette(src, [], "none")
    assert np.array_equal(np.asarray(out), np.asarray(src))
    assert out is not src
    with pytest.raises(ValueError):
        quantize_to_palette(src, PALETTE, "ordered")


def test_floyd_warning_names_dither_crawl():
    assert "crawl" in FLOYD_WARNING
    assert "bayer" in FLOYD_WARNING


# --- Task 6 -------------------------------------------------------------------------

def make_profile(**kw):
    base = dict(name="pixel", enabled=True, cell_size=(64, 64), binary_alpha=True,
                alpha_threshold=128, defringe_px=0, palette_size=8, dither="none",
                palette_lock=True, locked_palette=None)
    base.update(kw)
    return SimpleNamespace(**base)


def make_project():
    return SimpleNamespace(name="proj", modified="2026-01-01T00:00:00")


def test_remap_to_locked_is_nearest_no_dither():
    src = Image.new("RGBA", (4, 4), (100, 100, 100, 255))
    out = np.asarray(remap_to_locked(src, ["#000000", "#FFFFFF"]))
    assert (out[..., :3] == 0).all()
    assert (out[..., 3] == 255).all()


def test_ensure_palette_builds_and_locks_on_first_run():
    project, profile = make_project(), make_profile()
    frames = [square_frame((8, 8), (8, 8), color=(255, 0, 0, 255))]
    assert ensure_palette(project, profile, frames) == ["#FF0000"]
    assert profile.locked_palette == ["#FF0000"]
    assert project.modified != "2026-01-01T00:00:00"


def test_ensure_palette_reuses_locked_palette_when_locked():
    project, profile = make_project(), make_profile(locked_palette=["#123456"])
    frames = [square_frame((8, 8), (8, 8), color=(255, 0, 0, 255))]
    assert ensure_palette(project, profile, frames) == ["#123456"]
    assert profile.locked_palette == ["#123456"]


def test_ensure_palette_keeps_existing_palette_when_unlocked():
    """I1 regression: an unlocked profile with a stored palette must not
    rebuild from whatever action happens to run -- the palette is
    project-wide, shared by every action, and only an explicit "Rebuild
    palette" call (rebuild_palette, not ensure_palette) replaces it."""
    project, profile = make_project(), make_profile(palette_lock=False, locked_palette=["#123456"])
    frames = [square_frame((8, 8), (8, 8), color=(0, 255, 0, 255))]
    assert ensure_palette(project, profile, frames) == ["#123456"]
    assert profile.locked_palette == ["#123456"]


def test_ensure_palette_builds_when_unlocked_and_no_palette_yet():
    project, profile = make_project(), make_profile(palette_lock=False, locked_palette=None)
    frames = [square_frame((8, 8), (8, 8), color=(0, 255, 0, 255))]
    assert ensure_palette(project, profile, frames) == ["#00FF00"]
    assert profile.locked_palette == ["#00FF00"]


def test_ensure_palette_empty_when_no_palette_size():
    project, profile = make_project(), make_profile(palette_size=None, locked_palette=["#123456"])
    assert ensure_palette(project, profile, []) == []
    assert profile.locked_palette == ["#123456"]


def test_rebuild_palette_overrides_lock():
    project, profile = make_project(), make_profile(locked_palette=["#123456"])
    frames = [square_frame((8, 8), (8, 8), color=(0, 0, 255, 255))]
    assert rebuild_palette(project, profile, frames) == ["#0000FF"]
    assert profile.locked_palette == ["#0000FF"]


def test_rebuild_palette_keeps_existing_palette_when_frames_are_empty():
    """I1 sub-case regression: an all-transparent action (e.g. keying removed
    every pixel) must never clobber a non-empty project palette."""
    project, profile = make_project(), make_profile(locked_palette=["#123456"])
    assert rebuild_palette(project, profile, [Image.new("RGBA", (4, 4), (0, 0, 0, 0))]) == ["#123456"]
    assert profile.locked_palette == ["#123456"]


def test_rebuild_palette_stays_empty_when_frames_are_empty_and_no_prior_palette():
    project, profile = make_project(), make_profile(locked_palette=None)
    assert rebuild_palette(project, profile, [Image.new("RGBA", (4, 4), (0, 0, 0, 0))]) == []
    assert profile.locked_palette is None


def test_rebuild_palette_requires_palette_size():
    with pytest.raises(ValueError):
        rebuild_palette(make_project(), make_profile(palette_size=None), [])
