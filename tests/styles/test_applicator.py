"""Application matrix: placement x smart x provider ref limits."""
import json

from core.styles.applicator import StyledRequest, apply_style, style_ref_limit
from core.styles.models import Style, StyleDescriptor


def _style(**over):
    base = dict(id="s1", name="S1", prompt_text="bold watercolor washes",
                descriptor=StyleDescriptor(summary="watercolor"))
    base.update(over)
    return Style(**base)


def _exemplars(tmp_path, n):
    out = []
    for i in range(n):
        p = tmp_path / f"e{i}.jpg"
        p.write_bytes(b"JPEGDATA" + bytes([i]))
        out.append(p)
    return out


def test_ref_limits():
    assert style_ref_limit("google", "gemini-2.5-flash-image") == 5
    assert style_ref_limit("google", "gemini-3.1-flash-image-preview") == 8
    assert style_ref_limit("google", "gemini-3-pro-image-preview") == 14
    assert style_ref_limit("google", "imagen-4") == 3          # google default
    assert style_ref_limit("openai", "gpt-image-2") == 10
    assert style_ref_limit("openai", "gpt-image-1.5") == 10
    assert style_ref_limit("openai", "dall-e-3") == 0
    assert style_ref_limit("stability", "sd3") == 0
    assert style_ref_limit("local_sd", "any") == 0
    assert style_ref_limit("", "") == 0


def test_plain_suffix_default():
    res = apply_style("a red fox", _style(), "stability", "sd3")
    assert isinstance(res, StyledRequest)
    assert res.prompt == "a red fox. In this style: bold watercolor washes"
    assert res.extra_kwargs == {}
    assert res.meta["smart_merge_used"] is False
    assert res.meta["style_id"] == "s1"


def test_plain_prefix():
    res = apply_style("a red fox", _style(placement="prefix"), "stability", "sd3")
    assert res.prompt == "In this style: bold watercolor washes. a red fox"


def test_empty_prompt_text_leaves_prompt_alone():
    res = apply_style("a red fox", _style(prompt_text="  "), "openai", "dall-e-3")
    assert res.prompt == "a red fox"


def test_smart_merge_success():
    reply = json.dumps({"prompt": "a red fox rendered in bold watercolor"})
    res = apply_style("a red fox", _style(), "openai", "dall-e-3",
                      smart=True, completion_fn=lambda m: reply)
    assert res.prompt == "a red fox rendered in bold watercolor"
    assert res.meta["smart_merge_used"] is True


def test_smart_merge_failure_falls_back_to_plain():
    def boom(messages):
        raise RuntimeError("llm down")
    res = apply_style("a red fox", _style(), "openai", "dall-e-3",
                      smart=True, completion_fn=boom)
    assert res.prompt == "a red fox. In this style: bold watercolor washes"
    assert res.meta["smart_merge_used"] is False


def test_smart_without_completion_fn_is_plain():
    res = apply_style("a red fox", _style(), "openai", "dall-e-3", smart=True)
    assert res.meta["smart_merge_used"] is False


def test_exemplars_attached_within_limit(tmp_path):
    ex = _exemplars(tmp_path, 3)
    res = apply_style("a red fox", _style(), "google", "gemini-2.5-flash-image",
                      exemplar_paths=ex)
    assert res.meta["exemplars_attached"] == 3
    assert len(res.extra_kwargs["reference_images"]) == 3
    assert res.extra_kwargs["reference_images"][0] == ex[0].read_bytes()


def test_user_references_take_priority(tmp_path):
    ex = _exemplars(tmp_path, 3)
    user_refs = [b"USER1", b"USER2", b"USER3", b"USER4"]  # limit 5 -> 1 slot
    res = apply_style("a red fox", _style(), "google", "gemini-2.5-flash-image",
                      exemplar_paths=ex, existing_references=user_refs)
    refs = res.extra_kwargs["reference_images"]
    assert refs[:4] == user_refs
    assert len(refs) == 5
    assert res.meta["exemplars_attached"] == 1
    assert res.meta["exemplars_dropped"] == 2


def test_no_slots_no_extra_kwargs(tmp_path):
    ex = _exemplars(tmp_path, 2)
    user_refs = [b"U"] * 5
    res = apply_style("a red fox", _style(), "google", "gemini-2.5-flash-image",
                      exemplar_paths=ex, existing_references=user_refs)
    assert "reference_images" not in res.extra_kwargs
    assert res.meta["exemplars_attached"] == 0
    assert res.meta["exemplars_dropped"] == 2


def test_missing_exemplar_files_degrade_to_text(tmp_path):
    ghost = tmp_path / "gone.jpg"  # never created
    res = apply_style("a red fox", _style(), "google", "gemini-2.5-flash-image",
                      exemplar_paths=[ghost])
    assert "reference_images" not in res.extra_kwargs
    assert res.meta["exemplars_attached"] == 0


from core.styles.applicator import apply_style_for_surface


def test_apply_style_for_surface_none_style_is_identity():
    prompt, kwargs, meta = apply_style_for_surface(
        "a fox", None, "google", "m", smart=False, config=None,
        store=None, existing_references=None)
    assert prompt == "a fox" and kwargs == {} and meta is None


def test_apply_style_for_surface_full_path(tmp_path):
    from core.styles.models import Style
    from core.styles.store import StyleStore
    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id="w", name="W", prompt_text="washes")
    store.save(s)
    prompt, kwargs, meta = apply_style_for_surface(
        "a fox", s, "stability", "sd3", smart=False, config=None,
        store=store, existing_references=None)
    assert prompt == "a fox. In this style: washes"
    assert meta["style_id"] == "w"


def test_apply_style_for_surface_smart_without_key_degrades(tmp_path):
    from core.styles.models import Style
    from core.styles.store import StyleStore

    class NoKeyConfig:
        def get_api_key(self, provider):
            return None
        def get(self, k, d=None):
            return d

    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id="w", name="W", prompt_text="washes")
    store.save(s)
    prompt, kwargs, meta = apply_style_for_surface(
        "a fox", s, "stability", "sd3", smart=True, config=NoKeyConfig(),
        store=store, existing_references=None)
    assert prompt == "a fox. In this style: washes"  # plain fallback
    assert meta["smart_merge_used"] is False


def test_apply_style_for_surface_attach_exemplars_off(tmp_path):
    from core.styles.models import Style
    from core.styles.store import StyleStore
    store = StyleStore(base_dir=tmp_path / "styles")
    s = Style(id="w", name="W", prompt_text="washes")
    store.save(s)
    refs = store.style_dir("w") / "refs"
    refs.mkdir(parents=True)
    (refs / "0001.jpg").write_bytes(b"X")
    s.reference_images = ["refs/0001.jpg"]; s.exemplars = ["refs/0001.jpg"]
    store.save(s)
    prompt, kwargs, meta = apply_style_for_surface(
        "a fox", s, "google", "gemini-2.5-flash-image", smart=False,
        config=None, store=store, existing_references=None,
        attach_exemplars=False)
    assert prompt == "a fox. In this style: washes"
    assert kwargs == {}
    assert meta["exemplars_attached"] == 0


def test_apply_style_for_surface_caps_smart_merge_retries(monkeypatch):
    """GUI seam runs on the UI thread: one attempt, no ~14s retry backoff."""
    from core.styles.applicator import apply_style_for_surface
    captured = {}

    def fake_build(config, provider=None, model=None, max_retries=None):
        captured["max_retries"] = max_retries
        return (lambda messages: '{"prompt": "merged"}'), "openai", "gpt-x"

    monkeypatch.setattr("core.styles.analyzer.build_completion_fn", fake_build)
    prompt, extra, meta = apply_style_for_surface(
        "a fox", _style(), "google", "m", smart=True, config=object(),
        store=None, existing_references=None)
    assert captured["max_retries"] == 0
    assert meta["smart_merge_used"] is True and prompt == "merged"
