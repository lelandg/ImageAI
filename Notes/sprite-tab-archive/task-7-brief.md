### Task 7: Image route — edit-chain (+ difference-matte pairs)

**Files:**
- Modify: `core/sprite/generation/image_route.py` (Task 6) — append `edit_chain`
- Test: `tests/sprite/test_image_route.py` — append the chain tests

**Interfaces:**
- Consumes: `GoogleProvider.start_edit_session(character_image: bytes, style_context=None, model=None) -> bool` (`providers/google.py:2016-2085`), `reset_edit_session()` (`:2087-2095`), `edit_image` with a list input (multi-reference, `:1832-1905`); `OpenAIProvider.edit_image` with a list of bytes (`providers/openai.py:855-877` normalizes bytes/paths); `difference_matte(on_white, on_black) -> Image` (`core/sprite/matting.py`, sub-project 3); `CancelToken`.
- Produces: `edit_chain(provider, character, action, out_dir, *, frames, pose_instructions, plate_color, model=None, log=logger.info, token=None, matte_pairs=False) -> List[Path]`.

Continuity: frame k is an edit whose inputs are `[character, frame k-1]`, so identity comes from the character and motion continuity from the previous frame. `edit_image` on both providers is single-shot; the Gemini chat session started by `start_edit_session` establishes style context and is reset in `finally`. With `matte_pairs=True` every step is rendered twice (white plate `#FFFFFF`, black plate `#000000`); `difference_matte` produces the RGBA frame, the two plates stay on disk as `NNNN.white.png` / `NNNN.black.png`, and the chain continues from the white plate.

- [ ] **Step 1: Write the failing tests**

Append to `tests/sprite/test_image_route.py`:

```python
from core.sprite.generation.image_route import default_openai_edit_model, edit_chain, openai_edit_size


def _distinct_replies(n):
    return [png_bytes(w=16, h=16, squares=1, color=(0, 255, 0, 255)) if i % 2 == 0
            else png_bytes(w=16, h=16, squares=1, color=(0, 250, 5, 255)) for i in range(n)]


def test_edit_chain_google_chains_previous_frame(tmp_path):
    provider = _google()
    provider.start_edit_session.return_value = True
    replies = _distinct_replies(3)
    provider.edit_image.side_effect = [([], [r]) for r in replies]
    character = _character(tmp_path)
    out = edit_chain(provider, character, _action(), tmp_path / "chain", frames=3,
                     pose_instructions=["pose one", "pose two", "pose three"], plate_color="#00FF00")
    assert [p.name for p in out] == ["0001.png", "0002.png", "0003.png"]
    calls = provider.edit_image.call_args_list
    assert calls[0].args[0] == [character.read_bytes(), character.read_bytes()]
    assert calls[1].args[0] == [character.read_bytes(), replies[0]]
    assert calls[2].args[0] == [character.read_bytes(), replies[1]]
    assert all(c.kwargs["model"] == "default-google-image-model" for c in calls)
    assert "pose two" in calls[1].args[1] and "#00FF00" in calls[1].args[1]
    provider.start_edit_session.assert_called_once()
    provider.reset_edit_session.assert_called_once()
    sidecar = json.loads((tmp_path / "chain" / "0002.png.json").read_text(encoding="utf-8"))
    assert sidecar["step"] == 2 and sidecar["of"] == 3 and sidecar["route"] == "image_edit_chain"
    assert sidecar["reference_images"][1].endswith("0001.png")


def test_edit_chain_openai_passes_size_and_default_model(tmp_path):
    provider = _openai()
    provider.edit_image.side_effect = [([], [r]) for r in _distinct_replies(2)]
    out = edit_chain(provider, _character(tmp_path), _action(), tmp_path / "chain", frames=2,
                     pose_instructions=["a", "b"], plate_color="#00FF00")
    assert len(out) == 2
    kwargs = provider.edit_image.call_args_list[0].kwargs
    assert kwargs["model"] == default_openai_edit_model()
    assert kwargs["size"] == openai_edit_size(default_openai_edit_model(), (16, 16)) and kwargs["n"] == 1
    provider.start_edit_session.assert_not_called()


def test_openai_edit_size_prefers_custom_when_legal_else_closest_preset():
    model = next(m for m, c in MODEL_CAPS.items() if c["supports_custom_size"])
    assert openai_edit_size(model, (1024, 1024)) == "1024x1024"
    assert openai_edit_size(model, (1000, 1010)) == "1008x1008"
    small = openai_edit_size(model, (200, 200))          # below the pixel floor -> preset
    assert small in MODEL_CAPS[model]["valid_sizes"]
    legacy = next(m for m, c in MODEL_CAPS.items() if not c["supports_custom_size"] and c["supports_mask"])
    assert openai_edit_size(legacy, (300, 100)) == max(
        (s for s in MODEL_CAPS[legacy]["valid_sizes"] if s != "auto"),
        key=lambda s: parse_size_string(s)[0] / parse_size_string(s)[1])


def test_edit_chain_matte_pairs(tmp_path, monkeypatch):
    provider = _google()
    provider.start_edit_session.return_value = True
    provider.edit_image.side_effect = [([], [r]) for r in _distinct_replies(4)]
    seen = []

    def fake_matte(on_white, on_black):
        seen.append((on_white.size, on_black.size))
        return Image.new("RGBA", on_white.size, (10, 20, 30, 128))

    monkeypatch.setattr("core.sprite.matting.difference_matte", fake_matte)
    out = edit_chain(provider, _character(tmp_path), _action(), tmp_path / "chain", frames=2,
                     pose_instructions=["a", "b"], plate_color="#00FF00", matte_pairs=True)
    assert len(out) == 2 and len(seen) == 2
    assert (tmp_path / "chain" / "0001.white.png").exists() and (tmp_path / "chain" / "0001.black.png").exists()
    assert Image.open(out[0]).getchannel("A").getextrema() == (128, 128)
    prompts = [c.args[1].lower() for c in provider.edit_image.call_args_list]
    assert "#ffffff" in prompts[0] and "#000000" in prompts[1]
    sidecar = json.loads((tmp_path / "chain" / "0001.png.json").read_text(encoding="utf-8"))
    assert sidecar["matte_pairs"] is True and len(sidecar["plates"]) == 2


def test_edit_chain_cancels_between_steps(tmp_path):
    provider = _google()
    provider.start_edit_session.return_value = True
    token = CancelToken()

    def first_then_cancel(*args, **kwargs):
        token.cancel()
        return ([], [png_bytes(w=16, h=16, squares=1)])

    provider.edit_image.side_effect = first_then_cancel
    with pytest.raises(Cancelled):
        edit_chain(provider, _character(tmp_path), _action(), tmp_path / "chain", frames=3,
                   pose_instructions=["a", "b", "c"], plate_color="#00FF00", token=token)
    assert sorted(p.name for p in (tmp_path / "chain").glob("*.png")) == ["0001.png"]
    provider.reset_edit_session.assert_called_once()


def test_edit_chain_length_mismatch(tmp_path):
    with pytest.raises(ValueError):
        edit_chain(_google(), _character(tmp_path), _action(), tmp_path / "chain", frames=3,
                   pose_instructions=["a"], plate_color="#00FF00")


def test_edit_chain_session_failure_is_logged_not_fatal(tmp_path):
    provider = _google()
    provider.start_edit_session.return_value = False
    provider.edit_image.side_effect = [([], [r]) for r in _distinct_replies(1)]
    logged = []
    out = edit_chain(provider, _character(tmp_path), _action(), tmp_path / "chain", frames=1,
                     pose_instructions=["a"], plate_color="#00FF00", log=logged.append)
    assert len(out) == 1 and any("session" in l for l in logged)
    provider.reset_edit_session.assert_not_called()
```

- [ ] **Step 2: Run the tests to see them fail**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_image_route.py -v -k edit_chain` → `ImportError: cannot import name 'edit_chain'`.

- [ ] **Step 3: Implement `edit_chain`**

Append to `core/sprite/generation/image_route.py`:

```python
# --------------------------------------------------------------------------- edit-chain route

MATTE_PLATES = ("#FFFFFF", "#000000")


def edit_chain(
    provider,
    character: Path,
    action: ActionCard,
    out_dir: Path,
    *,
    frames: int,
    pose_instructions: Sequence[str],
    plate_color: str,
    model: Optional[str] = None,
    log: LogFn = logger.info,
    token: Optional[CancelToken] = None,
    matte_pairs: bool = False,
) -> List[Path]:
    """Render ``frames`` PNGs where frame k is an edit of [character, frame k-1]."""
    if frames < 1:
        raise ValueError("frames must be >= 1")
    if len(pose_instructions) != frames:
        raise ValueError(f"pose_instructions has {len(pose_instructions)} entries; expected {frames}")
    character = Path(character)
    if not character.exists():
        raise FileNotFoundError(character)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    kind = provider_kind(provider)
    model = model or (default_openai_edit_model() if kind == "openai" else provider.get_default_model())
    character_bytes = character.read_bytes()
    with Image.open(character) as img:
        char_size: Size = img.size
    session_started = False
    if kind == "google":
        session_started = bool(provider.start_edit_session(
            character_bytes, style_context="sprite animation frames; keep the exact character", model=model))
        if not session_started:
            log("[image route] edit session did not start; continuing with single-shot edits")
            logger.warning("[image route] start_edit_session returned False")
    plates = list(MATTE_PLATES) if matte_pairs else [plate_color]
    outputs: List[Path] = []
    prev_bytes = character_bytes
    try:
        for k, instruction in enumerate(pose_instructions, start=1):
            if token is not None:
                token.raise_if_cancelled()
            what = f"edit-chain step {k}/{frames}"
            out_png = out_dir / f"{k:04d}.png"
            step_images: Dict[str, bytes] = {}
            prompts: Dict[str, str] = {}
            for color in plates:
                prompt = inject_chroma(STEP_PROMPT.format(instruction=instruction.strip()), color, loop=False)
                prompts[color] = prompt
                params: Dict = {"step": k, "plate": color}
                refs = [character_bytes, prev_bytes]
                if kind == "openai":
                    size = openai_edit_size(model, char_size)
                    params["size"] = size
                    log_request(log, what=what, provider=kind, model=model, prompt=prompt, params=params)
                    texts, images = call_provider(provider, "edit_image", refs, prompt, what=what,
                                                  model=model, size=size, n=1)
                else:
                    log_request(log, what=what, provider=kind, model=model, prompt=prompt, params=params)
                    texts, images = call_provider(provider, "edit_image", refs, prompt, what=what, model=model)
                log_response(log, what=what, texts=texts, images=images)
                step_images[color] = first_image(texts, images, what=what)
            plate_paths: List[str] = []
            if matte_pairs:
                from core.sprite.matting import difference_matte
                white = save_png(step_images[MATTE_PLATES[0]], out_dir / f"{k:04d}.white.png")
                black = save_png(step_images[MATTE_PLATES[1]], out_dir / f"{k:04d}.black.png")
                with Image.open(white) as w_img, Image.open(black) as b_img:
                    matted = difference_matte(w_img.convert("RGB"), b_img.convert("RGB"))
                matted.convert("RGBA").save(out_png, "PNG")
                plate_paths = [str(white), str(black)]
                next_bytes = step_images[MATTE_PLATES[0]]
            else:
                save_png(step_images[plate_color], out_png)
                next_bytes = step_images[plate_color]
            write_image_sidecar(out_png, {
                "prompt": prompts[plates[0]], "prompts": prompts, "provider": kind, "model": model,
                "timestamp": _timestamp(), "route": "image_edit_chain",
                "action": action.name, "action_id": action.id, "step": k, "of": frames,
                "pose": instruction, "plate_color": plate_color, "matte_pairs": matte_pairs,
                "plates": plate_paths,
                "reference_images": [str(character), str(outputs[-1]) if outputs else str(character)],
            })
            outputs.append(out_png)
            prev_bytes = next_bytes
            log(f"[image route] step {k}/{frames} saved: {out_png}")
    finally:
        if kind == "google" and session_started:
            provider.reset_edit_session()
    return outputs
```

- [ ] **Step 4: Run the tests to see them pass**

`$PY -m pytest /mnt/d/Documents/Code/GitHub/ImageAI/tests/sprite/test_image_route.py -v` → 19 passed.

- [ ] **Step 5: Commit**

```bash
git -C /mnt/d/Documents/Code/GitHub/ImageAI add core/sprite/generation/image_route.py tests/sprite/test_image_route.py
git -C /mnt/d/Documents/Code/GitHub/ImageAI commit -m "feat(sprite): image route edit-chain with optional white/black difference-matte pairs"
```

---

