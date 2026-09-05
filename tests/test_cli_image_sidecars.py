"""Every image saved by the CLI carries the same reproducible provenance."""

import io
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

import core.paths as paths_module
from cli.parser import build_arg_parser
from cli.runner import run_cli
from core.config import ConfigManager
from core.paths import DataPaths
from core.utils import sidecar_path


@pytest.fixture
def generation(tmp_path, monkeypatch):
    # Exercise the real ConfigManager against a dedicated test data resolver.
    monkeypatch.setattr(paths_module, "_INSTANCE", DataPaths(config_path=tmp_path / "config.json"))
    config = ConfigManager()
    provider = MagicMock()
    provider.get_default_model.return_value = "test-image-model"
    monkeypatch.setattr("cli.runner.get_provider", lambda *_: provider)
    monkeypatch.setattr("cli.runner.preload_provider", lambda *_: None)
    monkeypatch.setattr("cli.runner.resolve_api_key", lambda *_: (None, "none"))
    return config, provider


def image_bytes(fmt="PNG", color="orange"):
    stream = io.BytesIO()
    Image.new("RGB", (32, 24), color).save(stream, format=fmt)
    return stream.getvalue()


def run(provider, *options):
    args = build_arg_parser().parse_args(["--provider", "local_sd", "--prompt", "a curious lantern", *options])
    return run_cli(args)


@pytest.mark.parametrize("suffix,fmt", [(".png", "PNG"), (".jpeg", "JPEG")])
def test_explicit_and_numbered_images_get_sidecars(generation, tmp_path, suffix, fmt):
    _, provider = generation
    provider.generate.return_value = ([], [image_bytes(fmt, "orange"), image_bytes(fmt, "blue")])
    destination = tmp_path / "chosen" / ("lantern" + suffix)
    assert run(provider, "-o", str(destination), "-n", "2", "--quality", "high",
               "--custom-size", "1536x1024", "--output-format", fmt.lower(),
               "--output-compression", "87", "--moderation", "low") == 0
    for index, path in enumerate([destination, destination.with_name("lantern_2" + suffix)], 1):
        assert path.is_file()
        assert sidecar_path(path).name == path.name + ".json"
        meta = json.loads(sidecar_path(path).read_text())
        assert meta["prompt"] == meta["effective_prompt"] == "a curious lantern"
        assert meta["provider"] == "local_sd"
        assert meta["model"] == "test-image-model"
        assert meta["image_index"] == index
        assert meta["num_images"] == 2
        assert meta["size"] == meta["custom_size"] == "1536x1024"
        assert meta["quality"] == "high"
        assert meta["output_format"] == fmt.lower()
        assert meta["output_compression"] == 87
        assert meta["moderation"] == "low"
        assert datetime.strptime(meta["timestamp"], "%Y%m%d_%H%M%S")
        with Image.open(path) as image:
            assert image.format == fmt


def test_auto_output_uses_same_metadata_and_real_config_paths(generation):
    config, provider = generation
    provider.generate.return_value = ([], [image_bytes(), image_bytes(color="blue")])
    assert run(provider, "-n", "2", "--size", "1024x1024", "--quality", "medium") == 0
    outputs = sorted(config.get_images_dir().glob("*.png"))
    assert len(outputs) == 2
    for path in outputs:
        meta = json.loads(sidecar_path(path).read_text())
        assert meta["quality"] == "medium"
        assert meta["size"] == "1024x1024"
        assert meta["prompt"] == "a curious lantern"


def test_edit_sidecar_preserves_references_mask_and_provider_default_size(generation, tmp_path):
    _, provider = generation
    provider.edit_image.return_value = ([], [image_bytes()])
    references = [tmp_path / "one.png", tmp_path / "two.png"]
    mask = tmp_path / "mask.png"
    for path in [*references, mask]:
        path.write_bytes(image_bytes())
    destination = tmp_path / "composed.png"
    assert run(provider, "--reference", str(references[0]), "--reference", str(references[1]),
               "--mask", str(mask), "-o", str(destination)) == 0
    meta = json.loads(sidecar_path(destination).read_text())
    assert meta["reference_images"] == [str(p) for p in references]
    assert meta["mask"] == str(mask)
    assert meta["size"] is None
    assert meta["quality"] is None
    assert provider.edit_image.call_args.kwargs["mask"] == mask.read_bytes()


def test_explicit_style_sidecar_retains_original_and_effective_prompts(generation, tmp_path, monkeypatch):
    from core.styles.models import Style
    from core.styles.store import StyleStore

    _, provider = generation
    provider.generate.return_value = ([], [image_bytes()])
    store = StyleStore(base_dir=tmp_path / "styles")
    store.save(Style(id="water", name="Water", prompt_text="translucent watercolor washes"))
    monkeypatch.setattr("core.styles.StyleStore", lambda: store)
    destination = tmp_path / "styled.png"
    assert run(provider, "--style", "Water", "-o", str(destination)) == 0
    meta = json.loads(sidecar_path(destination).read_text())
    assert meta["prompt"] == "a curious lantern"
    assert meta["effective_prompt"] == provider.generate.call_args.kwargs["prompt"]
    assert "watercolor washes" in meta["effective_prompt"]
    assert meta["style_applied"]["style_id"] == "water"


def test_streaming_partials_and_final_share_metadata(generation, tmp_path):
    _, provider = generation

    def stream(**kwargs):
        kwargs["on_partial"](0, image_bytes(color="blue"))
        kwargs["on_partial"](1, image_bytes(color="green"))
        return [], [image_bytes()]

    provider.generate.side_effect = stream
    destination = tmp_path / "stream.png"
    assert run(provider, "--stream-partials", "-o", str(destination)) == 0
    for index in (0, 1):
        path = destination.with_name(f"stream.p{index}.png")
        meta = json.loads(sidecar_path(path).read_text())
        assert meta["partial"] is True and meta["partial_index"] == index
        assert meta["quality"] == "auto"
        assert meta["prompt"] == "a curious lantern"
    assert sidecar_path(destination).exists()


def test_sidecar_failure_is_logged_without_discarding_image(generation, tmp_path, monkeypatch, caplog):
    _, provider = generation
    provider.generate.return_value = ([], [image_bytes()])
    destination = tmp_path / "saved.png"
    original = Path.write_text

    def fail_sidecar(path, *args, **kwargs):
        if path == sidecar_path(destination):
            raise OSError("sidecar disk failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_sidecar)
    assert run(provider, "-o", str(destination)) == 0
    assert destination.exists()
    assert "Could not write image sidecar" in caplog.text
    assert "sidecar disk failure" in caplog.text
